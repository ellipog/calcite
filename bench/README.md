---
title: Bot benchmark
description: How Calcite's server is timed with 100 bot players joining, walking and chatting, how to run it, and the results per commit.
---

# Bot benchmark

D34 tracks performance per commit, from the tick-loop benchmark in Phase 3 to a fixed bot scenario from Phase 4. This is that scenario (P4.10, [D154](../docs/decisions.md)): the real server, its release build, with players on it.

```sh
py -I bench/run.py                       # 5 runs of the scenario, and the change from what's recorded
py -I bench/run.py --record              # the same, written to bench/results/bots-<platform>.json
py -I bench/run.py --runs 1 --bots 20 --seconds 20     # a quick look, not recorded
```

On Linux, use `python3` for `py`. The runner builds the server and the bots with calx into `build/bench/<platform>/`, then runs each in `build/bench/<platform>/world/`, a fresh start each time. It needs nothing but Python.

## The scenario

- **The server** is the release build, in offline mode, with vanilla's compression threshold of 256, and view and simulation distance 10, so a player has 473 chunks in view. `max-players` is 1000.
- **100 bots join**, 20 a second, over TCP on 127.0.0.1. Each does what a client must to stay: logs in, finishes configuration, accepts its teleport, acknowledges each chunk batch, answers keep-alives and ends a tick every 50 ms.
- **Once a bot has every chunk of its view**, it walks at walking speed, 0.21585 blocks a tick, on a heading of its own: its index times the golden angle. So the players spread out, and the server sends each a new row of chunks every few seconds, the whole run.
- **Each bot chats every 10 seconds**, starting at a second of its own, and every message goes to all 100.
- **The run lasts 45 seconds**, then the server is told `stop`.

The bots are [`src/rig/swarm.calx`](../src/rig/swarm.calx), on one thread of their own process. They're made from Calcite's own protocol code; the format is checked elsewhere, by the network tests and vanilla's codecs ([D145](../docs/decisions.md)).

## What's measured

| Measure | What it is |
| --- | --- |
| MSPT, mean, p99 and max | The server thread's work for each tick and what it handled since the one before, as the console's bar counts it, over the steady part: from 2 seconds after the last bot had its chunks to the end |
| TPS | Ticks a second over the steady part |
| MSPT while joining | The same, from the first bot's connection to the last's last spawn chunk |
| Join to all chunks | Each bot's time from connecting to having every chunk of its view |
| CPU time | The server process's, on every thread, from start to end |
| Peak memory | The server's peak working set on Windows, and its peak resident set on Linux |
| Chunks sent, bytes to the bots | What the bots received, which only changes with the protocol |

The tick times come from the server itself: `--tick-times FILE` writes each tick's start and work as it ends. The rest come from the system and the bots. Each number is the median of the runs. A run is a fresh process, after one start that isn't measured, so a new build has made its boot cache first.

A later run prints each number beside the recorded one, and names any that's more than 5% worse, which D34 says to look into before more work lands. The numbers come from one machine, since CI runners are too noisy to compare.

## Results

On the reference machine, an i9-13900K, the medians of 5 runs, recorded in [`results/`](results/) with the commit, the Calx compiler's commit and the machine. Linux is Ubuntu in WSL 2 on the same machine.

| Measure | Windows 11 | Linux |
| --- | --- | --- |
| MSPT, mean | 0.508 ms | 0.459 ms |
| MSPT, p99 | 1.787 ms | 1.237 ms |
| MSPT, max | 2.085 ms | 2.176 ms |
| TPS | 20.01 | 20.00 |
| MSPT while joining, mean | 1.099 ms | 1.495 ms |
| MSPT while joining, max | 2.529 ms | 3.496 ms |
| Join to all chunks, median | 1097 ms | 1098 ms |
| Join to all chunks, max | 1116 ms | 1101 ms |
| CPU time | 2.98 s | 2.40 s |
| Peak memory | 46.9 MiB | 44.7 MiB |
| Chunks sent | 79952 | 79975 |
| Bytes to the bots | 21.2 MiB | 21.2 MiB |

Commit 08e6657, Calx f6ad008. A join takes about 1.1 s because the client's first batch is 9 chunks, then 25 a tick as the bots ask for, so 473 chunks take about 20 ticks; it's the protocol's pace, not the server's.

The runs are noisy: one run's mean MSPT is from 0.46 to 0.56 ms on Windows, about ±10%, from the system and the other threads. So before looking into a number flagged as more than 5% worse, run it again with `--runs 10`, and look into it if it stays.
