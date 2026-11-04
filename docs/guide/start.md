---
title: Getting started
description: Install Calx, build Calcite, start it and join it with Minecraft: Java Edition 26.3.
---

# Getting started

There's no release to download yet, so you build Calcite from source. It's one command once Calx is installed.

## What you need

- Windows or Linux, on x86-64.
- [Calx](https://calxlang.com), with clang and lld from LLVM 18 or later, which Calx builds programs with. [Install Calx](https://calxlang.com/guide/install/) says how to get them.
- Git.
- Minecraft: Java Edition 26.3, to join with.

## Install Calx

On Windows, in PowerShell:

```powershell
irm https://calxlang.com/install.ps1 | iex
```

On Linux:

```sh
curl -fsSL https://calxlang.com/install.sh | sh
```

## Build Calcite

```sh
git clone https://github.com/ellipog/calcite
cd calcite
calx build --release src/calcite.calx -o server/calcite
```

On Windows, name it `server/calcite.exe`. The release build is the one to run: a debug build is many times slower.

## Start it

Calcite reads and writes its files in the folder it's started in, as vanilla does:

```sh
cd server
./calcite
```

The first time, it:

- writes `server.properties` with every setting vanilla has, at its default, and `calcite.properties` with Calcite's own ([Configuration](configuration.md));
- reads vanilla's data from Minecraft's client jar: from the game, if Mojang's launcher, Prism Launcher or the Modrinth App has installed 26.3, or else by downloading only the 5.6 MB of the jar that hold it from Mojang, checked against its pinned hash and kept in `cache/`;
- writes `banned-players.json`, `banned-ips.json`, `ops.json` and `whitelist.json`, each empty;
- makes the world in `world/`, or the folder `level-name` names, from `level-seed` and `level-type`.

When it's ready, a terminal shows its card, here for a later start:

```text
   calcite   Minecraft 26.3 · ready in 4.8 ms

  ›  Address    localhost:25565
  ›  Accounts   checked with Mojang
  ›  World      Default, 10 chunks in view, 10 simulated
  ›  Players    up to 20
```

A file or a pipe, which is how hosting panels run a server, gets vanilla's exact lines instead ([The console](console.md)). The first start makes the boot cache, `cache/boot.bin`, which takes about 50 ms more, or half a second with the download. Later starts read it, and listen a few milliseconds after they start.

## Let players in

The whitelist is on, as vanilla's is by default, and Calcite has no command to change it yet. Either:

- turn it off, with `white-list=false` in `server.properties`; or
- add each player to `whitelist.json`, as vanilla writes it:

  ```json
  [{ "uuid": "069a79f4-44e9-4726-a5be-fca90e38aaf5", "name": "Notch" }]
  ```

The lists are read as the server starts, so restart it after changing one. Operators go in `ops.json` the same way, with a `level`; `pregen` needs level 4, or the console.

## Join

In Minecraft 26.3, open Multiplayer, Add Server, and give it `localhost`, or the machine's address from another one. Calcite listens on 25565 unless `server-port` says otherwise.

To stop the server, type `stop` in its console, or press Ctrl+C.

## Next

- [Configuration](configuration.md): what you can set, and how.
- [Pregenerating chunks](../pregen.md): make a world's chunks before anyone walks there.
- [Behind a proxy](proxies.md): run it behind Velocity.
