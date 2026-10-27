---
title: Host API sketch
description: The one contract both native Calx plugins and WASM addons build against.
---

# Host API sketch

Status: skeleton. This is the one contract both plugin kinds build against. Native Calx bindings, WASM imports and the reference docs are all generated from it, so anything here must be expressible in both kinds of plugin.

## Rules

These come from `docs/decisions.md`:

- **Chunky calls.** One call moves a batch of data, not a single block.
- **Instances.** Each plugin runs as one instance per region plus one global instance, and the instances talk by messages (D16).
- **Limits.** Native plugins get only this API unless they're marked trusted in the server config (D15).
- **Handles, not pointers.** Entities, players, chunks and block entities are generational handles. A stale handle gives an error the plugin must handle (D24).
- **Semver.** A plugin built against major version N loads on any Calcite with the same major version (D35).
- **Documented.** Every function, type and event has a doc comment, and the build fails without one. The reference docs are generated from these comments (D41).

## What great plugin development needs from this API

These are the bar for the sketch. Each should be easy to write in a few lines.

- **Typed events** with priorities and cancellation. Handlers run in the region where the event happened.
- **Commands** declared as Brigadier-style trees, sent to the client so plugin commands get the same tab completion and argument checking as vanilla's
- **Persistent data** per player, entity, chunk and world, stored in Calcite's own files beside the world (D36). Data that has to travel with an item or entity uses vanilla's `custom_data` component.
- **Text** built from components, with a short formatting syntax for colors and styles
- **Scheduling** by tick, in the region or the global instance
- **Messaging** between a plugin's instances, including handing a player from one region to another
- **Inter-plugin APIs**: a plugin can export typed functions and messages for other plugins
- **Permissions**: permission nodes with defaults by op level
- **Custom content without client mods**: data components, item models, dialogs and data-pack registries
- **Profiling**: tick time per plugin and per handler, always on

## Calcite exposes

### World access

TBD

### Events

TBD

### Commands

TBD

### Scheduler

TBD

### Messaging between plugin instances

TBD: region instance to region instance, region to global, cross-region handoff (the teleport sample)

### Persistent data

TBD (the `/home` sample)

### Permissions

TBD

## Plugins expose

TBD: lifecycle (load, unload, state-migration hook for hot reload), event handlers, command handlers, exported APIs for other plugins
