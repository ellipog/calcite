---
title: Sample addons
description: Five small plugins written in imagined Calx, used to design the language and the host API, and later to test the plugin host.
---

# Sample addons

These five plugins were written first, in imagined Calx syntax, before the language or the host API existed (`P0.1`). Writing them showed what both need. In Phase 7 they're ported to the real syntax and become the plugin host's acceptance test (G7.1), and in Phase 9 they become tutorials.

| Addon | Stresses | File |
| --- | --- | --- |
| Homes | Commands, persistent per-player data, teleporting | [`homes/homes.calx`](homes/homes.calx) |
| Chat filter | Events that can cancel or change what happens, string handling | [`chatfilter/chatfilter.calx`](chatfilter/chatfilter.calx) |
| Zombie heart (custom mob drop) | Entity and loot events, making an item | [`zombieheart/zombieheart.calx`](zombieheart/zombieheart.calx) |
| Teleport requests (cross-region teleport) | Messages between region instances, handing a player to another region | [`tpa/tpa.calx`](tpa/tpa.calx) |
| Supply drops (timed world event) | Scheduler, the global instance, broadcasting to every region | [`supplydrop/supplydrop.calx`](supplydrop/supplydrop.calx) |

None of this compiles yet. The syntax is a draft for `CALX_SPEC.md` v0 to settle, and the calls are a draft for the host API sketch ([`../api/HOST_API.md`](../api/HOST_API.md)).

## How a plugin is laid out

A plugin is one module with an `@plugin(...)` declaration. Its code goes in three kinds of place:

- **`region { ... }`** holds handlers that run inside a region: events, player commands, and messages sent to a player or a position. There is one copy per region (D16), but it has no fields. Inside it, `region` is the current region.
- **`global { ... }`** holds the global instance: timers, world-wide state, and messages sent to `global`. There is exactly one. Inside it, `global` is the instance itself.
- **Top level** holds types, config, permissions, items, and functions that work anywhere. A command that the console can run lives here too, because a player's command runs in their region and the console's runs in the global instance, so its body can use only what both have.

