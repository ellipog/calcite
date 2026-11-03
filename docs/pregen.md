# Pregenerating chunks

Calcite can generate the chunks of an area ahead of time, as the Chunky mod does, so players exploring there never wait on world generation. It's built in: there's nothing to install. The command is `/pregen`, with Chunky's subcommands, so they carry over. Only the console and operators at level 4 can use it, as it can keep every generator thread busy for hours.

## Quick start

```
pregen radius 5000
pregen start
```

That generates every chunk within 5000 blocks of 0, 0 in a square, in the dimension you're in, or the Overworld from the console. The console says how it's going every 5 seconds, and the dashboard shows how far it's come and how fast:

```
Pregen minecraft:overworld: 36466 of 62500 chunks (58.35%), 2071 a second, 19 s spent, 13 s left, at 63, 30
Pregen minecraft:overworld done: 62500 chunks in 31 s, 1956 a second
```

## Choosing what to generate

Each player, and the console, has a selection of their own. It starts as Chunky's default: a square 500 blocks around 0, 0, region by region. These change it, and the next `pregen start` uses it:

| Command | What it does |
| --- | --- |
| `pregen dimension <dimension>` | The dimension, such as `minecraft:the_nether`. Chunky's `pregen world <dimension>` works too. Until it's set, it's the dimension you're in. |
| `pregen center [<x> <z>]` | The center, in blocks. Without `x` and `z`, it's where you stand. |
| `pregen spawn` | The center at the world's spawn. |
| `pregen radius <radius> [<radius_z>]` | The radius, in blocks. A rectangle or an ellipse can have another along `z`. |
| `pregen shape <shape>` | `square`, `rectangle`, `circle`, `ellipse`, `diamond`, `triangle`, `pentagon`, `hexagon` or `star`. A triangle's, pentagon's, hexagon's or star's first point is to the north. |
| `pregen pattern <pattern>` | The order chunks are generated in: `region`, a region file's 32 × 32 chunks at a time, which writes each file in one go and is the fastest; `concentric`, square rings out from the center; `spiral`, one spiral out from it; or `loop`, row by row. |
| `pregen worldborder` | A square the world border's size, 29,999,984 blocks around 0, 0. |
| `pregen selection` | Says what the selection is now, and how many chunks it holds. |

A chunk is in the area when its middle is in the shape.

## Running tasks

| Command | What it does |
| --- | --- |
| `pregen start` | Starts generating the selection. Each dimension can have one task at a time. |
| `pregen pause` | Pauses every task. The chunks it's working on finish first. |
| `pregen continue` | Carries on with every paused task. |
| `pregen cancel` | Cancels every task. |
| `pregen progress` | Says how each task is going. |
| `pregen quiet <seconds>` | How often the console is told how the tasks are going: every 5 seconds until it's set. |
| `pregen silent` | Turns those progress lines off, or back on. Starting, finishing, pausing and cancelling are still said. |

The player who started a task is told in chat each time another tenth of it is done, and when it's finished. Operators are told when a task starts, pauses, carries on or is cancelled, as vanilla tells them of other commands.

## How it works

A task holds up to 1024 chunks at once. It loads each with a ticket of its own, and lets it go once the chunk is fully generated and lit. The chunk is then saved and unloaded, so memory stays flat however large the area is. A chunk that's already saved fully generated is read, not generated again.

Tasks survive restarts and crashes. How far each has come is saved in the world's `data/calcite/pregen.dat`: as it starts, pauses, carries on, is cancelled or finishes, every 30 seconds while it runs, and with each save of the world. When the server starts, each task carries on where it was, paused if it was paused. The chunks it was working on when it stopped are generated again or read.

Players come first. While a player's chunks are loading in the dimension, as they join or travel into new terrain, a task starts no new chunks, and its progress line says `giving way to players`. It carries on once their chunks are in. On our test machine, a real client joining at view distance 32 had 90% of its chunks at 2.8 s with no pregen running and at 3.5 to 3.7 s with one running.

A pregenerated chunk is the same chunk a player walking there would have generated.

On our test machine, with 32 threads, a new world's Overworld pregenerates at about 2,000 chunks a second: a 2000-block radius, 62,500 chunks, takes 31 seconds, with the server using at most 764 MB. It runs as fast as Calcite generates chunks, so it's faster on more cores. `chunk-workers` in calcite.properties sets how many threads generate chunks.
