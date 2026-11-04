---
title: Configuration
description: server.properties as vanilla reads it, calcite.properties for Calcite's own settings, the server icon, and the lists of who may join.
---

# Configuration

A Calcite server's folder looks like a vanilla server's, and Calcite reads vanilla's files as vanilla reads them, so a server's folder can move over unchanged. Calcite's own settings go in a file of their own, `calcite.properties`.

## server.properties

Vanilla's file, read as vanilla reads it: UTF-8, or ISO-8859-1 if it isn't, with Java's rules for escapes, continued lines and comments. A setting that's missing or doesn't parse is its default.

As the server starts, it writes the file back as vanilla does, so a new server gets one with every setting vanilla has, at its default, byte for byte what the 26.3 jar writes but for line ends. Keys vanilla doesn't read are kept as they are.

The settings Calcite reads so far:

| Setting | What it does |
| --- | --- |
| `server-ip`, `server-port` | Where it listens. 25565 by default |
| `online-mode` | Checks players' accounts with Mojang. On by default |
| `motd`, `max-players`, `enable-status`, `hide-online-players` | What the server list shows |
| `white-list` | Lets in only the players on `whitelist.json` and operators. On by default |
| `level-name`, `level-seed`, `level-type`, `generate-structures` | The world's folder, and how a new one is made |
| `gamemode`, `difficulty`, `hardcore` | A name, such as `creative`, or vanilla's number |
| `view-distance`, `simulation-distance` | How far players see, and how far the world runs, in chunks |
| `network-compression-threshold`, `rate-limit` | Packets bigger than this are compressed; a player who sends more packets a second than `rate-limit` is kicked |
| `enforce-secure-profile`, `prevent-proxy-connections`, `accepts-transfers` | Signed chat, proxy checks and transfers, as in vanilla |
| `chat-spam-threshold-seconds`, `command-spam-threshold-seconds` | The burst of chat and commands a player may send |
| `log-ips` | `false` logs `IP hidden` for every address |
| `resource-pack`, `resource-pack-sha1`, `resource-pack-id`, `require-resource-pack`, `resource-pack-prompt` | The resource pack players are offered |
| `enable-code-of-conduct` | Shows the `.txt` files in `codeofconduct/` to each player in their language, to accept before they join |
| `bug-report-link` | The link the game's pause menu offers for reporting a bug |
| `region-file-compression`, `sync-chunk-writes` | How region files are written |

The rest are written back as vanilla writes them, and come into use as what they set comes to Calcite.

## calcite.properties

Calcite's own settings, in the same format, read the same way. A server that has none writes one, with each setting at its default and a comment on what it does:

<!-- calcite.properties -->

A setting that stops the server, such as forwarding with no secret, is logged as `Failed to start the minecraft server: ...`.

## The server icon

`server-icon.png`, beside `server.properties`, is the picture in the server list. It must be a 64 × 64 PNG, as vanilla checks it.

## Who may join

Calcite reads vanilla's lists as it starts, as vanilla writes them, and writes an empty one where there's none:

| File | What it holds |
| --- | --- |
| `whitelist.json` | The players `white-list=true` lets in, by UUID and name |
| `ops.json` | Operators, with their `level` and whether they may join a full server, `bypassesPlayerLimit` |
| `banned-players.json` | Banned players, with the reason and when the ban ends, if it does |
| `banned-ips.json` | Banned addresses |

Players are told what vanilla tells them: that they're banned, why and until when, that they aren't on the whitelist, or that the server is full. The lists are read once, so restart the server after changing one, until the commands that change them come in Phase 6.

## Tries to log in

Vanilla lets an address try to log in as often as it likes. On a public server, `login-throttle=4000` in `calcite.properties` refuses a try from an address that tried less than 4 seconds before, and tells the player to wait a moment.
