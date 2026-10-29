---
title: Oracle rig
description: How Calcite is checked against vanilla, bit for bit, and how to run, extend and read the rig.
---

# Oracle rig

The rig runs the same inputs through vanilla and through Calcite and compares the results bit for bit (Phase 1). Vanilla's results are recorded once, as goldens, and their hashes are committed. Calcite is scored against those hashes on every change.

| Part | Where | What it does |
| --- | --- | --- |
| Protocol | [`PROTOCOL.md`](PROTOCOL.md) | The wire format between the runner and an adapter, and every probe's signature |
| Runner | [`runner/`](runner/) | Python: loads cases, runs adapters, records, self-checks, scores |
| Vanilla adapter | [`../oracle/vanilla-adapter/`](../oracle/vanilla-adapter/) | Java 25: runs probes against Mojang's server code |
| Calcite adapter | [`calcite-adapter/`](calcite-adapter/) | Runs probes against Calcite's own code, built from [`../src/rig/`](../src/rig/) with calx |
| Cases | [`../cases/`](../cases/) | Committed inputs, one folder per probe |
| Expected hashes | `../expected/26.3/` | Committed: the hash of vanilla's result for every case, and the quarantine list |
| Goldens | `../golden/26.3/` | Gitignored: vanilla's full results, for `diff` |
| Differences | [`differences/`](differences/) | The registry of places Calcite deliberately differs |
| Math comparison | [`runner/mathcmp.py`](runner/mathcmp.py) | `Math` against `StrictMath` on large sweeps (`P1.5`) |
| Protocol suites | [`runner/sessions.py`](runner/sessions.py) | The protocol bot against vanilla and Calcite, packet by packet (`P4.8`) |
| A real client | [`runner/realclient.py`](runner/realclient.py) | Mojang's 26.3 client joins Calcite, walks and chats (`G4.1`) |

The runner needs only Python 3.10 or newer, with no packages. Run it from anywhere. Paths are relative to the repo.

## Vanilla's two configurations

At the last bit, "vanilla" depends on the JVM. On x86-64, HotSpot replaces `Math.sin`, `cos`, `tan`, `pow`, `log`, `log10`, `exp`, `cbrt` and `tanh` with intrinsics. Those differ from `StrictMath` by 1 or 2 ULP on up to 10% of inputs, so the same seed can give slightly different numbers. Matching the intrinsics would mean copying HotSpot's code, which is GPL and so can't go in an MIT project (D59). So the rig records vanilla two ways (D60):

| Configuration | JVM flags | Role |
| --- | --- | --- |
| `strict-math` | `-XX:+UnlockDiagnosticVMOptions -XX:-UseLibmIntrinsic` | **The reference.** `Math` gives exactly `StrictMath`'s results, which Calx's `std.java.math` can match. Hashes in `expected/26.3/` |
| `intrinsics` | HotSpot's defaults | What most servers run. Hashes in `expected/26.3/intrinsics/` |

Calcite is scored against `strict-math`. The scoreboard also says how many cases Calcite would pass against `intrinsics`, and `list` shows how many cases come out differently in the two. That gap is the measured cost of not copying. In 26.3 it shows up in `math` (33 cases), `rng` (17, every one using `nextGaussian`, which calls `Math.log`) and `mth` (2: `Mth.atan2`, whose table is built with `Math.cos`).

