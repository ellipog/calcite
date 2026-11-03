---
title: Benchmarks
description: How Calcite's server is timed with 100 bot players joining, walking and chatting, and generating a world with Terralith and Terratonic beside C2ME's numbers, how to run each, and the results.
---

# Benchmarks

Two benchmarks, each run on the server's release build: [the bots](#bot-benchmark), which time the server with 100 players on it, and [worldgen](#worldgen-benchmark), which times generating a world with Terralith and Terratonic, set up as C2ME's own benchmark is.

## Bot benchmark

D34 tracks performance per commit, from the tick-loop benchmark in Phase 3 to a fixed bot scenario from Phase 4. This is that scenario (P4.10, [D154](../docs/decisions.md)): the real server, its release build, with players on it.

```sh
py -I bench/run.py                       # 5 runs of the scenario, and the change from what's recorded
py -I bench/run.py --record              # the same, written to bench/results/bots-<platform>.json
py -I bench/run.py --runs 1 --bots 20 --seconds 20     # a quick look, not recorded
```

On Linux, use `python3` for `py`. The runner builds the server and the bots with calx into `build/bench/<platform>/`, then runs each in `build/bench/<platform>/world/`, a fresh start each time. It needs nothing but Python.

### The scenario

- **The server** is the release build, in offline mode with the whitelist off, with vanilla's compression threshold of 256, and view and simulation distance 10, so a player has 473 chunks in view. `max-players` is 1000.
- **The world is flat**, `level-type=minecraft:flat`, and new for each run, as it was when the scenario was set, before Calcite generated terrain. So this times the tick loop and the network with 100 players, not worldgen; [the worldgen benchmark](#worldgen-benchmark) and [the real client's flights](../rig/README.md#a-real-client) time chunks being made and sent.
- **100 bots join**, 20 a second, over TCP on 127.0.0.1. Each does what a client must to stay: logs in, finishes configuration, accepts its teleport, acknowledges each chunk batch, answers keep-alives and ends a tick every 50 ms.
- **Once a bot has every chunk of its view**, it walks at walking speed, 0.21585 blocks a tick, on a heading of its own: its index times the golden angle. So the players spread out, and the server sends each a new row of chunks every few seconds, the whole run.
- **Each bot chats every 10 seconds**, starting at a second of its own, and every message goes to all 100.
- **The run lasts 45 seconds**, then the server is told `stop`.

The bots are [`src/rig/swarm.calx`](../src/rig/swarm.calx), on one thread of their own process. They're made from Calcite's own protocol code; the format is checked elsewhere, by the network tests and vanilla's codecs ([D145](../docs/decisions.md)).

### What's measured

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

### Results

On the reference machine, an i9-13900K, the medians of 5 runs, recorded in [`results/`](results/) with the commit, the Calx compiler's commit and the machine. Linux is Ubuntu in WSL 2 on the same machine.

| Measure | Windows 11 | Linux |
| --- | --- | --- |
| MSPT, mean | 0.455 ms | 0.452 ms |
| MSPT, p99 | 1.479 ms | 1.133 ms |
| MSPT, max | 1.967 ms | 1.750 ms |
| TPS | 20.02 | 20.00 |
| MSPT while joining, mean | 0.964 ms | 1.314 ms |
| MSPT while joining, max | 2.224 ms | 3.830 ms |
| Join to all chunks, median | 1100 ms | 1097 ms |
| Join to all chunks, max | 1121 ms | 1099 ms |
| CPU time | 3.25 s | 2.06 s |
| Peak memory | 47.2 MiB | 44.3 MiB |
| Chunks sent | 79952 | 79975 |
| Bytes to the bots | 21.2 MiB | 21.2 MiB |

Commit 1195b56, Calx f6ad008, after the chunk sender stopped sorting every chunk waiting each tick ([D155](../docs/decisions.md)); at 08e6657, the first recorded, the mean MSPT was 0.508 ms on Windows and 0.459 ms on Linux. A join takes about 1.1 s because the client's first batch is 9 chunks, then 25 a tick as the bots ask for, so 473 chunks take about 20 ticks; it's the protocol's pace, not the server's.

Since then the worst tick while joining has moved with how chunks load. On Windows, in 15-second runs, it went from 2.0 ms to 4.4 when chunks began to be read on threads (d30ab20), since the first bot's come back in one burst, and to 10.6 when the level began to light them (3b8d324). Lighting a tick's worth at a time brought it to 4.8 ms, and on a world vanilla generated, where most chunks need their light spread, to 7.9 ms from 41.0, the medians of 3 30-second runs ([D197](../docs/decisions.md)).

The runs are noisy, from the system and the other threads: one run's mean MSPT is from 0.46 to 0.56 ms on Windows, about ±10%. CPU time on Windows varies more, from 2.3 to 3.6 s in one set of runs, and a worst tick can be one the system held up, such as 18 ms while joining in one run on Linux where the others were 2 to 4. So before looking into a number flagged as more than 5% worse, run it again with `--runs 10`, and look into it if it stays.

## Worldgen benchmark

```sh
py -I bench/terralith.py                      # 1, 8, 16 and 32 workers, the full run, not recorded
py -I bench/terralith.py --record             # the same, written to bench/results/terralith-<platform>.json
py -I bench/terralith.py --threads 8 --radius 512     # a quick look, not recorded
py -I bench/terralith.py --no-packs --record  # vanilla's own worldgen, the same runs, to bench/results/worldgen-<platform>.json
```

[C2ME](https://modrinth.com/mod/c2me-fabric) publishes how fast it generates a world with [Terralith](https://modrinth.com/datapack/terralith) and [Terratonic](https://modrinth.com/datapack/terratonic), beside Paper's and vanilla's, from 1 to 16 threads. [`terralith.py`](terralith.py) runs the same benchmark on Calcite (CAL-92), set up as theirs is:

- **The packs** are the versions made for 26.3, Terralith 2.6.5+26.3 and Terratonic 3.0.31, fetched from Modrinth into `build/bench/packs/` and checked against their SHA-512s. They're Stardust Labs', so they're never committed.
- **The seed** is C2ME's, 114862964781274189.
- **One launch on a fresh world**: a warm-up of a 1,536-block radius about the origin, then the measured run, a 3,072-block radius about 1,000,000, 1,000,000, 148,225 chunks, each with the server's own `pregen` command. The release server runs in `build/bench/<platform>/terralith/` with `chunk-workers` set to the thread count.

It reports the measured run's chunks a second, overall and steady, the CPU time and peak memory the system gives for the whole launch, any warning the server logged, and how the workers' time split between the generator's stages: the strongholds' rings, the structures' starts, the biomes, the terrain, the features, and finishing a chunk as the server's, with its sky's light sources and its bytes. The stage times come from the server: `--stage-times FILE` keeps the seconds its workers have spent on each kind of job in the file as they go ([D287](../docs/decisions.md)). The steady rate is the chunks a second from the `pregen` progress line at 10% done to the one at 90%: it leaves out the start, while the first starts and biomes fill the generator's pipeline, and the last chunks, which fewer workers share. The whole run is over an hour, most of it at 1 thread.

With `--no-packs`, the same runs have no packs, so they time vanilla's own worldgen, on the same seed and areas.

C2ME's numbers are from their machine, a Xeon Platinum 8558P held to 3.2 GHz, on Minecraft 26.2 with Terralith 2.6.4 and Terratonic 3.0.27, so only the curves compare, not the numbers themselves. The script prints its table beside theirs, and `--record` keeps theirs in the results with ours.

Whether what Calcite generates with the packs is vanilla's is checked by the rig's [`terragen.py`](../rig/README.md#worldgen-with-packs), on a sample of chunks.
