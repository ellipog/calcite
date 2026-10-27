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
| Calcite adapter | [`calcite-adapter/`](calcite-adapter/) | Runs probes against Calcite. A stub until Calcite has code |
| Cases | [`../cases/`](../cases/) | Committed inputs, one folder per probe |
| Expected hashes | `../expected/26.3/` | Committed: the hash of vanilla's result for every case, and the quarantine list |
| Goldens | `../golden/26.3/` | Gitignored: vanilla's full results, for `diff` |
| Differences | [`differences/`](differences/) | The registry of places Calcite deliberately differs |
| Math comparison | [`runner/mathcmp.py`](runner/mathcmp.py) | `Math` against `StrictMath` on large sweeps (`P1.5`) |

The runner needs only Python 3.10 or newer, with no packages. Run it from anywhere. Paths are relative to the repo.

## Vanilla's two configurations

At the last bit, "vanilla" depends on the JVM. On x86-64, HotSpot replaces `Math.sin`, `cos`, `tan`, `pow`, `log`, `log10`, `exp`, `cbrt` and `tanh` with intrinsics. Those differ from `StrictMath` by 1 or 2 ULP on up to 10% of inputs, so the same seed can give slightly different numbers. Matching the intrinsics would mean copying HotSpot's code, which is GPL and so can't go in an MIT project (D59). So the rig records vanilla two ways (D60):

| Configuration | JVM flags | Role |
| --- | --- | --- |
| `strict-math` | `-XX:+UnlockDiagnosticVMOptions -XX:-UseLibmIntrinsic` | **The reference.** `Math` gives exactly `StrictMath`'s results, which Calx's `std.math` can match. Hashes in `expected/26.3/` |
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

The score is passes over the cases that count: everything except differences, quarantined and unrecorded cases. The full report, with every case's outcome, goes to `build/rig/<platform>/scoreboard-<adapter>.json`. Adapter logs go to `build/rig/<platform>/logs/`.

Scoring vanilla against itself should always give 100%. If it doesn't, something isn't repeatable that the self-check missed.

### `diff`

Runs one case on an adapter and compares it with vanilla's golden: the output fields, the blob count, and for each blob the first differing byte, with a hex dump of that row. It needs the goldens from `record`, which are only on the machine that recorded them.

## Case files

Cases live in `cases/<probe>/*.json`. The format is in [`PROTOCOL.md`](PROTOCOL.md#case-files). Hand-written files cover edge cases. Generated ones (`generated.json`, `limits.json`) come from the `gen.py` beside them, which is deterministic: run it again and the file comes out the same.

```sh
py -I cases/rng/gen.py      # cases/rng/generated.json
py -I cases/nbt/gen.py      # cases/nbt/limits.json
py -I cases/math/gen.py     # cases/math, cases/strictmath and cases/mth
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

## Adding a probe

1. Specify it in [`PROTOCOL.md`](PROTOCOL.md#probes), at version 1.
2. Implement it in the vanilla adapter and list it in its `hello`.
3. Add cases under `cases/<probe>/`.
4. `record`, then `check --variants all`. Quarantine what doesn't repeat, and look at why.
5. Commit the cases and `expected/26.3/<probe>.json`.

Calcite's adapter reports the new probe as unimplemented until Calcite can run it.

## Found so far

- **Deep SNBT overflows the stack.** Vanilla's SNBT parser has no depth limit. From about depth 511 it throws `StackOverflowError`, at a depth that changes with case order and JIT tier. Quarantined, and listed as a [difference](differences/snbt-depth.md).
- **Over-long strings depend on where they're written.** A string over 65,535 bytes can't be written in the network form (the packet fails), but the file form quietly writes `""`. The `nbt` probe returns both.
- **`Math` isn't `StrictMath` on x86-64.** HotSpot's intrinsics differ from `StrictMath` by 1 ULP on 3% of `sin` and `cos` results, 9% of `pow`, 7% of `log` on (0, 1), and similar shares of `tan`, `exp`, `log10` and `cbrt`. `tanh` differs by up to 2 ULP. `mathcmp.py` measured this on 500,000 arguments per range, with the same counts on Windows and Linux. It's why the rig records [two configurations](#vanillas-two-configurations). Full table: [`CALX_SPEC.md`](https://github.com/ellipog/calx/blob/main/docs/CALX_SPEC.md#transcendental-functions).
- **With the intrinsics off, `Math` is exactly `StrictMath`.** Under `-XX:-UseLibmIntrinsic`, every function matched on all 22 million arguments.
- **Each configuration agrees with itself.** Every case gives the same bits under the interpreter, C1 and C2, in both configurations. So does `Mth`'s sine table: rounding to `f32` hides the 1-ULP differences, and all 65,536 entries equal both `(float) StrictMath.sin` and `(float) Math.sin`.
