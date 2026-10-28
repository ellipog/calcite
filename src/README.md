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
| `java.text` | `string_hash`, Java's `String.hashCode` over UTF-16 code units | `String.hashCode` |
| `java.uuid` | `Uuid`, two `i64`s, written and read as Java writes and reads them; name-based (version 3) and random (version 4) UUIDs | `java.util.UUID` |
| `java.base64` | `encode`, Base64 with padding and no line breaks, and `decode`, which takes what Java's decoder takes | `java.util.Base64.getEncoder()`, `getDecoder()` |
| `java.properties` | `Properties`, a `.properties` file read with Java's rules for escapes, continued lines and comments | `java.util.Properties.load` |
| `java.uri` | `Uri`, a URI checked as Java's `new URI` checks it, with its messages, and `Uri.untrusted`, the links vanilla lets players open | `java.net.URI`, `Util.parseAndValidateUntrustedUri` |
| `json.gson` | `JsonWriter`, compact JSON with Gson's escapes | Gson's `JsonWriter`, with `disableHtmlEscaping` |
| `json.tree` | `Json`, a JSON value, with a strict parser, a writer and lookups | |
| `nbt.tag` | `Tag`, an NBT tag, read and written in network and file form with `Accounter`'s limits, and printed as SNBT | `Tag` and its types, `NbtIo`, `NbtAccounter`, `StringTagVisitor` |
| `pack.zip` | `Zip`, a zip archive in memory: the central directory, Zip64, and entries stored or deflated, each checked against its CRC-32 | `java.util.zip.ZipFile` |
| `pack.resources` | `Pack`, a data pack's files under `data/`, and `Resources`, the packs in order, whose `list` and `stacks` give files in vanilla's order, later packs over earlier ones, and `KnownPack` | `PackResources`, `MultiPackResourceManager`, `FileToIdConverter`, `KnownPack` |
| `pack.vanilla` | `vanilla_pack`: the built-in data pack, from the jar bundled in Mojang's server jar, downloaded the first time and checked against its pins | `VanillaPackResources`, the bundler's `versions.list` |
| `pack.pin` | Where the pinned server jar comes from, and its size and SHA-1, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | |
| `registry.builtin` | The 95 built-in registries and their entries in ID order, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | `BuiltInRegistries` |
| `registry.registry` | `Registry`, a registry's entries with their IDs and its tags, and `Tag` | `MappedRegistry`, `HolderSet.Named` |
| `registry.tags` | `load_tags`: a registry's tags from the packs, read, merged and built in vanilla's order, with its log lines | `TagLoader`, `TagFile`, `TagEntry`, `DependencySorter` |
| `registry.registries` | `Registries`: the synchronized registries, in the order they're sent, and the built-in ones, each with its tags | `RegistryDataLoader`, `RegistrySynchronization` |
| `chat.component` | `Component`: text and translations with their arguments and siblings, their JSON and NBT, written and read, and `get_string`, their text | `Component`, `ComponentSerialization.CODEC`, `TranslatableContents` |
| `chat.language` | `Language`, the text of each translation key, which the server's own text, such as its log, is made with | `Language` |
| `resources.identifier` | `Identifier`, a namespace and a path, parsed with vanilla's rules and messages | `Identifier` |
| `auth.profile` | `GameProfile` and `ProfileProperty`, as the login sends them; offline profiles, and which names vanilla takes | authlib's `GameProfile` and `Property`, `ByteBufCodecs.GAME_PROFILE`, `UUIDUtil.createOfflineProfile`, `StringUtil.isValidPlayerName` |
| `auth.session` | The server's hash, the session server's `hasJoined` URL, and what each answer of Mojang's services means | `Crypt.digestData`, authlib's `MinecraftClient`, `MinecraftServicesSessionService.hasJoinedServer`, `PropertyMap.Serializer` |
| `auth.velocity` | `read`, the player data Velocity's modern forwarding sends, checked against the secret, and `parse_ip`, the address in it | |
| `auth.services` | `Services`: the discovery document and the services' public keys, fetched and fetched again as authlib does, and `JoinCheck`, a login's check with the session server | authlib's `Environment`, `MinecraftServicesDiscoveryService`, `RetryableFetch`, `MinecraftServicesKeyInfo` |
| `protocol.state` | `State`, the five protocol states, and `Bound`, a packet's direction | `ConnectionProtocol`, `PacketFlow` |
| `protocol.ids` | The protocol version and each state's packet names in ID order, written by [`calx_tables.py`](../oracle/datagen/README.md#calx-modules) | The order packets register in each state's protocol |
| `protocol.wire` | `Reader` and `Writer`, the `Wire` and `Packet` interfaces, `write_packet` | `FriendlyByteBuf`, `VarInt`, `VarLong`, `Utf8String`, `ByteBufCodecs` |
| `protocol.codegen` | The attributes that write packets' code: `@packet`, `@packets`, `@wire`, `@wire_enum` | Each packet's `STREAM_CODEC`, `IdDispatchCodec`, `PacketDecoder` |
| `protocol.handshake`, `protocol.status`, `protocol.login`, `protocol.configuration` | Their states' packets | The packets in `network.protocol.handshake`, `.status`, `.login`, `.cookie` and `.configuration` |
| `protocol.common` | The packets configuration and play share: keep-alives, pings, plugin channels, resource packs, links, tags and disconnecting; `ClientInformation` | The packets in `network.protocol.common`, `ClientInformation` |
| `protocol.frame` | `FrameReader`, which collects a connection's bytes and gives back whole frames, and `frame` | `Varint21FrameDecoder`, `Varint21LengthFieldPrepender` |
| `protocol.compression` | `compress` and `decompress`, a packet inside a frame once compression is on, with vanilla's checks and messages | `CompressionEncoder`, `CompressionDecoder` |
| `protocol.codec` | `Codec`, a connection's frames and packets with its encryption and compression | The pipeline of `CipherDecoder`, `CipherEncoder` and the frame and compression handlers |
| `protocol.legacy` | The server list ping of clients before 1.7, and its answer | `LegacyQueryHandler`, `LegacyProtocolUtils` |
| `server.properties` | `ServerProperties`, the settings read so far, and `load`, which reads server.properties | `DedicatedServerProperties`, `Settings` |
| `server.config` | `CalciteConfig`, the settings in calcite.properties, and the text of a new one | |
| `server.status` | `ServerStatus`, what the server list shows, and its JSON; `check_icon` | `ServerStatus`, `PngInfo`, `MinecraftServer.loadStatusIcon` |
| `server.configuration` | `Configuration`: what configuration sends every player, encoded once; the server's links, its resource pack and its code of conduct, from server.properties and the `codeofconduct` folder | `startConfiguration`, `SynchronizeRegistriesTask`, `TagNetworkSerialization`, `getServerPackInfo`, `createServerLinks`, `readCodeOfConducts` |
| `server.network` | `Network`: accepting connections, reading frames, the handshake, the status and ping, old pings, logins offline and online, configuration, and the read timeout | `ServerConnectionListener`, `ServerHandshakePacketListenerImpl`, `ServerStatusPacketListenerImpl`, `ServerLoginPacketListenerImpl`, `ServerConfigurationPacketListenerImpl`, its tasks, `Connection`, `ReadTimeoutHandler` |
| `server.log` | `log` and `line`, the console's lines, and `Entry`, a line left for the caller to log, with the thread vanilla logs it on | Mojang's log4j2 console pattern |
| `calcite` | The server's `main`, which loads the vanilla data pack, and its loop of 20 ticks a second | `Main`, `DedicatedServer.initServer`, `MinecraftServer.runServer` |
| `rig.adapter` | The rig adapter's main: answers `hello`, `run` and `bye` | |
| `rig.frame` | The rig's frames, whose headers are JSON | |
| `rig.rng` | The `rng` probe | |
| `rig.collections` | The `collections` probe: Calx's Java-ordered tables against Java's and fastutil's | |
| `rig.registries` | The `registries` probe: the vanilla data pack's registries and tags against vanilla's | |
| `rig.nbt` | The `nbt` probe: binary NBT read, printed and written back, against vanilla's | |

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

