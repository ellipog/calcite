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

[`PacketCheck`](src/calcite/rig/vanilla/PacketCheck.java) is a second entry point, not a probe ([D145](../../docs/decisions.md)). Calcite's network tests write every packet their clients get to `build/packets/`, and [`check_packets.py`](check_packets.py) runs `PacketCheck` on them with the adapter's command line. It reads each packet with the codec vanilla's client reads it with: `StatusProtocols`, `LoginProtocols`, `ConfigurationProtocols` or `GameProtocols`, bound to the vanilla data pack's registries. A packet passes if it decodes, leaves no bytes over and encodes back to the same bytes. `set_time` and `update_tags` are compared as values instead, since their maps are keyed by identity-hashed objects and vanilla's order changes from run to run. It prints a line for each kind of packet and exits with 1 if any failed. `src/test/run.py` runs it at its end.

## Layout

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
| `PacketCheck.java` | Vanilla reading Calcite's packets, run by `check_packets.py` |
| `RegistriesProbe.java` | `registries`: the vanilla data pack's registries and tags, loaded once as `WorldLoader.load` loads them |

## Rules for probes

- **A probe is a pure function of its case.** No clock, no unseeded randomness, no state carried between cases, except caches that don't change results (like the registry lookup).
- **Malformed cases throw `CaseError`.** `Args` reads every field and throws `CaseError` for anything missing or mistyped. So any other exception came from the game, and becomes a rejection result instead of an error.
- **Bits, not text.** Floats go out as raw bits in a blob, never formatted.

## Randomness in later probes

Vanilla isn't repeatable run to run. Each level's `random` is seeded from `RandomSupport.generateUniqueSeed()`, which mixes in `System.nanoTime()`, and the entity ID counter is a static `AtomicInteger`. The Phase 1 probes don't touch either. Probes that run a level (random ticks, spawning, mob AI) will need the Java agent from the plan's layout to pin both, so the self-check can pass.