Three names are always available: `config` (the plugin's config, the same for every region during a tick), `server` (the player directory, broadcasts and time) and the plugin's own declarations.

## Syntax used in the drafts

| Syntax | Meaning |
| --- | --- |
| `let x = ...`, `var x = ...` | An immutable or a mutable binding |
| `T?`, `none`, `if let x = opt { }` | An optional value. There is no null (D23) |
| `let x = opt else <return, fail or similar>` | Unwraps an optional or leaves the function |
| `a ?? b` | `a` if it has a value, otherwise `b` |
| `fn f() -> T ! E`, `fail e` | A function that can fail with an `E` instead of returning a `T` |
| `t"<green>Hi {name}"` | A text component. Tags are checked at compile time, and interpolated strings are escaped, so a player's name can't inject formatting. Interpolated `Text` values are inserted as components |
| `\|p\| { ... }`, `p.after(ticks: n) \|p\| { ... }` | A closure, and a closure passed as the last argument |
| `@attribute(args)` | An attribute that the host API gives meaning to, such as `@command` or `@save` |
| `send target Msg { ... }` | Sends a message to a player, `global`, or `region_at(world, pos)` |
| `struct Name(String)`, `name.0` | A one-field wrapper type |
| `Item.red_dye`, `EntityKind.zombie` | A constant generated from vanilla's data, named by its vanilla ID. Hand-written enums, like `MoveCause.Walk`, use capitals |

### Attributes the host API defines

| Attribute | On | Meaning |
| --- | --- | --- |
| `@plugin(id:, name:, version:, api:)` | the module | Plugin metadata. `api` is the host API major version (D35) |
| `@config` | a struct | Loaded from `plugins/<id>/config.toml`, with the field defaults filling gaps. A reload takes effect at the tick barrier |
| `@derived` | a config field | Computed from the other fields each time the config loads, then shared read-only |
| `@permission(node, default:)` | a `const` | Declares a permission node, with `everyone` or `op` as the default |
| `@save(per: Player \| Chunk \| Entity)` | a struct | Persistent data attached to that object, in Calcite's files beside the world (D36) |
| `@session(per: Player)` | a struct | Data attached to an online player, never saved |
| `@save var` | a global field | Persistent global state |
| `@message` | a struct | A type that can be sent between instances |
| `@item(id)` | a `const` | A custom item, made from a vanilla item and data components |
| `@command(path, permission:)` | a function | A command. The path and the parameters make the Brigadier tree |
| `@on(Event, priority:)` | a function | An event handler |
| `@receive` | a function | Handles a message, chosen by the message type |
| `@every(ticks:)` | a global function | A timer in the global phase |

## What the drafts found

These are the design results. The ones that are now decisions are logged in [`../../docs/decisions.md`](../../docs/decisions.md).

1. **Regions keep no plugin state (D42).** Regions split and merge (D22), so state kept per region would need plugin code to split and merge it. None of the five needed it. State lives on players, chunks and entities (and moves with them), in the global instance, or in the config, whose derived values are shared read-only.
2. **Views and handles (D43).** `Player`, `Region`, chunk data and other live objects are *views*: references that can't be stored, captured by a closure or sent. They're valid only in the handler that got them, which is what makes region scoping a compile-time check. `PlayerRef` and other handles (D24) can be stored and sent, and resolving one gives a view only in the region where the object is. Plugin code never writes a lifetime.
3. **Closures that run later capture only values that can be sent.** A task or callback can fire after the player has moved to another region, so it gets the player back as a fresh view (`p.after(...) |p| { ... }`) instead of capturing the old one. The compiler checks the captures.
4. **Randomness and time come from the host (D44).** Each plugin has its own random stream per region and one in the global instance, never vanilla's, so installing a plugin doesn't change what vanilla rolls next. `server.now()` is the wall-clock time captured once at the start of the tick and recorded in the input log, so replays match (D21).
5. **Chat is filtered by masking (D45).** Changing a signed chat message breaks its signature. The filter masks ranges with vanilla's own filter mask, which the client shows as `####`. The host converts UTF-8 byte ranges to the UTF-16 positions the protocol uses.
6. **Messages have explicit delivery rules (D46).** A message sent in tick N is handled in tick N+1. To a player it goes wherever they are, and if they're offline it's dropped, or kept until they join with `offline: keep`. To a position it goes to whichever region owns that chunk at delivery, and if the chunk isn't loaded the sender chooses `load: true` (load it, then deliver) or `load: false` (deliver when it next loads).
7. **Events carry snapshots of facts from other regions.** A zombie can die to an arrow shot from another region, so `EntityDeath` carries the killer as a `PlayerRef` and a copy of the weapon, instead of the handler reaching across regions.
8. **Teleporting is a request resolved at the tick barrier.** `p.teleport(location)` and `p.teleport_to(player_ref)` hand the player over to another region or dimension if needed, loading chunks first. `teleport_to` uses the target's position at the barrier. Failures come back to a callback in the player's region.
9. **Every region can read a player directory.** Names, handles, worlds and positions, snapshotted at the start of each tick, in a fixed order. Commands use it to resolve player arguments, and the global instance uses it to pick players.
10. **Coarse events keep handlers cheap.** `PlayerMoveBlock` fires only when a player enters a new block. Movement handlers are the most common source of plugin lag on other servers.
11. **Attributes need a codegen mechanism in Calx.** Nearly every host API feature here is an attribute (`@command`, `@save`, `@message` and the rest). Calx needs a way for a library to define attributes that generate code at compile time, the same mechanism packet codegen (`P4.1`) needs, so the host API isn't hard-coded into the compiler.
12. **Vanilla parity issues for the global systems inventory (`P0.4`).** Entity selectors (`@a[distance=..10]`, `@p`) and player-name arguments have to see players in every region, and broadcasts have to reach every region on the same tick.

## What Calx needs (for `CALX_SPEC.md` v0)

- Modules and imports, free functions, named arguments and default parameter values
- Structs with field defaults, one-field wrapper structs, enums, and `match` with patterns for enums and optionals
- Equality, hashing and ordering worked out for plain types, so a `HomeName` can be a map key
- A way for a type to say how it appears in text, so `{config.mute_for}` can be interpolated
- Interfaces with associated constants (`Argument`'s `parser`), and generics (`List<T>`, `Map<K, V>`, `SortedMap`, `LinkedMap`)
- Optionals with `if let`, `let ... else`, `??` and `map`/`or`, and comparing a `T?` with a `T`
- Error types (`! E`, `fail`), so a command can fail with a message
- Closures, trailing-closure syntax, and a capture check for closures that run later
- Views as second-class references, so plugin code needs no lifetimes
- A "can be sent" property the compiler works out for each type: plain data and handles yes, views and closures no
- `send` as part of region actors, with destinations given by the library
- Library-defined attributes and compile-time codegen, and library-defined string-literal prefixes such as `t"..."` that are checked at compile time
- `let`/`var`, `+=`, `and`/`or`/`not`, `for ... in`, and explicit numeric conversions like `f64(x)`

## What the host API needs (for `HOST_API.md`)

- **Plugin and config:** metadata, TOML config with defaults, reload at the tick barrier, derived config values
- **Permissions:** nodes, `everyone`/`op` defaults, `has`
- **Data:** saved data per player, chunk and entity, session data per player, saved global state, and adding fields without breaking old data
- **Commands:** literal paths, typed arguments with defaults, the `Argument` interface (client parser, parse, suggest), player and console senders, failure messages, `PlayerRef` arguments for online or offline players
- **Text:** tagged literals, click and hover actions, joining and appending
- **Players:** `send`, `name`, `ref`, `location`, `block_position`, `eye_position`, `has`, `heal`, `teleport`, `teleport_to`, `after`, `data`
- **Tasks:** per-player delayed tasks that move with the player and can be cancelled, and global timers
- **Events:** `PlayerMoveBlock` with its cause, `PlayerChat` (cancel, mask), `EntityDeath` (kind, player kill, weapon snapshot, drops), `ItemConsumed`, `ContainerOpen`, with priorities
- **Items:** custom items from vanilla items and data components, `is`, `stack`
- **World:** `top_y` by heightmap, `block`, `set_block` (with or without drops), typed `block_entity`, `chunk_at`, `play_sound`, `particles`
- **Loot:** loot tables and seeds on containers, and plugin data packs
- **Messages:** to a player (drop or keep when offline), to `global`, to a position (load or wait), `@receive` handlers
- **Server:** the player directory, `broadcast` (optionally to a permission), `broadcast_sound`, `now`, `tick`
- **Randomness:** `region.random()`, `global.random()`
- **Registries:** typed constants for entity kinds, items, blocks, enchantments, sounds, particles and heightmaps, generated from the 26.3 data (Phase 2)

## Open questions

- **Waiting across ticks.** The teleport-request flow is spread over five handlers. Something like `await` over ticks would let it read top to bottom. Revisit once Phase 7 shows how often plugins need it.
- **Region caches.** If a real plugin needs per-region state, add a cache the host may throw away at any split or merge. None of the samples needed one.
- **Undeliverable messages.** A message to a player who logged out is dropped silently. A plugin might want to know.
- **Kept messages and plugin updates.** A message kept for an unloaded chunk or an offline player may outlive the plugin version that sent it, so message types need the same rules for adding fields as saved data.
- **Renaming saved fields.** Adding a field is safe. Renaming one needs a way to say what it was called before.
