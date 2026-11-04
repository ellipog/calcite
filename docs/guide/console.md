---
title: The console
description: Calcite's console, its two styles, the dashboard, the commands it takes and its log files.
---

# The console

Calcite's console works as vanilla's does, so hosting panels and wrappers that read vanilla's lines read Calcite's too. On a terminal it can look like Calcite instead.

## Two styles

`console-style` in `calcite.properties` picks one:

- **`auto`**, the default: Calcite's own look on a terminal, and vanilla's exact lines in a file or a pipe, which is how Pterodactyl, AMP, Crafty and wrappers run a server and read lines such as `Done (...)! For help`.
- **`calcite`** or **`vanilla`**: always that one.

`logs/latest.log` always has vanilla's lines.

Calcite's look starts with the card when the server is ready, in place of vanilla's lines from `Starting minecraft server version` to `Done`. After it, each line is the time, a mark for what happened and the words: `→` for a player coming in, `←` for one going or turned away, `▲` for a warning and `×` for an error. Lines that tell whoever runs the server nothing new, such as `Loading properties`, aren't shown. `NO_COLOR` turns its colors off and keeps the layout.

## The dashboard

`console-dashboard=bottom` or `top` pins a bar to that edge of the terminal, redrawn once a second, while the log scrolls by:

```text
            ›  stop
    calcite    20.0 TPS · 1.4 MSPT · 3.2% CPU · 214 MB / 16 GB RAM · 1/20 players · 441 chunks · up 12m 4s
```

- **TPS** is ticks a second over the last 100 ticks, and **MSPT** the mean milliseconds they took. TPS turns amber under 19.5 and red under 15, MSPT amber over 40 and red over 50.
- **CPU** is the process's share of every processor over the last second, and **RAM** what it holds out of what it may: the machine's memory, or a container's limit.
- **Players**, the **chunks** in their views, and the time it's been **up**.

Commands are typed beside the bar, after the `›`, with a shell's keys: arrows, Home and End, Ctrl+Left and Right by words, up and down for the commands typed before. Ctrl+C stops the server, and a second one ends it at once.

The bar is drawn only on a terminal that gives its size and takes raw input, never in a file, a pipe or a hosting panel, which get the plain log.

## Commands

The console takes what a vanilla console does, between ticks, so a hosting panel's `stop` works. So far:

| Command | What it does |
| --- | --- |
| `stop` | Tells each player the server closed, saves, and stops |
| `gamemode <mode> [<player>]` | As vanilla's; `gmc`, `gms`, `gma` and `gmsp` are short for it |
| `pregen ...` | Generates an area ahead of time ([Pregenerating chunks](../pregen.md)) |
| `calcite flyspeed [<speed>]` | A player's flying speed as a multiple of vanilla's, up to 1,000, for testing |
| `calcite dimension <dimension> [<player>]` | Takes a player to another dimension, for testing |

The rest of vanilla's come in Phase 6. Anything else gets vanilla's answer to a command it doesn't know.

## Logs

Each line goes to the console and to `logs/latest.log`, in Mojang's pattern, `[12:04:31] [Server thread/INFO]: ...`, and the file rolls as vanilla's does: at the start and at the first line of each day, into `logs/<day>-<N>.log.gz`, seven a day at most. The file is written, rolled and compressed off the server thread, so a slow disk never holds a tick up.
