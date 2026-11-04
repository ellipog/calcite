---
title: Recording and replay
description: Record everything a server is handed, and play it back later to see a bug again, or that a fix took it away.
---

# Recording and replay

Calcite can record everything that comes into the server from outside, and play it back. A bug a player found can be replayed at the same tick, with the same packets, as often as you like, and replayed again with a fix to see that it's gone.

## Record

In `calcite.properties`:

```properties
record-inputs=true
```

Each start then writes a new input log in `recordings/`, named for the day: `2026-10-28-1.inputs`, then `-2` and on. It holds what the network handed the server and when, each tick, the clock, the random bytes it drew, Mojang's answers, each line typed into the console, and what the server read of the world's files, in the order the server asked for them, with a hash of each packet it sent and each line it logged.

A thread of its own writes the log after each turn of the loop, so the tick never waits for the disk. Recording costs about a microsecond for each 7 KB chunk sent, to hash it; with it off, it costs nothing.

The log holds what players sent, and the server's private key. Keep it to yourself.

## Replay

Start the server in the same folder with the log:

```sh
./calcite --replay recordings/2026-10-28-1.inputs
```

It runs with no network, handed what the log holds wherever it would have asked the world outside, and checks that it sends and logs what it did:

```text
Replayed recordings/2026-10-28-1.inputs: 55 ticks, 8 packets and lines compared, 0 different
```

A replay that goes another way stops at the first difference and says where, such as `at tick 5, connection 2 was sent packet 0x02 of 40 bytes, where the recording sent connection 2 packet 0x03 of 3 bytes`.

The files the server reads as it starts aren't in the log, so replay with the same settings and world. A replay writes nothing to the world and logs to the console alone.

## Why it works

The server's tick is deterministic: given the same inputs, in the same order, it does the same thing, on one thread or many. Everything from outside the server comes through one place, which the log records and a replay stands in for. Every network test in Calcite's own suite records its scenario and replays it, so each path the tests take is checked to replay exactly.
