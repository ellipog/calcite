---
title: The server's brand is calcite
kind: identity
cases:
  - session:*/configuration/custom_payload
---

# The server's brand is `calcite`

**Vanilla:** the first packet of configuration is `minecraft:brand`, from `MinecraftServer.getServerModName()`, which is `vanilla`.

**Calcite:** the brand is `calcite` ([D132](../../docs/decisions.md)).

**Why:** a client shows the brand in its debug screen, and the server isn't vanilla. Plugins, bug reports and server lists can then tell which server they're talking to, as they can with every other server that isn't vanilla. Nothing in the client acts on the brand.

The protocol suites see it in every session that gets to configuration.
