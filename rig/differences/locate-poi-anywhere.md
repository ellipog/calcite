---
title: locate poi finds the nearest point of interest the level has, past 256 blocks too
kind: feature
cases:
  - session:locate/locate-far-lodestone/system_chat
---

# locate poi finds the nearest point of interest the level has, past 256 blocks too

**Vanilla:** `PoiManager.findClosestWithType` looks only within 256 blocks of the source, loading the chunks there to read theirs, and takes the nearest. Past that it's "not found", though the level holds points of interest farther off.

**Calcite:** `locate poi` reads in those within 256 first, as vanilla does, without holding the tick, and takes vanilla's pick where there's one ([D602](../../docs/decisions.md)). Where there's none so near, it takes the nearest of every point of interest the level holds, from the chunks loaded or read since it opened; where the level has none, the next dimension's, as `locate structure` and `locate biome` do. Nothing beyond 256 can be nearer than what's within it, so where vanilla finds one, Calcite finds the same.

On the `locate` session's world, the bot sets a lodestone beside it. From 1000 blocks east, vanilla's search has none; Calcite's finds it, 998 blocks away.

**Why:** Elliot asked for searches that do far better than vanilla's. Nothing in the world depends on where `locate poi` points.
