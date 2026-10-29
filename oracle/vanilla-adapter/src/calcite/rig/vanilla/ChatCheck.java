package calcite.rig.vanilla;

import com.mojang.authlib.GameProfile;
import io.netty.buffer.Unpooled;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.PublicKey;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Stream;
import net.minecraft.SharedConstants;
import net.minecraft.network.chat.MessageSignatureCache;
import net.minecraft.network.chat.PlayerChatMessage;
import net.minecraft.network.chat.RemoteChatSession;
import net.minecraft.network.chat.SignedMessageBody;
import net.minecraft.network.chat.SignedMessageLink;
import net.minecraft.network.chat.SignedMessageValidator;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientboundLoginPacket;
import net.minecraft.network.protocol.game.ClientboundPlayerChatPacket;
import net.minecraft.network.protocol.game.ClientboundPlayerInfoRemovePacket;
import net.minecraft.network.protocol.game.ClientboundPlayerInfoUpdatePacket;
import net.minecraft.server.Bootstrap;
import net.minecraft.util.Crypt;
import net.minecraft.util.CryptException;
import net.minecraft.util.SignatureValidator;
import net.minecraft.world.entity.player.ProfilePublicKey;

/**
 * Reads the signed chat Calcite's tests were sent as a 26.3 client takes it in, with vanilla's own
 * chat validation: each player's chat session is checked against the key standing in for
 * Mojang's, each message's last-seen list is unpacked from the client's signature cache, and each
 * signature is checked, in its sender's chain. The tests run on a fixed clock, so a key's expiry
 * is judged at the time the message says it was sent. A test client made from Calcite's code would agree
 * with Calcite's signing on every mistake; this doesn't.
 *
 * <p>The folder holds {@code services.der}, the stand-in's public key, and a file for each player
 * of what they were sent, as {@link PacketCheck} reads it. What a client does with it is written
 * here from what the shared classes do; the client's own code isn't in the server jar. Prints a
 * line for each player, and exits with 1 if a client would have refused anything.
 *
 * <pre>java -cp ... calcite.rig.vanilla.ChatCheck build/packets/chat</pre>
 */
public final class ChatCheck {
    private ChatCheck() {}

