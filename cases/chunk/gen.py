"""Writes cases/chunk/generated.json: chunks with blocks set as LevelChunk.setBlockState sets them,
their sections' counts and bytes, and their heightmaps kept, updated and primed.

    py -I cases/chunk/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.

The states are 26.3's, picked for what each heightmap and count makes of them: air, cave air and
void air, which are all air but only the first is skipped when heightmaps are primed; full blocks;
leaves, which one motion-blocking heightmap leaves out; water and lava, and blocks waterlogged or
holding water as kelp does, which count as fluids; blocks that take random ticks; and ones nothing
stands on, as torches and grass. The cases build the flat world, stack and clear columns of them,
tell the generation heightmaps of states as the flat generator does, set thousands at random until
a section's palette holds every kind, and prime every heightmap, in dimensions from one section
high to the most a dimension has.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261030
STATES = 35723

AIR, STONE, GRASS_BLOCK, DIRT, BEDROCK = 0, 1, 9, 10, 88
CAVE_AIR, VOID_AIR = 18650, 18649
WATER, WATER_FLOWING, LAVA = 89, 90, 105
OAK_LEAVES, OAK_LEAVES_DEFAULT = 267, 294
GLASS, SHORT_GRASS, TORCH, COBWEB, SEAGRASS = 661, 2363, 4926, 2362, 2370
OAK_SLAB_FIRST = 15177  # top, bottom and double, each waterlogged and not
KELP, BUBBLE_COLUMN = 18419, 18651
OAK_FENCE, SUGAR_CANE, SNOW, OAK_SAPLING = 8666, 8617, 8589, 30
CHEST, LADDER, POWDER_SNOW, SCAFFOLDING = 5544, 7308, 30519, 24094
OAK_TRAPDOOR, WHEAT, FIRE = 8799, 6867, 4962

# A state of each kind, for random sets.
POOL = [AIR, AIR, AIR, CAVE_AIR, VOID_AIR, STONE, GRASS_BLOCK, DIRT, BEDROCK, WATER, WATER_FLOWING,
        LAVA, LAVA + 3, OAK_LEAVES, OAK_LEAVES_DEFAULT, GLASS, SHORT_GRASS, TORCH, COBWEB, SEAGRASS,
        *range(OAK_SLAB_FIRST, OAK_SLAB_FIRST + 6), KELP, KELP + 25, BUBBLE_COLUMN, OAK_FENCE,
        SUGAR_CANE, SNOW, SNOW + 7, OAK_SAPLING, CHEST, CHEST + 1, LADDER, LADDER + 1, POWDER_SNOW,
        SCAFFOLDING, OAK_TRAPDOOR, WHEAT, WHEAT + 7, FIRE]
OVERWORLD = (-64, 24)
LOOK = [["heightmap", k] for k in range(6)] + [["counts"], ["highest"], ["write"]]
KEPT = [1, 3, 4, 5]


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def seed(self):
        """A long for the probe's LCG, as a string."""
        x = self.u64()
        return str(x - (1 << 64) if x >= 1 << 63 else x)


def case(name, dimension, ops):
    min_y, sections = dimension
    return {"id": name, "input": {"min_y": min_y, "sections": sections, "ops": ops}}


def flat():
    ops = []
    for y, state in enumerate([BEDROCK, DIRT, DIRT, GRASS_BLOCK]):
        ops.append(["fill", 0, -64 + y, 0, 15, -64 + y, 15, state])
    return case("flat", OVERWORLD, ops + LOOK + [["recount"], ["counts"]])


def no_change():
    """What setBlockState leaves alone: air in a section of only air, and a state already there."""
    ops = [["set", 3, 70, 9, AIR], ["set", 3, 70, 9, CAVE_AIR], ["set", 3, 70, 9, CAVE_AIR],
           ["set", 3, 70, 9, STONE], ["set", 3, 70, 9, STONE], ["set", 3, 70, 9, AIR],
           ["set", 3, 70, 9, AIR], ["block", 3, 70, 9]]
    return case("no-change", OVERWORLD, ops + LOOK)


