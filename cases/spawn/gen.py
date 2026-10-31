"""Writes cases/spawn/generated.json: where vanilla's `PlayerSpawnFinder` puts a player new to the
world, over chunks the cases make.

    py -I cases/spawn/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.

The states are 26.3's, picked for what the finder makes of them: ground a player stands on, full
or not, as stone, glass, soul sand, mud and paths are; tops a player can't stand on all of, as
leaves, cactus, slabs and stairs set one way or another, snow layers, fences, walls, beds, chests
and hoppers have; blocks with no collision, as torches, grass, cobwebs, scaffolding and powder
snow have here; liquids, still and flowing, blocks that hold them, as kelp and waterlogged slabs
do, and the blocks they stand on; and blocks whose collision reaches out of their block, as
fences and walls do. The cases put each in columns of a flat world and ask what the finder makes
of them, then search for a spawn in flat worlds, in oceans with every candidate under water or
with islands among them, in worlds filled to the top, and over terrain at random, from places
and with radii and offsets at random, up to the 1024 candidates a search takes at most.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261031

AIR, STONE, GRASS_BLOCK, DIRT, BEDROCK, SAND, OAK_PLANKS = 0, 1, 9, 10, 88, 121, 15
OAK_LEAVES, GLASS, ICE, MAGMA, SLIME, HONEY, SOUL_SAND, MUD = 294, 661, 8597, 16826, 14379, 25173, 8668, 33772
FARMLAND, DIRT_PATH, CACTUS, SNOW_BLOCK, POWDER_SNOW = 6875, 16796, 8599, 8598, 30519
SLAB_BOTTOM, SLAB_TOP, SLAB_DOUBLE, SLAB_BOTTOM_WET, SLAB_TOP_WET = 15180, 15178, 15182, 15179, 15177
STAIRS_BOTTOM, STAIRS_TOP = 5474, 5524
SNOW_1, SNOW_2, SNOW_8 = 8589, 8590, 8596
CARPET, FENCE, FENCE_GATE, FENCE_GATE_OPEN, WALL = 14743, 8666, 10387, 10385, 11726
CHEST, END_PORTAL_FRAME, BED, HOPPER, LANTERN, TORCH, COBWEB = 5544, 11207, 2257, 13080, 24197, 4926, 2362
SCAFFOLDING, BAMBOO, DRIPSTONE, SULFUR_SPIKE = 24094, 18636, 33571, 33591
WATER, WATER_FLOWING, LAVA, KELP, SEAGRASS, BUBBLES = 89, 92, 105, 18419, 2370, 18651
MOVING_PISTON, BIG_DRIPLEAF, CAULDRON, COMPOSTER, LADDER, END_ROD = 3801, 33714, 11194, 25100, 7308, 16615
SHORT_GRASS, TALL_GRASS, VINE, GLASS_PANE, SHULKER_BOX = 2363, 14771, 10123, 10065, 16849
TRAPDOOR_TOP, TRAPDOOR_BOTTOM, DAYLIGHT_DETECTOR, ANVIL, CAMPFIRE = 8791, 8799, 13062, 12962, 24237
CAVE_AIR, VOID_AIR, PISTON_HEAD, CHAIN, LILY_PAD, SEA_PICKLE = 18650, 18649, 2387, 9983, 10654, 18624

# A player stands on all of these' tops.
GROUND = [STONE, GRASS_BLOCK, DIRT, BEDROCK, SAND, OAK_PLANKS, GLASS, ICE, MAGMA, SLIME, HONEY, SOUL_SAND,
          MUD, FARMLAND, DIRT_PATH, SNOW_BLOCK, SLAB_DOUBLE, SLAB_TOP, SLAB_TOP_WET, STAIRS_TOP, SNOW_8,
          TRAPDOOR_TOP, CHEST, SHULKER_BOX]
# Blocks with some collision that isn't a whole top, or none, or that reach out of their block.
SHAPED = [OAK_LEAVES, CACTUS, SLAB_BOTTOM, SLAB_BOTTOM_WET, STAIRS_BOTTOM, SNOW_1, SNOW_2, POWDER_SNOW,
          CARPET, FENCE, FENCE_GATE, FENCE_GATE_OPEN, WALL, END_PORTAL_FRAME, BED, HOPPER, LANTERN,
          SCAFFOLDING, BAMBOO, DRIPSTONE, SULFUR_SPIKE, MOVING_PISTON, BIG_DRIPLEAF, CAULDRON, COMPOSTER,
          LADDER, END_ROD, GLASS_PANE, TRAPDOOR_BOTTOM, DAYLIGHT_DETECTOR, ANVIL, CAMPFIRE, PISTON_HEAD,
          CHAIN, LILY_PAD, SEA_PICKLE]
# Nothing to collide with.
OPEN = [AIR, CAVE_AIR, VOID_AIR, TORCH, COBWEB, SHORT_GRASS, TALL_GRASS, VINE]
# Liquids, and blocks that hold them.
WET = [WATER, WATER_FLOWING, LAVA, KELP, SEAGRASS, BUBBLES]
EVERY = GROUND + SHAPED + OPEN + WET
POOL = GROUND * 2 + SHAPED + OPEN * 3 + WET

MIN_Y, TOP = -64, 319


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def between(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def seed(self):
        """A long for the probe's LCG, as a string."""
        x = self.u64()
        return str(x - (1 << 64) if x >= 1 << 63 else x)


