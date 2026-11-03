---
title: Benchmarks
description: How Calcite's server is timed with 100 bot players, generating a world with Terralith and Terratonic beside vanilla, Paper and C2ME on the same machine, and without them, with Mojang's own client joining and flying at 25 and 100 times vanilla's speed, and with its light engine against vanilla's, how to run each, and the results.
---

# Benchmarks

Four, each run on the server's release build:

- [the bots](#bot-benchmark), which time the server with 100 players on it;
- [worldgen](#worldgen-benchmark), which times generating a world with Terralith and Terratonic, set up as C2ME's own benchmark is, beside vanilla, Paper and C2ME on the same machine, and without the packs;
- [a real client](#a-real-client), Mojang's own, joining a new world at view distance 32 and flying over it at 25 and 100 times vanilla's speed, with the server's memory;
- [light](#light), Calcite's light engine against vanilla's.

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
| MSPT, mean | 0.419 ms | 0.472 ms |
| MSPT, p99 | 1.112 ms | 1.259 ms |
| MSPT, max | 1.644 ms | 1.853 ms |
| TPS | 20.00 | 20.00 |
| MSPT while joining, mean | 1.164 ms | 6.135 ms |
| MSPT while joining, max | 3.422 ms | 34.639 ms |
| Join to all chunks, median | 549 ms | 552 ms |
| Join to all chunks, max | 604 ms | 603 ms |
| CPU time | 3.03 s | 2.92 s |
| Peak memory | 70.0 MiB | 68.3 MiB |
| Chunks sent | 80251 | 80362 |
| Bytes to the bots | 21.3 MiB | 21.3 MiB |

Commit 565d961, Calx 5bc903e, after worldgen's speed-ups ([CAL-107](https://acta.aaenz.no/aaen-studios/calcite#CAL-107)) and the server's tick in vanilla's order ([D295](../docs/decisions.md)). At 868e0a0, recorded at the end of Phase 5, the mean MSPT was 0.400 ms on Windows and 0.471 ms on Linux; at 1195b56, the end of Phase 4, 0.455 and 0.452; and at 08e6657, the first recorded, 0.508 and 0.459. The tick thread no longer compresses packets or compares every pair of players ([D291](../docs/decisions.md), [D292](../docs/decisions.md)).

This set is flagged against 868e0a0's: its p99 and max are 10 to 29% higher on both platforms, and its CPU time 8 to 9%. On Windows the flags stayed in 10 runs, at 1.086 ms, 1.554 ms and 3.27 s. That's the machine's, the evening it was recorded, and not the code's: 868e0a0, built with the same compiler and run in turn with 565d961 on the same evening, 6 runs each, measured 0.419 and 0.421 ms mean, 1.073 and 1.095 ms p99, 1.534 and 1.520 ms max, and 3.27 and 2.93 s of CPU. So D295's vanilla work each tick, the time sent to everyone every 20 ticks and everyone's latency every 601, costs too little to see here.

A join takes about 550 ms, half what it did. The client's first batch is 9 chunks. The bots then ask for 25 a tick, and since [D272](../docs/decisions.md) a client that asks for fewer than 64 is sent 4 times as many, up to 64. So 473 chunks take about 9 ticks, where at 1195b56 they took 20. Sending a join's chunks faster makes its ticks dearer: the mean MSPT while joining went from 0.964 to 1.125 ms on Windows.

On Linux under WSL, the ticks while joining average 6.1 ms, and the worst was 35 ms. They were 8.6 ms before D291 too (D292), and on Windows on the same machine they're 1.1 ms, so this is still to be found ([CAL-108](https://acta.aaenz.no/aaen-studios/calcite#CAL-108)). Peak memory went from 47 to 69 MiB over Phase 5; it was 67 to 69 MiB before D291 as well (D292).

Since then the worst tick while joining has moved with how chunks load. On Windows, in 15-second runs, it went from 2.0 ms to 4.4 when chunks began to be read on threads (d30ab20), since the first bot's come back in one burst, and to 10.6 when the level began to light them (3b8d324). Lighting a tick's worth at a time brought it to 4.8 ms, and on a world vanilla generated, where most chunks need their light spread, to 7.9 ms from 41.0, the medians of 3 30-second runs ([D197](../docs/decisions.md)).

The runs are noisy, from the system and the other threads: one run's mean MSPT is from 0.46 to 0.56 ms on Windows, about ±10%. CPU time on Windows varies more, from 2.3 to 3.6 s in one set of runs, and a worst tick can be one the system held up, such as 18 ms while joining in one run on Linux where the others were 2 to 4. So before looking into a number flagged as more than 5% worse, run it again with `--runs 10`, and look into it if it stays.

## Worldgen benchmark

```sh
py -I bench/terralith.py                      # Calcite at 1, 8, 16 and 32 workers, not recorded
py -I bench/terralith.py --record             # the same, written to bench/results/terralith-<platform>.json
py -I bench/terralith.py --threads 8 --radius 512     # a quick look, not recorded
py -I bench/terralith.py --no-packs --record  # vanilla's own worldgen, the same runs, to bench/results/worldgen-<platform>.json
py -I bench/others.py --record                # vanilla, Paper and C2ME, the same runs, to bench/results/others-<platform>.json
py -I bench/others.py --servers c2me --threads 8 --radius 512     # a quick look at one, not recorded
```

[C2ME](https://modrinth.com/mod/c2me-fabric) publishes a benchmark of how fast it generates a world with [Terralith](https://modrinth.com/datapack/terralith) and [Terratonic](https://modrinth.com/datapack/terratonic), beside Paper and vanilla. [`terralith.py`](terralith.py) runs it on Calcite (CAL-92), and [`others.py`](others.py) runs it on vanilla, Paper and C2ME, on the same machine ([D293](../docs/decisions.md)). Both are set up as C2ME's benchmark is, but over smaller areas, so the whole comparison takes about an hour and a half:

- **The packs** are the versions made for 26.3, Terralith 2.6.5+26.3 and Terratonic 3.0.31, fetched from Modrinth into `build/bench/packs/` and checked against their SHA-512s. They're Stardust Labs', so they're never committed.
- **The seed** is C2ME's, 114862964781274189.
- **One launch on a fresh world**: a warm-up of a 512-block radius about the origin, then the measured run, a 1,024-block radius about 1,000,000, 1,000,000. Chunky counts 16,641 chunks there, 129 a side. Calcite's `pregen` takes a chunk where its middle is ([D275](../docs/decisions.md)), so it counts 16,384, 128 a side; the rates are a second either way. C2ME's own benchmark measures a 3,072-block radius after a 1,536-block warm-up, 148,225 chunks, which takes vanilla hours on one thread.

Calcite runs from the release build in `build/bench/<platform>/terralith/`, with `chunk-workers` set to the thread count, and generates with its own `pregen` command. The others each run in their own folder in `build/bench/<platform>/java/` with Chunky 1.5.3 and its `force-load-existing-chunks` on, as C2ME's benchmark has it:

| Server | What runs | Threads set by |
| --- | --- | --- |
| Vanilla | Fabric loader 0.20.1 with Fabric API 0.165.0 | `-Dmax.bg.threads` |
| Paper | Paper 26.3-238 | `chunk-system.worker-threads`, with `io-threads` at 4 |
| C2ME | C2ME 0.4.2-alpha.0.115, with Lithium 0.26.3, ScalableLux 0.3.0-alpha.0.6, VMP 0.2.0+beta.7.238 and zfastnoise 1.1.2, as C2ME's benchmark runs it | C2ME's `globalExecutorParallelism` |

Each runs on JDK 25.0.5 (Temurin) with C2ME's JVM flags: a 16 GiB ZGC heap, touched up front, with compact object headers. Large pages are left out, since Windows only gives them to a process with a privilege it doesn't have. The jars are fetched into `build/bench/jars/` and checked against their hashes, and Fabric and Paper fetch Mojang's server themselves.

Vanilla with Chunky puts off unloading chunks while its ticks are behind, and its heap fills. At 8 threads over C2ME's area, its 16 GiB were full 120,000 chunks into the measured run. It then fell from 150 to 200 chunks a second to 21, with its ticks 2.3 s behind. C2ME's benchmark gives vanilla a patched Chunky that forces chunks to unload, and doesn't publish it. So `others.py` types vanilla's own `save-all flush` every 120 seconds instead, which unloads them. On a 1,536-block area at 8 threads:

- without it, vanilla's heap after each major collection grew past 14 GiB in 400 seconds;
- with it, the heap stayed at 3 to 4.5 GiB;
- vanilla made 116.6 chunks a second with it, against 127.4 without, a cost of 8%. A flush every 30 seconds cost 14%.

Each reports the measured run's chunks a second, overall and steady, and the CPU time and peak memory the system gives for the whole launch. Calcite also reports any warning the server logged, and how its workers' time split between the generator's stages:

- the strongholds' rings
- the structures' starts
- the biomes
- the terrain
- the features
- finishing a chunk as the server's, with its sky's light sources and its bytes

The stage times come from the server: `--stage-times FILE` keeps the seconds its workers have spent on each kind of job in the file as they go ([D287](../docs/decisions.md)). The steady rate counts the chunks a second from the progress line at 10% done to the one at 90%. That leaves out the start, while the first starts and biomes fill the generator's pipeline, and the last chunks, which fewer workers share.

With `--no-packs`, `terralith.py`'s runs have no packs, so they time vanilla's own worldgen, on the same seed and areas.

Whether what Calcite generates with the packs is vanilla's is checked by the rig's [`terragen.py`](../rig/README.md#worldgen-with-packs), on a sample of chunks: every one of its 264 has what must be vanilla's.

### Results

With Terralith and Terratonic, on the reference machine, an i9-13900K on Windows 11, in chunks a second over the measured run. Calcite's are recorded in [`results/terralith-windows.json`](results/terralith-windows.json) at commit 565d961 with Calx 5bc903e, and the others' in [`results/others-windows.json`](results/others-windows.json), from their runs at 868e0a0:

| Threads | Calcite | C2ME | Paper | Vanilla | Calcite's peak memory |
| --- | --- | --- | --- | --- | --- |
| 1 | 80.1 | 48.8 | 52.8 | 37.9 | 767 MiB |
| 8 | 414.8 | 312.5 | 313.7 | 98.0 | 946 MiB |
| 16 | 610.2 | 484.4 | 308.5 | 103.9 | 1,101 MiB |
| 32 | 878.6 | 687.1 | 312.5 | 112.9 | 1,309 MiB |

Calcite was the fastest at every thread count. It made 1.64 times C2ME's rate on one thread, 1.33 times on 8, and 1.26 and 1.28 times on 16 and 32. On one thread Paper came second, and Calcite made 1.52 times its rate. At 868e0a0 Calcite made 60.8, 389.7, 521.8 and 746.0: since then a chunk takes less at every stage of the pipeline ([CAL-107](https://acta.aaenz.no/aaen-studios/calcite#CAL-107), D294 to D310), most of all on one thread, where it's 1.32 times as fast. Paper used the 16 and 32 worker threads it was given, as its log says, and made no more than with 8. Vanilla made about 100 at every count from 8 up, the threads helping it little.

Over the whole launch, warm-up included, Calcite used the least CPU time: on one thread 279 s, against Paper's 532 s, C2ME's 545 s and vanilla's 685 s, and at 8 threads 419 s, against 565, 684 and 815. The Java servers' peak memory is their 16 GiB heap, which C2ME's flags touch up front, so it isn't compared. The steady rates are in the results: Calcite's are 77.4, 396.3, 553.6 and 921.2.

Calcite's workers spent 65 to 69% of their time on terrain, 24 to 27% on features, 3% on biomes, 3% on starts and 1 to 2% finishing chunks. Starts took 9% at 32 threads at 868e0a0, as the workers queued for the templates; since the first worker to ask for one loads it ([D294](../docs/decisions.md)), they take 3% at every count. No run logged a warning. At 815d1cc, over C2ME's whole area, Calcite made 60.4, 331.8, 512.3 and 780.4. The smaller area's measured run is 22 s at 32 threads, so its start and end weigh more.

Vanilla's own worldgen, the same runs without the packs, recorded in [`results/worldgen-windows.json`](results/worldgen-windows.json) at the same commit:

| Threads | Calcite | Steady | Peak memory |
| --- | --- | --- | --- |
| 1 | 150.6 | 153.0 | 498 MiB |
| 8 | 1,014.1 | 1,147.8 | 644 MiB |
| 16 | 1,559.4 | | 762 MiB |
| 32 | 2,022.1 | | 915 MiB |

At 16 and 32 threads the measured run takes 10.5 and 8.1 s, too short to have two progress lines between 10% and 90% done, so they have no steady rate. At 868e0a0 these were 136.3, 832.1, 1,286.4 and 1,689.8. Here the workers spent 62 to 64% on terrain, 23 to 24% on features, 7% on biomes, 3% on starts and 3 to 4% finishing chunks. The packs' terrain is the dearer part: with them a chunk takes 1.9 times as long on one thread. These go through the whole server, as a player's chunks do: each chunk is lit, saved to its region file, deflated, and kept until it's let go. The generator by itself, with no server around it, made 3,078 to 3,091 chunks a second on 31 workers under WSL, over a 120-chunk radius on another seed ([CAL-88](https://acta.aaenz.no/aaen-studios/calcite#CAL-88)).

## A real client

```sh
py -I bench/client.py                 # a join and flights at 25 and 100 times vanilla's flying speed, not recorded
py -I bench/client.py --record        # the same, written to bench/results/client-<platform>.json
```

The bots pace themselves as the server lets them. A real player's client asks for chunks as fast as it takes them in, renders them, and flies over them, so what a player gets is measured with Mojang's own 26.3 client, through the rig's [`realclient.py`](../rig/README.md#a-real-client) ([D162](../docs/decisions.md)). For each speed, [`client.py`](client.py) starts the release server on a new world, with C2ME's seed, and the client joins at render and view distance 32:

1. Its join is timed through the rig's relay: the chunks it's sent, and when it had 95% of them and all.
2. Once the chunks have stopped coming for 3 seconds, and 15 more have passed, the server's memory is read as a still player's.
3. The client types `/calcite flyspeed`, takes off and flies forward for 30 seconds. Four times a second the relay counts how much of the circle of 32 chunks about the player the client has, and how far the nearest chunk it doesn't have is. The server's ticks come from its `--tick-times` file.
4. It stops, and the chunks have up to a minute to catch up.

Memory is the server's working set on Windows: before the client joined, 15 seconds after the server was ready, then with the player still, and the most it had, which is the flight's peak. It needs a desktop and a launcher that has run 26.3, and takes the client's window to the front while it flies, so it isn't in CI.

### Results

On the reference machine, Windows 11, recorded in [`results/client-windows.json`](results/client-windows.json) at commit 565d961 with Calx 5bc903e. The server has 31 generator workers, its default. The view is the 3,209 chunks within 32 of the player's.

| | 25× | 100× |
| --- | --- | --- |
| Join: the client had 95% of its 3,725 chunks | 2.98 s | 2.98 s |
| Join: the client had all of them | 3.10 s | 3.09 s |
| Flight speed | 269 blocks a second | 1,075 blocks a second |
| Chunks sent a second while flying | 1,117 | 1,193 |
| The view the client had, mean | 97.9% | 12.5% |
| The view the client had, least | 90.7% | 0.4% |
| The nearest chunk it didn't have, median | 30.0 chunks away | 0.0 |
| MSPT while flying, mean | 4.88 ms | 5.95 ms |
| MSPT while flying, p99 | 14.89 ms | 11.37 ms |
| MSPT while flying, max | 30.19 ms | 15.17 ms |
| Memory, idle | 76.6 MiB | 76.6 MiB |
| Memory, a still view-32 player | 365.0 MiB | 366.1 MiB |
| Memory, at the most | 1,117 MiB | 1,126 MiB |

At 25 times vanilla's speed the client has nearly all of its view the whole flight, and what it lacks is at the edge: the nearest missing chunk is 30 chunks away at the median, and never nearer than 23. At 100 times it flies 67 chunks a second, so the circle ahead of it needs about 4,360 new chunks a second, more than twice the 2,022 a second the server generated on 32 workers in [the worldgen benchmark](#worldgen-benchmark), and the player outruns its chunks within the first seconds. It was sent 1,193 chunks a second as it flew, where at 815d1cc it was sent 990, so it had 12.5% of its view on average, not 8.6%. The generator drops what nothing wants any more as the player goes past it ([D243](../docs/decisions.md)). The client is told to forget each chunk that leaves its view, sent or not, as vanilla tells it: 122,701 at 100×.

The peak is the generator's, while it's making a thousand chunks a second, and it's handed back once the workers go quiet ([D226, D228](../docs/decisions.md)). A still player costs about 288 MiB over idle: the chunks it's sent and the border the server holds about them, with their blocks, light and what else they hold.

## Light

```sh
py -I rig/runner/light_timing.py      # Calcite's light engine against vanilla's, 15 runs of each workload
```

[`light_timing.py`](../rig/runner/light_timing.py) runs the rig's `light` probe on vanilla's server and on Calcite, each a few times to warm up and then 15 times, with three workloads: a flat 9×9 chunks, 7×7 chunks of random terrain, and the same with 5,000 random edits relit. Each is run twice, once whole and once with only its chunks and blocks, so the difference is the light. It says whether both engines' light came out the same, which the probe also checks nibble for nibble.

### Results

On the reference machine, Windows 11, at commit 565d961 with Calx 5bc903e, the median of 15 runs each; the light is the run with it less the run without:

| Workload | Vanilla | Calcite | Calcite is |
| --- | --- | --- | --- |
| Flat, 9×9 chunks | 4.10 ms | 3.72 ms | 1.10× as fast |
| Terrain, 7×7 chunks | 252.4 ms | 141.7 ms | 1.78× as fast |
| Terrain, 7×7 chunks, 5,000 edits relit | 311.1 ms | 194.7 ms | 1.60× as fast |

Both engines' light came out the same in every workload. A flat world's light is the sky's, a level at a time, so there's little to do either way. Both engines take the same steps, the ones each case lists, on the probe's one thread; how the server batches light on a thread of its own ([D264, D265](../docs/decisions.md)) isn't part of what's timed.