`read` takes a frame's bytes after its length and any compression, as vanilla's `PacketDecoder` does: the ID, then the packet, which must end where the frame does. It fails with vanilla's messages, such as `Received unknown packet id 5`, and says which packet failed to decode: `Failed to decode packet 'serverbound/minecraft:intention': Unknown connection intent: 4`.

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
```

It starts as vanilla's dedicated server does, with its log lines, loads the vanilla data pack, answers the server list: the status, with the description, player counts, version and icon, the ping, and the old pings of clients before 1.7, logs players in and configures them. It ticks 20 times a second, as vanilla does, and like vanilla warns `Can't keep up!` when it's more than 2 seconds behind, at most once in 15 seconds, and skips the ticks it missed.

- **server.properties** is read as vanilla reads it: UTF-8, or ISO-8859-1 if it isn't, with Java's `Properties` rules. A setting that's missing or doesn't parse is its default, as `Boolean.valueOf` and `Integer.parseInt` decide. The settings read so far are `online-mode`, `server-ip`, `server-port`, `motd`, `max-players`, `enable-status`, `hide-online-players`, `enforce-secure-profile`, `accepts-transfers`, `prevent-proxy-connections`, `network-compression-threshold`, `rate-limit`, `log-ips`, `enable-code-of-conduct`, `bug-report-link`, `resource-pack`, `resource-pack-id`, `resource-pack-sha1`, the older `resource-pack-hash`, `require-resource-pack` and `resource-pack-prompt`.
- **calcite.properties** holds Calcite's own settings, those server.properties hasn't, in the same format, and is read the same way. A server that has none writes one, with each setting at its default and a comment on what it does. A setting that stops the server, such as forwarding with no secret, is logged as `Failed to start the minecraft server: ...` on `main`.

  | Setting | Default | What it does |
  | --- | --- | --- |
  | `velocity-forwarding` | `false` | Lets players in only through a Velocity proxy, with the player data its modern forwarding sends. The proxy authenticates them, so `online-mode` is ignored, and its offline-mode warning isn't logged. |
  | `velocity-secret` | empty | The text of Velocity's forwarding.secret, which signs that data. It must be set when `velocity-forwarding` is on. |

