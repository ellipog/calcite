---
title: jfr fails as it does on a JVM without the Flight Recorder
kind: platform
cases:
  - session:world-commands/jfr-stop/system_chat
---

# jfr fails as it does on a JVM without the Flight Recorder

**Vanilla:** `JfrCommand` asks `JvmProfiler.INSTANCE`, which is `JfrProfiler` on a JVM that has the Flight Recorder, as the rig's JDK does. There, `jfr start` records the JVM's events into `debug/` and says `commands.jfr.started`, and `jfr stop` with nothing recording fails with `commands.jfr.dump.failed` and `Not currently profiling`. On a JVM without it, `INSTANCE` is `NoOpProfiler`: `jfr start` logs `Attempted to start Flight Recorder, but it's not supported on this JVM` and fails with `commands.jfr.start.failed`, and `jfr stop` fails with `commands.jfr.dump.failed` and `Attempted to stop Flight Recorder, but it's not supported on this JVM`.

**Calcite:** isn't a JVM, so it has no Flight Recorder and answers as `NoOpProfiler` does ([D962](../../docs/decisions.md)). `perf` and `debug` record what Calcite can.

**Why:** the Flight Recorder records the JVM itself. A server that doesn't run on one can't make its recordings.
