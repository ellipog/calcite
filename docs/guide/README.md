---
title: Running Calcite
description: How to run a Calcite server, from building it to letting players in, pregenerating chunks, proxies, the console and recordings.
---

# Running Calcite

This guide is for whoever runs a Calcite server. It's written as Calcite is now, before its first release: you build it from source, and it does what the [status](#what-works-today) below says. The website renders these pages; each is plain Markdown here too.

## What works today

Calcite has passed the gates of Phases 0 to 5 of its [plan](../PLAN.md). A Minecraft: Java Edition 26.3 client can:

- find it in the server list and join, in online mode with Mojang's accounts or in offline mode, directly or through a Velocity proxy;
- chat, with signed chat checked as vanilla checks it;
- explore worlds generated as vanilla generates them, in the Overworld, the Nether and the End, with data packs such as Terralith, while the server saves and loads them in vanilla's format.

Phase 6, simulation, is under way, so blocks don't tick or update yet, players can't break or place them, there are no mobs and no inventories, and the commands are `stop`, `gamemode` with its short forms, `pregen`, and `calcite flyspeed` and `calcite dimension` for testing.

## Pages

1. [Getting started](start.md)
2. [Configuration](configuration.md)
3. [Pregenerating chunks](../pregen.md)
4. [Behind a proxy](proxies.md)
5. [The console](console.md)
6. [Recording and replay](recording.md)
7. [Worlds and vanilla](vanilla.md)