- **server-icon.png** must be a 64 by 64 PNG, checked as vanilla's `PngInfo` checks it, with its messages.
- **The vanilla data pack** is in Mojang's server jar, which the server downloads from Mojang the first time it starts, into `cache/`, and checks against its pin each time ([D131](../docs/decisions.md)). Its registries and their tags load before the server starts, as vanilla's `Main` loads data packs, and a tag that can't be built stops it with vanilla's `Failed to load datapacks, can't proceed with server load`.
- **The handshake** sends a client of another protocol version vanilla's `multiplayer.disconnect.outdated_client` or `multiplayer.disconnect.incompatible`, and a transfer, with `accepts-transfers` off, `multiplayer.disconnect.transfers_disabled`. A second status request closes the connection, and so does the pong.
- **Broken input**, such as a frame of no bytes, a length longer than 3 bytes, an unknown packet or one with bytes left over, closes the connection without an answer and logs nothing, as vanilla does in these states: it has no disconnect packet to send, and logs the reason only at debug level.
- **A connection that sends nothing for 30 seconds** is closed, as by vanilla's `ReadTimeoutHandler`.
- **The login** gives a player in offline mode the profile vanilla gives, with the UUID made from `OfflinePlayer:` and their name. On the tick after the client's hello, it turns on compression if `network-compression-threshold` isn't negative and sends the profile, with a session ID shared by every login while the server has a connection open. A client that acknowledges it goes on to configuration. A login that takes more than 600 ticks is told `multiplayer.disconnect.slow_login`.
- **Online mode** authenticates players with Mojang's session server, as vanilla does. The server makes a 1024-bit RSA key pair when it starts, and sends a client its public key and 4 random bytes; the client sends back a secret and those bytes, encrypted with the key, and everything after is encrypted with AES-CFB8 and the secret. A challenge that isn't the server's, or a secret that isn't 16 bytes, is `java.lang.IllegalStateException: Protocol error`. An authenticator asks the session server whether the player joined with the server's hash, while the server goes on, and gives the player the UUID and properties it answers with, under the name they gave. The session server is given the player's address too with `prevent-proxy-connections=true`. A player it says didn't join is told `multiplayer.disconnect.unverified_username`, and one it can't be asked about `multiplayer.disconnect.authservers_down`, which is what every player is told while Mojang's services can't be reached.
- **Configuration** runs as vanilla's does. The server sends its brand, `calcite`, on `minecraft:brand`, the enabled features, `minecraft:vanilla`, and asks which of its packs the client has: `minecraft:core` at `26.3`. A client that has it is sent each synchronized registry's entries by name, in ID order, without their contents, then every registry's tags; one that hasn't would need the contents, which Calcite can't send yet, so it's told so and disconnected. The code of conduct and the resource pack come next when the server has them, then configuration ends once the player's place in the world is ready, on the next tick. These packets are the same for every player, so they're encoded once when the server starts. A keep-alive goes every 15 seconds, its challenge the time in milliseconds; one still unanswered when the next is due, or an answer to none, is `disconnect.timeout`. A packet that comes at the wrong time gets what vanilla gives it: one vanilla handles on the server thread, such as `finish_configuration` before configuration has ended, is logged as `Failed to handle packet ..., suppressing error` with the exception, and the connection goes on; another, such as accepting a code of conduct that wasn't sent, ends the connection with `disconnect.genericReason` and the exception. A client that says it's finished is told `Calcite can't run the play state yet`, in play's disconnect, until play is written (`P4.5`). [`test/configuration.calx`](test/configuration.calx) checks each step.
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

An offline player's UUID, and a component as text, which is how the log shows a disconnect's reason. The server's language has no translations until it's read from the jar (`P5.8`), so for now a key is its own text, as vanilla shows a key its language hasn't:

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

The log's lines follow Mojang's console pattern, `[%d{HH:mm:ss}] [%t/%level]: %msg`, in the local time zone:

