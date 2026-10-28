# Calx + Calcite: Build Plan

Oct 26, 2026 · Elliot. Revised the same day after review, adding decisions D18–D41.

## Goals

Calcite exists for three reasons (D18):

1. **Plugin development.** The best plugin experience of any Minecraft server: safe by default, fast, hot-reloadable, testable, well documented and well tooled.
2. **Performance.** Faster than Paper and Folia at every player count, and scaling across cores.
3. **Vanilla parity.** Everything vanilla does, worldgen included, block for block. The exceptions are bugs and exploits, which are fixed and listed.

When they conflict, parity wins wherever players, farms or data packs could observe the difference. Performance wins wherever nothing is observable. The plugin API never forces a parity or performance compromise in core.

## Overview

Build Calx and Calcite in ten phases, and don't start a phase until the one before it has passed its gate. The oracle rig comes before any server code, and Calx grows alongside Calcite: each phase adds only the language features it needs. The exception is the foundations that are expensive to retrofit (memory safety, generics, modules, the tick model), which Phase 0 settles up front.

Rough estimate: 3–6 months with AI assistance for Phases 0–4. Bit-exact worldgen in three dimensions (Phase 5) could take that long by itself, and simulation parity after it is a long tail.

| Phase | Builds | Gate |
| --- | --- | --- |
| 0 | Design on paper | Sample addons and sketches written with no hand-waving; spec and host API v0 |
| 1 | Oracle rig | Vanilla agrees with itself; the scoreboard shows Calcite at 0% |
| 2 | Generated data tables | One command regenerates everything, byte-identical on rerun |
| 3 | Calx compiler core | RNG probes 100% bit-exact; tick-loop benchmark within 10% of Rust |
| 4 | Protocol and a flat world | A real client joins in online mode, walks around and chats |
| 5 | Chunks, storage, regions, worldgen | Worldgen suites pass in all three dimensions; worlds round-trip; one thread and many give identical results |
| 6 | Simulation | Suite parity where you want it; a survival session feels like vanilla |
| 7 | Plugin host | Five sample addons run natively and one as WASM; runaways are stopped; reload keeps state |
| 8 | Benchmarks and your own servers | MSPT recorded against Paper, Folia and Pumpkin; one of your servers runs on Calcite |
| 9 | Plugin SDK, tooling and docs site | A newcomer ships a tested plugin in under an hour using only the docs |

Phase 9 can overlap Phase 8.

The Phase 3 gate is the one to take seriously. If Calx can't reproduce vanilla's RNG exactly or keep up with Rust on a tick loop, stop and change Calx (D37) before building a server on it.

Task IDs (`P3.5`) and gate IDs (`G3.1`) are stable. Never renumber them, and add new tasks at the end of their phase. Work is tracked on two Acta boards, one per repo:

