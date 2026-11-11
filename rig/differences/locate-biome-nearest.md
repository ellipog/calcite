---
title: locate biome finds the nearest anywhere, at the biome's edge, and in the dimension that has it
kind: feature
cases:
  - session:locate/locate-plains/system_chat
  - session:locate/locate-forest/system_chat
  - session:locate/locate-mushrooms/system_chat
  - session:locate/locate-deep-dark/system_chat
  - session:locate/locate-crimson/system_chat
  - session:locate/locate-nether-crimson/system_chat
---

# locate biome finds the nearest anywhere, at the biome's edge, and in the dimension that has it

**Vanilla:** `BiomeSource.findClosestBiome3d` samples every 32 blocks across and 64 up, in a square spiral out to 6400 blocks, and takes the first sample with the biome. That can be farther than one later in the spiral, and it's on the 32-block grid, up to 32 blocks short of where the biome starts. Past 6400 blocks, or where the dimension has no such biome, such as a crimson forest from the Overworld, it's "not found". The tick waits for the whole search.

**Calcite:** `locate biome` runs its own search ([D601](../../docs/decisions.md)). It samples the same places, with the samplers' caches on as vanilla's are, in squares outward, and keeps the nearest by the distance the message shows until no square left could hold one nearer, with no limit. Then it samples every quart within a step of what it found and takes the nearest of those, at its block nearest the source. So the answer is never farther than vanilla's, and it's at the biome's edge. Where the dimension hasn't the biome, it searches the one that has, as `locate structure` does ([locate-nearest](locate-nearest.md)), and it runs off the tick the same way.

On the `locate` session's world, Calcite finds plains at 1221 blocks against vanilla's 1289, the forest tag's grove at 997 against 1018, mushroom fields at 4313 against 4324, the deep dark at 1259 against 1298, and a crimson forest in the Nether, 48 away, where vanilla's has none; searched for in the Nether itself, vanilla's finds one 71 away, on its grid. The session then searches from each place Calcite found, and vanilla's search finds the same biome there, 0 blocks away.

**Why:** Elliot asked for searches that do far better than vanilla's. Nothing in the world depends on where `locate biome` points.
