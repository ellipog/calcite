---
title: Global systems
description: Every vanilla system that reads or writes beyond one region, where it runs in Calcite, and what changes because of it.
---

# Global systems

Every vanilla 26.3 system that reads or writes beyond one region, where it runs in Calcite, and whether anyone could tell (`P0.4`). It was built from the decompiled 26.3 server: every `SavedData` type (vanilla's world-wide saved state), every loop over all players or all worlds, and every server-wide counter or random stream.

This page decides what the global actor is. The tick sketch is in [`sketches/tick-loop.calx`](sketches/tick-loop.calx).

## The tick, in brief

From D50, which replaces the phase order in D20:

1. **Inputs** for the tick are cut (D21).
2. **Packet phase**, all regions in parallel: messages from the last tick, then this tick's packets.
3. **Global phase**, one thread with access to every region: commands escalated from the packet phase in input order, functions, clocks, then each world's world-wide steps.
4. **World phase**, all regions in parallel: scheduled ticks, chunks, block events, entities, block entities, connections.
5. **Barrier**, one thread again: console and RCON commands (where vanilla's `tickConnection` runs them), then handoffs, region split and merge, message routing, fan-out and flush.

Vanilla handles every packet at the start of the tick, then runs functions, then ticks the worlds. Handling packets in their own phase before the global phase keeps that order, so a command a player types sees the same game time as in vanilla. A message is handled the next time its destination runs, so a region's message to the global instance during the packet phase is handled in the same tick.

## Homes

| Home | Meaning |
| --- | --- |
| **Global** | Runs in the global phase. Regions read it from the tick snapshot |
| **Region** | Runs in a region. The row says which one owns it |
| **Escalated** | Starts in a region, and moves to the global phase if it can reach beyond the region (D51) |
| **Lent** | Server-wide or world-wide state that regions use all the time. With one region (in the server, or in the world for per-world state), the region owns it for the tick and behaves exactly like vanilla. With several, it's split per region or changed by messages (D52) |
| **Fan-out** | Output only, such as sounds or chat. Routed to other regions' players at the barrier and sent in the same tick |
| **Handoff** | Moves an entity or player between regions at the barrier |

**Difference** says what anyone could notice:

- **None**: identical to vanilla.
- **Multi-region**: identical in a single region. With several regions, deterministic, but it can differ in timing or in what random numbers come out (D52).
- **Listed**: different even in a single region. It goes in `rig/differences/`.

## Commands

| System | Home | Difference |
| --- | --- | --- |
| Console and RCON commands | At the barrier after the world phase, where vanilla runs them (`tickConnection`), with access to every region | None |
| Commands typed by players | Region, in the packet phase. Escalated if not region-safe, then run in the same tick's global phase in input order | Multi-region: an escalated command runs after every region's packets for the tick, not in arrival order among them |
| Command blocks (and command block minecarts), advancement reward functions | Region, in the world phase. Escalated if not region-safe, then run in the next tick's global phase | Multi-region: an escalated command runs one tick late, and its comparator output follows a tick later |
| Data pack functions: `#minecraft:tick`, `#minecraft:load`, `/schedule` (vanilla's `TimerQueue`), `/function` from the console | Global, at vanilla's points in the tick | None |
| Command storage (`/data ... storage`) | Global. Region commands that touch it escalate | Follows the command rows |
| Entity selectors | See "Region-safe commands" below | Follows the command rows |
| `/reload` | At the barrier: functions, loot tables, recipes and tags are rebuilt and the snapshot is swapped | None |
| `/gamerule`, `/difficulty`, `/time`, `/weather`, `/worldborder`, `/forceload`, `/setworldspawn`, `/bossbar`, objective and team changes | Global. Always escalated | Follows the command rows |

### Region-safe commands

A command runs in its region only if the compiler of the command (Brigadier's parse, then a check) can prove it touches nothing outside the region (D51):

- `@s`, and positions and block arguments that resolve to chunks the region owns, are region-safe.
- `@p` and `@n` are region-safe when the nearest match in the region is closer than the distance to any other region in that world, which proves nobody outside could be nearer.
- `@a`, `@e` and `@r` are region-safe only with a `distance`, `dx`/`dy`/`dz` or `limit`-plus-`sort=nearest` bound that keeps them inside the region. Without one, vanilla searches every world (`EntitySelector.isWorldLimited`), so they escalate.
- `execute in` another world, storage, scores of holders that aren't entities in the region, and anything in the "always escalated" row escalate.
- A function is region-safe if all its commands are, worked out once per `/reload`. A function with macro lines escalates, since its commands aren't known until it runs.

In a single region, every command is region-safe: there's nothing outside.

## Time, weather, sleeping

| System | Home | Difference |
| --- | --- | --- |
| Tick rate (`/tick` freeze, step, sprint; `ServerTickRateManager`) | Global. The frozen state is in the snapshot | None |
| World clocks, day time and game time (`ServerClockManager`, new in 26.x) | Global. Game time is shared by every world, as in vanilla | None |
| Time sync packets every 20 ticks | Global, fan-out | None |
| Weather cycle (`WeatherData`) | Global | None |
| Rain, snow and lightning per chunk | Region (`tickChunk`, `tickThunder`) | Multi-region: random numbers come from the region's stream |
| Sleeping (`SleepStatus`): counting sleepers, skipping to morning, waking everyone, clearing rain | Global, after the packet phase, so it sees players who got into or out of bed this tick as vanilla does. The global phase can wake players in any region directly | None |
| Stopwatches (`/stopwatch`, new in 26.x), which read real time | Global, using the wall clock recorded at the start of the tick (D54) | None for players. Replays repeat the recorded times |

## Spawning

| System | Home | Difference |
| --- | --- | --- |
| Phantoms, patrols, cats, village sieges, wandering traders (vanilla's `CustomSpawner`s and `WanderingTraderData`) | Lent per world. With one region in the world, the region runs them at vanilla's point, after ticking chunks. With several, the global phase runs the countdowns and picks the player, and the chosen player's region spawns at that same point in its world phase | Multi-region: random numbers come from the world's global stream |
| Natural spawning: the world-wide mob cap (`NaturalSpawner.SpawnState`) | Region, counting its own mobs plus the other regions' counts from the last barrier | Multi-region: the cap can be off by what other regions spawned in the same tick |
| Natural spawning: per-player local mob caps (players within 8 chunks) | Region. Always inside one region (D53) | None |
| Mob despawning (nearest player in the world, with 32 and 128 block thresholds) | Region. A player within 128 blocks is always in the same region (D53). Whether any player is in the world at all comes from the directory | None |

## World-wide structures and events

| System | Home | Difference |
| --- | --- | --- |
| Raids (`Raids`) | Region that owns the raid's center chunk. The raid moves with that chunk. With several regions, a new raid's ID comes from the global actor at the barrier, so it starts one tick after the omen triggers | Multi-region: a raid starts a tick late |
| Dragon fight (`EnderDragonFight`) | Region that owns chunk (0, 0) in the End. The main island is one loaded area, so it's one region (D47) | None |
| World border (`WorldBorder`) | Global. Regions read it from the snapshot for collision and damage | None |
| Maps (`MapItemSavedData`, `MapIndex`) | Lent. With several regions, map pixels and decorations are owned by the global actor. Each region sends its map updates at the barrier, applied in region ID order, and a new map's ID is given out at the barrier | Multi-region: map updates and new maps show up a tick later |
| Lodestone compasses, which check that their lodestone still exists | Region, reading a world-wide set of lodestone positions kept in the snapshot and updated at the barrier | Multi-region: a broken lodestone in another region is noticed a tick later |
| Structure searches: `/locate`, eyes of ender, explorer maps, dolphins | Region, reading a world-wide index of structure starts. Starts are fixed once generated, so the index only grows, and new ones join it at the barrier. A start that hasn't been generated is made by a worldgen worker while the region waits, as vanilla's main thread does | None |
| Points of interest: villages, bells, beds, portals, bees | Region, saved with the chunk. Every vanilla search is 128 blocks or less (D53) | None |

## Scoreboards, boss bars, players, chat

| System | Home | Difference |
| --- | --- | --- |
| Scoreboard objectives, teams and display slots (`ScoreboardSaveData`) | Global. Regions read them from the snapshot for collision rules, name tags and friendly fire | None |
| Scores | Lent. With several regions, an online player's or an entity's scores move with it, and other holders' scores (fake players like `#temp`, offline players) are global. Criteria updates (deaths, kills, statistics, health, XP) happen in the holder's region | Multi-region: follows the command rows for commands that read other holders |
| Score display packets | Fan-out | None |
| Custom boss bars (`CustomBossEvents`) | Global. Updates fan out | None |
| Player list: joining, leaving, tab list, latency, whitelist, ops, bans | Global. A joining player is placed in the region that owns their position | None |
| Chat, `/msg`, `/say`, `/me`, `/tellraw` | Handled in the sender's region (plugin events, filtering), then global, sorted by the packet's input sequence number, then fan-out in the same tick | None |
| World-wide level events (wither spawn, dragon death, end portal opening) and thunder | Fan-out | None |
| Advancements, statistics, recipe book | With the player | None |
| Respawning in another world or far away | Escalated from the packet phase, so the global phase moves the player to the target region in the same tick | None |

## Chunk tickets and crossing between regions

| System | Home | Difference |
| --- | --- | --- |
| Player tickets (view distance) and other tickets | Region that owns the chunk. A ticket for a chunk outside the region becomes a load request at the barrier, and the loaded chunk joins a region through the layout (D22, D47) | None |
| Forced chunks (`/forceload`, `TicketStorage`) | Global, saved. The layout reads them | None |
| Ender pearls: they load chunks as they fly, and are saved with their owner when the owner logs out | Region that owns the pearl. A pearl that lands in another region from its owner hands the owner over at the barrier. The owner keeps handles to their pearls, and logout and login remove and restore them by message | Multi-region: the owner arrives one tick late |
| Nether portals, end portals, end gateways | Handoff to the destination world's region, which finds or creates the portal, loading chunks while it waits as vanilla does | Multi-region (always, since another world is another region): arrival is one tick later |
| `/tp`, `/teleport`, `/spreadplayers`, plugin teleports | Escalated commands, so the global phase moves entities directly. From a command block, one tick late | Follows the command rows |
| Entities walking or flying into another region's chunks | Can't happen: regions merge before that (D47) | None |
| Vehicles with passengers, leashed mobs | Hand over together | None |

## Counters and randomness

| System | Home | Difference |
| --- | --- | --- |
| Entity network IDs (`ServerLevel.ENTITY_COUNTER`, one counter for the whole server) | Lent. With several regions, each region takes IDs from blocks the global actor hands out | Multi-region: IDs differ. Clients can't see it |
| Unique random seeds (`RandomSupport.generateUniqueSeed`, which mixes in `System.nanoTime()`), used for every entity's random and UUID | Lent, with a recorded starting value instead of the time, so runs repeat. The rig's vanilla adapter has to make vanilla repeat the same way (`P1.2`) | Multi-region: UUIDs and entity randoms differ |
| Loot random sequences (`RandomSequences`): mob drops, block drops and fishing all draw from one server-wide stream per loot table when the roll has no seed | Lent. With several regions, each region forks every sequence from the sequence's state and its region ID. Forks aren't saved, and the saved state is the global one. `/random` escalates | Multi-region: different drops |
| Level random (`Level.random`, one per world, seeded from the time in vanilla) | Per region. With one region it's vanilla's stream, seeded from the recorded seed. A region made by a split forks its parent's | Multi-region: different random numbers |

## Saving

| System | Home | Difference |
| --- | --- | --- |
| Autosave, `/save-all`, stopping | At the barrier: regions save their chunks in parallel, and the global actor saves level data and every saved world-wide store | None |

## What this means for the design

- **The global actor owns:** tick rate, clocks and time, weather, the world border, command storage, scoreboard objectives and teams and non-entity scores, custom boss bars, the player list, forced chunks, wandering trader data, the structure-start index, the lodestone set, map data with several regions, the spawners with several regions, and the server-wide counters and random sequences when they aren't lent.
- **Merge distance (D53).** Regions must be far enough apart that every bounded vanilla query is answered inside one region. The longest are mob despawning and local mob caps at 128 blocks, so the merge distance is at least 9 chunks. Phase 5 picks the final value.
- **Single-region runs are exact, and the rig tests them that way (D52).** Everything marked "multi-region" is the price of running regions in parallel, and it's all deterministic. The rig has a separate multi-region suite that checks determinism across thread counts, not equality with vanilla.

## Checks for the rig

- Every "None" row needs a case that would catch a mistake.
- The packet phase moved before functions and the world-wide steps on purpose. A case should show a player command reading game time sees vanilla's value.
- Vanilla's level random and unique seeds have to be fixed by the adapter before any case can compare them.