    public static void main(String[] args) throws IOException, CryptException {
        PrintStream out = new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8);
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        Path folder = Path.of(args[0]);
        PublicKey services = Crypt.byteToPublicKey(Files.readAllBytes(folder.resolve("services.der")));
        // Mojang signs a player's chat key as ServicesKeyType.PROFILE_KEY's keys do.
        SignatureValidator mojang = SignatureValidator.from(services, "SHA1withRSA");
        List<Path> files;
        try (Stream<Path> listed = Files.list(folder)) {
            files = listed.filter(p -> p.toString().endsWith(".bin")).sorted().toList();
        }
        int messages = 0;
        int signed = 0;
        List<String> problems = new ArrayList<>();
        for (Path file : files) {
            Client client = new Client(mojang);
            String name = file.getFileName().toString().replace(".bin", "");
            try (DataInputStream in = new DataInputStream(Files.newInputStream(file))) {
                while (true) {
                    int state;
                    try {
                        state = in.readUnsignedByte();
                    } catch (EOFException e) {
                        break;
                    }
                    byte[] bytes = new byte[in.readInt()];
                    in.readFully(bytes);
                    // Play is state 4. PacketCheck reports a packet that doesn't decode.
                    if (state != 4) {
                        continue;
                    }
                    Packet<?> packet;
                    try {
                        packet = PacketCheck.codecOf(state).decode(Unpooled.wrappedBuffer(bytes));
                    } catch (RuntimeException e) {
                        continue;
                    }
                    String problem = client.take(packet);
                    if (problem != null) {
                        problems.add(name + ": " + problem);
                    }
                }
            }
            out.println("ok   " + name + "'s client took " + client.messages + " messages, " + client.signed + " of them signed");
            messages += client.messages;
            signed += client.signed;
        }
        for (String problem : problems) {
            out.println("FAIL " + problem);
        }
        out.println(messages + " chat messages as " + files.size() + " clients read them, " + signed + " signed, "
            + problems.size() + " refused");
        System.exit(problems.isEmpty() ? 0 : 1);
    }

    /** What one client keeps of the chat it's sent. */
    private static final class Client {
        private final SignatureValidator mojang;
        private final MessageSignatureCache cache = MessageSignatureCache.createDefault();
        private final Map<UUID, RemoteChatSession> sessions = new HashMap<>();
        private final Map<UUID, SignedMessageValidator> validators = new HashMap<>();
        private boolean enforcesSecureChat;
        private int nextIndex;
        // The time a key's expiry is judged at: the message's own, as a client whose clock agrees
        // with its sender's would, since the tests run on a fixed clock.
        private Instant now = Instant.EPOCH;
        int messages;
        int signed;

        Client(SignatureValidator mojang) {
            this.mojang = mojang;
        }

        private SignedMessageValidator unsignedValidator() {
            return this.enforcesSecureChat ? SignedMessageValidator.REJECT_ALL : SignedMessageValidator.ACCEPT_UNSIGNED;
        }

        /** Takes in one packet, and says what's wrong if a client would refuse it. */
        String take(Packet<?> packet) {
            if (packet instanceof ClientboundLoginPacket login) {
                this.enforcesSecureChat = login.enforcesSecureChat();
            } else if (packet instanceof ClientboundPlayerInfoUpdatePacket info
                && info.actions().contains(ClientboundPlayerInfoUpdatePacket.Action.INITIALIZE_CHAT)) {
                for (ClientboundPlayerInfoUpdatePacket.Entry entry : info.entries()) {
                    UUID id = entry.profileId();
                    if (entry.chatSession() == null) {
                        this.sessions.remove(id);
                        this.validators.put(id, unsignedValidator());
                        continue;
                    }
                    try {
                        RemoteChatSession session = entry.chatSession().validate(new GameProfile(id, "Player"), this.mojang);
                        this.sessions.put(id, session);
                        // As RemoteChatSession.createMessageValidator, with the message's clock.
                        ProfilePublicKey.Data key = session.profilePublicKey().data();
                        this.validators.put(id, new SignedMessageValidator.KeyBased(session.profilePublicKey().createSignatureValidator(),
                            () -> this.now.isAfter(key.expiresAt().plus(ProfilePublicKey.EXPIRY_GRACE_PERIOD))));
                    } catch (ProfilePublicKey.ValidationException e) {
                        this.sessions.remove(id);
                        this.validators.put(id, unsignedValidator());
                        return "the chat session of " + id + " isn't valid: " + e.getComponent().getString();
                    }
                }
            } else if (packet instanceof ClientboundPlayerInfoRemovePacket removed) {
                for (UUID id : removed.profileIds()) {
                    this.sessions.remove(id);
                    this.validators.remove(id);
                }
            } else if (packet instanceof ClientboundPlayerChatPacket chat) {
                this.messages++;
                int expected = this.nextIndex++;
                if (chat.globalIndex() != expected) {
                    return "message " + expected + " came as global index " + chat.globalIndex();
                }
                Optional<SignedMessageBody> body = chat.body().unpack(this.cache);
                if (body.isEmpty()) {
                    return "message " + expected + "'s last-seen list names a signature the client's cache doesn't hold";
                }
                this.cache.push(body.get(), chat.signature().orElse(null));
                this.now = body.get().timeStamp();
                RemoteChatSession session = this.sessions.get(chat.sender());
                SignedMessageLink link = session != null
                    ? new SignedMessageLink(chat.index(), chat.sender(), session.sessionId())
                    : SignedMessageLink.unsigned(chat.sender());
                PlayerChatMessage message = new PlayerChatMessage(
                    link, chat.signature().orElse(null), body.get(), chat.unsignedContent().orElse(null), chat.filterMask());
                SignedMessageValidator validator = this.validators.getOrDefault(chat.sender(), unsignedValidator());
                if (validator.updateAndValidate(message) == null) {
                    return "message " + expected + " (\"" + body.get().content() + "\") fails vanilla's validation";
                }
                if (session != null && message.signature() != null) {
                    this.signed++;
                }
            }
            return null;
        }
    }
}
