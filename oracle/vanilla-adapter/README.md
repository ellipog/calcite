---
title: Vanilla adapter
description: The Java 25 program that runs rig probes against Mojang's 26.3 server code and reports the results.
---

# Vanilla adapter

This is the rig's source of truth (`P1.2`). It loads Mojang's server jar, boots vanilla's registries, and answers [rig protocol](../../rig/PROTOCOL.md) requests by calling vanilla's own code. Since 26.1 the jar is unobfuscated, so the probes call vanilla by its real names with no mapping step.

Nothing from the jar is committed. The build reads it from the gitignored `oracle/jars/` and unpacks into the gitignored `oracle/work/` and `build/` (D30).

## Building

You need the 26.3 server jar in `oracle/jars/server-26.3.jar` (`P1.1`) and JDK 25.

```sh
py -I build.py                         # finds JDK 25 from CALCITE_JAVA_HOME, JAVA_HOME or PATH
py -I build.py --java-home <jdk-25>    # or name it
```

The build:

1. Reads `META-INF/versions.list` and `META-INF/libraries.list` from the bundler jar.
2. Extracts the inner server jar and its 39 libraries into `oracle/work/versions/` and `oracle/work/libraries/`, checking each against the bundler's SHA-256. Files that are already there with the right hash are kept.
3. Compiles `src/` with `javac --release 25`, with warnings as errors.
4. Writes `build/adapter.json`, the command line the runner starts the adapter with.

## Running

The runner starts it from `build/adapter.json`. To start it by hand, use that file's `argv` with `oracle/work/` as the working directory, and talk to it over stdin and stdout.

- **Stdout carries only frames.** The adapter takes the real stdout before vanilla loads, and points `System.out` at stderr, so a stray print can't corrupt a frame.
- **Logs go to stderr.** [`log4j2.xml`](log4j2.xml) sends every log there, and the runner saves it.
- **Startup takes about 3 seconds**, mostly `Bootstrap.bootStrap()`. The first `text` case takes a little longer, since it builds the registry lookup.

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

## Rules for probes

- **A probe is a pure function of its case.** No clock, no unseeded randomness, no state carried between cases, except caches that don't change results (like the registry lookup).
- **Malformed cases throw `CaseError`.** `Args` reads every field and throws `CaseError` for anything missing or mistyped. So any other exception came from the game, and becomes a rejection result instead of an error.
- **Bits, not text.** Floats go out as raw bits in a blob, never formatted.

## Randomness in later probes

Vanilla isn't repeatable run to run. Each level's `random` is seeded from `RandomSupport.generateUniqueSeed()`, which mixes in `System.nanoTime()`, and the entity ID counter is a static `AtomicInteger`. The Phase 1 probes don't touch either. Probes that run a level (random ticks, spawning, mob AI) will need the Java agent from the plan's layout to pin both, so the self-check can pass.
