---
title: Host API sketch
description: The one contract both native Calx plugins and WASM addons build against.
---

# Host API sketch

Status: v0 sketch (`P0.5`). This is the one contract both plugin kinds build against. Native Calx bindings, WASM imports and the reference docs are all generated from it, so everything here has to work in both kinds of plugin. The calls are written as a Calx plugin sees them, in the imagined syntax of the [sample addons](../samples/README.md). The real definition is written in Phase 7 (`P7.1`).

## Rules

These come from [`docs/decisions.md`](../../docs/decisions.md):

- **Chunky calls.** One call moves a batch of data, not a single block.
- **Instances.** Each plugin runs as one instance per region plus one global instance, and the instances talk by messages (D16). Region code keeps no state of its own (D42).
- **Views and handles.** Live objects are views that last one handler. Handles can be stored and sent (D24, D43). A stale handle gives an error the plugin must handle.
- **Limits.** Native plugins get only this API unless they're marked trusted in the server config (D15).
- **Determinism.** Randomness and time come from the host (D44). Results of plugin I/O are inputs (D21).
- **Semver.** A plugin built against major version N loads on any Calcite with the same major version (D35).
- **Documented.** Every function, type and event has a doc comment, and the build fails without one. The reference docs are generated from these comments (D41).

## What great plugin development needs from this API

These are the bar for the sketch. Each should take a few lines.

