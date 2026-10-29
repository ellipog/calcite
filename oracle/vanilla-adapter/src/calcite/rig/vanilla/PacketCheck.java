package calcite.rig.vanilla;

import io.netty.buffer.ByteBuf;
import io.netty.buffer.ByteBufUtil;
import io.netty.buffer.Unpooled;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.lang.reflect.RecordComponent;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import net.minecraft.SharedConstants;
import net.minecraft.network.ProtocolInfo;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.configuration.ConfigurationProtocols;
import net.minecraft.network.protocol.game.GameProtocols;
import net.minecraft.network.protocol.login.LoginProtocols;
import net.minecraft.network.protocol.status.StatusProtocols;
import net.minecraft.server.Bootstrap;

/**
 * Reads the packets Calcite's tests were sent with vanilla's own codecs, as a 26.3 client reads
 * them (D145). Each must decode, leave no bytes over, and encode back to the same bytes. A test
 * client made from Calcite's code agrees with Calcite on every mistake; this doesn't.
 *
 * <p>Each file holds packets one after another: the state's number, as `ConnectionProtocol`
 * orders them from handshake at 0, the length as 4 bytes, big-endian, then the packet's ID and
 * fields. Prints a line for each kind of packet, and exits with 1 if any packet failed.
 *
 * <pre>java -cp ... calcite.rig.vanilla.PacketCheck build/packets/play.bin</pre>
 */
public final class PacketCheck {
    /**
     * Packets whose bytes vanilla itself doesn't fix, with why. They must decode to a packet equal
     * to the one vanilla encodes back, but needn't have its bytes.
     */
    private static final String TAGS = "its registries are a HashMap keyed by ResourceKey, which hashes by identity, and each"
        + " registry's tags a HashMap the server grows from 16 buckets and the decoder sizes for its count, so vanilla neither"
        + " fixes the order nor encodes back the one it read";
    private static final Map<String, String> UNORDERED = Map.of(
        "play/set_time", "its clocks are a HashMap keyed by Holder.Reference, which hashes by identity, so vanilla's order changes from run to run",
        "configuration/update_tags", TAGS,
        "play/update_tags", TAGS);

    private PacketCheck() {}

