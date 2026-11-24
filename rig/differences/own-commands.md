---
title: Game masters and owners get Calcite's own commands too
kind: identity
cases:
  - session:*/*/<own commands>
---

# Game masters and owners get Calcite's own commands too

**Vanilla:** the commands packet a player gets is the dedicated server's command tree, copied for their permission level by `Commands.fillUsableCommands`. At level 4 that's 2399 nodes.

**Calcite:** vanilla's tree, in vanilla's order. After vanilla's come Calcite's own: `calcite flyspeed` and `calcite dimension` and the `gmc`, `gms`, `gma` and `gmsp` shortcuts for game masters, and `pregen` for owners. At level 4 that's 2522 nodes, and the root has six more children ([D552](../../docs/decisions.md), [D553](../../docs/decisions.md)).

**Why:** a client only offers and checks the commands it's sent, so Calcite's own commands have to be in the tree for players who may use them. Players below level 2 get vanilla's packet exactly, as the `talk` session shows.

A session whose bot is an operator shows this at the join. The comparison takes Calcite's own commands out of its tree and drops the nodes only they reach. It puts `gamerule`'s children in order by name on both sides, since vanilla's come in the order of its `GameRuleMap`, a map by identity whose order changes from run to run. Then it numbers the nodes again as the packet does, `enumerateNodes`, and compares what's left with vanilla's packet. The names it took out stand on their own as `<own commands>`, which this covers ([CAL-325](https://acta.aaenz.no/aaen-studios/calcite#CAL-325)).

What's left still differs in two ways, which are bugs and not covered. Vanilla adds some nodes under more than one parent, such as `execute store`'s `byte` to `double` with their `scale`, and its packet writes each once; Calcite's tree copies them, 2471 nodes to vanilla's 2399 ([CAL-345](https://acta.aaenz.no/aaen-studios/calcite#CAL-345)). And Calcite offers `gamerule max_minecart_speed`, which vanilla offers only with `minecart_improvements` on ([CAL-346](https://acta.aaenz.no/aaen-studios/calcite#CAL-346)).
