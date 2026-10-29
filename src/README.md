---
title: Calcite's source
description: The Calx modules in src/, what each matches in vanilla, and how they're tested.
---

# Calcite's source

Calcite is written in [Calx](https://github.com/ellipog/calx). Module `a.b` is the file `src/a/b.calx` ([modules](https://github.com/ellipog/calx/blob/main/docs/reference/modules.md)). Every module that reproduces vanilla behavior is checked bit for bit by the [oracle rig](../rig/README.md).

| Module | What it is | Vanilla's |
| --- | --- | --- |
| `random.source` | `RandomSource`, the interface every random source implements; `Bits`, a source built on `next(bits)`, with the formulas built on it; the polar Gaussian; `position_seed` | `RandomSource`, `BitRandomSource`, `MarsagliaPolarGaussian`, `Mth.getSeed` |
| `random.legacy` | `LegacyRandom`, Java's 48-bit LCG, and `LegacyPositional` | `LegacyRandomSource`, `SingleThreadedRandomSource` and their positional factory |
| `random.xoroshiro` | `XoroshiroRandom` on xoroshiro128++, and `XoroshiroPositional` | `XoroshiroRandomSource`, `Xoroshiro128PlusPlus`, `RandomSupport`'s seeding |
| `random.worldgen` | `WorldgenRandom<T>` over a legacy or xoroshiro source, with its chunk and feature seeding | `WorldgenRandom` |
| `hash.md5` | MD5, for seeding from names and for offline players' UUIDs | Guava's `Hashing.md5()` |
| `java.text` | `string_hash`, Java's `String.hashCode` over UTF-16 code units, and `compare_to`, its `compareTo` | `String.hashCode`, `String.compareTo` |
| `java.date` | `to_string`, a moment as `Date.toString` writes it, and `zone_name`, the zone's name there | `java.util.Date.toString` |
| `java.uuid` | `Uuid`, two `i64`s, written and read as Java writes and reads them; name-based (version 3) and random (version 4) UUIDs | `java.util.UUID` |
| `java.base64` | `encode`, Base64 with padding and no line breaks, and `decode`, which takes what Java's decoder takes | `java.util.Base64.getEncoder()`, `getDecoder()` |
| `java.properties` | `Properties`, a `.properties` file read with Java's rules for escapes, continued lines and comments, and written as `store` writes it | `java.util.Properties.load`, `store` |
| `java.uri` | `Uri`, a URI checked as Java's `new URI` checks it, with its messages, and `Uri.untrusted`, the links vanilla lets players open | `java.net.URI`, `Util.parseAndValidateUntrustedUri` |
| `java.number` | `parse_int` and the rest: Java's integer parsing in radixes 2 to 36, signed and unsigned, with the messages of its `NumberFormatException`s | `Integer.parseInt`, `Long.parseLong`, `Byte`, `Short`, `parseUnsignedInt`, `parseUnsignedLong` |
| `java.character` | `is_whitespace`, the units Java counts as white space, and `code_point_of`, the code point a character's name names | `Character.isWhitespace`, `Character.codePointOf` |
| `java.names` | The names of the code points, JDK 25's, written by [`oracle/unicode/names.py`](../oracle/unicode/names.py) | `Character.getName` |
| `json.gson` | `JsonWriter`, compact JSON with Gson's escapes, and a `Json` tree as Gson's `JsonObject` writes it | Gson's `JsonWriter`, with `disableHtmlEscaping`, and `JsonElement.toString` |
| `json.tree` | `Json`, a JSON value, with a strict parser, a writer and lookups | |
| `nbt.tag` | `Tag`, an NBT tag, read and written in network and file form with `Accounter`'s limits, and printed as SNBT | `Tag` and its types, `NbtIo`, `NbtAccounter`, `StringTagVisitor` |
| `nbt.snbt` | `parse` and `parse_compound`: SNBT read into a tag, with vanilla's errors at vanilla's places, and `SyntaxError`, brigadier's message and context | `TagParser`, `SnbtGrammar`, `SnbtOperations`, the packrat parser in `util.parsing.packrat`, `CommandSyntaxException` |
| `pack.zip` | `Zip`, a zip archive in memory: the central directory, Zip64, and entries stored or deflated, each checked against its CRC-32; `Zip.walk`, a stretch of one without its directory, file by file, with sizes from data descriptors | `java.util.zip.ZipFile`, `ZipInputStream` |
| `pack.resources` | `Pack`, a pack's files under `data/`, and under `assets/` with `read_file`, and `Resources`, the packs in order, whose `list` and `stacks` give files in vanilla's order, later packs over earlier ones, and `KnownPack` | `PackResources`, `MultiPackResourceManager`, `FileToIdConverter`, `KnownPack` |
| `pack.vanilla` | `vanilla_data`: the built-in data pack, from the stretch of Mojang's client jar that holds it, kept in `cache/`, read from an installed game or downloaded the first time, and checked against its pin; `vanilla_pack`, the same pack from the server jar the rig runs; `vanilla_language`, the server's language from the same data | `VanillaPackResources`, the bundler's `versions.list`, `Language.loadDefault` |
| `pack.pin` | Where the pinned server and client jars come from, their sizes and SHA-1s, and where the data is in the client jar, with its SHA-256, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | |
| `registry.builtin` | The 95 built-in registries and their entries in ID order, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | `BuiltInRegistries` |
| `world.modes` | `GameType` and `Difficulty`, by ID and by name, as server.properties gives them | `GameType`, `Difficulty` |
| `world.pos` | `BlockPos` and `ChunkPos`, and the longs vanilla packs them into | `BlockPos`, `ChunkPos` |
| `world.item` | `ItemStack`, an item and a count, as a slot sends it, without components so far | `ItemStack.OPTIONAL_STREAM_CODEC` |
| `world.flat` | `FlatWorld`: the classic flat world's chunk, with its heightmaps and light, encoded once | `FlatLevelSource`, `ClientboundLevelChunkPacketData`, `ClientboundLightUpdatePacketData` |
| `world.blocks` | Each block's first state ID and default state, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | `Block.BLOCK_STATE_REGISTRY` |
| `registry.registry` | `Registry`, a registry's entries with their IDs and its tags, and `Tag` | `MappedRegistry`, `HolderSet.Named` |
| `registry.tags` | `load_tags`: a registry's tags from the packs, read, merged and built in vanilla's order, with its log lines | `TagLoader`, `TagFile`, `TagEntry`, `DependencySorter` |
| `registry.registries` | `Registries`: the synchronized registries, in the order they're sent, and the built-in ones, each with its tags | `RegistryDataLoader`, `RegistrySynchronization` |
| `chat.component` | `Component`: text and translations with their arguments, siblings and `Style`, their JSON and NBT, written and read, and `get_string`, their text; `Style`'s colors, flags, font, insertion, and click and hover events | `Component`, `ComponentSerialization.CODEC`, `TranslatableContents`, `Style`, `TextColor`, `ClickEvent`, `HoverEvent` |
| `chat.chat_type` | `Decoration`, how a chat type shows a message, such as `chat.type.text` with the sender and the message; `load_chat_types`, each type's from the data packs, in the registry's order | `ChatType`, `ChatTypeDecoration` |
| `chat.language` | `Language`, the text of each translation key, which the server's own text, such as its log and SNBT's errors, is made with; `from_json` makes it from en_us.json and deprecated.json | `Language`, `Language.loadDefault` |
| `resources.identifier` | `Identifier`, a namespace and a path, parsed with vanilla's rules and messages | `Identifier` |
| `auth.profile` | `GameProfile` and `ProfileProperty`, as the login sends them; offline profiles, and which names vanilla takes | authlib's `GameProfile` and `Property`, `ByteBufCodecs.GAME_PROFILE`, `UUIDUtil.createOfflineProfile`, `StringUtil.isValidPlayerName` |
| `auth.session` | The server's hash, the session server's `hasJoined` URL, and what each answer of Mojang's services means | `Crypt.digestData`, authlib's `MinecraftClient`, `MinecraftServicesSessionService.hasJoinedServer`, `PropertyMap.Serializer` |
| `auth.velocity` | `read`, the player data Velocity's modern forwarding sends, checked against the secret, and `parse_ip`, the address in it | |
| `auth.services` | `Services`: the discovery document and the services' public keys, fetched and fetched again as authlib does, or given with `with_keys`, and `JoinCheck`, a login's check with the session server | authlib's `Environment`, `MinecraftServicesDiscoveryService`, `RetryableFetch`, `MinecraftServicesKeyInfo` |
| `protocol.state` | `State`, the five protocol states, and `Bound`, a packet's direction | `ConnectionProtocol`, `PacketFlow` |
| `protocol.ids` | The protocol version and each state's packet names in ID order, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | The order packets register in each state's protocol |
| `protocol.wire` | `Reader` and `Writer`, the `Wire` and `Packet` interfaces, `write_packet` | `FriendlyByteBuf`, `VarInt`, `VarLong`, `Utf8String`, `ByteBufCodecs` |
| `protocol.codegen` | The attributes that write packets' code: `@packet`, `@packets`, `@wire`, `@wire_enum` | Each packet's `STREAM_CODEC`, `IdDispatchCodec`, `PacketDecoder` |
| `protocol.handshake`, `protocol.status`, `protocol.login`, `protocol.configuration` | Their states' packets | The packets in `network.protocol.handshake`, `.status`, `.login`, `.cookie` and `.configuration` |
| `protocol.chat` | Chat's packets: a player's chat session, with its key; a message and a command as the client sends them, signed or not, and its acknowledgements; and a player's message as the server sends it, with its signature, its signed body, what a filter hid and its type | `ServerboundChatSessionUpdatePacket`, `RemoteChatSession.Data`, `ServerboundChatPacket`, `ServerboundChatAckPacket`, `ServerboundChatCommandPacket`, `ServerboundChatCommandSignedPacket`, `ArgumentSignatures`, `ClientboundPlayerChatPacket`, `MessageSignature`, `LastSeenMessages.Update`, `SignedMessageBody.Packed`, `FilterMask`, `ChatType.Bound` |
| `protocol.play` | The play packets Calcite sends and reads so far: the join, chunks and their light, the player's position, the tab list, the time, system chat, and the moves a client sends | The packets in `network.protocol.game` |
| `protocol.common` | The packets configuration and play share: keep-alives, pings, plugin channels, resource packs, links, tags and disconnecting; `ClientInformation` | The packets in `network.protocol.common`, `ClientInformation` |
| `protocol.frame` | `FrameReader`, which collects a connection's bytes and gives back whole frames, and `frame` | `Varint21FrameDecoder`, `Varint21LengthFieldPrepender` |
| `protocol.compression` | `compress` and `decompress`, a packet inside a frame once compression is on, with vanilla's checks and messages | `CompressionEncoder`, `CompressionDecoder` |
| `protocol.codec` | `Decoder` and `Encoder`, what a connection receives and sends, with its encryption and compression, apart so an encoder can move to another thread; `Codec`, both, for a client | The pipeline of `CipherDecoder`, `CipherEncoder` and the frame and compression handlers |
| `protocol.legacy` | The server list ping of clients before 1.7, and its answer | `LegacyQueryHandler`, `LegacyProtocolUtils` |
| `server.properties` | `ServerProperties`, the settings read so far; `load`, which reads server.properties; and `settled`, what vanilla writes back to it | `DedicatedServerProperties`, `Settings`, `Settings.store` |
| `server.config` | `CalciteConfig`, the settings in calcite.properties, and the text of a new one | |
| `server.status` | `ServerStatus`, what the server list shows, and its JSON, which the network rebuilds every 5 seconds; `check_icon` | `ServerStatus`, `PngInfo`, `MinecraftServer.loadStatusIcon` |
| `server.configuration` | `Configuration`: what configuration sends every player, encoded once; the server's links, its resource pack and its code of conduct, from server.properties and the `codeofconduct` folder | `startConfiguration`, `SynchronizeRegistriesTask`, `TagNetworkSerialization`, `getServerPackInfo`, `createServerLinks`, `readCodeOfConducts` |
| `server.chat` | What the server checks of a player's chat: `is_illegal`, the characters it can't have; `Throttler`, the spam count; `LastSeenValidator`, the window of signed messages a player has seen, and its checksum; `signed_by_services`, the services' signature of a player's chat key; `Chain`, the chain a player's signed messages come on, with what each signs; and `SignatureCache`, the signatures a client keeps of those it was sent | `isChatMessageIllegal`, `TickThrottler`, `LastSeenMessagesValidator`, `LastSeenMessages.computeChecksum`, `ProfilePublicKey`, `SignedMessageChain`, `PlayerChatMessage`, `SignedMessageBody`, `MessageSignatureCache` |
| `server.network` | `Network`: accepting connections, reading frames, the handshake, the status and ping, old pings, logins offline and online, configuration, play in the flat world, chat, and the read timeout | `ServerConnectionListener`, `ServerHandshakePacketListenerImpl`, `ServerStatusPacketListenerImpl`, `ServerLoginPacketListenerImpl`, `ServerConfigurationPacketListenerImpl`, its tasks, `ServerGamePacketListenerImpl`, `PlayerList`, `Connection`, `ReadTimeoutHandler` |
| `server.play` | `World`: the flat world and what players join it with, from server.properties and the registries, with the hashed seed and the chat types; `display_name`, a player's name as chat shows it | `PlayerList.placeNewPlayer`, `BiomeManager.obfuscateSeed`, `Player.getDisplayName` |
| `server.chunks` | `in_view`, the chunks a player sees, and `ChunkSender`, which sends them a batch at a time, nearest first | `ChunkTrackingView`, `PlayerChunkSender` |
| `server.boot` | `Boot`, what the data packs make as the server starts, and the boot cache that keeps it, keyed by the build and the data | |
| `server.sending` | `Outbox`, what a connection has queued to send, in order, with where its compression and encryption start, and `Sending`, which encodes it at a flush, on the tick thread if it's small and on a codec thread otherwise | `Connection`'s sending and flushing, the server's `suspendFlushing` and `resumeFlushing`, and Netty's event loops |
| `server.link` | `Link`, everything from outside the server, as it asks for it: the network's events and bytes, the ticks' times, the wall clock, connections' addresses, the system's random bytes, the key pair and the answers of Mojang's services, passed through, recorded to an input log, or replayed from one; and `Report`, what a replay found ([D144](../docs/decisions.md)) | |
| `server.log` | `Log`, where the server's lines go: the console, in its `Style`, and logs/latest.log on a thread of its own; `line`, a line in Mojang's pattern; `styled`, one in Calcite's; `Look`, how a line shows in Calcite's style; and `Entry`, a line left for the caller to log, with the thread vanilla logs it on | Mojang's log4j2.xml: its console pattern and its `RollingRandomAccessFile` |
| `server.log_file` | `LogFile`, latest.log and its archives, rolled at start and at midnight and numbered as log4j numbers them; `FileWriter`, the thread that writes it and compresses each archive | log4j's `OnStartupTriggeringPolicy`, `TimeBasedTriggeringPolicy`, `DefaultRolloverStrategy` and `GzCompressAction` |
| `calcite` | The server's `main`, which loads the vanilla data pack or the boot cache, and its loop of 20 ticks a second | `Main`, `DedicatedServer.initServer`, `MinecraftServer.runServer` |
| `rig.adapter` | The rig adapter's main: answers `hello`, `run` and `bye` | |
| `rig.frame` | The rig's frames, whose headers are JSON | |
| `rig.rng` | The `rng` probe | |
| `rig.collections` | The `collections` probe: Calx's Java-ordered tables against Java's and fastutil's | |
| `rig.registries` | The `registries` probe: the vanilla data pack's registries and tags against vanilla's | |
| `rig.nbt` | The `nbt` probe: binary NBT read, printed and written back, and SNBT parsed, against vanilla's | |

## Random sources

```calx
import random.legacy.{LegacyRandom}
import random.worldgen.{WorldgenRandom}

fn main() {
    var r = LegacyRandom.new(42)
    println("{r.next_int()} {r.next_int_below(10)}")    // out: -1170105035 3
    var w = WorldgenRandom.new(LegacyRandom.new(0))
    w.set_large_feature_seed(12345, 3, -7)
    println("{w.next_long()}")                        // out: 8624464025789168634
}
```

The same numbers as `new java.util.Random(42)`, and as seeding one with `setLargeFeatureSeed`'s formula. A type's interface methods need no import: `next_int` works on a `LegacyRandom` because the type implements `RandomSource`.

How they're built (D86):

- Each source is a small `Copy` struct, 24 to 32 bytes, so it lives on the stack or inside whatever owns it, with no allocation and no atomics. Vanilla's `LegacyRandomSource` uses an `AtomicLong` only to detect misuse from two threads, which region actors rule out.
- Calls go through generics, not virtual calls. `RandomSource` methods on a `LegacyRandom` compile to straight-line C. `WorldgenRandom<T>` is one generic struct for both inner sources, so each copy is specialized.
- `SingleThreadedRandomSource` is `LegacyRandom`: it gives the same numbers.
- A bound vanilla rejects, such as `next_int_below(0)`, panics, since vanilla throws `IllegalArgumentException` there and nothing catches it.
- Every constant was read from the bytecode with `javap`: the decompiler prints one of `XoroshiroRandomSource`'s doubles as a float ([found by the rig](../rig/README.md#found-so-far)).

The rig's `rng` probe runs 182 cases through every source and operation, including the rejections, and Calcite passes all of them on Windows and Linux.

## Packets

A packet is a struct named as vanilla's class without `Packet`, marked with `@packet` and the name vanilla gives it (D126). The attribute writes the code that reads and writes it, from its fields in order, and its ID in each state, from `protocol.ids`:

```calx
import java.uuid.{Uuid}
import protocol.codegen.{packet}
import protocol.state.{State, Bound}
import protocol.wire.{Reader}

/// Vanilla's `ServerboundHelloPacket`.
@packet(Bound.Serverbound, "hello")
pub struct ServerboundHello {
    @max(16)
    pub name: String
    pub profile_id: Uuid
}

fn main() {
    var r = Reader.new([4, 65, 108, 101, 120, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 2])
    match ServerboundHello.read(mut r) {
        ok(p) => println("{p.name} {p.profile_id.to_string()}"),    // out: Alex 00000000-0000-0001-0000-000000000002
        err(e) => println(e.message),
    }
    println("{ServerboundHello.id(State.Login)} {ServerboundHello.id(State.Play)}")    // out: 0 -1
}
```

- A field is written as its type says: `bool`, the integers and floats big-endian, `String` with its UTF-8 length first, `Uuid` as two `i64`s, `List<u8>` as a byte array, any other list with its count first, an optional with a `bool` first, and any other type with its own `Wire`. `@varint` writes an `i32` or `i64` as a VarInt or VarLong, `@max(n)` limits a string's UTF-16 units or a list's length, and `@rest` makes a `List<u8>` every byte left.
- Reading checks what vanilla checks, in its order, and fails with its message, such as `The received string length is longer than maximum allowed (17 > 16)`.
- A packet in several states, such as `cookie_response` in login and configuration, has an ID in each, and `-1` where it isn't one.
- A name vanilla doesn't have is a compile error that suggests the closest: ``vanilla 26.3 has no serverbound packet `intentoin`; did you mean `intention`?``

An enum marked `@packets` reads every packet a client can send in one state. Each variant is named after its packet, which gives the ID it's read for:

```calx
import protocol.handshake.{ClientIntent, ClientIntention, HandshakeIn}
import protocol.state.{State}
import protocol.wire.{Reader, Writer, write_packet}

fn main() {
    let intention = ClientIntention { protocol_version: 777, host_name: "localhost", port: 25565, intention: ClientIntent.Login }
    var w = Writer.new()
    write_packet(intention, State.Handshake, mut w)
    let bytes = w.into_bytes()
    println("{bytes.len()} bytes, ID {bytes[0]}")    // out: 16 bytes, ID 0
    var r = Reader.new(bytes)
    match HandshakeIn.read(mut r) {
        ok(HandshakeIn.Intention(p)) => println("{p.host_name}:{p.port}"),    // out: localhost:25565
        err(e) => println(e.message),
    }
}
```

`read` takes a frame's bytes after its length and any compression, as vanilla's `PacketDecoder` does: the ID, then the packet, which must end where the frame does. It fails with vanilla's messages, such as `Received unknown packet id 5`, and says which packet failed to decode: `Failed to decode packet 'serverbound/minecraft:intention': Unknown connection intent: 4`. `reads(id)` says whether a packet ID is one of the enum's, which play uses to skip the packets it doesn't handle yet.

## NBT

```calx
import chat.component.{Component}
import nbt.tag.{Accounter, Tag, read_any}

fn main() {
    var m = JavaHashMap<String, Tag>()
    m.insert(String("name"), Tag.Str(String("Steve")))
    m.insert(String("health"), Tag.Float(20.0f32))
    let tag = Tag.Compound(m)
    println(tag.to_snbt())    // out: {health:20.0f,name:"Steve"}
    var bytes = List<u8>()
    tag.write_any(mut bytes)!
    var at: usize = 0
    var accounter = Accounter.unlimited()
    let back = read_any(bytes, mut at, mut accounter)!
    println("{bytes.len()} bytes: {back.to_snbt()}")    // out: 29 bytes: {health:20.0f,name:"Steve"}
    let reason = Component.translatable("multiplayer.disconnect.incompatible", [Component.literal("26.3")])
    println(reason.to_nbt().to_snbt())    // out: {translate:"multiplayer.disconnect.incompatible",with:["26.3"]}
}
```

A tag is written as vanilla's `NbtIo` writes it to the network: its type, then its payload, with no name. A compound writes its keys in the order Java's `HashMap` holds them, since it is a `JavaHashMap`, and prints them sorted, as vanilla's `toString` does. A list of mixed types is written as vanilla writes one, each element in a compound under an empty key, and read back unwrapped. Reading counts what each tag takes as vanilla's `NbtAccounter` does: a packet's tag may take 2 MiB and 512 levels, and a read that goes past either fails with vanilla's message. [`test/nbt.calx`](test/nbt.calx) checks each type, the errors and the printing, and the rig's `nbt` probe checks binary NBT against vanilla's; reading SNBT comes later.

A text component goes to the client as NBT, as vanilla sends it: plain text with no siblings as a string, and anything else as a compound with the fields its JSON has.

## The server

```sh
calx run --release src/calcite.calx     # in the folder that holds server.properties and calcite.properties
calx run --release src/calcite.calx -- --replay recordings/2026-10-28-1.inputs     # a recorded run, played back
```

It starts as vanilla's dedicated server does, with its log lines, loads the vanilla data pack, answers the server list: the status, with the description, player counts, version and icon, the ping, and the old pings of clients before 1.7, logs players in, configures them, and lets them into a flat world. It ticks 20 times a second, as vanilla does, and like vanilla warns `Can't keep up!` when it's more than 2 seconds behind, at most once in 15 seconds, and skips the ticks it missed.

- **server.properties** is read as vanilla reads it: UTF-8, or ISO-8859-1 if it isn't, with Java's `Properties` rules. A setting that's missing or doesn't parse is its default, as `Boolean.valueOf` and `Integer.parseInt` decide. The settings read so far are `online-mode`, `server-ip`, `server-port`, `motd`, `max-players`, `enable-status`, `hide-online-players`, `enforce-secure-profile`, `accepts-transfers`, `prevent-proxy-connections`, `network-compression-threshold`, `rate-limit`, `log-ips`, `chat-spam-threshold-seconds`, `command-spam-threshold-seconds`, `enable-code-of-conduct`, `bug-report-link`, `resource-pack`, `resource-pack-id`, `resource-pack-sha1`, the older `resource-pack-hash`, `require-resource-pack`, `resource-pack-prompt`, `view-distance`, `simulation-distance`, `gamemode`, `difficulty`, `hardcore` and `level-seed`. `gamemode` and `difficulty` are a name, such as `creative`, or an ID, as vanilla reads them.
- **server.properties is written back** as the server starts, as vanilla's `Settings.store` writes it, so a new server gets one with every setting vanilla knows, at its default. It matches what the 26.3 jar writes byte for byte, but for the line ends: `#Minecraft server properties`, the date as Java's `Date.toString` writes it, then every key in Java's `String.compareTo` order, with Java's escapes.
  - Each setting vanilla reads is written as it read it: `TRUE` is `true`, `difficulty=2` is `normal`, `+5` is `5`, a number that doesn't parse is its default, `max-world-size` and the permission levels are kept in range, and `level-type` is in lower case.
  - `generator-settings` is written again as Gson writes the JSON object vanilla reads from it: compact, a key given twice in the place of its first with the value of its last, and anything after the object gone. A value that isn't a JSON object stops the server, as it stops vanilla.
  - `resource-pack-hash` and `announce-player-achievements` are gone, as vanilla reads them only to replace them. Keys vanilla doesn't read stay as they are.
  - `management-server-secret` is 40 letters and digits from the system's secure generator, where there's none.
  - The date names the zone as Java does, by tzdata's abbreviation, such as `CET`. Windows has none, so there it's the offset, such as `GMT+01:00` ([properties-on-windows](../rig/differences/properties-on-windows.md)).
  - A file that can't be written is logged as vanilla logs it, `Failed to store properties to file: server.properties`, and the server carries on. A replay leaves the file be.
- **calcite.properties** holds Calcite's own settings, those server.properties hasn't, in the same format, and is read the same way. A server that has none writes one, with each setting at its default and a comment on what it does. A setting that stops the server, such as forwarding with no secret, is logged as `Failed to start the minecraft server: ...` on `main`.

  | Setting | Default | What it does |
  | --- | --- | --- |
  | `velocity-forwarding` | `false` | Lets players in only through a Velocity proxy, with the player data its modern forwarding sends. The proxy authenticates them, so `online-mode` is ignored, and its offline-mode warning isn't logged. |
  | `velocity-secret` | empty | The text of Velocity's forwarding.secret, which signs that data. It must be set when `velocity-forwarding` is on. |
  | `record-inputs` | `false` | Records everything the server is handed to a new input log in `recordings/` each time it starts, which `--replay` plays back. |
  | `login-throttle` | `0` | The fewest milliseconds between two tries to log in from one address, such as `4000` on a public server. `0` lets every try in, as vanilla does. It's ignored with `velocity-forwarding`, since every player then comes from the proxy's address. |
  | `console-style` | `auto` | How the console shows the server's lines. `auto` gives Calcite's own look on a terminal, and vanilla's exact lines in a file or a pipe. `calcite` or `vanilla` picks one. Any other value is `auto`. logs/latest.log always has vanilla's lines. |

- **server-icon.png** must be a 64 by 64 PNG, checked as vanilla's `PngInfo` checks it, with its messages.
- **The vanilla data pack** is in Mojang's client jar too, with each file compressed on its own, so the server reads only the 5.6 MB stretch of it that holds data/ and the language files ([D140](../docs/decisions.md)). The first time it starts, it reads that from the game's jar if the game is installed, from Mojang's launcher, Prism Launcher or the Modrinth App, or else downloads just those bytes from Mojang, and keeps them in `cache/`, checked against their pinned SHA-256 each time they're read. Its registries and their tags load before the server starts, as vanilla's `Main` loads data packs, and a tag that can't be built stops it with vanilla's `Failed to load datapacks, can't proceed with server load`.
- **Recording and replay** ([D144](../docs/decisions.md)). Everything from outside the server goes through one place, `server.link`, in the order the server asks for it: what the network hands it, with the time each was handled, each tick, the wall clock, connections' addresses, the random bytes it draws, such as a random seed's and the login's challenges, its key pair, and Mojang's services' answers. With `record-inputs=true`, the server writes all of that to `recordings/2026-10-28-1.inputs`, then `-2` and on that day, with a hash of each packet it sent and each line it logged, which a thread of its own appends after each turn of the loop, so the tick never waits for the disk. `--replay FILE` starts the server in the same folder, with no network, handing it what the log holds where it would have asked the world outside, and checks it sends and logs what it did: it logs as it did, then `Replayed ...: 55 ticks, 8 packets and lines compared, 0 different`. A replay that goes another way fails, saying where it first did, such as `at tick 5, connection 2 was sent packet 0x02 of 40 bytes, where the recording sent connection 2 packet 0x03 of 3 bytes`, and how many things differed, so a recorded bug can be replayed with a fix to see that it's gone. The files the server reads as it starts aren't in the log, so a replay with other settings goes another way where they change what it does. The log holds what players sent and the server's private key, so it's for the server's admin alone. Recording hashes each packet as it's sent, about 1 µs for a flat chunk's 7 KB; with it off, the link costs nothing. Every network test records its scenario and replays it at the end, so each path the tests take is checked to replay exactly.
- **The boot cache**, `cache/boot.bin`, keeps what the data makes: the language, the registries and their tags, the chat types, the packs a client may know, and the lines loading them logged. A server started again by the same build, with the same data, reads it instead, and logs those lines again, so it's listening about 4 ms after it starts. A new build, new data, or a cache that can't be read makes it again, which takes about 50 ms more, or 0.5 s with the download.
- **The handshake** sends a client of another protocol version vanilla's `multiplayer.disconnect.outdated_client` or `multiplayer.disconnect.incompatible`, and a transfer, with `accepts-transfers` off, `multiplayer.disconnect.transfers_disabled`. A second status request closes the connection, and so does the pong.
- **Broken input**, such as a frame of no bytes, a length longer than 3 bytes, an unknown packet or one with bytes left over, closes the connection without an answer and logs nothing, as vanilla does in these states: it has no disconnect packet to send, and logs the reason only at debug level.
- **A connection that sends nothing for 30 seconds** is closed, as by vanilla's `ReadTimeoutHandler`.
- **`rate-limit`**, when it's above 0, kicks a connection that sends too many packets, as vanilla's `RateKickingConnection` does. Every packet that decodes counts. On a connection's first tick and every 20th after, the count since the last check is averaged in, a quarter of it to three quarters of the old average. A connection whose average is over the limit is logged as `Player exceeded rate-limit (sent 16.375 packets per second)` and told `disconnect.exceeded_packet_rate`. Before configuration a connection sends at most 3 packets, so only one in configuration or play can be kicked. [`test/play.calx`](test/play.calx) checks the exact average and the tick it's kicked on.
- **`login-throttle`**, Calcite's own setting, refuses a login or transfer from an address that tried less than that many milliseconds before. The client sees `You tried to join too soon after your last try. Wait a moment, then join again.` Every try, refused or not, starts the wait again, so an address that keeps trying stays refused. Status pings aren't throttled, since the server list sends them often and they cost little. Vanilla has no such limit, so it's off by default. The table of addresses forgets each one once a second after its wait is over. [`test/play.calx`](test/play.calx) checks a refusal, a retry that comes too soon, and a login once the wait is over.
- **What the server sends** is queued, and flushed once a tick ends and after each thing it handles between ticks, as vanilla holds a tick's packets and flushes them when it ends ([D143](../docs/decisions.md)). So a tick's packets reach the system in one send a connection. A flush of up to 1 KiB of packets is encoded on the tick thread, where that costs less than handing it over; more, such as a tick's chunks, goes to a codec thread with the connection's encoder, which compresses, frames and encrypts it there and sends the bytes back, waking the poll. One batch of a connection is away at a time, so its bytes keep their order, with compression and encryption starting where the login turned them on, and a connection the server closes closes once everything before is sent. The codec threads start as batches need them, up to one fewer than the processors. 64 flat chunks, compressed and encrypted, take 685 µs to encode; handed over, they take 2 µs of the tick thread. [`test/sending.calx`](test/sending.calx) checks the order, the switches and the close over TCP.
- **The login** gives a player in offline mode the profile vanilla gives, with the UUID made from `OfflinePlayer:` and their name. On the tick after the client's hello, it turns on compression if `network-compression-threshold` isn't negative and sends the profile, with a session ID shared by every login while the server has a connection open. A client that acknowledges it goes on to configuration. A login that takes more than 600 ticks is told `multiplayer.disconnect.slow_login`.
- **Online mode** authenticates players with Mojang's session server, as vanilla does. The server starts making a 1024-bit RSA key pair as it starts, on its own thread, so it listens without waiting for it, and the first online login waits for it if it isn't made yet. It sends a client its public key and 4 random bytes; the client sends back a secret and those bytes, encrypted with the key, and everything after is encrypted with AES-CFB8 and the secret. A challenge that isn't the server's, or a secret that isn't 16 bytes, is `java.lang.IllegalStateException: Protocol error`. An authenticator asks the session server whether the player joined with the server's hash, while the server goes on, and gives the player the UUID and properties it answers with, under the name they gave. The session server is given the player's address too with `prevent-proxy-connections=true`. A player it says didn't join is told `multiplayer.disconnect.unverified_username`, and one it can't be asked about `multiplayer.disconnect.authservers_down`, which is what every player is told while Mojang's services can't be reached.
- **Configuration** runs as vanilla's does. The server sends its brand, `calcite`, on `minecraft:brand`, the enabled features, `minecraft:vanilla`, and asks which of its packs the client has: `minecraft:core` at `26.3`. A client that has it is sent each synchronized registry's entries by name, in ID order, without their contents, then every registry's tags; one that hasn't would need the contents, which Calcite can't send yet, so it's told so and disconnected. The code of conduct and the resource pack come next when the server has them, then configuration ends once the player's place in the world is ready, on the next tick. These packets are the same for every player, so they're encoded once when the server starts. A keep-alive goes every 15 seconds, its challenge the time in milliseconds; one still unanswered when the next is due, or an answer to none, is `disconnect.timeout`. A packet that comes at the wrong time gets what vanilla gives it: one vanilla handles on the server thread, such as `finish_configuration` before configuration has ended, is logged as `Failed to handle packet ..., suppressing error` with the exception, and the connection goes on; another, such as accepting a code of conduct that wasn't sent, ends the connection with `disconnect.genericReason` and the exception. A client that says it's finished goes on to play. [`test/configuration.calx`](test/configuration.calx) checks each step.
- **Play** puts the player in the classic flat world: bedrock, two layers of dirt and grass, from y −64 to −61, in plains, everywhere. Every chunk is the same, so it's encoded once, as the server starts. The player joins as vanilla's `placeNewPlayer` has them join, at 0.5, −60, 0.5, in the game mode `gamemode` gives, with the packets in its order: the login, with the seed hashed with SHA-256 as vanilla hashes it, the difficulty, the abilities of their game mode, the commands' root alone, no recipes, their position, the tab list, the world border, the time and the spawn, then an empty inventory. Everyone else is told `multiplayer.player.joined` and sees them in the tab list; when they leave, they're told `multiplayer.player.left` and the player's taken off it. Chunks go as vanilla's `PlayerChunkSender` sends them: a batch at a time, nearest first, 9 at first, then as many a tick as the client says it can take once it has the last batch, out to the client's view distance or `view-distance`, whichever is less. When the player moves into another chunk, the client's told its new center, the chunks that left their view are forgotten and those that came in are sent. A move before the client accepts the position it was sent doesn't count, and one more than 20 ticks after it was sent gets it sent again; two moves in one tick, or a position that isn't a number, is `multiplayer.disconnect.invalid_player_movement`. Keep-alives go every 15 seconds, as in configuration. The log has vanilla's lines: `Steve[/127.0.0.1:50412] logged in with entity id 1 at (0.5, -60.0, 0.5)`, `System chat: Steve joined the game`, and `Steve lost connection: ...`. [`test/play.calx`](test/play.calx) checks each step.
- **Chat** goes as vanilla sends it ([D141](../docs/decisions.md)). A message goes to every player who shows all chat, the sender too, as `minecraft:chat` from the sender's name. A player without a chat session sends unsigned messages, which are stamped with the server's clock and logged as vanilla logs them, `[Not Secure] <Steve> hello`. While the server enforces secure chat, which it does with `enforce-secure-profile` in online mode once it has the services' keys, such a message is refused, with `chat.disabled.missingProfileKey` to the player in red and `Failed to update secure chat state for Steve: '...'` in the log. The status's `enforcesSecureChat` says so, rebuilt every 5 seconds as vanilla rebuilds it.
- **Signed chat** is checked as vanilla checks it ([D142](../docs/decisions.md)). Once in the world, a client sends its chat session: a session ID, and the key Mojang gave the player, with its expiry and Mojang's signature, which the server checks with the services' keys, `SHA1withRSA`, as vanilla does. A key Mojang didn't sign for the player is `multiplayer.disconnect.invalid_public_key_signature`, one that expires before the player's last is `multiplayer.disconnect.expired_public_key`, and bytes that aren't an RSA key don't decode. Without the services' keys the session is ignored, with vanilla's warning. Everyone is told of the session, as the tab list's `initialize_chat`, and a player who joins later gets it with the tab list, while its key hasn't expired. From then on the player's messages are links in a chain: each is signed with their key, `SHA256withRSA`, with its place in the chain, its text, time stamp, salt and the signatures they'd seen, and none may be from before the last. A message that isn't signed, or whose key has expired, is refused; one from before the last, or whose signature isn't theirs, is refused and breaks the chain, so every message after it is refused too, until a new session starts another. Each refusal is vanilla's `chat.disabled.*` message, in red, with its warning in the log. A signed message goes to each player with its signature, and the signatures its sender had seen by their places in that player's client's cache, where it has them, as vanilla's `MessageSignatureCache` keeps them; the console logs it without `[Not Secure]`, unless it was sent more than 5 minutes ago, which is also logged as vanilla warns of it. A player sent more than 4096 signed messages they haven't said they saw is `multiplayer.disconnect.too_many_pending_chats`. Calcite has no commands with arguments to sign, so a signed command with signatures doesn't match, as vanilla finds one whose arguments don't, and is refused with `chat.disabled.invalid_command_signature`, which breaks the chain; without signatures it's unknown, as any command is.
- **Chat's checks** are vanilla's too. Each message says which of the signed messages the player was sent they've seen, and one that doesn't add up, or an acknowledgement that does, is `multiplayer.disconnect.chat_validation_failed`, with vanilla's line on why; a message with `§`, a control character or DEL is `multiplayer.disconnect.illegal_characters`; and a player who hides chat is told `chat.disabled.options` and gets no one's messages. Messages and commands each count toward a spam limit of one a second, with a burst of `chat-spam-threshold-seconds` or `command-spam-threshold-seconds` of them, 10 by default, past which the player is kicked with `disconnect.spam`. Calcite has no commands yet, so a command gets vanilla's answer to one it doesn't know: `command.unknown.command`, then the command in red, which can be clicked to try again, and `command.context.here`. [`test/chat.calx`](test/chat.calx) checks the window of seen messages and its checksum against Java's arithmetic, and [`test/play.calx`](test/play.calx) checks chat between players over TCP, byte for byte, signed with sessions whose keys a test key signs where Mojang's would.
- **The bug report link**, `bug-report-link`, is the link the client's pause menu offers for reporting a bug, sent in configuration as vanilla's `BUG_REPORT` link. It must be a URI Java's `java.net.URI` takes, with the scheme `http` or `https` in any case, as vanilla's `Util.parseAndValidateUntrustedUri` checks it; one that isn't is logged as `Failed to parse bug link ...` with Java's exception, such as `java.net.URISyntaxException: Missing protocol in URI: ...`, and the server has no links. `java.uri` checks a URI as Java does, and gave JDK 25's answer for 80,000 random strings ([`test/uri.calx`](test/uri.calx) has the cases picked by hand).
- **The resource pack**, `resource-pack`, is offered to each player in configuration, after the code of conduct, with its SHA-1 from `resource-pack-sha1`, or the older `resource-pack-hash`, and its UUID from `resource-pack-id`. They're read as vanilla's `getServerPackInfo` reads them, with its warnings on `main` as the server starts: for both hashes, for the older one alone, for none, and for one that isn't 40 hex digits. A pack with no ID gets the UUID made from its URL, which is logged; one whose ID isn't a UUID isn't offered. `resource-pack-prompt` is a text component's JSON, read strictly; one that doesn't read is logged as `Failed to parse resource pack prompt '...'`, and the pack has no prompt. With `require-resource-pack=true`, a player who declines it is disconnected.
- **The code of conduct**, with `enable-code-of-conduct=true`, is the `.txt` files in the `codeofconduct` folder, each in the language its name gives, in lowercase, such as `en_us.txt`. A file's lines are joined by `\n` and its `§` formatting codes removed, as vanilla's `readCodeOfConducts` reads it. Each player is sent the one in their language, or else `en_us`, or else the first, and must accept it to join. The server doesn't start, with vanilla's exception, if the folder isn't there or is a link, a file links out of it, a file can't be read as UTF-8, or two files give the same language. [`test/offers.calx`](test/offers.calx) checks the link, the pack and the code of conduct.
- **Velocity's modern forwarding**, with `velocity-forwarding=true`, lets players in through a Velocity proxy set to `player-info-forwarding-mode = "modern"`, as Paper does. After the client's hello, the server asks on `velocity:player_info` for the newest version of the player data it reads, 4, and Velocity answers with the player's address, UUID, name and properties, signed with HMAC-SHA256 and the secret. The player gets that profile, and the log shows that address, with the port the proxy connected from, and `UUID of player Notch is ...`. Older versions, which add a chat key Calcite skips, are read too. A client that answers the query itself, with no data, because it didn't come through the proxy, is told `This server only lets players in through its Velocity proxy`; data signed with another secret, of a newer version, or that can't be read is turned away with a line saying which.
- **Mojang's services** are found as authlib finds them: the discovery document, fetched when the server starts, says where each is, and the services' public keys are fetched after it. Each is fetched again every 24 hours, and one that fails is tried again after 1 and 5 minutes, then twice as long each time, up to 64 times as long. The server uses Mojang's own services unless it's started with `-Dminecraft.api.env=staging`, or `-Dminecraft.api.discovery.host=` and a discovery URL of one's own, as vanilla's `java -D...` picks them.
- **A login that goes wrong** ends as vanilla's does: a name vanilla doesn't take, or a packet out of order, sends `disconnect.genericReason` with Java's exception (`Internal Exception: java.lang.IllegalStateException: Unexpected hello packet`), and so does a packet that can't be read, with the exception vanilla's pipeline throws, such as `io.netty.handler.codec.DecoderException: Received unknown packet id 9` or `io.netty.handler.codec.CorruptedFrameException: length wider than 21-bit`. A compressed packet is checked as vanilla checks it, with its messages, and an answer to a query the server didn't send is `multiplayer.disconnect.unexpected_query_response`.
- **The log** has vanilla's lines for logins: `Disconnecting Steve (/127.0.0.1:50412): ...` when the server ends a login, and `Steve (/127.0.0.1:50412) lost connection: ...` once it's gone, or the address alone before the client gives a name. The address is written as Java writes it, `/[0:0:0:0:0:0:0:1]:50412` for IPv6, or is `IP hidden` with `log-ips=false`. Once a player is in configuration, the line is `Steve (5627dd98-e6be-3c21-b8a8-e92344183641) lost connection: ...`. Each line names the thread vanilla logs it on: an authenticator's are on `User Authenticator #1` and up, such as `UUID of player Steve is ...`, and they're logged even if the player has left by then, as vanilla's are. The services' are on `Minecraft Services Discovery`, such as `Failed to connect` when the discovery document can't be fetched. `Environment: Environment[discoveryUrl=..., name=PROD]` comes before the server starts, on `main`.

The status's JSON is what vanilla's codecs and Gson write, member for member:

```calx
import chat.component.{Component}
import server.status.{ServerStatus}

fn main() {
    let status = ServerStatus {
        description: Component.literal("A Minecraft Server"),
        max_players: 20,
        online: 0,
        sample: [],
        version_name: "26.3",
        protocol: 777,
        favicon: none,
        enforces_secure_chat: false,
    }
    println(status.to_json())    // out: {"description":"A Minecraft Server","players":{"max":20,"online":0},"version":{"name":"26.3","protocol":777}}
    let reason = Component.translatable("multiplayer.disconnect.incompatible", [Component.literal("26.3")])
    println(reason.to_json())    // out: {"translate":"multiplayer.disconnect.incompatible","with":["26.3"]}
}
```

A member at its codec's default is left out, as vanilla's `lenientOptionalFieldOf` leaves it: an empty description or sample, no icon, and `enforcesSecureChat` when it's false. Plain text with no siblings is a bare string. [`test/status.calx`](test/status.calx) checks each case against what vanilla 26.3 gives, including Gson's escapes, which leave `<`, `>`, `&` and DEL as they are and escape U+2028 and U+2029.

An offline player's UUID, and a component as text, which is how the log shows a disconnect's reason. The server reads its language from the vanilla data as it starts, as vanilla reads it from its jar: en_us.json, with the changes deprecated.json makes. A key the language hasn't is its own text, as in vanilla:

```calx
import auth.profile.{GameProfile}
import chat.component.{Component}
import chat.language.{Language}

fn main() {
    println(GameProfile.offline("Steve").id.to_string())    // out: 5627dd98-e6be-3c21-b8a8-e92344183641
    let reason = Component.translatable("disconnect.genericReason", [Component.literal("Internal Exception: boom")])
    var lang = Language.empty()
    println(reason.get_string(lang))    // out: disconnect.genericReason
    lang.add("disconnect.genericReason", "Oops: %s")
    println(reason.get_string(lang))    // out: Oops: Internal Exception: boom
}
```

The log's lines follow Mojang's console pattern, `[%d{HH:mm:ss}] [%t/%level]: %msg`, in the local time zone. Each goes to the console, and to logs/latest.log as Mojang's log4j2.xml has log4j write it:

- **When it rolls.** A latest.log left from before the server started, with something in it, is archived as it starts. So is the file at the first line of each new day.
- **What an archive is named.** It's `logs/<day>-<N>.log.gz`, for the day its lines are from: the day the file was last written, at the start, or the day before the first line after midnight. N is one more than the highest that day already has, so gaps stay.
- **7 a day.** With 7 already, the lowest is removed and the rest move down one. A number of 7 or more there also moves every one down.
- **An empty latest.log** is never archived.
- **The work is off the server thread.** The file is opened, written and rolled on a thread of its own, so a slow disk never holds the server up, and each archive is compressed on another, as log4j's asynchronous actions are. When `main` returns, it waits until every line is written and every archive compressed.
- **A replay** (`--replay`) logs to the console alone, so it never rolls the log of the server it replays.

These rules were measured by running log4j 2.26.0 with Mojang's own configuration. [`test/log_file.calx`](test/log_file.calx) checks each case it was run on.

The console has two styles:

- **Vanilla's** lines, exactly. Hosting panels such as Pterodactyl, AMP and Crafty, and wrappers, read the console for lines such as `Done (...)! For help` and `joined the game`. So it's vanilla's style when the output is a file or a pipe, which is how they run a server.
- **Calcite's**, on a terminal. The time is dimmed, and each line has a colored tag:
  - `INFO`, `WARN` or `ERROR` for its level.
  - `READY` when players can join.
  - `JOIN`, `LEAVE` and `CHAT` for what players do.

  A thread is named only when it isn't the server's own. Each later line of a message, such as an exception's, starts under its first. Calcite has its own words where they read better: `Ready for players on 127.0.0.1:25565, 5.0 ms after starting` for `Done`, one line for a join, and two for offline mode's four warnings. Lines that tell whoever runs the server nothing new aren't shown, such as `Loading properties`, a login's `UUID of player`, and the `System chat` that repeats a join or a leave.

`console-style` in calcite.properties picks one. Until the server has read that file, it's Calcite's on a terminal. On Windows, the console's reading of ANSI codes is turned on first, and a console that can't read them gets vanilla's style. Calcite's words are its own, not Mojang's en_us text. `styled` writes the style's lines, and [`test/console.calx`](test/console.calx) checks each look.


```calx
import server.log.{Level, line}
import std.time.{Timestamp}

fn main() {
    let at = Timestamp { unix_ms: 1792540800000 }    // 2026-10-21 00:00 UTC
    println(line(at, 7200, "Server thread", Level.Info, "Done (0.001s)! For help, type \"help\""))    // out: [02:00:00] [Server thread/INFO]: Done (0.001s)! For help, type "help"
}
```

A block's position goes in a long, as vanilla packs it: 26 bits of `x`, 26 of `z`, then 12 of `y`. A game mode or difficulty is read by name or ID, and an ID out of range is survival, or wraps around for a difficulty, as vanilla's `byId`s have it:

```calx
import world.modes.{Difficulty, GameType}
import world.pos.{BlockPos, ChunkPos}

fn main() {
    let pos = BlockPos { x: 1, y: -60, z: -1 }
    println("{pos.pack()} {BlockPos.unpack(pos.pack()).z}")    // out: 549755813828 -1
    println("{ChunkPos.containing(-0.5, 40.5).x} {ChunkPos.containing(-0.5, 40.5).z}")    // out: -1 2
    println((GameType.by_name("creative") ?? GameType.Survival).name())    // out: creative
    println("{GameType.by_id(9).name()} {Difficulty.by_id(5).name()}")    // out: survival easy
}
```

Where it differs from vanilla, for now:

| Vanilla | Calcite | Until |
| --- | --- | --- |
| Asks you to agree to Mojang's EULA in eula.txt | Doesn't: Calcite isn't Mojang's software | Always |
| Rolls logs/latest.log a second time at its first line after starting, with nothing to archive, which still moves the day's archives down, and can remove one | Rolls once ([log-second-roll](../rig/differences/log-second-roll.md)) | Always |
| Ends each line of logs/latest.log with the system's line break, `\r\n` on Windows | Ends each with `\n` ([log-line-endings](../rig/differences/log-line-endings.md)) | Always |
| On Windows, ends each line of server.properties with `\r\n`, and names the zone in its date, such as `CET` | Ends each with `\n`, and names the zone by its offset, such as `GMT+01:00` ([properties-on-windows](../rig/differences/properties-on-windows.md)) | Always |
| Doesn't start when `entity-broadcast-range-percentage` isn't a number | Takes the default, 100, as for every other number ([properties-range-percentage](../rig/differences/properties-range-percentage.md)) | Always |
| Shows vanilla's lines on the console | Shows Calcite's own look and words on a terminal, and vanilla's lines in a file or a pipe, or with `console-style=vanilla` | Always |
| The status's player counts and sample come from who's online, rebuilt every 5 seconds | Rebuilt every 5 seconds too, but it shows no one online | The player list (`P4.5`) |
| Checks bans, the whitelist and a full server before it lets a player in, and kicks a player already in the world with the same UUID | Lets every valid login in, since there's no player list yet | Play (`P4.5`) |
| Logs an exception's stack trace after lines such as `Failed to connect` | Logs the line alone | A later change |
| Fetches the services' public keys twice when it starts, once for its session service and once for itself, so with no internet it logs their failure twice | Fetches them once | Always |
| Reads the services' answers with Gson, which takes some JSON that isn't strict, a number where a string goes, and text that isn't UTF-8 | Reads strict UTF-8 JSON, and takes a number or boolean where a string goes, as Gson does; anything else is an answer it can't read | A later change |
| A few answers that can't be read, such as a property without a name, throw an exception authlib doesn't catch, so the login waits until it takes too long | They mean the player didn't join | Always |
| zlib names what's wrong with deflate data it can't read, such as `invalid distance too far back` | Names a broken header and block type as zlib does, and anything past them `invalid deflate data` | A later change |
| Has no proxy support: a server behind one sees every player at the proxy's address, with the profile the proxy sends in its hello | Reads Velocity's modern forwarding, as Paper does, with Calcite's own messages and settings | Always |
| `Done (...)` times loading the level | Times the whole start, since there's no level | Worlds (Phase 5) |
| Sends its brand as `vanilla` | Sends `calcite` | Always |
| Sends a client without `minecraft:core` the registries' contents | Disconnects it, saying it can't yet; no 26.3 client lacks it while the server's data is vanilla's alone (D134) | The world's data packs (`P5.8`) |
| Puts the registries in `update_tags` in an order that changes from run to run, from a `HashMap` of their keys | Keeps theirs, the synchronized ones first, then the built-in ones; the tags in each are in vanilla's order | Always |
| Handles some packets on the server thread, at its next chance, and the rest as they're read | Handles each as it's read, in order, with the error handling vanilla gives it on its thread | Always |
| Decrypts, decompresses and decodes what arrives on Netty's threads | Encodes what it sends on codec threads, but reads what arrives on the tick thread: a client's packets are few and small, so it costs little | Regions (Phase 5), whose threads the reading moves off |
| Logs a packet that failed on the server thread with Java's `toString`, which names `finish_configuration` by its class and the instance's hash code, then the stack trace | Leaves out the hash code, which changes from run to run, and logs the exception's first line alone | Always |
| Puts a player who's played before where they were, with what they had | Puts every player at the spawn as a new one, since nothing is saved | The world folder (`P5.2`) |
| Generates the world from its settings and keeps it in region files | Has one world, the classic flat one, kept nowhere | Worldgen (`P5.9`) |
| Has the Nether and the End | Has the overworld alone | The Nether and the End (`P5.10`) |
| Lights each chunk with its light engines | Sends every chunk the same light, the light vanilla's engines give a flat chunk | Lighting (`P5.7`) |
| Handles every packet a client sends in play | Reads those it handles so far, the join's, chunks', moves', keep-alives' and chat's, and skips the rest unread | Phase 6 |
| Reads a chat key in any DER Java's `KeyFactory` takes, of up to 16384 bits | Reads DER in its shortest form, of 512 to 4096 bits, as Java's `getEncoded()` writes a key; any other is `Malformed public key bytes`, where vanilla would find the services didn't sign it. Mojang's keys are all of that form | Always |
| Logs why a chat key or a signature couldn't be checked with the exception's stack trace | Logs the exception's first line | Always |
| Logs a last-seen window that doesn't add up on the connection's Netty thread, with the exception's stack trace | Logs it on the server thread, with the exception's first line | Always |
| Runs a command, or says where it went wrong | Says every command is unknown | Commands (`P6.6`) |
| Lets operators spam | Has no operators, so it kicks anyone who does | The player list (`P4.5`) |
| Sends recipes, advancements, the commands a player may run, and their operator level | Sends no recipes or advancements, and the commands' root alone | Phase 6 |
| Shows players to each other in the world, and checks their moves against the blocks and how fast they may go | Shows them in the tab list alone, and takes every move a client sends | Phase 6 |
| Tells a player who joined under another name `multiplayer.player.joined.renamed`, from the names it's seen | Always says `multiplayer.player.joined` | The world folder (`P5.2`) |
| Lists the `codeofconduct` folder in the order the system gives, which decides the code of conduct a client gets when there's none in its language and no `en_us` | Lists it sorted by name, so it's the same on every system | Always |
| Refuses every code of conduct file when the server's folder is reached through a link, since it compares each file's real path with the folder's absolute one | Compares real paths, so only a file that links out of the folder is refused | Always |
| Has several messages for a mistake inside an IPv6 address in a link, such as `IPv6 address too long` | Says `Malformed IPv6 address`, at the address's start | Always |
| Keeps a resource pack prompt's other contents, such as key binds, items in its hover events and dialogs in its click events, and sends its number and boolean arguments as numbers | Keeps text, translations and styles, with the arguments as text, and refuses other contents, items and dialogs | Items and dialogs (Phase 6) |
| Logs a prompt that isn't JSON with Gson's exception, and one its codec refuses with the codec's message; reads one nested up to 255 deep | Logs the first without an exception, and the second with Calcite's own message, such as `No matching codec found`; reads one nested up to 64 deep | Always |
| Reads SNBT nested as deep as its stack holds, then throws `StackOverflowError`, which nothing catches | Stops at 512 levels of compounds, lists and operations together, as binary NBT does, with `Tried to read NBT tag with too high complexity, depth > 512` at the bracket of the level too deep ([the difference](../rig/differences/snbt-depth.md)) | Always |
| Makes a lone half of a surrogate pair from an SNBT escape such as `\ud800` | Makes a `?`, since a `String` holds only Unicode | Always |

## Tests

`src/test/` holds Calx tests that need no vanilla data, such as MD5's published test vectors. Each panics on a wrong result and prints `ok`:

```sh
py -I src/test/run.py                   # every test and example on this page, debug and release, and builds the server
py -I rig/runner/rig.py score           # everything the rig can check
```

An example's `// out:` comments give the lines it must print, as in Calx's own docs. Both commands run in CI on Windows and Linux. A test's source root is `src/`, since it starts with a `module test.<name>` line, so it imports Calcite's modules as Calcite does.

[`test/fuzz.calx`](test/fuzz.calx) feeds every decoder of what a client sends bytes no client would. It sends random bodies after each packet ID of each state, plus IDs that belong to no packet, then changes, truncates and extends the ones that decoded. It also sends random streams, in pieces, to the frame reader, and real and random compressed bodies to the decompressor. Each must give a packet or an error, never a panic, an overflow or an allocation as large as the bytes claim. Its random source is seeded, so a failure repeats.

The network tests' clients are made from Calcite's own codecs, so a wrong idea of the format would pass on both ends. So [`test/play.calx`](test/play.calx) and [`test/configuration.calx`](test/configuration.calx) also write every packet their clients get to `build/packets/`, and `run.py` ends by reading them with vanilla's own codecs, from the 26.3 jar, once the [vanilla adapter](../oracle/vanilla-adapter/README.md) is built ([D145](../docs/decisions.md)). Each must decode, leave no bytes over and encode back to the same bytes; `set_time` and `update_tags`, whose order vanilla itself doesn't fix, are compared as values. Without the adapter, that step is skipped. CI builds it.

```sh
py -I oracle/vanilla-adapter/build.py           # once, with JDK 25
py -I oracle/vanilla-adapter/check_packets.py   # after the tests: ok or FAIL for each kind of packet
```