- [aaen-studios/calcite](https://acta.aaenz.no/aaen-studios/calcite) (`CAL-n`) has the server, the rig, the plugin host and every gate card.
- [aaen-studios/clx](https://acta.aaenz.no/aaen-studios/clx) (`CLX-n`, named "calx") has the language, compiler, runtime, standard library and Calx tooling.
- Each phase is an Acta project on whichever boards have work in it.
- Each `P` task is a card that names its plan ID. A task that is all Calx, like `P0.3` or `P4.1`, goes on the calx board.
- Each phase's gate is a "Pass the Phase N gate" card on the calcite board whose subtasks are the gate conditions. It links any calx cards it depends on.
- Phases 3–9 have only their gate card and a few placeholder cards for now. Their task cards are created when the previous gate passes.

**Rules for every phase**

- **Test first.** A feature starts as failing rig cases and is done when they pass. Progress is measured by the scoreboard, not by lines written.
- **Docs as you go.** A Calx feature isn't done until its reference page is written and the examples on it pass as tests (D40, D41). From Phase 7 the same applies to every host API function. Docs are never a later task.
- **You own the design, the model writes the code.** This plan, `decisions.md` and `CALX_SPEC.md` are the source of truth. Give Opus small tasks against them, and let the rig, the compiler tests and the doc tests judge the result.
- **Bit-exact, not close.** Floats are compared as raw bits, so a near miss counts as a failure. The only exceptions are deliberate differences, such as fixed bugs and exploits, which the rig lists by name.
- **Keep vanilla material local.** The jar, any decompiled source and the full goldens stay out of both repos (D30). Commit only case inputs and hashes.
- **Grow Calx on demand.** Add a language feature when a Calcite phase needs it, with tests and docs, instead of building the whole language up front. The foundations Phase 0 settles are the exception.
- **Same inputs, same answer.** From the first multi-region test on, the same input log must give identical results with one region thread and with many (D21).
- **Track performance from Phase 3,** not just in Phase 8 (D34).
- **Stay on 26.3** until Phase 5 is done. As of Oct 26, 2026, 26.4 is at snapshot 5.

## Phase 0: Design on paper

Settle the language, the tick model and the plugin API on paper before writing a compiler, because all three are expensive to change later. Plugins are native Calx first and WASM second, both built against one host API, so that API is the contract that matters most.

**How**

- **P0.1** Write the five sample addons in imagined syntax: a `/home` command with saved data, a chat filter, a custom mob drop, a teleport that crosses regions, and a timed world event. See `plugins/samples/README.md` for what each one has to test.
- **P0.2** Sketch three pieces of Calcite in imagined Calx: the tick loop with D20's phases, one region actor and one packet handler.
- **P0.3** Write `CALX_SPEC.md` v0 from what those needed. It must settle every "Must" in the spec skeleton:
  - Java-exact integer and float semantics
  - memory safety, handles and panics (D23–D25)
  - generics, interfaces and modules (D26)
  - strings and Java-compatible collections (D27, D28)
  - region actors and the tick phases (D19–D21)
  - FFI
  - what Calx leaves out
- **P0.4** Inventory vanilla's world-wide systems in `docs/global-systems.md`: every system that reads or writes beyond one region, where it runs (global phase or region), and whether it becomes a deliberate difference. Start with these:
  - commands and entity selectors, and data pack functions
  - sleeping
  - the phantom, patrol, wandering trader and cat spawners
  - raids, the world border, weather and time, and the dragon fight
  - maps, scoreboards and the player list
  - chunk tickets that cross regions (ender pearls, portals)
- **P0.5** Write the host API sketch in `plugins/api/HOST_API.md`, once for both kinds of plugin, with the plugin model built in:
  - one instance per region plus one global instance, with messages between them
  - host API only unless the plugin is trusted
  - chunky calls and handles
  - versioning and doc comments on everything
- **P0.6** Define the Phase 3 tick-loop benchmark in `calx/docs/benchmarks.md`, so the gate is fixed before the compiler exists. It should cover palette-container reads and writes, entity physics in doubles, hash-map work and actor messages.
- **P0.7** Keep the decision log current. Every settled question goes in it, numbered in order.

**Done when**

- [ ] **G0.1** All five addons and all three sketches are written without hand-waving over a missing feature
- [ ] **G0.2** `CALX_SPEC.md` v0 settles every "Must" in it
- [ ] **G0.3** The host API sketch covers every call the five addons make
- [ ] **G0.4** Every entry in the global-systems inventory has a home
- [ ] **G0.5** The benchmark is defined

## Phase 1: Oracle rig

Build the rig before any server code, so every feature is measured from the day it starts. Begin with the cheap pure probes and add the heavier pieces just before the phase that needs them.

**How**

- **P1.1** Keep your own `server-26.3.jar` in the gitignored `oracle/jars/` folder. It's already there, downloaded from Mojang and checked against the SHA-1 in Mojang's manifest.
- **P1.2** Write the vanilla adapter in Java 25: boot, a probe dispatcher over stdin/stdout, and the first probes (RNG, NBT, text components). The jar has been unobfuscated since 26.1, so the adapter calls vanilla by its real names, with no mapping step.
- **P1.3** Write the runner in Python: case files, golden recording, hashes in `expected/26.3/`, the self-check and the scoreboard.
- **P1.4** Make the self-check vary everything vanilla itself might be sensitive to, not just run it twice: JVM restarts, worker thread counts and generation order. Quarantine anything that varies, or list it as a deliberate difference.
- **P1.5** Add a `Math` against `StrictMath` probe for every transcendental function vanilla calls (`sin`, `cos`, `tan`, `atan2`, `exp`, `log`, `pow` and so on), and run it on Windows and on Linux. Done: HotSpot's x86-64 intrinsics differ from `StrictMath`, and can't be matched without copying GPL code. So the rig's reference is vanilla with the intrinsics off, where `Math` is exactly `StrictMath`, and default vanilla is recorded too, to measure the gap (D60).
- **P1.6** Add a Calcite adapter stub that answers "unimplemented" to every probe.
- **P1.7** Write `rig/PROTOCOL.md` for the adapter wire format: a JSON header plus raw byte blobs, sharing no code with Calcite.
- **P1.8** Keep a registry of deliberate differences in `rig/differences/`: each fixed vanilla bug or exploit, the cases it affects, and why. The scoreboard reports these separately instead of counting them as failures.
- **P1.9** Set up CI on Windows and Linux. For now it runs the runner's own tests. Compiler tests, doc tests and Calcite checks against the committed hashes come later. Because only hashes are committed, CI can check Calcite without the vanilla jar.

**Add later, just before the phase that needs it**

| Rig piece | Add before |
| --- | --- |
| Command parse probe (inputs generated from the command tree, plus fuzzing) | Any time after Phase 2 |
| Java collection probes (iteration order of `HashMap`, `HashSet` and fastutil maps) | Phase 3 |
| Protocol bot and packet normalizer | Phase 4 |
| Input log recording and replay tools | Phase 4 |
| Noise, worldgen and light probes; canonical chunk format | Phase 5 |
| Canonical-order worldgen driver for vanilla (D29) | Phase 5 |
| Java agent: seeded randomness, tick control, RNG tape | Phase 6 |
| Sim probe with structure-file fixtures | Phase 6 |

**Done when**

- [ ] **G1.1** Vanilla agrees with itself on every pure probe under the varied self-check, with any nondeterministic cases quarantined
- [ ] **G1.2** The scoreboard shows Calcite at 0% across the board
- [ ] **G1.3** CI runs on Windows and Linux

## Phase 2: Generated data tables

Generate every table from the vanilla jar instead of typing it, so moving to a new version means regenerating rather than rewriting.

**How**

- **P2.1** Run Mojang's data generator: `java -DbundlerMainClass=net.minecraft.data.Main -jar server-26.3.jar --all --output <dir>`. This was checked on 26.3 with Java 25. The options are `--all`, `--reports`, `--server`, `--dev`, `--validate`, `--input` and `--output`. The bundler unpacks its libraries into the working directory, so run it from the gitignored `oracle/work/`. Done: `oracle/datagen/datagen.py` runs it, fetching the jar first, and drops the generator's timestamped `.cache/` (see [`oracle/datagen/README.md`](../oracle/datagen/README.md)).
- **P2.2** Write a converter that turns the reports into neutral input for Calx codegen: block states with global IDs and properties, registries, packet IDs per protocol state, the command tree and items. Done: `oracle/datagen/convert.py` writes eight canonical tables, keeping every number's original text. Block states turned out to be pure arithmetic: consecutive IDs per block, mixed radix over the properties in name order. The converter checks all 35,723 states against that rule, and the `block_state` probe confirms it against the live game.
- **P2.3** Split what is compiled in (block states, packet IDs) from what is loaded at startup (data packs: worldgen settings, loot tables, tags, recipes), so Calcite reads data packs the way vanilla does. Done: D61. What vanilla defines in code is compiled in, including item default components and the code-defined biome parameter lists. What its built-in data pack holds is loaded from the jar at startup.
- **P2.4** Write the jar fetch step for the build (D30), shared with the rig: read Mojang's version manifest, download the jar and check its SHA-1. Calcite gets its own runtime version in Phase 5. Done: `oracle/fetch.py`, used by the adapter's build and the data generator step. The manifest is read once, to pin a version's URL, size and SHA-1 in the committed `oracle/versions.json`, so builds verify offline (D62).
- **P2.5** Write the cases for a block-state lookup probe (ID to properties and back), ready for when Calx can run them. Done: 104 cases in `cases/block_state/`, recorded against vanilla and repeatable under every self-check variant. Range cases cover every state and block ID with no game data in the repo. The parser cases found vanilla accepting trailing commas and leading zeros.

**Done when**

- [ ] **G2.1** One command regenerates every table from a jar
- [ ] **G2.2** Running it twice gives byte-identical output

## Phase 3: Calx compiler core

Build the smallest Calx that can run a tick loop and talk to C, written from zero. Then prove the two things everything else depends on: Java-exact math and native speed.

**How**

- **P3.1** Write the Rust version of the P0.6 benchmark and run it on both platforms.
- **P3.2** Build the compiler in C++ with CMake and Ninja: lexer, parser, type checker and C emitter, with clang compiling its output. Goose's design notes are worth reading for ideas, but no code is reused.
- **P3.3** Core language:
  - structs, enums with pattern matching, and functions
  - generics and interfaces, and modules with separate compilation (D26)
  - fixed-width integers with Java's semantics
  - bounds-checked arrays and optionals
  - arenas, `unsafe` and `extern` FFI, and panics (D23–D25)
- **P3.4** Java-exact semantics in the emitted C:
  - `-ffp-contract=off` and no fast-math
  - every case in the spec's integer list
  - vanilla's RNGs: java.util.Random's LCG, Xoroshiro128++ and the positional random factories, which need MD5
- **P3.5** A runtime library in C for Windows and Linux, with macOS later:
  - event-driven sockets (IOCP and epoll, D33), threads and typed queues
  - a monotonic clock and plugin library loading
  - zlib, lz4, hashes and crypto written in the runtime, and TLS from the system (D118, which replaces D32)
  - an HTTPS client for Mojang's session server

  Use clang on both platforms, and build and test on both from the first commit.
- **P3.6** Start the standard library: Java-compatible collections (D27) and strings (D28), checked against Java by the collection probes.
- **P3.7** Region actors, minimal at first: spawn an actor, send a flat message, receive it, and a lockstep tick barrier that delivers messages in a fixed order (D19, D20).
- **P3.8** Write the Calcite adapter in Calx: stdin/stdout and enough JSON to read `PROTOCOL.md` headers, answering the RNG probes.
- **P3.9** A compiler test suite of small Calx programs with expected output, run on every change in CI on both platforms. Docs examples run as part of it (D41).
- **P3.10** Debugging support: emit `#line` directives so debuggers and profilers on both platforms show Calx source lines, and make compiler errors readable. Editor support starts here (D65): a VS Code extension with a TextMate grammar, the compiler's errors as you type through `calx check --json`, and running files.
- **P3.11** Start performance tracking (D34): run the benchmark per commit and keep the results in `bench/`. Have the emitter add `restrict` where ownership proves there's no aliasing.
- **P3.12** Write the reference page for every feature as it lands (D40), and move its section out of `CALX_SPEC.md`. Start the guide with a first tutorial once there's enough language to write one.
- **P3.13** Make the type checker as strict as D63 says: exact-only `T(x)`, named lossy conversions, no implicit optionals, no dropped values, no unused names or shadowing, and parentheses where precedence surprises. Every rule gets a compile-fail test.
- **P3.14** Make builds fast (D64): a cache of objects keyed by their C text, parallel clang, a prebuilt runtime, lld, and `calx run` reusing an unchanged executable. Track build time per commit next to run time in `bench/`.

**Done when**

- [ ] **G3.1** RNG probes are 100% bit-exact against vanilla
- [ ] **G3.2** The tick-loop benchmark runs within about 10% of the Rust version on both platforms. If it doesn't, follow D37 before going further.
- [ ] **G3.3** Every shipped language feature has a reference page, and every example in the docs passes in CI
- [ ] **G3.4** On the reference machine, `calx run` on a small program takes under half a second from a cold cache and under 50 ms when nothing changed, and changing one module of the benchmark rebuilds it in debug mode in under a second

## Phase 4: Protocol and a flat world

Get a real 26.3 client connected and walking around before any real world exists.

**How**

- **P4.1** Add packet codegen to Calx: declare a packet's fields once and generate its reader and writer.
- **P4.2** Handshake and status, so the server shows up in the multiplayer list.
- **P4.3** Login, in this order:
  1. Offline mode.
  2. Online mode: RSA key exchange, AES/CFB8 encryption, and Mojang session authentication over HTTPS with the SHA-1 server hash.
  3. Compression.
  4. Velocity's modern forwarding (HMAC-SHA256), so Calcite can run behind a proxy.
- **P4.4** Configuration state: registry data, known packs, tags and feature flags.
- **P4.5** Play state: join (with the SHA-256 hashed seed), a flat world sent as simple chunks, movement, keep-alive and chat. Start with unsigned chat (offline mode, `enforce-secure-profile=false`), then add signed chat: chat sessions, message chains and acknowledgements of recently seen messages.
- **P4.6** The network layer (D33):
  - the network layer owns connections and routes packets to the region that owns each player
  - encoding, compression and encryption run off the region threads
  - each connection flushes once per tick
- **P4.7** The input log (D21): record every handled packet with the tick that handled it, and add a replay mode.
- **P4.8** Point the rig's protocol bot at both servers and compare sessions packet by packet.
- **P4.9** Hardening: size limits on every packet and every decompressed payload, connection throttling, and a fuzzer on each packet decoder.
- **P4.10** Add a fixed bot scenario to performance tracking (D34).

**Done when**

- [ ] **G4.1** A real client joins in online mode, walks around and chats, with signed chat on
- [ ] **G4.2** The login and configuration protocol suites pass
- [ ] **G4.3** A recorded session replays to identical output

## Phase 5: Chunks, storage, regions and worldgen

Make the world real: storage that vanilla can read, Folia-style regions on a lockstep tick, and terrain that matches vanilla block for block.

**How**

- **P5.1** Palette containers for block states and biomes as Calx primitives, plus chunk sections and heightmaps.
- **P5.2** Read and write the whole world folder, not just the region files, in 26.3's format only (D31):
  - `region/`, `entities/` and `poi/`
  - `level.dat` and `playerdata/`
  - advancement and stats files
  - `data/`: maps, raids, scoreboard, command storage and random sequences

  Test round trips: a vanilla world loaded and saved by Calcite must open in vanilla unchanged.
- **P5.3** Crash-safe saving: write files atomically, and autosave each region without pausing its tick.
- **P5.4** Build regions in steps: one region, then several fixed regions, then regions that split and merge as players move (D22).
  - Every tick runs the global phase, the region phase and then message exchange (D19, D20).
  - Global state such as world time, weather, entity IDs, scoreboards and the player list lives in the central world actor.
  - Run every test with one thread and with many.
- **P5.5** Chunk tickets and load levels as vanilla has them: view distance, simulation distance, entity ticking range, forced chunks, and portal and ender pearl tickets. What's loaded and ticking decides how farms behave, so this gets its own parity suite.
- **P5.6** Chunk loading and generation run as jobs off the region threads, and their completions go into the input log (D21).
- **P5.7** Lighting: sky light and block light, checked by the light probe.
- **P5.8** Load data packs at startup: the built-in pack read from the jar (D30), plus the world's own packs.
- **P5.9** Worldgen in vanilla's stage order, with a probe per stage: noise and density functions, biomes, terrain shape, surface, carvers, features, then structures. Features are decorated in the 3×3-colored order (D29), and the rig drives vanilla in the same order.
- **P5.10** The Overworld first, then the Nether and the End.
- **P5.11** Cache chunk packets: encode each chunk once and send the same bytes to every player who needs it.

**Done when**

- [ ] **G5.1** The worldgen suites pass on the seed grid in all three dimensions
- [ ] **G5.2** Worlds round-trip between vanilla and Calcite
- [ ] **G5.3** One-thread and many-thread runs of the same input log give identical results

## Phase 6: Simulation

This is the long tail, and the scoreboard is how you track it. Work outward from the tick loop, in the order systems depend on each other.

**How**

- **P6.1** Copy vanilla's order of work inside a tick exactly, mapped onto the tick phases. Turn on the agent's seeded randomness and keep the RNG tape running from here on.
- **P6.2** Blocks: neighbor updates, scheduled and random ticks and fluids, then redstone (wire, repeaters, comparators, then pistons). Use the Java-compatible collections wherever vanilla's iteration order shows, starting with redstone wire.
- **P6.3** Players and items: inventories and containers, placing and breaking blocks, crafting.
- **P6.4** Entities: movement and collision, then mobs (AI goals, pathfinding, brains), then spawning.
- **P6.5** Combat, damage, effects, enchantments, loot tables, advancements and scoreboards.
- **P6.6** Commands: a parser driven by the generated command tree, then the commands themselves. Selectors and anything else that can reach beyond a region run in the global phase (D20).
- **P6.7** The rest of the data pack system: functions, predicates, item modifiers, recipes, `/reload` and `/datapack`.
- **P6.8** The world-wide systems from the Phase 0 inventory.
- **P6.9** Build test contraptions in vanilla, save them as structure files, and use them as sim fixtures. Vanilla's data-driven GameTest framework (`/test`) may already be able to run them in vanilla, so check that before building a custom harness.

Command parsing is a pure probe, so it can run in parallel with any phase after Phase 3.

**Done when**

- [ ] **G6.1** Each suite's parity is where you want it on the scoreboard
- [ ] **G6.2** You can play an ordinary survival session on Calcite without noticing a difference

## Phase 7: Plugin host (native Calx first, then WASM)

Plugins come in two kinds, both built against one host API. Native Calx plugins are the priority and run at full speed. WASM addons add sandboxing and plugins written in other languages. The five sample addons from Phase 0 are the acceptance test.

**How**

- **P7.1** Generate both bindings and the reference docs from the one host API definition: a Calx interface for native plugins and WASM imports for addons (D41).
- **P7.2** Native Calx plugins: compile each to a shared library against the host API and load it at startup. Calx's type checker enforces region scoping at compile time.
- **P7.3** Tick budgets for native plugins: have the compiler insert cheap budget checks at loop back-edges in plugin builds, so a runaway plugin can be stopped without a sandbox.
- **P7.4** Native plugin limits and isolation: a plugin gets only the host API unless it's marked trusted, and a panic stops only that plugin's instance (D15, D25).
- **P7.5** Hot reload for native plugins: load the new library, run a state-migration hook, and swap between ticks.
- **P7.6** Per-plugin profiling from day one: tick time per plugin and per handler, always on and cheap enough to leave on.
- **P7.7** Host API versioning (D35) and plugin data storage (D36).
- **P7.8** Permissions: permission nodes, with defaults by op level. A plugin can replace the permission store.
- **P7.9** Inter-plugin APIs: a plugin can export typed functions and messages for other plugins to use.
- **P7.10** WASM second: embed Wasmtime, expose the same host API as imports, enforce budgets with the runtime's interruption, and grant capabilities per addon. Calx emits C and clang can compile C to wasm32, so a plugin that stays inside the host API can build both ways from one source.
- **P7.11** Write the plugin developer guide in `docs/plugins/` alongside the host: getting started, the plugin model, events, commands, data, testing.
- **P7.12** Port the five sample addons as native plugins, then build one of them as WASM too.

Anything performance-critical belongs in Calcite itself or in a native plugin, not in a WASM addon.

**Done when**

- [ ] **G7.1** All five sample addons run as native plugins
- [ ] **G7.2** One of them also runs as WASM, built from the same source
- [ ] **G7.3** A runaway or panicking plugin of either kind is stopped without hurting the tick
- [ ] **G7.4** Reloading a plugin keeps its state
- [ ] **G7.5** Every host API function the samples use has generated reference docs and a guide page that covers it

## Phase 8: Benchmarks and your own servers

Measure Calcite against the servers it would replace, then run it for real.

**How**

- **P8.1** Reuse the rig's bot as a swarm of 25, 50, 100 and 200 bots that walk, explore new chunks, build and fight.
- **P8.2** Run the same seed and script on Calcite, Paper, Folia and Pumpkin. Record MSPT (mean and 99th percentile), memory and CPU use per core.
- **P8.3** Profile the slowest systems and fix them, rerunning the rig after every fix.
- **P8.4** Soak test: run the bot swarm for a full day to catch memory leaks and slow drift in tick time.
- **P8.5** Operations: read vanilla's server.properties, ops, whitelist and ban files so a server folder moves over unchanged, and add the console, RCON, logs, metrics and crash reports.
- **P8.6** Move one of your own servers over, keeping backups. Because worlds round-trip, vanilla or Paper stays your fallback. Older worlds go through vanilla 26.3 first (D31).

**Done when**

- [ ] **G8.1** MSPT is recorded at every bot count for all four servers
- [ ] **G8.2** One of your own servers runs on Calcite

## Phase 9: Plugin SDK, tooling and docs site

Make Calcite the best server to write plugins for. Determinism (D21) is the secret weapon here: a plugin test can replay a real session and get the same result every time.

**How**

- **P9.1** A `calx` CLI for plugins:
  - `new` (from templates), `build` and `test`
  - `run`: a dev server that hot-reloads on save
  - a plugin manifest with dependencies on other plugins
- **P9.2** A Calx language server (diagnostics, completion, go-to-definition, hover docs from the host API), which the VS Code extension from P3.10 switches to (D65).
- **P9.3** A plugin test harness: headless Calcite, scripted bots (the rig's bot) and recorded input logs replayed against the plugin, with assertions on world state and packets.
- **P9.4** The docs website, built from the Markdown both repos have been keeping since Phase 0 (D40). Pick the site generator then. It covers the Calx guide and reference, the plugin guide, and the generated host API reference. The five samples become tutorials. This can come earlier if you want it sooner.
- **P9.5** A profiler view for the per-plugin data from P7.6.
- **P9.6** SDKs for WASM addons in other languages, Rust first, generated from the host API.
- **P9.7** Custom content without client mods: helpers for data components, item models, dialogs and data-pack registries.

**Done when**

- [ ] **G9.1** Someone new to Calcite goes from nothing to a working, tested plugin in under an hour using only the docs
- [ ] **G9.2** The language server works in VS Code on Windows and Linux
- [ ] **G9.3** The docs website is live and is rebuilt from the repos on every merge

## Moving to new Minecraft versions

New drops arrive roughly quarterly, so treat each one as a routine update rather than a project, and support one version at a time. 26.4 is expected around the end of 2026, while the early phases are still running. Stay on 26.3 until Phase 5 is done, so goldens don't change underneath work in progress.

1. Put the new jar in `oracle/jars/` and regenerate the data tables.
2. Record new goldens and diff them against the old ones. That diff shows exactly how vanilla's behavior changed. Since the jar is unobfuscated, a diff of the decompiled code between versions is readable too.
3. Run Calcite against the new goldens. Every failure is a to-do item.
4. Bump the protocol version once the suites are back where they were. Upgrade existing worlds by opening them in the new vanilla version (D31).

## Decisions

Every decision is in [`decisions.md`](decisions.md), with the date and the phase it applies from. New questions go there too.

Notes on licensing and legal questions:

- **Copying code (D59).** Copy only when it's clearly the best option and its license allows it in an MIT project, keeping the notice. GPL code can't be copied.
- MIT is one more reason not to read GPL servers. Pumpkin, Paper and Folia are GPL; Pumpkin's plugin API crates are MIT/Apache.
- Bit-exact parity means reproducing Mojang's behaviour closely, and vanilla's code is easy to read now that it's unobfuscated. Mojang's code has no license that allows copying, so Calcite is written from it as a reference, in its own structure for regions and actors. Where the bits force it, the arithmetic still follows vanilla's, in the same order. That raises the same derivative-work question every third-party server lives with. Before publishing anything, read Mojang's EULA and usage guidelines; I'm not a lawyer.
- Wasmtime's Apache 2.0 license is fine to embed in an MIT project. No other native library is vendored: zlib, lz4 and the crypto are written in Calx's runtime (D118).
- For Bedrock, Geyser's standalone proxy translates to the Java protocol, so it should work in front of Calcite unchanged. Bedrock-only accounts would need an auth plugin along the lines of Floodgate.

## Repo layout

There are two repos side by side (D38). Everything derived from your vanilla jar stays gitignored; only case inputs and hashes are committed.

```
calx/
├─ compiler/             # C++: lexer, parser, type checker, C emitter
├─ runtime/              # C: sockets, threads, queues, compression, crypto (Windows + Linux)
├─ std/                  # Calx standard library, including Java-compatible collections
├─ tests/                # small Calx programs with expected output
├─ tools/                # the VS Code extension (P3.10); later the language server
├─ bench/                # Phase 3: the tick-loop benchmark in Calx and Rust, results per commit
└─ docs/
   ├─ README.md          # docs index and page order
   ├─ CALX_SPEC.md       # designed but not yet built
   ├─ benchmarks.md      # Phase 0: the tick-loop benchmark definition
   ├─ reference/         # one page per shipped feature (normative)
   └─ guide/             # learning Calx, in reading order

calcite/
├─ src/                  # Calcite, written in Calx
├─ plugins/
│  ├─ api/               # the host API; bindings and reference docs are generated from it
│  └─ samples/           # the five sample addons
├─ oracle/
│  ├─ jars/              # gitignored: server-26.3.jar, fetched by fetch.py
│  ├─ work/              # gitignored: the data generator's working directory
│  ├─ datagen/           # runs the data generator into generated/26.3/ and converts it
│  ├─ fetch.py           # fetches and verifies the jar against versions.json (D62)
│  ├─ versions.json      # committed: each version's pinned jar URL, size and SHA-1
│  └─ vanilla-adapter/   # Java 25 harness and agent
├─ rig/
│  ├─ runner/            # Python: dispatch, goldens, diff, scoreboard
│  ├─ bot/               # protocol bot, reused as the benchmark swarm
│  ├─ differences/       # registry of deliberate differences
│  └─ PROTOCOL.md        # adapter wire format and probe signatures
├─ cases/                # committed: inputs only
├─ expected/26.3/        # committed: hash of vanilla's output per case
├─ golden/26.3/          # gitignored: full vanilla outputs
├─ generated/26.3/       # gitignored: data generator output
└─ docs/
   ├─ PLAN.md            # this file
   ├─ decisions.md       # the decision log
   ├─ global-systems.md  # Phase 0: world-wide systems and where each runs
   ├─ sketches/          # Phase 0: the tick loop, a region and a packet handler in imagined Calx
   └─ plugins/           # Phase 7: plugin developer guide
```

## Toolchain

| Tool | Version | Needed for |
| --- | --- | --- |
| Java | 25 (26.x requires it) | Vanilla adapter, data generator |
| LLVM / clang | 23 on both platforms | Calx output, the compiler itself |
| MSVC toolset and Windows SDK | Any recent | Linking with clang on Windows |
| CMake and Ninja | CMake 4, Ninja 1.13 | Building the compiler and runtime |
| Python | 3.14 | Rig runner, datagen converter |
| Rust | Stable | The Phase 3 reference benchmark only |
| Linux | Ubuntu 26.04 (WSL is fine) | Second platform from the first commit |

## Terms

The plan's working vocabulary, so it reads the same wherever you take it.

| Term | Meaning |
| --- | --- |
| Calcite | The Minecraft Java server, written in Calx |
| Calx | The language: compiled to C by a C++ compiler, then built with clang |
| Canonical order | The fixed chunk order (D29) in which both Calcite and the rig's vanilla driver decorate features |
| Central world actor | The one actor that owns global state such as world time, weather, entity IDs and scoreboards, and runs the global phase |
| Deliberate difference | A place where Calcite intentionally differs from vanilla, such as a fixed exploit, listed in the rig |
| Global phase | The part of each tick where the central world actor has exclusive access to the whole world (D20) |
| Golden | Vanilla's recorded output for one case; hashes are committed, full outputs stay local |
| Handle | A checked reference to an entity, player, chunk or block entity, used instead of a pointer (D24) |
| Host API | The functions Calcite exposes to plugins; native and WASM bindings and the reference docs are generated from it |
| Input log | The tick-indexed record of everything that enters Calcite from outside; replaying it reproduces a run exactly (D21) |
| Lockstep | Every region finishes tick N before any region starts tick N+1 (D19) |
| MSPT | Milliseconds per tick; the budget is 50 ms at 20 ticks per second |
| Native plugin | A Calx plugin compiled to a shared library and loaded at startup |
| Oracle rig | The test harness that runs the same inputs through vanilla and Calcite and compares the outputs |
| Probe | One named function both rig adapters implement, such as an RNG sequence or one generated chunk |
| Region | A group of chunks ticked by its own actor, Folia-style; regions split and merge as players move |
| RNG tape | A log of every random draw with its call site, used to find where two runs diverge |
| Scoreboard | The rig's report of passing cases per suite, and the only measure of progress |
| Trusted plugin | A native plugin you allow, in the server config, to call C through `extern` and use `unsafe` |
| WASM addon | A plugin compiled to WebAssembly and run in the embedded Wasmtime runtime |
