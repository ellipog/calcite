# Host API sketch

Status: skeleton. This is the one contract both plugin kinds build against. Native Calx bindings and WASM imports are both generated from it, so anything here must be expressible in both.

Rules (D14 to D16 in `docs/decisions.md`):

- Calls are chunky: one call moves a batch of data, not a single block
- Each plugin runs as one instance per region plus one global instance, talking by messages
- Native plugins get only this API unless marked trusted in the server config

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

## Plugins expose

TBD: lifecycle (load, unload, state-migration hook for hot reload), event handlers, command handlers