Both configurations repeat bit for bit under every self-check variant, on Windows (Temurin 25.0.5) and on Linux (Ubuntu's OpenJDK 25.0.4), and the two platforms give the same hashes.

## Commands

```sh
py -I rig/runner/rig.py list                     # cases per probe, recorded, quarantined
py -I rig/runner/rig.py record --config all      # run vanilla; write goldens and expected hashes
py -I rig/runner/rig.py check --variants all     # the self-check
py -I rig/runner/rig.py score                    # score Calcite
py -I rig/runner/rig.py diff rng legacy-seed-0   # one case, Calcite's result against vanilla's golden
py -I rig/runner/mathcmp.py                      # Math against StrictMath, 500,000 arguments per range
```

Every command takes `--probe NAME` (repeatable) to limit it to some probes. `record` and `check` take `--config strict-math` (the default), `intrinsics` or `all`. On Linux, use `python3` for `py`.

The vanilla adapter builds into `oracle/vanilla-adapter/build/<platform>/`, and the runner's logs and reports go to `build/rig/<platform>/`. So one checkout can be run from Windows and from WSL.

### `record`

Starts the vanilla adapter (build it first with `py -I oracle/vanilla-adapter/build.py`), runs every case, and writes:

- `golden/26.3/<probe>.jsonl`: every full result, one per line, with blobs in base64
- `expected/26.3/<probe>.json`: each case's hash, the configuration, and the adapter's `about` (JVM, flags and OS)

Other configurations write into a subfolder named for them, such as `expected/26.3/intrinsics/`.

Quarantined cases get a golden but no hash: they aren't repeatable, so a hash would change on every record.

It reports how many hashes are new, changed and removed, and names the changed cases. For a game update, that list is the behavior change. If any case comes back `error` or `unimplemented`, that probe isn't written at all, since a case vanilla can't run is a broken case.

### `check`: the self-check

Runs vanilla again and compares with its own expected hashes (`P1.3`, `P1.4`). A case that doesn't repeat can't be used to judge Calcite. `--variants` picks what changes between runs:

| Variant | What changes |
| --- | --- |
| `default` | Nothing. Catches anything that depends on time or the process |
| `shuffled` | Case order, so no case depends on the one before |
| `twice` | Every case runs twice in one process, comparing the second, which catches state carried between cases |
| `interpreter` | `-Xint`: no JIT at all |
| `c1` | Only the C1 compiler |
| `c2` | Only C2, compiling early |
| `serial-1cpu` | Serial GC on one CPU |
| `parallel-8cpu` | Parallel GC on eight CPUs |

With `--quarantine`, the cases that didn't repeat are added to `expected/26.3/quarantine.json`, with what varied. Quarantined cases aren't scored. Quarantine a case only after reading why it varies; if Calcite should do something definite instead, add a [difference](differences/README.md) too.

### `score`

Runs an adapter (`--adapter calcite`, the default, or `vanilla`, or a path to an `adapter.json`) on every case, and prints the scoreboard:

| Outcome | Meaning |
| --- | --- |
| Pass | Same hash as vanilla |
| Fail | A different hash, and no difference covers it |
| Difference | A different hash, covered by an entry in `differences/` |
| Unimplemented | The adapter doesn't have this probe, or this part of it, yet |
| Error | The adapter failed or crashed, or the case's probe version doesn't match |
| Quarantined | Vanilla itself isn't repeatable here, so it isn't run |
| Unrecorded | No expected hash yet. Run `record` |

The score is passes over the cases that count: everything except differences, quarantined and unrecorded cases. `ping` tests the rig itself, so its row is marked `(rig)` and it isn't part of the total. The full report, with every case's outcome, goes to `build/rig/<platform>/scoreboard-<adapter>.json`. Adapter logs go to `build/rig/<platform>/logs/`.

With `--strict`, it exits with status 1 if any case fails or errors, as CI runs it. Unimplemented cases don't count.

Scoring vanilla against itself should always give 100%. If it doesn't, something isn't repeatable that the self-check missed.

### `diff`

Runs one case on an adapter and compares it with vanilla's golden: the output fields, the blob count, and for each blob the first differing byte, with a hex dump of that row. It needs the goldens from `record`, which are only on the machine that recorded them.

## Case files

Cases live in `cases/<probe>/*.json`. The format is in [`PROTOCOL.md`](PROTOCOL.md#case-files). Hand-written files cover edge cases. Generated ones (`generated.json`, `limits.json`) come from the `gen.py` beside them, which is deterministic: run it again and the file comes out the same.

```sh
py -I cases/rng/gen.py      # cases/rng/generated.json
py -I cases/nbt/gen.py      # cases/nbt/limits.json
py -I cases/math/gen.py     # cases/math, cases/strictmath and cases/mth
py -I cases/collections/gen.py   # cases/collections/generated.json
py -I cases/registries/gen.py    # cases/registries/configuration.json
py -I cases/palette/gen.py       # cases/palette/generated.json
py -I cases/chunk/gen.py         # cases/chunk/generated.json
py -I cases/region/gen.py        # cases/region/generated.json
py -I cases/chunk_nbt/gen.py     # cases/chunk_nbt/generated.json
```

### Blobs in case files

Each entry in a case's `"blobs"` is one part, or a list of parts joined in order. The runner expands them to bytes, so adapters only see bytes.

| Part | Bytes |
| --- | --- |
| `"AAEC"` | Base64 |
| `{"hex": ["00ff", "10 20"]}` | Hex, spaces allowed |
| `{"f64": ["1.5", "-0", "inf", "nan", "0x1p-1074"]}` | `f64`s, big-endian. Decimal or hex-float strings |
| `{"f32": [...]}` | `f32`s, rounded from those values |
| `{"f64_bits": ["7ff8000000000001"]}`, `{"f32_bits": [...]}` | Exact bit patterns in hex, such as NaN payloads |
| `{"i32": [1, -2]}`, `{"i64": ["-9223372036854775808"]}` | Integers, big-endian |
| `{"gen": "f64_bits", "seed": "1", "count": 1000}` | `count` random `f64` bit patterns: every NaN, infinity and subnormal included |
| `{"gen": "f32_bits", ...}` | The same for `f32` |
| `{"gen": "f64_range", "seed": "1", "count": 1000, "min": "-10", "max": "10"}` | `count` values in `[min, max)` |
| `{"gen": "f64_range", ..., "ranges": [["0", "100"], ["-10", "10"]]}` | `count` tuples, one value from each range, for two-argument functions |
| `{"gen": "f32_range", ...}` | The same, rounded to `f32` |
| `{"gen": "i32_range", "seed": "1", "count": 3000, "min": "-30000000", "max": "30000000"}` | `count` integers in `[min, max]` |

The generators use SplitMix64 from the given seed. A range value is `min + (max - min) * u`, with `u` the top 53 bits of the next output times 2^-53, computed in `f64`. `i32_range` takes the next output modulo the range's size. These definitions are fixed: changing one changes every case that uses it.

## The Calcite adapter

`calcite-adapter/adapter.json` starts [`launch.py`](calcite-adapter/launch.py), which builds [`src/rig/adapter.calx`](../src/rig/adapter.calx) with `calx build --release` and runs it (D87). The build takes under half a second, and about 50 ms when nothing changed, so it happens on every start. The binary goes to `build/rig/<platform>/`.

- calx is found from the `CALX` environment variable, then `PATH`, then `../calx/build/compiler/<platform>/` beside this repository. calx finds clang itself.
- `CALCITE_DEBUG=1` builds the adapter in debug mode, where it checks that it frees everything it allocates and exits with status 102 if not.
- It implements `ping`, `rng`, `collections`, `registries`, `palette`, `chunk`, `region` and `chunk_nbt`, which pass 100% on Windows and Linux, and `nbt` for binary input, whose 32 cases pass; its SNBT cases wait for the SNBT parser. Every other probe reports `unimplemented` until Calcite has the code behind it.
- It runs from the repository's root. `registries`, `chunk` and `chunk_nbt` read the vanilla data pack from the pinned jar in `oracle/jars/`, which [`fetch.py`](../oracle/fetch.py) gets.

The adapter's parts are in [`src/`](../src/README.md): the frames in `rig.frame`, their JSON in `json.tree`, and one module per probe.

## Adding a probe

1. Specify it in [`PROTOCOL.md`](PROTOCOL.md#probes), at version 1.
2. Implement it in the vanilla adapter and list it in its `hello`.
3. Add cases under `cases/<probe>/`.
4. `record`, then `check --variants all`. Quarantine what doesn't repeat, and look at why.
5. Commit the cases and `expected/26.3/<probe>.json`.

Calcite's adapter reports the new probe as unimplemented until Calcite can run it. To implement it there, add a module under `src/rig/` and list the probe in `hello` in `src/rig/adapter.calx`.

## Protocol suites

The probes check Calcite's parts. The protocol suites check the server as a client sees it (`P4.8`): the [protocol bot](../src/rig/session.calx), one player made from Calcite's protocol code, runs the same scenarios against vanilla 26.3 and against Calcite, writes down every packet each sends, and the two sessions are compared packet by packet.

```sh
py -I rig/runner/sessions.py                       # both configurations, every scenario
py -I rig/runner/sessions.py --config compressed --scenario join
py -I rig/runner/sessions.py --compare-only --show 0
```

[`sessions.py`](runner/sessions.py) builds Calcite and the bot with `calx build --release`, then, for each configuration, starts vanilla in a fresh folder under `build/rig/sessions/CONFIG/vanilla/`, runs the bot once for each scenario, and stops it; then the same for Calcite. Both servers get the same `server.properties`: offline, a flat world named by its seed with no structures, peaceful, a view of 4 chunks, and the default `white-list=true`, with a `whitelist.json` that lists the bot. The configurations are `compressed`, at the default threshold, and `uncompressed`, at `-1`. Vanilla runs from the jar's own classes, which [`build.py`](../oracle/vanilla-adapter/build.py) unpacks, with Mojang's EULA accepted in its scratch folder only; it needs the vanilla adapter built, and never runs in CI. What vanilla draws at random that Calcite doesn't yet, the spawn's spread, is set from its console as it starts. `--compare-only` compares what the last run recorded.

The scenarios:

| Scenario | What the bot does |
| --- | --- |
| `status` | The server list's query, then a ping |
| `outdated` | A login from a client one protocol version behind |
| `bad-name` | A login with a name no vanilla client sends |
| `stranger` | A login from a player the whitelist doesn't list |
| `join` | A login, configuration knowing vanilla's core pack, then play: it loads its view, walks into the next chunk a block a tick, says something, types a command no server has, and leaves |

The bot cuts its session into steps, `login`, `configuration`, `join`, `walk`, `chat`, `command` and `leave`, and ends a step once the server has sent nothing for a second but its clock. The vanilla adapter's [`SessionDump`](../oracle/vanilla-adapter/README.md#reading-sessions) reads both servers' packets with vanilla's own codecs, so the bot's reading agrees with neither server on a mistake, and [`sessiondiff.py`](runner/sessiondiff.py) lines each step's packets up by kind, as `diff` lines up text. Two lined-up packets match when their values are the same tree and their bytes are the same. What depends on timing rather than on the server is taken out first:

- **The clock.** `set_time` and keep-alives come every so many ticks or milliseconds, so each side's are compared once a step, by their values with the times taken out.
- **Chunks.** Vanilla sends the chunks that are ready, nearest first, from worker threads, so its batches and their order change from run to run. A step's chunks are compared as a set, by position.
- **Unfixed bytes.** Where vanilla itself writes the same value in other bytes from run to run, only the values must match: tags, `set_time`, and a chunk's heightmaps, which vanilla keeps in a `HashMap` keyed by an enum, so they come out in another order each run.
- **What vanilla draws.** The session ID a server draws as it starts, which `login_finished` carries, and the time on a chat message without a signature are left out of both sides.

Each packet that differs is keyed `session:SCENARIO/STEP/KIND`, such as `session:join/configuration/custom_payload`, which a file in [`differences/`](differences/) can cover, with `*` for any scenario. The status scenario and the login and configuration steps are the suites the Phase 4 gate needs (`G4.2`): `sessions.py` exits with 1 if one of them has a difference no file covers. Play is reported, not gated, until Calcite sends what vanilla sends there. A run of every scenario also notes a difference file whose session cases covered nothing, as `score` does.

Status, login and configuration pass in both configurations, with the server's [brand](differences/brand.md) the one deliberate difference. Play matches in its positions, its chat, the unknown command's answer and nearly every chunk, and differs where Calcite has yet to do what vanilla does, each with the phase that brings it:

- vanilla's three dimensions, where Calcite has one (Phase 5)
- the 25 chunks within 2 of the spawn, which vanilla loads as it starts, saves and drops. Their blocks are the same, but vanilla's sections list their blocks in the order they first come, bedrock first, as a section read back from a region file does, where a new section, Calcite's or vanilla's, lists air first. Every other chunk matches byte for byte. Matching these needs the world on disk (Phase 5, P5.2)
- recipes, the command tree, the player's entity data, advancements, health, experience and attributes (Phase 6)

## A real client

```sh
py -I rig/runner/realclient.py
py -I rig/runner/realclient.py --message "anyone here" --keep-open 30
py -I rig/runner/realclient.py --online Ellipog     # online, with signed chat, as your own account
```

Everything else here plays the client's side with Calcite's own code. [`realclient.py`](runner/realclient.py) runs the game itself instead: Mojang's 26.3 client, from the files of a launcher that has run 26.3 once (the official launcher, the Modrinth App or Prism Launcher), each checked against the SHA-1 in 26.3's version file, with JDK 25 ([D162](../docs/decisions.md)). It starts Calcite's release build, `build/server/calcite.exe`, in a fresh folder under `build/rig/realclient/`, and the client in a game folder beside it, with its sound off and the first-run screens skipped, joining with `--quickPlayMultiplayer`. On Windows, [`realclient_keys.ps1`](runner/realclient_keys.ps1) then plays it a little: the debug screen on, a screenshot, a walk of about 11 blocks and a jump, a screenshot, a chat message and a last screenshot. It sends a key only while the client's window is in front and stops if it isn't, so nothing is typed into another window; it does take the focus for about 10 seconds. It passes if Calcite logs the join and the message, the client gets the message back, nobody is disconnected before the client is stopped, and the client logs no error but the ones on its download threads, which Mojang's services and Realms give a client with no account. The screenshots show the coordinates before and after the walk. It needs a desktop and a launcher's files, so it isn't in CI.

Without `--online`, the server is offline and the client is `RealClient`, with no account, so its chat isn't signed. With `--online NAME`, the server is in online mode, and the client plays as the Modrinth App's account `NAME`, which must be your own. Its session is renewed as the launcher renews it, from the launcher's Microsoft refresh token through Xbox Live to a Minecraft access token, and kept in memory: no token is printed or written, and nothing is written back to the launcher. The client then fetches its chat key from Mojang and signs what it says, and the message must come through signed on both sides: Calcite logs it without `[Not Secure]`, and so does the client. That is `G4.1`. What the client checks of signed chat, `ChatCheck` also checks after every test run, as vanilla's client checks it (see [the adapter](../oracle/vanilla-adapter/README.md#checking-calcites-packets)).

## Tests and CI

```sh
py -I -m unittest discover -s rig/runner/tests -v
```

The runner's tests use only the standard library and never need the vanilla jar. They cover:

- frames and the result hash
- blob parts and generators, including SplitMix64's published outputs
- that every `gen.py` reproduces its committed case file exactly
- that every case has an expected hash
- the differences registry and the store
- a ping-only test adapter, end to end through `score`
- the protocol suites' comparison, on sessions made up for it

The data converter and the jar fetch step have their own tests, which don't need the jar either ([`oracle/datagen/`](../oracle/datagen/README.md#tests)):

```sh
py -I -m unittest discover -s oracle/datagen/tests -v
```

CI ([`.github/workflows/rig.yml`](../.github/workflows/rig.yml)) runs both on Windows and Linux, with the oldest supported Python (3.10) and the newest. A second job checks out calx beside Calcite, builds it, runs Calcite's Calx tests (`py -I src/test/run.py`), fetches the pinned server jar, which the `registries` probe reads and which it caches, and scores Calcite against the committed hashes with `--strict` (`P1.9`).

## Found so far

- **Deep SNBT overflows the stack.** Vanilla's SNBT parser has no depth limit. From about depth 511 it throws `StackOverflowError`, at a depth that changes with case order and JIT tier. Quarantined, and listed as a [difference](differences/snbt-depth.md).
- **Over-long strings depend on where they're written.** A string over 65,535 bytes can't be written in the network form (the packet fails), but the file form quietly writes `""`. The `nbt` probe returns both.
- **`Math` isn't `StrictMath` on x86-64.** HotSpot's intrinsics differ from `StrictMath` by 1 ULP on 3% of `sin` and `cos` results, 9% of `pow`, 7% of `log` on (0, 1), and similar shares of `tan`, `exp`, `log10` and `cbrt`. `tanh` differs by up to 2 ULP. `mathcmp.py` measured this on 500,000 arguments per range, with the same counts on Windows and Linux. It's why the rig records [two configurations](#vanillas-two-configurations). Full table: [`CALX_SPEC.md`](https://github.com/ellipog/calx/blob/main/docs/CALX_SPEC.md#transcendental-functions).
- **With the intrinsics off, `Math` is exactly `StrictMath`.** Under `-XX:-UseLibmIntrinsic`, every function matched on all 22 million arguments.
- **Each configuration agrees with itself.** Every case gives the same bits under the interpreter, C1 and C2, in both configurations. So does `Mth`'s sine table: rounding to `f32` hides the 1-ULP differences, and all 65,536 entries equal both `(float) StrictMath.sin` and `(float) Math.sin`.
- **Two float constants in the decompiled source are wrong.** `XoroshiroRandomSource` shows `DOUBLE_UNIT = 1.110223E-16F` and multiplies by that float literal, which would make `nextDouble` inexact. The bytecode holds the double 2^-53 (`1.1102230246251565E-16`), so the decompiler printed a double as a float. Calcite's sources read their constants from `javap`, not the decompiler (D86).
- **Block state IDs are arithmetic.** Each block's states take consecutive IDs, in block registry order, and a state's offset within its block is the mixed-radix number of its property values, with properties in name order and the last changing fastest. The data generator's report lists properties in a different order (its JSON writer puts `type` first), so the [converter](../oracle/datagen/README.md#blocksjson) sorts them itself. All 35,723 states and 1,286 blocks match the `block_state` probe.
- **The block state parser is lenient in places.** It accepts a trailing comma (`oak_stairs[facing=east,]`), a leading zero or plus sign on a number (`note=07`, `note=+7`), and spaces around `=` and `,`. It stops at the first character it can't use, without complaint (`stone trailing` parses as stone). Values are case-sensitive (`TRUE` is rejected), and `Stone` is read as an empty name.
- **The block state NBT reader never fails.** An unknown or malformed block name reads as air, and an unknown property, a value of the wrong type or a value out of range is skipped, leaving the default. 26.3 stores states as `{id, properties}`; the old `{Name, Properties}` form reads as air.
- **Registry IDs and tags come out of the data pack exactly as vanilla builds them.** All 129 `registries` cases match: the 32 synchronized registries' entries in vanilla's order, and the tags of every registry the server sends, 773 in all, with their entries in vanilla's order. Entries of a data-driven registry take IDs in the order of their files' identifiers, which vanilla sorts by path and then namespace, and a tag's tags go in where they're listed, each entry once.
- **Calx's Java-ordered tables iterate exactly as Java's do.** `JavaHashMap`, `LinkedMap`, `SortedMap`, `OpenHashMap`, their sets, `PriorityQueue` and `Deque` give the same results and the same order as `HashMap`, `LinkedHashMap`, `TreeMap`, fastutil's open tables, `PriorityQueue` and `ArrayDeque` in all 180 `collections` cases. Those cases include keys whose hashes all collide, so `HashMap`'s bins turn into trees, fastutil tables that shrink and `trim`, and removal through a priority queue's iterator.
- **Paletted containers keep what nothing refers to, and the bits nothing uses.** A palette keeps an entry after the last value that was it is overwritten, until the palette is full, and the resize then re-adds only the values that are there, in index order, so the order a client sees depends on the whole history of sets. `pack` re-lists them in the order they first appear, in the bits a palette of that size takes on disk, which is 9 for 300 block states, where memory takes 16. `unpack` keeps a palette's longs as they are, the bits above each long's last value too, and sends them on; past the lists, it turns indices into IDs and those bits go. `fill` spreads a value by doubling, which leaves the low bits of one more copy in those bits. An empty palette, or a value indexing past the palette's end, loads, and fails only when it's read. All 129 `palette` cases match std.palette ([D163](../docs/decisions.md)).
- **Which heightmaps count a block is data in 26.3.** The two `OCEAN_FLOOR` heightmaps and `MOTION_BLOCKING` count the blocks in the tag `blocks_motion_in_heightmap`, and `MOTION_BLOCKING_NO_LEAVES` those in `blocks_motion_in_heightmap_no_leaves`, both of which the data pack builds from `blocks_motion` and `leaves`; the motion ones also count every state with a fluid, and the surface ones every state that isn't air. All 13 `chunk` cases match, from one section high to 254: the heightmaps' longs, the four counts of every section, the sections' bytes and the highest section, through thousands of random sets of 42 states of every kind and then of 600 states at random. Setting a block in the world and in generation aren't the same: `LevelChunk.setBlockState` changes nothing for air (any of the three) into a section of only air, or for the state already there, and keeps four heightmaps, where `ProtoChunk`'s skips only `minecraft:air` and keeps the heightmaps its status names. `primeHeightmaps` passes over `minecraft:air` alone, but cave and void air count in no heightmap, so they make no difference.
- **The whitelist is on by default.** A new 26.3 server has `white-list=true` and an empty `whitelist.json`, so it lets no one in until someone is listed or made an op. The protocol suites' `stranger` found it: Calcite let the stranger in, where vanilla told them `multiplayer.disconnect.not_whitelisted`.
- **Region files come out the same, whole or broken.** All 5 `region` cases match byte for byte, every byte of the files but the clock's times: chunks in the first free sectors that fit, moved past the end when they grow while their old sectors are still taken, cleared, a chunk of 255 sectors kept inside and one of 256 put in a file of its own, every compression with the edges of each format, and 34 broken streams. A damaged header's bad places are dropped as the file opens, but two chunks may still share sectors, and freeing one's frees the other's, so the next write can go over it; Calcite does the same. A file shorter than a sector is padded when it's closed, even if nothing was written. Vanilla prints a chunk's position as `[3, 4]`, and its line for an oversized chunk says `(1048581 bytes} to external file`, with the brace.
- **A chunk reads whatever it can, and throws what it can't as late as it can.** All 265 `chunk_nbt` cases match: every line logged, every exception and its message, and every byte written. A field of the wrong type takes its default, a palette entry that isn't a block or a biome becomes air or plains, and a list of ticks keeps the ticks that read, each problem logged with the list's errors joined last first. Ticks outside the chunk are dropped, and the upgrade data's ticks naming nothing tick air or the empty fluid, without a line. What can't be read throws: a container without a palette or whose data doesn't fit it (`ChunkReadException`, logged first), light that isn't 2,048 bytes, even in a section outside the world, an empty palette (`IllegalStateException`), and a value past its palette's end (`MissingPaletteEntryException`). That last is thrown at once for a global palette, when the section counts its blocks for an indexed one, the first value in the order of a fastutil map of the values, and only when the chunk is saved for biomes, so a chunk with such biomes loads and can't be saved. Sections stay in the order they're saved, repeats and all, and `yPos` is written as the world's lowest section, whatever was read.
- **A chunk's heightmaps come in another order each run.** Vanilla collects them into a `HashMap` keyed by an enum, which hashes by identity, so the same chunk is written in other bytes from one run to the next. The client reads them into an `EnumMap`, so the order means nothing, and the suites compare a chunk by its value.
- **A ban that has ended throws once.** `canPlayerLogin` asks the ban list whether it holds the player, which an ended ban still answers yes, then gets the ban, which first drops every ended one and so returns null, and reads its reason from that. The login fails with a `NullPointerException`, and the next finds no ban. In Calcite a ban that has ended is no ban.
