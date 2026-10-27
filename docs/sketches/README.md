---
title: Calcite sketches
description: Three pieces of Calcite core written in imagined Calx, to find out what the language needs before it exists.
---

# Calcite sketches

Three pieces of Calcite core, written in imagined Calx before the compiler exists (`P0.2`). Together with the [sample addons](../../plugins/samples/README.md), they're what `CALX_SPEC.md` v0 is written from.

| Sketch | What it shows | Follows in vanilla 26.3 |
| --- | --- | --- |
| [`tick-loop.calx`](tick-loop.calx) | The main loop, and one tick: inputs, the global phase, the region phase, message exchange (D20) | `MinecraftServer.runServer`, `tickServer`, `tickChildren`; the world-wide parts of `ServerLevel.tick` |
| [`region.calx`](region.calx) | One region actor and its tick | The region-local parts of `ServerLevel.tick` and `ServerChunkCache.tickChunks` |
| [`packet-handler.calx`](packet-handler.calx) | The movement packets, declared for packet codegen, and their handler | `ServerboundMovePlayerPacket`, `ServerGamePacketListenerImpl.handleMovePlayer` |

The vanilla order was read from the 26.3 server jar, decompiled locally into `oracle/decompiled/`, which stays out of the repo (D30). Where the sketches change vanilla's order, they say so in a comment, and the rig decides whether anyone can tell.

## Conventions

The same as the samples, plus what core code needs:

| Syntax | Meaning |
| --- | --- |
| `x: T` | A read-only view of a `T`. Small plain types are copied instead |
| `x: mut T` | A mutable view. The caller passes `mut value` |
| `x: own T` | Ownership moves in. The caller can't use the value afterwards |
| `checkout e = map[key] else ...` | Takes one element out of a collection until the end of the enclosing block, then puts it back in the same place in the order |
| `parallel(pool) for x in mut xs { }` | Runs the body for every element at once, each with exclusive access to its element |
| `actor struct` | A struct with an inbox and an outbox that the tick loop delivers between |
| `a?.b` | `b` if `a` has a value |
| `f64(x)`, `f32(n)` | Explicit numeric conversion. Calx never converts implicitly |
| `1.0e-5f32` | A literal with its type. Unsuffixed float literals are `f64` |

## What the sketches found

1. **Mutable views can't overlap, and that came up four times.** An entity's tick needs the entity and the region around it, both mutable, but the entity is inside the region. So does a packet handler with its player, an inbox handler with its region, and a scheduled-tick loop whose callback needs the region the ticks live in. Three fixes covered all of them:
   - **checkout** takes one element out of its collection for the rest of the block, so the element and its owner are separate values. The slot stays reserved, so the order (vanilla's entity tick order) is unchanged.
   - **take, then loop** moves the work out first (`r.inbox.take()`, `block_ticks.take_due(...)`), which is also how vanilla's `LevelTicks` does it.
   - **shared code in the snapshot**: plugin handlers keep no state (D42), so the dispatch table is read-only and lives in the tick snapshot, not in the region.
2. **The memory model needs no lifetimes (D48).** Values are owned. Parameters are read-only views, mutable views or moved ownership. Views are second-class, as in the plugin samples (D43), so they can't be stored and the compiler only has to check overlap within one function. That's enough for all three sketches.
3. **`parallel for` is the only parallelism for game state (D49).** The region phase is one loop over owned regions. The body gets exclusive access to its region, and everything else it touches must be read-only for the whole loop. The compiler checks the captures, so no locks are needed and the result doesn't depend on the thread count (D21).
4. **Actors are values with mailboxes, not threads.** A region is an `actor struct` in a map. The barrier code that collects outboxes and delivers messages is plain single-threaded code, so its order is easy to make fixed and easy to read.
5. **Not everything is an actor.** Network I/O (D33) and the chunk, lighting and worldgen workers run on their own threads. They talk to the tick loop through queues inside Calcite core, and what they produce enters as inputs at the start of a tick (D21). So `CALX_SPEC.md` should say actors are the only model *for game state*. The queues are runtime or `unsafe` code that plugins never see.
6. **Ownership moves make handoffs safe.** A handoff message owns the player or entity it carries. The sending region can't touch it afterwards, so a player is never in two regions.
7. **Region layout rule (D47).** Any two loaded chunks closer than the merge distance are in the same region. A contiguous loaded area is therefore one region, and anything ticking can only reach its own region's chunks. Things that jump across unloaded space (ender pearls, portals, teleports) are handoffs.
8. **Java-exact numbers show up everywhere, even in a movement handler.** `float * int` widened to `double` for a comparison, a float literal (`1.0E-5F`) widened to a double, clamping and degree wrapping. Calx has to keep literal types and never convert implicitly, so code like this says exactly what Java does.
9. **Vanilla's level random is seeded from `System.nanoTime()`.** So vanilla isn't repeatable run to run, and the rig's vanilla adapter has to set the seed (`P1.2`). Calcite records its seeds in the input log header.
10. **Cross-region effects can keep vanilla's arrival order.** Vanilla handles all packets in one queue in arrival order. Calcite splits them by region, which is fine for anything local, but chat from two regions in the same tick would arrive in region-ID order. Messages caused by a packet carry its input sequence number, and the global instance sorts broadcasts by it.
11. **Order differences for the rig and the global-systems inventory (`P0.4`):**
    - The scheduled-tick cap (65536 per world per tick) becomes per region.
    - Custom spawners (phantoms, patrols, cats, sieges, wandering traders) run in the global phase before the regions, not after the chunks tick.
    - Scheduled block and fluid ticks run at the start of each region's tick, after the world-wide steps, instead of between `tickTime` and raids.
    - Mob caps count other regions' mobs as of the last barrier.
    - The 300-tick empty-world timer that stops entity ticking is per region.
12. **One position packet per tick is new in 26.x.** A second one in a tick disconnects the client. Calcite's per-tick packet batches make this natural.

## What Calx needs (for `CALX_SPEC.md` v0)

On top of the samples' list:

- Parameter modes (read-only view, `mut`, `own`) and moves
- An overlap check for mutable views within a function, and `checkout`
- `parallel for` with the capture check, on a work-stealing pool in the runtime
- `actor struct`, with inboxes and outboxes the runtime can collect in a fixed order
- Tuples, destructuring, `if` as an expression, `continue`, `?.`
- Enums with an explicit representation (`enum MoveFlag: u8`) and bit sets over them
- Typed literals and no implicit numeric conversion
- String interpolation for plain strings (`log.warn("{p.name} moved wrongly!")`), not only `t"..."`
- `@packet` as a library-defined attribute that generates a reader and writer (the same mechanism the host API's attributes need)
