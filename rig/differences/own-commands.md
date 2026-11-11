---
title: Game masters and owners get Calcite's own commands too
kind: identity
cases:
  - session:select/*/commands
  - session:mites/*/commands
  - session:end/*/commands
  - session:crystals/*/commands
  - session:gateways/*/commands
  - session:eyes/*/commands
  - session:throws/*/commands
  - session:locate/*/commands
---

# Game masters and owners get Calcite's own commands too

**Vanilla:** the commands packet a player gets is the dedicated server's command tree, copied for their permission level by `Commands.fillUsableCommands`. At level 4 that's 2399 nodes.

**Calcite:** the same nodes, in the same order. After vanilla's come Calcite's own: `calcite flyspeed` and `calcite dimension` and the `gmc`, `gms`, `gma` and `gmsp` shortcuts for game masters, and `pregen` for owners. At level 4 that's 2522 nodes, and the root has six more children ([D552](../../docs/decisions.md), [D553](../../docs/decisions.md)).

**Why:** a client only offers and checks the commands it's sent, so Calcite's own commands have to be in the tree for players who may use them. Players below level 2 get vanilla's packet exactly, as the `talk` session shows.

The `select`, `mites`, `end`, `crystals`, `gateways`, `eyes` and `throws` sessions' bot is an operator, so its commands packet at the join shows this.