    public static void main(String[] args) throws IOException {
        // Bootstrap wraps System.out to log it; the results go to the real stream.
        PrintStream out = new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8);
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        Map<String, Integer> passed = new TreeMap<>();
        Map<String, String> failed = new TreeMap<>();
        Set<String> seen = new HashSet<>();
        int total = 0;
        for (String file : args) {
            try (DataInputStream in = new DataInputStream(Files.newInputStream(Path.of(file)))) {
                while (true) {
                    int state;
                    try {
                        state = in.readUnsignedByte();
                    } catch (EOFException e) {
                        break;
                    }
                    byte[] bytes = new byte[in.readInt()];
                    in.readFully(bytes);
                    total++;
                    // The same packet is sent many times, such as each flat chunk; one check does.
                    if (!seen.add(state + ":" + ByteBufUtil.hexDump(bytes))) {
                        continue;
                    }
                    check(state, bytes, passed, failed);
                }
            }
        }
        for (Map.Entry<String, Integer> e : passed.entrySet()) {
            String note = UNORDERED.containsKey(e.getKey()) ? ", compared as values: " + UNORDERED.get(e.getKey()) : "";
            out.println("ok   " + e.getKey() + " (" + e.getValue() + " different" + note + ")");
        }
        for (Map.Entry<String, String> e : failed.entrySet()) {
            out.println("FAIL " + e.getKey() + ": " + e.getValue());
        }
        out.println(total + " packets, " + seen.size() + " different, " + failed.size() + " kinds failed");
        System.exit(failed.isEmpty() ? 0 : 1);
    }

    // Decodes one packet, checks nothing is left, encodes it back and compares. A kind's first
    // failure is the one kept.
    private static void check(int state, byte[] bytes, Map<String, Integer> passed, Map<String, String> failed) {
        StreamCodec<ByteBuf, Packet<?>> codec = codecOf(state);
        String kind = stateName(state) + "/id " + idOf(bytes);
        ByteBuf in = Unpooled.wrappedBuffer(bytes);
        Packet<?> packet;
        try {
            packet = codec.decode(in);
        } catch (RuntimeException e) {
            failed.putIfAbsent(kind, "doesn't decode: " + e + "\n     " + ByteBufUtil.hexDump(bytes, 0, Math.min(bytes.length, 64)));
            return;
        }
        kind = stateName(state) + "/" + packet.type().id().getPath();
        if (in.readableBytes() > 0) {
            failed.putIfAbsent(kind, in.readableBytes() + " bytes left over after " + packet);
            return;
        }
        ByteBuf out = Unpooled.buffer();
        try {
            codec.encode(out, packet);
        } catch (RuntimeException e) {
            failed.putIfAbsent(kind, "doesn't encode back: " + e);
            return;
        }
        byte[] again = ByteBufUtil.getBytes(out);
        if (!Arrays.equals(bytes, again) && UNORDERED.containsKey(kind)) {
            Packet<?> back = codec.decode(Unpooled.wrappedBuffer(again));
            if (same(packet, back)) {
                passed.merge(kind, 1, Integer::sum);
            } else {
                failed.putIfAbsent(kind, "encodes back to another packet\n     sent    " + packet + "\n     vanilla " + back);
            }
            return;
        }
        if (!Arrays.equals(bytes, again)) {
            int at = Arrays.mismatch(bytes, again);
            int from = Math.max(0, at - 8);
            failed.putIfAbsent(kind, "encodes back differently from byte " + at + " of " + bytes.length
                + "\n     sent    " + hex(bytes, from) + "\n     vanilla " + hex(again, from));
            return;
        }
        passed.merge(kind, 1, Integer::sum);
    }

    // Whether two values hold the same: records field by field, maps entry by entry whatever their
    // order, lists element by element, and anything else by `equals`. A map's values are compared
    // the same way, since `IdentityHashMap.equals` compares them by reference.
    private static boolean same(Object a, Object b) {
        if (a == b) {
            return true;
        }
        if (a == null || b == null || a.getClass() != b.getClass()) {
            return false;
        }
        if (a instanceof Record) {
            try {
                for (RecordComponent c : a.getClass().getRecordComponents()) {
                    Method get = c.getAccessor();
                    get.setAccessible(true);
                    if (!same(get.invoke(a), get.invoke(b))) {
                        return false;
                    }
                }
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException(e);
            }
            return true;
        }
        if (a instanceof Map<?, ?> x && b instanceof Map<?, ?> y) {
            if (x.size() != y.size()) {
                return false;
            }
            for (Map.Entry<?, ?> e : x.entrySet()) {
                if (!y.containsKey(e.getKey()) || !same(e.getValue(), y.get(e.getKey()))) {
                    return false;
                }
            }
            return true;
        }
        if (a instanceof List<?> x && b instanceof List<?> y) {
            if (x.size() != y.size()) {
                return false;
            }
            for (int i = 0; i < x.size(); i++) {
                if (!same(x.get(i), y.get(i))) {
                    return false;
                }
            }
            return true;
        }
        return a.equals(b);
    }

    // Each state's codec, bound once.
    private static final Map<Integer, StreamCodec<ByteBuf, Packet<?>>> CODECS = new TreeMap<>();

    static StreamCodec<ByteBuf, Packet<?>> codecOf(int state) {
        return CODECS.computeIfAbsent(state, PacketCheck::bind);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static StreamCodec<ByteBuf, Packet<?>> bind(int state) {
        ProtocolInfo<?> info = switch (state) {
            case 1 -> StatusProtocols.CLIENTBOUND;
            case 2 -> LoginProtocols.CLIENTBOUND;
            case 3 -> ConfigurationProtocols.CLIENTBOUND;
            case 4 -> GameProtocols.CLIENTBOUND_TEMPLATE.bind(RegistryFriendlyByteBuf.decorator(RegistriesProbe.access()));
            default -> throw new IllegalArgumentException("no clientbound packets in state " + state);
        };
        return (StreamCodec) info.codec();
    }

    private static String stateName(int state) {
        return switch (state) {
            case 1 -> "status";
            case 2 -> "login";
            case 3 -> "configuration";
            case 4 -> "play";
            default -> "state " + state;
        };
    }

    // The packet's ID, its leading VarInt.
    static int idOf(byte[] bytes) {
        int value = 0;
        for (int i = 0; i < Math.min(bytes.length, 5); i++) {
            value |= (bytes[i] & 0x7F) << (7 * i);
            if ((bytes[i] & 0x80) == 0) {
                break;
            }
        }
        return value;
    }

    private static String hex(byte[] bytes, int from) {
        return ByteBufUtil.hexDump(bytes, from, Math.min(bytes.length - from, 32));
    }
}
