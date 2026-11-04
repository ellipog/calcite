---
title: Vanilla adapter
description: The Java 25 program that runs rig probes against Mojang's 26.3 server code and reports the results.
---

# Vanilla adapter

This is the rig's source of truth (`P1.2`). It loads Mojang's server jar, boots vanilla's registries, and answers [rig protocol](../../rig/PROTOCOL.md) requests by calling vanilla's own code. Since 26.1 the jar is unobfuscated, so the probes call vanilla by its real names with no mapping step.

Nothing from the jar is committed. The build reads it from the gitignored `oracle/jars/` and unpacks into the gitignored `oracle/work/` and `build/` (D30).

## Building

You need JDK 25. The build gets the 26.3 server jar itself: [`../fetch.py`](../fetch.py) downloads it to `oracle/jars/server-26.3.jar` if it's missing, and checks it against the SHA-1 pinned in [`../versions.json`](../versions.json) either way (`P2.4`, D62).

```sh
py -I build.py                         # finds JDK 25 from CALCITE_JAVA_HOME, JAVA_HOME or PATH
py -I build.py --java-home <jdk-25>    # or name it
```

The build:

1. Fetches the jar if it's missing, and checks its SHA-1 against the pin.
2. Reads `META-INF/versions.list` and `META-INF/libraries.list` from the bundler jar.
3. Extracts the inner server jar and its 39 libraries into `oracle/work/versions/` and `oracle/work/libraries/`, checking each against the bundler's SHA-256. Files that are already there with the right hash are kept.
4. Compiles `src/` with `javac --release 25`, with warnings as errors.
5. Writes `build/<platform>/adapter.json`: the command line the runner starts the adapter with, and the JVM flags for each vanilla configuration the rig records (D60). Each platform gets its own folder, so one checkout can be built from Windows and from WSL.

| Configuration | JVM flags |
| --- | --- |
| `strict-math`, the reference | `-XX:+UnlockDiagnosticVMOptions -XX:-UseLibmIntrinsic`, so `Math` gives exactly `StrictMath`'s results |
| `intrinsics` | none: HotSpot's defaults |

## Running

The runner starts it from `build/<platform>/adapter.json`. To start it by hand, use that file's `argv`, with a configuration's flags after the `java` executable, with `oracle/work/` as the working directory. Then talk to it over stdin and stdout.

- **Stdout carries only frames.** The adapter takes the real stdout before vanilla loads, and points `System.out` at stderr, so a stray print can't corrupt a frame.
- **Logs go to stderr.** [`log4j2.xml`](log4j2.xml) sends every log there, and the runner saves it.
- **Startup takes about 3 seconds**, mostly `Bootstrap.bootStrap()`. The first `text` case takes a little longer, since it builds the registry lookup.

## Checking Calcite's packets

[`PacketCheck`](src/calcite/rig/vanilla/PacketCheck.java) is a second entry point, not a probe ([D145](../../docs/decisions.md)). Calcite's network tests write every packet their clients get to `build/packets/`, and [`check_packets.py`](check_packets.py) runs `PacketCheck` on them with the adapter's command line. It reads each packet with the codec vanilla's client reads it with: `StatusProtocols`, `LoginProtocols`, `ConfigurationProtocols` or `GameProtocols`, bound to the vanilla data pack's registries. A packet passes if it decodes, leaves no bytes over and encodes back to the same bytes. `set_time`, `update_tags` and `login` are compared as values instead, since their maps and the login's set of dimensions are keyed by identity-hashed objects and vanilla's order changes from run to run. It prints a line for each kind of packet and exits with 1 if any failed. `src/test/run.py` runs it at its end.

[`ChatCheck`](src/calcite/rig/vanilla/ChatCheck.java) then reads signed chat the way vanilla's client does ([D162](../../docs/decisions.md)). `test.play`'s signed-chat test also writes what each of its clients is sent to a file of its own in `build/packets/chat/`, with the test's Mojang public key as `services.der`. For each client, `ChatCheck` follows the game packets in order. `login` says whether the server enforces secure chat. `player_info_update` with `initialize_chat` gives a player's chat session, which must pass `RemoteChatSession.Data.validate` against the test's Mojang key, as it does in vanilla's `ClientPacketListener`. Each `player_chat` must carry the next global index; its last-seen list is unpacked with the client's `MessageSignatureCache`; and its signature is checked by the sender's `SignedMessageValidator`, with the sender's link chain. A key expires by the message's own time, since the test's clock is fixed in 2025. It says how many messages each client took and how many were signed, and exits with 1 if vanilla would refuse any.

## Reading sessions