class World:
    """A case's chunks, as its operations make them, so each search can be checked to stay in them."""

    def __init__(self, name):
        self.name = name
        self.chunks = set()
        self.ops = []

    def chunk(self, cx, cz):
        assert (cx, cz) not in self.chunks
        self.chunks.add((cx, cz))
        self.ops.append(["chunk", cx, cz])

    def square(self, radius, cx=0, cz=0):
        for x in range(cx - radius, cx + radius + 1):
            for z in range(cz - radius, cz + radius + 1):
                self.chunk(x, z)

    def has(self, x, z):
        return (x >> 4, z >> 4) in self.chunks

    def fill(self, x0, y0, z0, x1, y1, z1, state):
        self.ops.append(["fill", x0, y0, z0, x1, y1, z1, state])

    def set(self, x, y, z, state):
        self.fill(x, y, z, x, y, z, state)

    def flat(self, x0, z0, x1, z1):
        """The classic flat preset's layers, bedrock, two of dirt and grass, in strips of 256."""
        for xs in range(x0, x1 + 1, 256):
            for zs in range(z0, z1 + 1, 256):
                xe, ze = min(xs + 255, x1), min(zs + 255, z1)
                for i, s in enumerate([BEDROCK, DIRT, DIRT, GRASS_BLOCK]):
                    self.fill(xs, MIN_Y + i, zs, xe, MIN_Y + i, ze, s)

    def bounds(self):
        xs = [cx for cx, _ in self.chunks]
        zs = [cz for _, cz in self.chunks]
        return min(xs) * 16, min(zs) * 16, max(xs) * 16 + 15, max(zs) * 16 + 15

    def search(self, x, y, z, radius, offset):
        """A search, its every candidate's chunk checked to be one the case made."""
        side = radius * 2 + 1
        count = min(1024, side * side)
        assert 0 <= offset < count
        coprime = count - 1 if count <= 16 else 17
        for i in range(count):
            v = (offset + coprime * i) % count
            assert self.has(x + v % side - radius, z + v // side - radius), (self.name, x, z, radius)
        assert self.has(x, z)
        self.ops.append(["search", x, y, z, radius, offset])

    def look(self, x, z, ys):
        """What the finder makes of a column: where it's stood on, and whether a player fits at each y."""
        self.ops.append(["respawn", x, z])
        for y in ys:
            self.ops.append(["fits", x, y, z])

    def case(self):
        return {"id": self.name, "input": {"ops": self.ops}}


def count_of(radius):
    side = radius * 2 + 1
    return min(1024, side * side)


def random_search(w, g, radius, y=None):
    """A search from a place at random whose square is in the case's chunks."""
    x0, z0, x1, z1 = w.bounds()
    # The candidates take whole rows from the square's least z, as many as 1024 reach.
    side = radius * 2 + 1
    rows = (count_of(radius) - 1) // side + 1
    x = g.between(x0 + radius, x1 - radius)
    z = g.between(z0 + radius, z1 - max(rows - 1 - radius, 0))
    w.search(x, g.between(MIN_Y - 64, TOP + 64) if y is None else y, z, radius, g.below(count_of(radius)))


def flat(g):
    """A flat world: searches of every radius from places on it, above it and below it."""
    w = World("flat")
    w.square(3)
    w.flat(-48, -48, 63, 63)
    w.search(0, -60, 0, 0, 0)
    w.search(0, 100, 0, 0, 0)
    w.search(0, -128, 0, 0, 0)
    for offset in range(9):
        w.search(0, -60, 0, 1, offset)
    for radius in [2, 3, 5, 10, 15, 16, 20, 32]:
        for _ in range(3):
            random_search(w, g, radius)
    for x, z in [(0, 0), (-1, -1), (15, 15), (16, -17), (-48, 63), (63, -48)]:
        w.look(x, z, [-62, -61, -60, -59])
        for y in [-128, -127, -65, -64, -61, -60, -59, 0, 319, 320, 383]:
            w.ops.append(["fixup", x, y, z])
    return w.case()


def columns(g, name, pattern):
    """Every state in a column of a flat world, as `pattern` sets it, each three blocks apart, and
    what the finder makes of each: where it's stood on, where a player fits, where the spawn
    moves to there, and a search of radius 0 from it."""
    w = World(name)
    w.square(2)
    w.flat(-32, -32, 47, 47)
    for i, s in enumerate(EVERY):
        x, z = -30 + 3 * (i % 25), -30 + 3 * (i // 25)
        for dy, state in pattern(s):
            w.set(x, -60 + dy, z, state)
    for i, s in enumerate(EVERY):
        x, z = -30 + 3 * (i % 25), -30 + 3 * (i // 25)
        w.look(x, z, range(-63, -54))
        w.ops.append(["fixup", x, -60, z])
        w.ops.append(["fixup", x, -40, z])
        w.ops.append(["fixup", x, -64, z])
        w.search(x, -60, z, 0, 0)
        w.search(x, -58, z, 1, g.below(9))
    return w.case()


PATTERNS = [
    ("columns-ground", lambda s: [(-1, s)]),
    ("columns-on", lambda s: [(0, s)]),
    ("columns-two", lambda s: [(0, s), (1, s)]),
    ("columns-high", lambda s: [(10, s)]),
    ("columns-over-water", lambda s: [(0, WATER), (1, s)]),
    ("columns-under-water", lambda s: [(0, s), (1, WATER)]),
    ("columns-over-air", lambda s: [(-1, AIR), (-2, AIR), (0, s)]),
    ("columns-on-fence", lambda s: [(0, FENCE), (1, s)]),
    ("columns-under-slab", lambda s: [(0, s), (2, SLAB_BOTTOM)]),
    ("columns-low-ceiling", lambda s: [(0, s), (2, STONE)]),
]


def beside(g):
    """States next to a column, and below and beside it, where a player's box reaches into theirs
    only if their collision reaches out of their block."""
    w = World("beside")
    w.square(2)
    w.flat(-32, -32, 47, 47)
    spots = []
    for i, s in enumerate(SHAPED + GROUND[:6]):
        x, z = -30 + 4 * (i % 19), -30 + 4 * (i // 19)
        for dx, dy, dz in [(1, 0, 0), (-1, 1, 0), (0, 0, 1), (0, 1, -1), (1, -1, 1), (-1, 0, -1)]:
            w.set(x + dx, -60 + dy, z + dz, s)
        spots.append((x, z))
    for x, z in spots:
        w.look(x, z, range(-62, -56))
        w.search(x, -60, z, 0, 0)
    return w.case()


def ocean(g, name, islands):
    """An ocean, every candidate under water, so a search ends at the spawn moved to where a player
    fits, or with islands among them, which the walk comes to in its order."""
    w = World(name)
    w.square(3)
    w.flat(-48, -48, 63, 63)
    for xs in (-48, 8):
        for zs in (-48, 8):
            w.fill(xs, -60, zs, xs + 55, 62, zs + 55, WATER)
    for _ in range(islands):
        x, z = g.between(-48, 63), g.between(-48, 63)
        w.fill(x, -60, z, x, g.between(60, 66), z, g.pick(GROUND))
        if g.below(3) == 0:
            w.set(x, 67, z, g.pick(SHAPED + OPEN))
    for _ in range(12):
        x, z = g.between(-48, 63), g.between(-48, 63)
        w.set(x, 63, z, g.pick([LILY_PAD, KELP, SLAB_BOTTOM_WET, SEA_PICKLE, BUBBLES, ICE]))
    w.search(0, 64, 0, 0, 0)
    w.search(0, 70, 0, 1, 4)
    w.search(0, -30, 0, 3, 0)
    for radius in [1, 5, 10, 16, 20, 32]:
        for _ in range(3):
            random_search(w, g, radius)
    for _ in range(40):
        x, z = g.between(-48, 63), g.between(-48, 63)
        w.look(x, z, [60, 61, 62, 63, 64])
        w.ops.append(["fixup", x, g.between(-70, 330), z])
    return w.case()


def filled(g):
    """A world of stone to its top, where nothing fits and the spawn goes to the top, then one with
    a cave in it."""
    w = World("filled")
    w.square(1)
    for y0 in range(MIN_Y, TOP + 1, 64):
        w.fill(-16, y0, -16, 31, min(y0 + 63, TOP), 31, STONE)
    w.search(0, 64, 0, 0, 0)
    w.search(0, -64, 0, 1, 3)
    w.search(3, 383, 3, 10, 200)
    w.look(0, 0, [318, 319, 320, 321])
    w.ops.append(["fixup", 5, -64, 5])
    w.ops.append(["fixup", 5, 319, 5])
    # A cave, and a column open to the top.
    w.fill(-10, 0, -10, 20, 5, 20, AIR)
    w.fill(0, 6, 0, 0, TOP, 0, AIR)
    w.set(7, 319, 7, AIR)
    w.set(8, 319, 8, SLAB_BOTTOM)
    w.set(9, 319, 9, WATER)
    for x, z in [(0, 0), (7, 7), (8, 8), (9, 9), (5, 5)]:
        w.look(x, z, [-1, 0, 1, 5, 6, 318, 319, 320])
        for y in [-64, 0, 2, 100, 319, 383]:
            w.ops.append(["fixup", x, y, z])
        w.search(x, 3, z, 0, 0)
    w.search(5, 3, 5, 10, 17)
    return w.case()


def terrain(g, name, chunks, count, low, high, radii):
    """Terrain at random: a flat world with boxes and blocks of the pool at random in it, and
    searches from places at random over it."""
    w = World(name)
    w.square(chunks)
    lo, hi = -16 * chunks, 16 * chunks + 15
    w.flat(lo, lo, hi, hi)
    for _ in range(count // 400):
        x, z = g.between(lo, hi - 8), g.between(lo, hi - 8)
        y = g.between(low, high - 8)
        w.fill(x, y, z, x + g.below(9), y + g.below(9), z + g.below(9), g.pick(POOL))
    for xs in range(lo, hi + 1, 64):
        for zs in range(lo, hi + 1, 64):
            w.ops.append(["random", g.seed(), count * 4096 // ((hi - lo + 1) ** 2), POOL,
                          xs, low, zs, min(xs + 63, hi), high, min(zs + 63, hi)])
    for radius in radii:
        for _ in range(4):
            random_search(w, g, radius, y=g.between(low - 5, high + 5))
    for _ in range(120):
        x, z = g.between(lo, hi), g.between(lo, hi)
        w.look(x, z, [g.between(low - 2, high + 2) for _ in range(3)])
        w.ops.append(["fixup", x, g.between(low - 10, high + 10), z])
    return w.case()


def edges(g):
    """Chunks with none beside them: columns at their edges, where a player's box and what it
    reaches beside go into chunks that aren't there, and blocks above and below the world."""
    w = World("edges")
    for cx, cz in [(0, 0), (2, 0), (0, 2), (5, 5), (-1, 0)]:
        w.chunk(cx, cz)
    for cx, cz in sorted(w.chunks):
        x0, z0 = cx * 16, cz * 16
        w.flat(x0, z0, x0 + 15, z0 + 15)
        for dx, dz in [(0, 0), (15, 15), (0, 15), (15, 0), (7, 0), (0, 7)]:
            w.set(x0 + dx, -60, z0 + dz, g.pick([FENCE, WALL, STONE, SLAB_BOTTOM, MOVING_PISTON, WATER]))
            w.set(x0 + dx, TOP, z0 + dz, g.pick([STONE, SLAB_BOTTOM, WATER, OAK_LEAVES]))
        for dx, dz in [(0, 0), (15, 15), (0, 15), (15, 0), (7, 0), (0, 7), (1, 1), (14, 14)]:
            x, z = x0 + dx, z0 + dz
            w.look(x, z, [-128, -127, -65, -64, -61, -60, -59, -58, 318, 319, 320, 321, 383])
            for y in [-128, -64, -59, 0, 319, 320, 383]:
                w.ops.append(["fixup", x, y, z])
            w.search(x, -60, z, 0, 0)
    return w.case()


def many(g):
    """Searches of 1024 candidates, the most, over a world all water but a few columns at random,
    and over one all water, where each comes to the spawn after the last."""
    w = World("many")
    w.square(5)
    lo, hi = -80, 95
    for xs in range(lo, hi + 1, 88):
        for zs in range(lo, hi + 1, 88):
            w.fill(xs, -64, zs, xs + 87, -63, zs + 87, STONE)
            w.fill(xs, -62, zs, xs + 87, -50, zs + 87, WATER)
    w.search(0, -40, 0, 64, 0)
    w.search(7, -49, 9, 16, 1023)
    w.search(-3, -62, 5, 40, 511)
    for _ in range(25):
        x, z = g.between(lo, hi), g.between(lo, hi)
        w.fill(x, -62, z, x, -50, z, g.pick(GROUND))
    for radius in [16, 17, 25, 33, 48, 64]:
        for _ in range(3):
            random_search(w, g, radius, y=g.between(-70, -40))
    return w.case()


def main():
    g = Gen(SEED)
    cases = [flat(g)]
    for name, pattern in PATTERNS:
        cases.append(columns(g, name, pattern))
    cases.append(beside(g))
    cases.append(ocean(g, "ocean", 0))
    cases.append(ocean(g, "ocean-islands", 6))
    cases.append(ocean(g, "ocean-archipelago", 60))
    cases.append(filled(g))
    cases.append(terrain(g, "terrain-surface", 4, 30000, -62, -40, [0, 1, 3, 10, 16, 30]))
    cases.append(terrain(g, "terrain-dense", 2, 40000, -62, -50, [0, 1, 2, 5, 10]))
    cases.append(terrain(g, "terrain-tall", 3, 20000, -64, 319, [0, 3, 16, 20]))
    cases.append(edges(g))
    cases.append(many(g))
    write_file(HERE / "generated.json", "spawn", f"cases/spawn/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
