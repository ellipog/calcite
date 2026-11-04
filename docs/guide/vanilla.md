---
title: Worlds and vanilla
description: How Calcite matches vanilla, how that's checked, where it deliberately differs, and moving worlds between them.
---

# Worlds and vanilla

Calcite means to do what vanilla 26.3 does, to the bit, wherever a player, a farm or a data pack could tell. The exceptions are vanilla's bugs and exploits, which it fixes and lists.

## How it's checked

An oracle rig runs the same inputs through vanilla's server code and through Calcite's, and compares the results bit for bit: floats as raw bits, so a near miss is a failure. Vanilla's results are recorded once and their hashes committed, and Calcite is scored against them on every change. The rig covers, among the rest:

- **Worldgen.** The Overworld, the Nether and the End pass the worldgen suites on the rig's grid of seeds, block for block. With Terralith and Terratonic, every one of 264 sampled chunks has what must be vanilla's; the blocks that differ are those the order chunks are decorated in decides, which vanilla doesn't fix either.
- **Light.** Every block gets the same light level, from 0 to 15, as in vanilla, in every workload.
- **The protocol.** The login and configuration suites match vanilla packet for packet, and Mojang's own 26.3 client joins, walks and chats.
- **Saves.** A world vanilla made, loaded and saved by Calcite, reads back in vanilla.
- **Lockstep.** A session recorded on many threads, replayed on one, gives the same packets and lines.

How the rig works, and how to run it, is in [its README](../../rig/README.md).

## Moving a world

Worlds round-trip: Calcite reads and writes vanilla 26.3's format, its region files, `level.dat`, player data and the rest, so a world can move from vanilla to Calcite and back. Keep a backup anyway: Calcite is pre-release.

A world from an older version goes through vanilla 26.3 first, which upgrades it. Calcite reads only what 26.3 writes.

## Data packs

A world's data packs, in its `datapacks` folder, load as vanilla loads them, with their overlays and filters, and worldgen packs such as Terralith and Terratonic generate as they do in vanilla. Vanilla's own data comes from Mojang's client jar, read from an installed game or downloaded the first time; Calcite contains no Mojang code or assets.

## Deliberate differences

Each place Calcite means to differ from vanilla is listed, with the rig cases it covers, so a fix never hides a failure and a failure never passes as a fix. Each is a `bug` vanilla has that Calcite fixes, an `exploit` it closes, Calcite saying what it is (`identity`), or vanilla depending on its JVM or system (`platform`).

<!-- differences -->

The list, with each difference's cases, is in [`rig/differences/`](../../rig/differences/README.md).