```calx
import server.log.{Level, line}
import std.time.{Timestamp}

fn main() {
    let at = Timestamp { unix_ms: 1792540800000 }    // 2026-10-21 00:00 UTC
    println(line(at, 7200, "Server thread", Level.Info, "Done (0.001s)! For help, type \"help\""))    // out: [02:00:00] [Server thread/INFO]: Done (0.001s)! For help, type "help"
}
```

Where it differs from vanilla, for now:

| Vanilla | Calcite | Until |
| --- | --- | --- |
| Asks you to agree to Mojang's EULA in eula.txt | Doesn't: Calcite isn't Mojang's software | Always |
| Writes server.properties back on start, with every setting | Only reads it | A later change |
| Also logs to logs/latest.log | Logs to the console only | A later change |
| `enforcesSecureChat` follows `enforce-secure-profile` and online mode | Always false, since nothing checks chat yet | Signed chat (`P4.5`) |
| The status's player counts and sample come from who's online, rebuilt every 5 seconds | No one can be online, so it's built once | Play (`P4.5`) |
| Reads its language, en_us.json, from the jar, so the log shows a reason's English text | Has no translations, so a translated reason shows its key, such as `multiplayer.disconnect.slow_login` | Reading the jar (`P5.8`) |
| Checks bans, the whitelist and a full server before it lets a player in, and kicks a player already in the world with the same UUID | Lets every valid login in, since there's no player list yet | Play (`P4.5`) |
| Logs an exception's stack trace after lines such as `Failed to connect` | Logs the line alone | A later change |
| Fetches the services' public keys twice when it starts, once for its session service and once for itself, so with no internet it logs their failure twice | Fetches them once | Always |
| Reads the services' answers with Gson, which takes some JSON that isn't strict, a number where a string goes, and text that isn't UTF-8 | Reads strict UTF-8 JSON, and takes a number or boolean where a string goes, as Gson does; anything else is an answer it can't read | A later change |
| A few answers that can't be read, such as a property without a name, throw an exception authlib doesn't catch, so the login waits until it takes too long | They mean the player didn't join | Always |
| zlib names what's wrong with deflate data it can't read, such as `invalid distance too far back` | Names a broken header and block type as zlib does, and anything past them `invalid deflate data` | A later change |
| Has no proxy support: a server behind one sees every player at the proxy's address, with the profile the proxy sends in its hello | Reads Velocity's modern forwarding, as Paper does, with Calcite's own messages and settings | Always |
| `Done (...)` times loading the level | Times the whole start, since there's no level | Worlds (Phase 5) |
| Sends its brand as `vanilla` | Sends `calcite` | Always |
| Sends a client without `minecraft:core` the registries' contents | Disconnects it, saying it can't yet | Registry contents (`P4.4`) |
| Puts the registries in `update_tags` in an order that changes from run to run, from a `HashMap` of their keys | Keeps theirs, the synchronized ones first, then the built-in ones; the tags in each are in vanilla's order | Always |
| Handles some packets on the server thread, at its next chance, and the rest as they're read | Handles each as it's read, in order, with the error handling vanilla gives it on its thread | Always |
| Logs a packet that failed on the server thread with Java's `toString`, which names `finish_configuration` by its class and the instance's hash code, then the stack trace | Leaves out the hash code, which changes from run to run, and logs the exception's first line alone | Always |
| Checks the player list when configuration ends, then puts the player in the world | Tells the player play isn't written yet | Play (`P4.5`) |
| Lists the `codeofconduct` folder in the order the system gives, which decides the code of conduct a client gets when there's none in its language and no `en_us` | Lists it sorted by name, so it's the same on every system | Always |
| Refuses every code of conduct file when the server's folder is reached through a link, since it compares each file's real path with the folder's absolute one | Compares real paths, so only a file that links out of the folder is refused | Always |
| Has several messages for a mistake inside an IPv6 address in a link, such as `IPv6 address too long` | Says `Malformed IPv6 address`, at the address's start | Always |
| Keeps a resource pack prompt's styles and other contents, such as key binds, and sends its number and boolean arguments as numbers | Keeps text and translations, with the arguments as text, and refuses other contents | Chat (`P4.5`) |
| Logs a prompt that isn't JSON with Gson's exception, and one its codec refuses with the codec's message; reads one nested up to 255 deep | Logs the first without an exception, and the second with Calcite's own message, such as `No matching codec found`; reads one nested up to 64 deep | Always |

## Tests

`src/test/` holds Calx tests that need no vanilla data, such as MD5's published test vectors. Each panics on a wrong result and prints `ok`:

```sh
py -I src/test/run.py                   # every test and example on this page, debug and release, and builds the server
py -I rig/runner/rig.py score           # everything the rig can check
```

An example's `// out:` comments give the lines it must print, as in Calx's own docs. Both commands run in CI on Windows and Linux. A test's source root is `src/`, since it starts with a `module test.<name>` line, so it imports Calcite's modules as Calcite does.