| Need | Where it's met |
| --- | --- |
| **Typed events** with priorities and cancellation, run in the region where the event happened | [Events](#events) |
| **Commands** declared as Brigadier-style trees and sent to the client, so plugin commands get the same tab completion and argument checking as vanilla's | [Commands](#commands) |
| **Persistent data** per player, entity, chunk and world, stored in Calcite's own files beside the world (D36). Data that has to travel with an item or entity uses vanilla's `custom_data` component | [Data](#persistent-and-session-data) |
| **Text** built from components, with a short formatting syntax for colors and styles | [Text](#text) |
| **Scheduling** by tick, in the region or the global instance | [Scheduling](#scheduling) |
| **Messaging** between a plugin's instances, including handing a player from one region to another | [Messages](#messages) |
| **Inter-plugin APIs**: a plugin can export typed functions and messages for other plugins | [Plugins expose](#plugins-expose) |
| **Permissions**: permission nodes with defaults by op level | [Permissions](#permissions) |
| **Custom content without client mods**: data components, item models, dialogs and data-pack registries | [Items](#items-and-custom-content) |
| **Profiling**: tick time per plugin and per handler, always on | [Limits and profiling](#limits-panics-and-profiling) |

## Two layers

The API has two layers, and only the lower one is the stable contract:

1. **The ABI.** Flat functions with plain arguments: integers, floats, handles (64-bit), byte buffers and UTF-8 strings as pointer and length. Native plugins get it as a table of function pointers. WASM addons get the same functions as imports from the module `calcite_v1`. It's versioned by the API major version, and minor versions only add functions. This layer is what semver (D35) covers.
2. **The `calcite` library.** What plugin code actually uses: views, attributes, `t"..."` text, typed events, the command tree from function signatures. It's compiled into the plugin and calls the ABI. It can change from release to release without breaking plugins that were already built. A WASM SDK for another language (`P9.6`) is its own library over the same ABI.

### How the library meets the ABI

- **Every call carries a context**: the handler invocation it came from. That's how the host knows the region, checks that a view is used in the right place, counts the time against the plugin and enforces budgets. A WASM plugin can't be trusted to keep views second-class, so the host checks at run time what the Calx compiler already checked.
- **Views are handles plus the context.** `Player` in a handler is the player's handle, valid only in that invocation and only in that region.
- **Saved data, session data and messages are bytes.** The library encodes them as an NBT compound keyed by field names. That's readable with ordinary NBT tools, takes new fields with their defaults, and is the same format whether the data is saved, kept for later delivery, or sent between regions. The host owns the bytes, so data can move with a player across regions and survive a plugin reload. The library decodes a value the first time a handler touches it and writes it back at the end of the handler if it changed.
- **Text crosses as NBT text components**, the same encoding the protocol uses since 1.20.3, so the host can check it and send it with no conversion.
- **Region instances are interchangeable.** Since region code keeps no state (D42), the host doesn't need one instance per region. It keeps one per worker thread and runs whichever region's work comes next. Splitting or merging regions costs plugins nothing.

## Where code runs

| Place | Runs | Can use |
| --- | --- | --- |
| `region { }` | Events, player commands, messages to a player or position, tasks on a player | Views of anything in the region, everything under "anywhere" |
| `global { }` | `@every` timers, messages to `global`, `@load` and `@unload` | Its own `@save` fields, the player directory, everything under "anywhere". No views: the global phase sees regions only through messages |
| Top level | Types, config, permissions, items, and commands the console can run | Only what works in both: `config`, `server`, `send`, the sender |

A player's command runs in the player's region during the packet phase. A console command runs at the barrier (D50). That's why a console-capable command only gets what works in both places.

## The manifest

The compiler turns the attributes into a manifest inside the plugin binary. The host reads it at load, before running any plugin code:

- `@plugin`: ID, name, version, API major version, dependencies
- Every `@command`: its path, argument types, permission and which context it runs in
- Every `@on`: the event and priority. The host only dispatches events a plugin subscribed to, so an unused event costs nothing
- Every `@permission`, `@item`, `@config`, `@save`, `@session` and `@message` type, with its schema
- Every `@export` and plugin-defined `@event`

## Server and time

| Call | Where | What it does |
| --- | --- | --- |
| `server.tick() -> Tick` | anywhere | Ticks since the world was created (vanilla's game time) |
| `server.now() -> Instant` | anywhere | Wall-clock time read once at the start of this tick and recorded in the input log (D44) |
| `server.players() -> List<PlayerInfo>` | anywhere | The player directory as of the start of this tick, in a fixed order. `PlayerInfo` has `ref`, `name()`, `uuid`, `world`, `location`, `block_position()` |
| `server.broadcast(text, permission: Permission? = none)` | anywhere | Sends to every online player, or every one with the permission. Fans out at the barrier, same tick |
| `server.broadcast_sound(sound, volume: f32 = 1.0, pitch: f32 = 1.0)` | anywhere | Plays a sound to every online player at their own position |
| `Tick`, `Ticks`, `Instant`, `Duration` | types | Game time and real time are different types, so they can't be mixed up. `Ticks.seconds(n)` is `20 * n` ticks |

## Players and handles

| Call | Where | What it does |
| --- | --- | --- |
| `p.ref() -> PlayerRef` | region | A handle to this player that can be stored and sent |
| `p.name() -> String`, `p.uuid() -> Uuid` | region | |
| `p.send(text)` | region | A system chat message |
| `p.location() -> Location`, `p.block_position() -> BlockPos`, `p.eye_position() -> Vec3` | region | `Location` is world, position and rotation, a plain value |
| `p.has(permission) -> bool` | region | |
| `p.heal(amount: f32)` | region | Health points, capped at max health |
| `p.teleport(to: Location)` | region | A request. Within the region it happens at once. Otherwise the player is handed over at the barrier, after the destination chunks load |
| `p.teleport_to(target: PlayerRef, on_fail: \|Player, TeleportError\|)` | region | Resolves `target`'s position at the barrier, so the player lands where the target is then |
| `p.after(ticks: Ticks, \|Player\| { }) -> Task` | region | See [Scheduling](#scheduling) |
| `p.data(T) -> view of T` | region | See [Data](#persistent-and-session-data) |
| `ref.name() -> String`, `ref.online() -> bool` | anywhere | From the directory. Works for offline players the server has seen |
| `ref == other` | anywhere | Handles compare by player |

Entities get the same shape: an `Entity` view with `kind`, `ref() -> EntityRef`, position, `data(T)`, and the living-entity calls (`heal`, effects, attributes) where the kind has them.

## World and blocks

| Call | Where | What it does |
| --- | --- | --- |
| `region.world -> World` | region | The world this region is in. A view |
| `world.block(pos) -> BlockState` | region | `state.is(Block.chest)` checks the block type |
| `world.set_block(pos, state, drops: bool = false)` | region | Updates neighbors and clients as vanilla's `setBlock` with its default flags does |
| `world.blocks(box) -> BlockBuffer`, `world.set_blocks(buffer)` | region | The chunky versions: one call for a whole box of block states |
| `world.top_y(x, z, Heightmap) -> i32` | region | The top block by one of vanilla's heightmaps |
| `world.block_entity(pos, T) -> T?` | region | A typed block entity handle, such as `Chest`, or none if it isn't one |
| `chest.set_loot_table(key, seed: i64)` | region | Loot rolled when first opened, as for dungeon chests |
| `world.chunk_at(pos) -> Chunk` | region | A view of the chunk, for `data(T)` |
| `world.play_sound(sound, at: Vec3, volume, pitch)`, `world.particles(particle, at, count, spread)` | region | Sent to players in range, as vanilla does |
| `region.random() -> Random` | region | This plugin's own stream in this region (D44) |
| `global.random() -> Random` | global | This plugin's own stream in the global instance |

A position outside the region's chunks is an error. With D47 that only happens when code tries to reach across unloaded space, which needs a message instead.

## Persistent and session data

| Declaration | Lives | Saved | Moves with |
| --- | --- | --- | --- |
| `@save(per: Player) struct T` | With the player, keyed by UUID | Beside the world (D36) | The player |
| `@save(per: Entity) struct T` | With the entity, keyed by UUID | Beside the world | The entity |
| `@save(per: Chunk) struct T` | With the chunk | Beside the world, with the chunk | The chunk, through splits and merges |
| `@session(per: Player) struct T` | With the online player | Never | The player, until they log out |
| `@save var x` in `global { }` | The global instance | Beside the world | Nothing, there's one |

- `x.data(T)` gives a view of the data, created with the field defaults the first time.
- Data that has to travel with an item, or survive a trip through vanilla on an entity, goes in vanilla's `custom_data` component instead.
- Adding a field is safe. `@was("old_name")` on a field reads data saved under its old name. `@migrate fn` on the type converts data from an older plugin version when the field types changed.
- Data is saved with the world's autosave and at shutdown.

## Config

- `@config struct Config` loads from `plugins/<id>/config.toml`. Missing keys take the field defaults, and the host writes a full file on first run.
- `config` is the same everywhere during a tick. A reload (`/calcite reload <plugin>`) takes effect at the barrier.
- `@derived` fields are computed after each load and shared read-only.
- A bad config fails the reload with the error shown, and the old config stays.

## Text

- `t"<green>Hello <white>{name}"` builds a text component at compile time. The tags are MiniMessage-like (colors, styles, `<click:...>` and `<hover:...>`), checked by the compiler. Interpolated strings are escaped. Interpolated `Text` is inserted as a component.
- `text.on_click(run: String)`, `on_click(suggest: String)`, `on_click(open_url: String)`, `text.on_hover(Text)`.
- `a + b` and `Text.join(separator, list)` combine text.
- `Text.translatable(key, args)` uses the client's language.

## Commands

- `@command(path, permission:)` on a function. The path's words are literals (`"chatfilter mute"`), and the parameters after the sender are arguments, in order. A parameter with a default is optional.
- The first parameter says who may run it: `Player` (only players, in their region), or `Sender` (players and the console, so the function must be at top level).
- Argument types come from vanilla's parsers (`i32` with bounds, `f64`, `bool`, `String` as a word, quoted string or greedy rest, `BlockPos`, `Vec3`, `Duration`, item, block and entity arguments) or from a plugin type implementing `Argument`:

```calx
interface Argument {
    const parser: Brigadier       // what the client checks as you type
    fn parse(raw: String) -> Self ! Text
    fn suggest(s: Suggest, sender: Player)
}
```

- `PlayerRef` arguments complete from every player the server has seen, online or offline, like `/ban`.
- Failing with `Text` shows it to the sender in red, as vanilla's command errors do.
- The host sends plugin commands to clients as part of vanilla's command tree, filtered by permission, so clients only see what they can run.

## Events

- `@on(Event, priority: early | normal | late | observe)` on a function in `region { }`.
- Handlers run in the region where the event happens, at the point in vanilla's code where it happens, before vanilla acts on the outcome.
- Within a priority, plugins run in a fixed order: dependencies first, then by plugin ID. Nothing depends on load timing.
- `early`, `normal` and `late` can change the outcome. `observe` runs last, sees the final outcome, and can't change it.
- A cancelled event stays cancelled unless a later handler explicitly un-cancels it.
- Events carry views for things in the region and snapshots for things that may be elsewhere.

The events the samples need:

| Event | Fields | Can change |
| --- | --- | --- |
| `PlayerMoveBlock` | `player`, `from`, `to: BlockPos`, `cause: MoveCause` (`Walk`, `Teleport`, `Vehicle`, `Pushed`) | cancel (puts the player back) |
| `PlayerChat` | `player`, `message: String` | `cancel()`, `mask(range)` (D45) |
| `EntityDeath` | `entity`, `player_kill: PlayerRef?` (a player hurt it in the last 100 ticks), `weapon: ItemStack?` (a snapshot), `drops: List<ItemStack>`, `xp: i32` | `drops`, `xp` |
| `ItemConsumed` | `player`, `item: ItemStack` | cancel (keeps the item, gives no food) |
| `ContainerOpen` | `player`, `block_position: BlockPos?`, `container` | cancel |

The first full set (Phase 7) also covers joining and leaving, block breaking and placing, interacting with blocks and entities, damage, inventory clicks, item drops and pickups, respawning, world changes, explosions and portals.

## Scheduling

| Call | Where | What it does |
| --- | --- | --- |
| `p.after(ticks: n) \|p\| { }` | region | Runs in whichever region the player is in when it fires. Dropped if they log out. Returns a `Task` |
| `e.after(ticks: n) \|e\| { }`, `chunk.after(...)` | region | The same for an entity or a chunk |
| `task.cancel()` | anywhere | `Task` is a handle, so it can be stored in session or saved data |
| `@every(ticks: n)` | global | A repeating timer in the global phase. `n` is read again after each run |

A task's closure can capture only values that can be sent (D43). The library encodes the captures, so a task survives its player moving to another region.

## Messages

| Call | Where | What it does |
| --- | --- | --- |
| `send player_ref Msg { }` | anywhere | To the player's region. Dropped if they're offline |
| `send player_ref Msg { }, offline: keep` | anywhere | Kept with their data until they join |
| `send global Msg { }` | region | To this plugin's global instance |
| `send region_at(world, pos, load: true) Msg { }` | anywhere | To the region that owns that chunk at delivery. Loads the chunk first |
| `send region_at(world, pos, load: false) Msg { }` | anywhere | Kept with the chunk until it next loads (D46) |
| `@receive fn f(p: Player, m: Msg)` | region | A message to a player |
| `@receive fn f(m: Msg)` | region or global | A message to a position, or to `global` |

- A message is handled the next time its destination runs (D50).
- Delivery is ordered by sender region, then send order (D20).
- `@message` types hold only sendable values: plain data and handles.

## Permissions

- `@permission("node", default: everyone | op | op(level))` declares a node.
- `p.has(node)` checks it.
- A permissions plugin can take over by exporting the `PermissionProvider` interface. The host then asks it, in the player's region, and caches answers until it says they changed.

## Items and custom content

- `@item("id") const X = CustomItem { base: Item.x, components: [...] }` declares an item made from a vanilla item and data components. Clients need no mod and no resource pack.
- The host marks each stack with `{"calcite:item": "<plugin>:<id>"}` in `custom_data`. `stack.is(X)` checks for it, and `X.stack(count:)` makes one.
- `Component.*` covers vanilla's data components (name, lore, rarity, glint, max stack size, consumable, food, item model, and the rest), generated from the 26.3 registries.
- Later (`P9.7`): dialogs, item models from a plugin-supplied resource pack, and data-pack registry entries (enchantments, loot tables, damage types).
- Plugins can ship a data pack in `plugins/<id>/data/`, loaded with the world's. The supply-drop loot table is one.

## Registries

Typed constants for everything in vanilla's registries, generated from the 26.3 data (Phase 2): `Block`, `Item`, `EntityKind`, `Enchantment`, `Sound`, `Particle`, `Heightmap`, `MobEffect`, and keys like `LootTableKey`, `WorldKey`. They're named by vanilla ID (`Item.red_dye`). Data-pack entries that aren't known at compile time are looked up by key at load.

## Plugin I/O

For HTTP, files in the plugin's own folder and databases:

- `http.get(url) then |response| { }` and the like start the I/O off the tick threads.
- The result comes back in a later tick as an input, recorded in the input log, so a replay gives the same result without doing the I/O again (D21).
- WASM addons get I/O only through these calls, and only with the capabilities the server config grants them. Trusted native plugins may also call C directly (D15).

## Plugins expose

- **Lifecycle:** `@load` and `@unload` functions in `global { }`.
- **Hot reload:** at a barrier, the host stops dispatching to the old version, keeps every plugin's data (it's bytes the host owns), swaps the code, and runs `@load` again. Region code has no state, so nothing else needs moving. The global instance's `@save` fields carry over through the same encoding, with `@was` and `@migrate` for changes.
- **Exported APIs:** `@export fn` and `@export interface` make functions callable by other plugins, with sendable arguments only. A call from region code runs the other plugin's region code in the same region and the same handler context, synchronously. The manifest lists exports, and a plugin declares the plugins it depends on.
- **Plugin events:** `@event struct E` declares an event other plugins can `@on`. `fire E { }` dispatches it in the current region, with the same priority rules.

## Limits, panics and profiling

- A panic in a handler stops that plugin instance, and its region keeps ticking. A plugin that keeps panicking is disabled (D25).
- Tick budgets: native plugins get budget checks at loop back-edges inserted by the compiler (`P7.3`). WASM uses the runtime's interruption. A handler over budget is stopped like a panic.
- Native plugins get only this API unless trusted (D15). WASM addons get only this API, ever.
- The host times every dispatch, so tick time per plugin and per handler is always available (`P7.6`).

## Versioning

- The manifest names the API major version. A plugin loads on any Calcite with the same major version (D35).
- Minor versions only add functions. `host.has(feature)` checks for one at run time, so a plugin can use new calls when they're there.
- Removing or changing a call needs a major version and a deprecation cycle. Deprecated calls warn at load.

## Coverage of the samples (G0.3)

Every call the five samples make, and where it's covered here:

| Sample | Calls | Sections |
| --- | --- | --- |
| Homes | `@config`, `@permission`, `@save`, `@session`, `Argument`, `Suggest.add`, `@command`, `p.data`, `p.has`, `p.location`, `p.send`, `p.teleport`, `p.after`, `Task.cancel`, `@on(PlayerMoveBlock)`, `MoveCause`, `on_click`, `on_hover`, `Text.join` | Config, Permissions, Data, Commands, Players, Scheduling, Events, Text |
| Chat filter | `@derived`, `@on(PlayerChat)`, `e.cancel`, `e.mask`, `server.broadcast(permission:)`, `server.now`, `Instant`, `Duration`, `Sender`, `PlayerRef` arguments, `send ..., offline: keep`, `@receive` | Config, Events, Server, Commands, Messages |
| Zombie heart | `@item`, `CustomItem`, `Component.*`, `@on(EntityDeath)`, `e.player_kill`, `e.weapon`, `enchantment_level`, `e.drops`, `HEART.stack`, `region.random`, `@on(ItemConsumed)`, `e.item.is`, `p.heal`, `p.eye_position`, `world.particles`, `EntityKind`, `Item`, `Enchantment`, `Particle` | Items, Events, World, Players, Registries |
| Teleport requests | `@message`, `send player_ref`, `@receive` with a player, `p.ref`, `p.name`, `ref.name`, `ref.online`, `p.teleport_to`, `TeleportError`, `p.after`, `LinkedMap` (standard library) | Messages, Players, Scheduling |
| Supply drops | `global { }`, `@save var`, `@every`, `server.players`, `PlayerInfo`, `global.random`, `send region_at(load:)`, `send global`, `server.broadcast`, `server.broadcast_sound`, `server.tick`, `world.top_y`, `Heightmap`, `world.set_block(drops:)`, `world.block`, `world.block_entity(_, Chest)`, `set_loot_table`, `@save(per: Chunk)`, `world.chunk_at`, `world.play_sound`, `@on(ContainerOpen)`, plugin data packs | Server, Messages, Data, World, Events, Items |

## Open questions

- **Asynchronous code over ticks.** `await` across ticks would make multi-step flows like the teleport requests read top to bottom (samples README).
- **Region caches.** If a real plugin needs per-region state, a cache the host may drop at any split or merge (D42).
- **Undeliverable messages.** Whether a plugin can ask to hear about a message that was dropped.
- **Cross-plugin calls between regions.** Only same-region calls are sketched. Anything else is a message.