def column():
    """One column stacked with a state of each kind, then cleared from the top down, and the rest
    from the bottom up, looking at the heightmaps after each."""
    stack = [STONE, OAK_LEAVES_DEFAULT, WATER, GLASS, TORCH, OAK_SLAB_FIRST + 1, CAVE_AIR, COBWEB,
             KELP, OAK_LEAVES, SHORT_GRASS, LAVA, SNOW, STONE, VOID_AIR, OAK_FENCE]
    look = [["heightmap", k] for k in KEPT]
    ops = []
    for i, state in enumerate(stack):
        ops += [["set", 5, 10 + i, 12, state]] + look
    for i in reversed(range(8, len(stack))):
        ops += [["set", 5, 10 + i, 12, AIR]] + look
    for i in range(8):
        ops += [["set", 5, 10 + i, 12, AIR]] + look
    return case("column", OVERWORLD, ops + LOOK)


def generation():
    """The generation heightmaps told of each state as the flat generator tells them, in layers
    with gaps, then primed again, which a column of cave air under the top doesn't stop."""
    layers = {-64: BEDROCK, -63: STONE, -61: WATER, -60: OAK_LEAVES_DEFAULT, -58: CAVE_AIR, -56: TORCH}
    ops = []
    for y, state in layers.items():
        for x in range(16):
            for z in range(16):
                ops.append(["set", x, y, z, state])
                ops.append(["update", 2, x, y, z, state])
                ops.append(["update", 0, x, y, z, state])
    ops += [["heightmap", 0], ["heightmap", 2], ["prime", [0, 1, 2, 3, 4, 5]]] + LOOK
    return case("generation", OVERWORLD, ops)


def updates(g):
    """`update` on its own, for states that weren't set: below the top, at it, and just over it."""
    ops = [["fill", 0, 0, 0, 15, 3, 15, STONE]]
    for _ in range(300):
        kind = g.below(6)
        x, z = g.below(16), g.below(16)
        y = g.below(10) - 2
        ops.append(["update", kind, x, y, z, POOL[g.below(len(POOL))]])
    return case("updates", OVERWORLD, ops + LOOK)


def randoms(g):
    """Random sets of the pool, over a few sections and then the whole height, growing the
    palettes, then the whole range of states, so a section holds more than 256."""
    out = []
    for name, dimension, low, high, count, pool in [
        ("random-low", OVERWORLD, -64, -33, 6000, POOL),
        ("random-high", OVERWORLD, 250, 319, 3000, POOL),
        ("random-all", OVERWORLD, -64, 319, 30000, POOL),
        ("random-states", OVERWORLD, 0, 15, 4000, sorted({g.below(STATES) for _ in range(600)} | {AIR, WATER, LAVA})),
        ("random-nether", (0, 16), 0, 255, 20000, POOL),
        ("random-one-section", (16, 1), 16, 31, 3000, POOL),
        ("random-tall", (-2032, 254), -2032, 2031, 20000, POOL),
    ]:
        ops = [["random_sets", g.seed(), count, pool, low, high]] + LOOK
        ops += [["random_sets", g.seed(), count // 3, [AIR, CAVE_AIR, VOID_AIR], low, high]] + LOOK
        ops += [["prime", [0, 1, 2, 3, 4, 5]]] + LOOK + [["recount"], ["counts"]]
        out.append(case(name, dimension, ops))
    return out


def cleared(g):
    """Sections filled and emptied again, so the highest section and the heightmaps fall."""
    ops = [["fill", 0, 100, 0, 15, 140, 15, OAK_LEAVES_DEFAULT], ["fill", 0, 0, 0, 15, 2, 15, WATER]] + LOOK
    ops += [["fill", 0, 100, 0, 15, 140, 15, CAVE_AIR]] + LOOK
    ops += [["random_sets", g.seed(), 2000, [STONE, AIR, KELP], 60, 75], ["fill", 0, 0, 0, 15, 2, 15, AIR]] + LOOK
    ops += [["prime", [0, 1, 2, 3, 4, 5]]] + LOOK
    return case("cleared", OVERWORLD, ops)


def main():
    g = Gen(SEED)
    cases = [flat(), no_change(), column(), generation(), updates(g)]
    cases += randoms(g)
    cases.append(cleared(g))
    write_file(HERE / "generated.json", "chunk", f"cases/chunk/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