[`SessionDump`](src/calcite/rig/vanilla/SessionDump.java) is a third entry point, for the [protocol suites](../../rig/README.md#protocol-suites). The protocol bot records every packet a server sends it, with the state it came in, and `SessionDump` reads each with the same codecs as `PacketCheck`, writing a `.jsonl` beside each recording: one line a packet, with its state, its size, the start of its SHA-256, its kind, such as `login_finished`, and its value as a tree. Records and Minecraft's objects are written field by field, by reflection, with their class's simple name under `@`; maps and sets are sorted, so their order doesn't count; an entry of a built-in registry is its name, such as `#item/stone`; a component, a UUID or an identifier is its `toString`; NBT is a tree; a block's or a fluid's state is its block and properties, as `toString` gives them, `Block{minecraft:redstone_wire}[east=side,...]`, not its fields, whose table of the states a property away holds every state of its block, each with its own, which made a section's changes of wire 19 MB a packet; a chunk packet's sections, its `buffer`, are each section's counts of blocks and fluids and a hash of its states and of its biomes, an ID at each place, as the client reads them, so how a palette's written, its order and its bits, doesn't count ([D343](../../docs/decisions.md)); and any other byte array of more than 64 bytes is its size and hash. A lambda inside a value is `<function>`, and a packet whose tree would pass a million nodes, or that leaves bytes over, says so in an `error`. The bot's marks, such as `step join` or `closed`, are lines of their own.

| File | Role |
| --- | --- |
| `src/calcite/rig/vanilla/Main.java` | Boot, then the request loop: `hello`, `run`, `bye` |
| `Frame.java` | Reading and writing frames |
| `Probe.java`, `Result.java`, `CaseError.java`, `Args.java` | The probe interface, results, and checked case input |
| `PingProbe.java` | `ping` |
| `RngProbe.java` | `rng` |
| `NbtProbe.java` | `nbt` |
| `TextProbe.java` | `text` |
| `MathProbe.java` | `math` and `strictmath` |
| `MthProbe.java` | `mth` |
| `BlockStateProbe.java` | `block_state` |
| `CollectionsProbe.java` | `collections` |
| `PaletteProbe.java` | `palette`: `PalettedContainer` and `SimpleBitStorage`, over a registry of objects compared by identity, as block states are |
| `ChunkProbe.java` | `chunk`: `LevelChunkSection` and `Heightmap` in a `ProtoChunk`, with blocks set as `LevelChunk.setBlockState` sets them |
| `RegionProbe.java` | `region`: a `RegionFile` in a new folder, with chunks written as the case gives their bytes, and what it logs, caught by an appender on its logger |
| `LevelDataProbe.java` | `level_data`: the `Data` of a `level.dat` read by `readDataConfig`, `LevelSettings.parse` and `PrimaryLevelData.parse` and written back by `createTag`, with `LastPlayed` as 0 |
| `WorldFolderProbe.java` | `world_folder`: a world's folder in a new folder of its own, opened, locked, read with the `level.dat_old` fallback, checked as `Main` checks it, saved and closed by `LevelStorageSource`, players' data read by `PlayerDataStorage.load`, saved data read and written by `SavedDataStorage`, with a type whose codec keeps `data` as it is, advancements and statistics read and saved as `PlayerAdvancements` and `ServerStatsCounter` read and save them around their codecs, and statistics found by `PlayerList.locateStatsFile` itself, with what they log, caught by an appender on the root logger |
| `EntitiesPoiProbe.java` | `entities_poi`: an entity chunk read by `EntityStorage.loadEntities`, upgraded and with its `Entities` read through `TagValueInput` in a `ProblemReporter.ScopedCollector`, before the entities are made, and saved by `storeEntities`; a POI chunk read and written back by `SectionStorage`'s own `PackedChunk.parse`, `unpackChunk` and `writeChunk` with `PoiSection`'s codec; and what they log, caught by an appender on the root logger |
| `ChunkNbtProbe.java` | `chunk_nbt`: a chunk's NBT read by `SerializableChunkData.parse` and written back by its `write`, with the data pack's biomes, and what it logs, caught by an appender on the root logger |
| `LightProbe.java` | `light`: a `LevelLightEngine` over `ProtoChunk`s the case makes, each with its own `ChunkSkyLightSources`, through a `LightChunkGetter` over a map, called as `ThreadedLevelLightEngine` calls it, with blocks set as generation sets them or as `LevelChunk.setBlockState` tells light |
| `BlockFlags.java` | Not a probe: writes each block state's flags from vanilla's state cache, the faces light sees of each, and the faces a fluid sees, checked against vanilla's own `canPassThroughWall` as they're written (D327), and each block's note block instrument (D332) and fire's ignite and burn odds (D339), run by `oracle/datagen/block_flags.py` |
| `EntityFacts.java` | Not a probe: writes what natural spawning asks of each entity type and block state, each type's spawn placement read from `SpawnPlacements`' class initializer, run by `oracle/datagen/entity_facts.py` (D317) |
| `PacketCheck.java` | Vanilla reading Calcite's packets, run by `check_packets.py` |
| `ChatCheck.java` | Vanilla's client checking the signed chat in `build/packets/chat/`, run by `check_packets.py` |
| `SessionDump.java` | Vanilla reading the protocol bot's sessions, as trees, run by `rig/runner/sessions.py` |
| `agent/Agent.java` | The rig's Java agent: its arguments, and the two classes it changes as they load |
| `agent/Levels.java` | What it does as each level's made: its random seeded, with its `randValue` (D318), the entity counter set back |
| `agent/Tape.java` | The RNG tape: each draw of a level's random, with where it was drawn |
| `WorldCheck.java` | Vanilla reading a world it saved and the same world saved by Calcite, with `RegionFile`, `NbtIo` and Gson, and comparing them file by file and chunk by chunk, run by `rig/runner/roundtrip.py` (`G5.2`) |
| `EnvironmentProbe.java` | `environment`: an `EnvironmentAttributeSystem` built as a level's but for the biomes, from a dimension type or a data pack's map and timelines, with every clock at the record's ticks and the record's rain and thunder, read by `getDimensionValue` |
| `RegistriesProbe.java` | `registries`: the vanilla data pack's registries and tags, loaded once as `WorldLoader.load` loads them |
| `NoiseProbe.java` | `noise`: `PerlinNoise`, `SmearedPerlinNoise`, `SimplexNoise`, the stacks `NormalNoise` and `BlendedNoise.createFbm` make, sampled with `get` and `addToVolume` |

## Rules for probes

- **A probe is a pure function of its case.** No clock, no unseeded randomness, no state carried between cases, except caches that don't change results (like the registry lookup).
- **Malformed cases throw `CaseError`.** `Args` reads every field and throws `CaseError` for anything missing or mistyped. So any other exception came from the game, and becomes a rejection result instead of an error.
- **Bits, not text.** Floats go out as raw bits in a blob, never formatted.

## The agent

Vanilla isn't repeatable run to run. Each level's `random` is seeded from `RandomSupport.generateUniqueSeed()`, which mixes in `System.nanoTime()`, and the entity ID counter is a static `AtomicInteger`, `ServerLevel.ENTITY_COUNTER`. The Phase 1 probes touch neither. For what does, the build also writes `build/<platform>/agent.jar`, the rig's Java agent ([D311](../../docs/decisions.md)), and names it in `adapter.json`'s `agent`. A vanilla server started with `-javaagent:agent.jar=seed=N`:

- seeds each level's random, as the level's made, with `mixStafford13(N ^ name.hashCode())`, the name its dimension's, such as `minecraft:overworld`, and sets the level's `randValue`, which picks where random ticks land, to the seed's low 32 bits, where vanilla starts it from a random of the thread's own ([D318](../../docs/decisions.md)). Calcite's `level-random-seed=N` seeds its own the same way;
- sets the entity counter back to 0 as the Overworld's level is made, so the first entity is 1;
- with `,tape=PATH` as well, writes each value a level's random draws to `PATH`, the RNG tape, a line each: the level, its game time, the bits drawn, the value, and the two frames of the stack that asked for it outside the random classes. As the JVM ends it adds `# end LEVEL TIME` for each level, its game time then. Calcite's `--rng-tape PATH` writes the same lines, without where each was drawn, and [`tapediff.py`](../../rig/runner/tapediff.py) lines the two up ([D312](../../docs/decisions.md));
- with `,reseed=T` as well, seeds each level's random again as it was seeded, with its `randValue`, the first time the level's tick starts at game time T or later, as Calcite's `--rng-reseed T` does, so the tapes line up again from there whatever each server drew before ([D316](../../docs/decisions.md)).

```
# seed 1103
minecraft:overworld 0 31 1530525153 Mth.randomBetweenInclusive:823 UniformInt.sample:27
minecraft:overworld 0 31 353078769 Mth.randomBetweenInclusive:823 UniformInt.sample:27
minecraft:overworld 1 31 699777690 PhantomSpawner.tick:41 ServerLevel.tickCustomSpawners:501
```

It changes two classes as they load, with the JDK's own `java.lang.classfile`: `ServerLevel`'s constructors call `Levels.made` before they return, its `tick` calls `Levels.ticking` as it starts, and `LegacyRandomSource.next`, which every draw of a level's random comes down to, hands each value it returns to `Tape.drew`. A change that fails stops the server, which would otherwise run unseeded. The rig's runners start every vanilla server with it, at seed 1103.
