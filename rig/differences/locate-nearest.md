---
title: locate structure finds the nearest anywhere, and in the dimension that has it
kind: feature
cases:
  - session:locate/locate-village/system_chat
  - session:locate/locate-villages/system_chat
  - session:locate/locate-treasure/system_chat
  - session:locate/locate-mansion/system_chat
  - session:locate/locate-city/system_chat
  - session:locate/locate-fortress/system_chat
---

# locate structure finds the nearest anywhere, and in the dimension that has it

**Vanilla:** `ChunkGenerator.findNearestMapStructure` searches squares of sectors outward from the source, out to 100. It stops at the first square where any set finds one, and each set takes the first it finds on that square, not the nearest. A structure that could be nearer on the next square is never looked at. A structure the source's dimension doesn't place, such as a fortress from the Overworld, is "not found". The server's tick waits for the whole search.

**Calcite:** `locate structure` runs its own search ([D600](../../docs/decisions.md)). It takes the squares of sectors outward, always for the set whose next square could hold something nearer, and tries each square's chunks nearest first. It stops once no square left could hold one nearer. So it finds the nearest by the distance the message shows, with no limit. Where the source's dimension doesn't place the structure, it searches the dimension that does, from the source's position scaled to it, and says which dimension, with a click that teleports there. The tick waits 25 ms; a search that takes longer answers when it's done, and the tick goes on. The message keys are vanilla's, so clients translate them.

On the `locate` session's world, Calcite finds a plains village at 2025 blocks against vanilla's 2276, the village tag's at 649 against 710, buried treasure at 675 against 694, a mansion at 4644 against 5472, an ancient city at 2217 against 2255, and the fortress in the Nether at 236 where vanilla's has none. The session then searches from each place Calcite found, and vanilla's search finds the same structure there, 0 blocks away.

**Why:** Elliot asked for searches that do far better than vanilla's: a search that says "not found" for something that's there, or names one farther than another, is a worse tool, and nothing in the world depends on it. An eye of ender's search changes where the eye flies, which players see, so it stays vanilla's.
