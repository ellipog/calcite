"""Writes cases/light/generated.json: chunks lit by vanilla's light engines, block light and sky
light, as a server lights the chunks it makes and loads, and lit again as blocks change.

    py -I cases/light/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.

The states are 26.3's, picked for what light makes of them: air, and blocks that let light through
whole or take one level from it, as glass, leaves and water; full blocks that stop it; blocks that
give it, from a redstone torch's 7 to glowstone's and lava's 15, some of which stop it too; and
blocks whose shape light sees, as slabs, stairs, snow and paths, which stop it only on some faces.
The cases light flat chunks, terrain at random, caves under a roof, towers with empty sections
between them, chunks with no neighbours, dimensions with no sky and of every height, and chunks
loaded with light already saved, then change blocks and light them again.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261031

AIR, STONE, GRASS_BLOCK, DIRT, BEDROCK, CAVE_AIR = 0, 1, 9, 10, 88, 18650
GLASS, TINTED_GLASS, ICE, COBWEB, OAK_LEAVES = 661, 30518, 8597, 2362, 294
WATER, LAVA = 89, 105
TORCH, SOUL_TORCH, REDSTONE_TORCH, END_ROD, LANTERN = 4926, 8676, 8555, 16615, 24197
GLOWSTONE, SEA_LANTERN, JACK_O_LANTERN, SHROOMLIGHT, MAGMA, BEACON = 8686, 14739, 8693, 24333, 16826, 11722
LAMP_ON, LAMP_OFF = 11213, 11214
SLAB_TOP, SLAB_BOTTOM, SLAB_DOUBLE, SLAB_BOTTOM_WET = 15178, 15180, 15182, 15179
STAIRS_NORTH, STAIRS_EAST_TOP, STAIRS_OUTER = 5474, 5524, 19170
SNOW, DIRT_PATH, FARMLAND, SCULK_SENSOR, DAYLIGHT_DETECTOR, LECTERN = 8589, 16796, 6875, 30521, 13062, 24144
OAK_FENCE, CHEST = 8666, 5544

CLEAR = [AIR, AIR, AIR, CAVE_AIR, GLASS, TINTED_GLASS, ICE, COBWEB, OAK_LEAVES, WATER, OAK_FENCE, CHEST]
SOLID = [STONE, STONE, DIRT, BEDROCK, SLAB_DOUBLE, LAMP_OFF]
GLOW = [TORCH, SOUL_TORCH, REDSTONE_TORCH, END_ROD, LANTERN, GLOWSTONE, SEA_LANTERN, JACK_O_LANTERN,
        SHROOMLIGHT, MAGMA, BEACON, LAMP_ON, LAVA, SCULK_SENSOR]
SHAPED = [SLAB_TOP, SLAB_BOTTOM, SLAB_BOTTOM_WET, STAIRS_NORTH, STAIRS_EAST_TOP, STAIRS_OUTER, SNOW,
          DIRT_PATH, FARMLAND, DAYLIGHT_DETECTOR, LECTERN]
POOL = CLEAR * 3 + SOLID * 3 + GLOW + SHAPED * 2

OVERWORLD = (-64, 24)
NETHER = (0, 16)


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


def case(name, dimension, sky, ops):
    min_y, sections = dimension
    return {"id": name, "input": {"min_y": min_y, "sections": sections, "sky": sky, "ops": ops}}


def square(radius, cx=0, cz=0):
    return [(x, z) for x in range(cx - radius, cx + radius + 1) for z in range(cz - radius, cz + radius + 1)]


def flat_fill(cx, cz, min_y):
    """The classic flat preset's layers in a chunk, set as generation sets them."""
    x, z = cx * 16, cz * 16
    return [["fill", x, min_y + i, z, x + 15, min_y + i, z + 15, s] for i, s in enumerate([BEDROCK, DIRT, DIRT, GRASS_BLOCK])]


def initialize(chunks, lighted=False):
    """The INITIALIZE_LIGHT status for each chunk: its sky sources, its sections, and light on or
    off, as `ThreadedLevelLightEngine.initializeLight` and a run between give them."""
    ops = []
    for cx, cz in chunks:
        ops += [["sources", cx, cz], ["sections", cx, cz], ["run"], ["enable", cx, cz, 1 if lighted else 0], ["retain", cx, cz, 0]]
    return ops


def light(chunks):
    """The LIGHT status for each chunk: its sources spread, then a run."""
    ops = []
    for cx, cz in chunks:
        ops += [["propagate", cx, cz], ["run"]]
    return ops


def generate(chunks):
    return initialize(chunks) + light(chunks)


def look(chunks, dimension, g=None, values=0, sky=1):
    """Each chunk's light as a packet sends it, every section's layers, and light at random blocks."""
    min_y, sections = dimension
    ops = [["work"]]
    for cx, cz in chunks:
        ops += [["light", cx, cz], ["on", cx, cz]]
        for sy in range((min_y >> 4) - 1, (min_y >> 4) + sections + 1):
            ops += [["layer", 1, cx, sy, cz], ["layer", 0, cx, sy, cz]]
    if g is not None:
        xs = [cx for cx, _ in chunks]
        zs = [cz for _, cz in chunks]
        for _ in range(values):
            x = min(xs) * 16 + g.below((max(xs) - min(xs) + 1) * 16)
            z = min(zs) * 16 + g.below((max(zs) - min(zs) + 1) * 16)
            y = min_y - 32 + g.below(sections * 16 + 64)
            ops.append(["value", g.below(2) if sky else 0, x, y, z])
    return ops


def made(chunks, dimension):
    return [["chunk", cx, cz] for cx, cz in chunks]


def flat(g):
    """Flat chunks, as `world.flat` sends them: the sky down to the grass, and no block light."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops += generate(chunks) + look(chunks, OVERWORLD, g, 300)
    return case("flat", OVERWORLD, 1, ops)


def flat_wide(g):
    """A 5 by 5 of flat chunks lit in the order a player's view makes them, from the middle out."""
    chunks = sorted(square(2), key=lambda c: (max(abs(c[0]), abs(c[1])), c))
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops += initialize(chunks) + light(chunks) + look(chunks[:9], OVERWORLD, g, 200)
    return case("flat-wide", OVERWORLD, 1, ops)


def glow(g):
    """A block of each kind that gives light, on flat ground, lit as it's made."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    for i, state in enumerate(GLOW):
        x, z = -14 + (i % 5) * 7, -14 + (i // 5) * 7
        ops.append(["fill", x, -60, z, x, -60 + i % 3, z, state])
    ops += generate(chunks) + look(chunks, OVERWORLD, g, 400)
    return case("glow", OVERWORLD, 1, ops)


def terrain(g, name, dimension, sky, count, low, high, radius=1):
    """Blocks of every kind at random, set as generation sets them, then lit."""
    chunks = square(radius)
    min_y, _ = dimension
    ops = made(chunks, dimension)
    ops.append(["fill", -radius * 16, min_y, -radius * 16, radius * 16 + 15, min_y + 2, radius * 16 + 15, STONE])
    ops.append(["random", 0, g.seed(), count, POOL, -radius * 16, low, -radius * 16, radius * 16 + 15, high, radius * 16 + 15])
    ops += generate(chunks) + look(chunks, dimension, g, 400, sky)
    return case(name, dimension, sky, ops)


def caves(g):
    """A stone roof with holes over open ground: the sky comes in sideways under it, and the
    sources move as the holes open and close."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops.append(["fill", -16, -20, -16, 31, -18, 31, STONE])
    for _ in range(12):
        x, z = -16 + g.below(48), -16 + g.below(48)
        ops.append(["fill", x, -20, z, min(x + g.below(3), 31), -18, min(z + g.below(3), 31), AIR])
    ops.append(["random", 0, g.seed(), 300, GLOW + [GLASS, WATER, SLAB_TOP], -16, -60, -16, 31, -21, 31])
    ops += generate(chunks) + look(chunks, OVERWORLD, g, 300)
    edits = []
    for _ in range(40):
        x, z = -16 + g.below(48), -16 + g.below(48)
        edits.append(["set", x, -19 - g.below(2), z, [AIR, STONE, GLASS, SLAB_BOTTOM, OAK_LEAVES][g.below(5)]])
        if g.below(4) == 0:
            edits.append(["run"])
    ops += edits + [["run"]] + look(chunks, OVERWORLD, g, 300)
    return case("caves", OVERWORLD, 1, ops)


def towers(g):
    """Blocks high up and low down with empty sections between them, so sky light goes down past
    sections kept for nothing, and comes out sideways at the bottom of the gap."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    ops.append(["fill", -16, -64, -16, 31, -62, 31, STONE])
    ops.append(["fill", 0, 200, 0, 15, 200, 15, STONE])
    ops.append(["fill", 3, 100, 3, 9, 140, 9, GLASS])
    ops.append(["fill", -16, 40, 20, -10, 40, 31, LAVA])
    ops.append(["random", 0, g.seed(), 600, POOL, -16, 150, -16, 31, 260, 31])
    ops += generate(chunks) + look(chunks, OVERWORLD, g, 400)
    edits = [["set", 5, 200, 5, AIR], ["set", 0, 200, 0, AIR], ["set", 15, 200, 15, AIR], ["run"],
             ["set", 6, 140, 6, STONE], ["set", 6, 141, 6, TORCH], ["run"],
             ["random", 1, g.seed(), 3000, [AIR], 3, 100, 3, 9, 140, 9]]
    for x in range(3, 10):
        for z in range(3, 10):
            edits.append(["set", x, 120, z, AIR])
    ops += edits + [["run"]] + look(chunks, OVERWORLD, g, 300)
    return case("towers", OVERWORLD, 1, ops)


def alone(g):
    """A chunk lit with no chunks around it: light stops at its edges as at bedrock, and its sky
    sources around are taken to go on below the world."""
    ops = [["chunk", 0, 0]] + flat_fill(0, 0, -64)
    ops.append(["random", 0, g.seed(), 800, POOL, 0, -60, 0, 15, -40, 15])
    ops += generate([(0, 0)]) + look([(0, 0)], OVERWORLD, g, 300)
    ops += [["set", 0, -50, 0, GLOWSTONE], ["set", 15, -50, 15, TORCH], ["run"]] + look([(0, 0)], OVERWORLD, g, 100)
    return case("alone", OVERWORLD, 1, ops)


def open_void(g):
    """Chunks with nothing in some columns, open to the void, where the sky goes all the way down,
    and a chunk with nothing at all."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    ops.append(["fill", 0, 0, 0, 15, 0, 15, STONE])
    ops.append(["fill", 4, 0, 4, 11, 0, 11, AIR])
    ops.append(["fill", -16, 10, -16, -1, 10, -1, GLASS])
    ops.append(["fill", 16, 30, 16, 31, 30, 31, TORCH])
    ops += generate(chunks) + look(chunks, OVERWORLD, g, 300)
    ops += [["set", 8, 0, 8, STONE], ["set", 8, -64, 8, STONE], ["run"], ["set", 4, 0, 4, GLOWSTONE], ["run"]]
    ops += look(chunks, OVERWORLD, g, 200)
    return case("open-void", OVERWORLD, 1, ops)


def edits(g, name, dimension, sky, rounds, per_round):
    """Lit terrain, then blocks changed at random as a world changes them, lit after each round."""
    chunks = square(1)
    min_y, sections = dimension
    top = min_y + sections * 16 - 1
    ops = made(chunks, dimension)
    ops.append(["fill", -16, min_y, -16, 31, min_y + 3, 31, STONE])
    ops.append(["random", 0, g.seed(), 4000, POOL, -16, min_y, -16, 31, min(min_y + 80, top), 31])
    ops += generate(chunks)
    for r in range(rounds):
        low = min_y + g.below(min(80, sections * 16 - 16))
        ops.append(["random", 1, g.seed(), per_round, POOL, -16, low, -16, 31, min(low + 15 + g.below(30), top), 31])
        ops.append(["run"])
        if r % 3 == 2:
            ops += look(chunks, dimension, g, 50, sky)
    ops += look(chunks, dimension, g, 300, sky)
    return case(name, dimension, sky, ops)


def checks(g):
    """Blocks checked that didn't change, and blocks outside any section light is kept for."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops.append(["fill", 2, -60, 2, 4, -58, 4, GLOWSTONE])
    ops += generate(chunks)
    for _ in range(200):
        ops.append(["check", -16 + g.below(48), -80 + g.below(400), -16 + g.below(48)])
    ops += [["run"], ["work"]] + look(chunks, OVERWORLD, g, 200)
    return case("checks", OVERWORLD, 1, ops)


def emptied(g):
    """Sections emptied of blocks and filled again: light stops being kept for them and their
    neighbours, and starts again, with the column's light kept and not."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops.append(["fill", 0, 64, 0, 15, 64, 15, STONE])
    ops.append(["fill", 5, 65, 5, 5, 65, 5, TORCH])
    ops += generate(chunks) + look(chunks, OVERWORLD)
    # Empty the section at 64 to 79 a block at a time, keeping the column's light once.
    ops.append(["retain", 0, 0, 1])
    ops.append(["set", 5, 65, 5, AIR])
    for x in range(16):
        for z in range(16):
            ops.append(["set", x, 64, z, AIR])
    ops += [["work"], ["run"]] + look(chunks, OVERWORLD)
    ops.append(["retain", 0, 0, 0])
    ops += [["set", 8, 70, 8, GLOWSTONE], ["run"]] + look(chunks, OVERWORLD)
    ops += [["set", 8, 70, 8, AIR], ["run"]] + look(chunks, OVERWORLD, g, 200)
    ops += [["status", 3, 10, 3, 0], ["run"], ["status", 3, 10, 3, 1], ["status", 3, 10, 3, 1], ["run"]] + look([(3, 3)], OVERWORLD)
    return case("emptied", OVERWORLD, 1, ops)


def layer(g, kind):
    if kind == 0:
        return [0, 0]
    if kind == 1:
        return [1, g.below(16)]
    return [2, g.seed()]


def loaded(g):
    """Chunks loaded with their light saved, as `ChunkSerializer` queues it, lighted, so their
    sources don't spread, and one saved with no light, which `setLightEnabled` fills."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops.append(["fill", 0, -60, 0, 3, -50, 3, GLOWSTONE])
    for cx, cz in chunks:
        ops.append(["retain", cx, cz, 1])
        for sy in range(-5, 2):
            if g.below(3) != 0:
                ops.append(["queue", 1, cx, sy, cz] + layer(g, g.below(3)))
            if g.below(2) != 0:
                ops.append(["queue", 0, cx, sy, cz] + layer(g, g.below(3)))
    # The middle chunk is saved with no light at all.
    ops = [op for op in ops if not (op[0] == "queue" and op[2] == 0 and op[4] == 0)]
    ops += initialize(chunks, lighted=True) + [["run"]] + look(chunks, OVERWORLD, g, 300)
    # A section loaded for a chunk that then goes, and one queued and taken back.
    ops += [["queue", 1, 5, 0, 5] + layer(g, 2), ["queue", 0, 5, 0, 5] + layer(g, 2), ["work"], ["queue", 0, 5, 0, 5, 0, 0], ["run"]]
    ops += [["set", 1, -49, 1, TORCH], ["set", 7, -60, 7, AIR], ["run"]] + look(chunks, OVERWORLD, g, 300)
    return case("loaded", OVERWORLD, 1, ops)


def nether(g):
    """A dimension with no sky, lava and glowstone in netherrack's place."""
    chunks = square(1)
    ops = made(chunks, NETHER)
    ops.append(["fill", -16, 0, -16, 31, 4, 31, STONE])
    ops.append(["fill", -16, 120, -16, 31, 127, 31, STONE])
    ops.append(["fill", -16, 31, -16, 31, 31, 31, LAVA])
    ops.append(["random", 0, g.seed(), 3000, [STONE, STONE, AIR, AIR, AIR, GLOWSTONE, LAVA, MAGMA, SHROOMLIGHT, SLAB_TOP], -16, 5, -16, 31, 119, 31])
    ops += generate(chunks) + look(chunks, NETHER, g, 400, 0)
    ops += [["random", 1, g.seed(), 300, [AIR, STONE, GLOWSTONE, TORCH], -16, 30, -16, 31, 60, 31], ["run"]]
    ops += look(chunks, NETHER, g, 200, 0)
    return case("nether", NETHER, 0, ops)


def heights(g):
    out = []
    for name, dimension in [("one-section", (16, 1)), ("tall", (-2032, 254)), ("low", (-2032, 16)), ("high", (1920, 7))]:
        min_y, sections = dimension
        top = min_y + sections * 16 - 1
        chunks = square(1)
        ops = made(chunks, dimension)
        ops.append(["fill", -16, min_y, -16, 31, min_y, 31, STONE])
        ops.append(["random", 0, g.seed(), 3000, POOL, -16, min_y, -16, 31, top, 31])
        seen = [(0, 0)] if sections > 64 else chunks
        ops += generate(chunks) + look(seen, dimension, g, 200)
        ops += [["random", 1, g.seed(), 300, POOL, -16, min_y, -16, 31, top, 31], ["run"]] + look(seen, dimension, g, 200)
        out.append(case(name, dimension, 1, ops))
    return out


def growing(g):
    """Chunks made a ring at a time, each ring lit while the one inside is already lit, as a world
    grows around its players, then blocks changed across the rings' edges."""
    ops = []
    done = []
    for ring in range(3):
        chunks = [c for c in square(ring) if c not in done]
        ops += made(chunks, OVERWORLD)
        for cx, cz in chunks:
            ops += flat_fill(cx, cz, -64)
        x0 = -ring * 16
        ops.append(["random", 0, g.seed(), 1500 * (ring + 1), POOL, x0, -60, x0, ring * 16 + 15, 0, ring * 16 + 15])
        ops += generate(chunks)
        done += chunks
    ops += look(square(1), OVERWORLD, g, 300)
    ops += [["random", 1, g.seed(), 2000, POOL, -32, -64, -32, 47, 20, 47], ["run"]] + look(square(1), OVERWORLD, g, 300)
    return case("growing", OVERWORLD, 1, ops)


def chaos(g, name, dimension, sky, count):
    """Every operation at random over lit terrain: blocks set, checked and told empty, chunks'
    light turned on and off, kept and let go, light queued and spread again, and runs between,
    so the engines meet what a world does in any order."""
    min_y, sections = dimension
    top = min_y + sections * 16 - 1
    low, high = (min_y >> 4) - 1, (min_y >> 4) + sections
    chunks = square(1)
    ops = made(chunks, dimension)
    ops.append(["fill", -16, min_y, -16, 31, min_y + 2, 31, STONE])
    ops.append(["random", 0, g.seed(), 6000, POOL, -16, min_y, -16, 31, min(min_y + 100, top), 31])
    ops += generate(chunks)

    def x():
        return -24 + g.below(64)

    def c():
        return -2 + g.below(5)

    for _ in range(count):
        kind = g.below(100)
        if kind < 45:
            ops.append(["set", -16 + g.below(48), min_y + g.below(min(120, sections * 16)), -16 + g.below(48), POOL[g.below(len(POOL))]])
        elif kind < 55:
            ops.append(["check", x(), min_y - 16 + g.below(sections * 16 + 32), x()])
        elif kind < 62:
            ops.append(["status", c(), low + g.below(high - low + 1), c(), g.below(2)])
        elif kind < 66:
            ops.append(["enable", c(), c(), g.below(2)])
        elif kind < 70:
            ops.append(["retain", c(), c(), g.below(2)])
        elif kind < 74:
            ops.append(["propagate", c(), c()])
        elif kind < 80:
            ops.append(["queue", g.below(2), c(), low + g.below(high - low + 1), c()] + layer(g, g.below(3)))
        elif kind < 84:
            ops.append(["value", g.below(2) if sky else 0, x(), min_y - 32 + g.below(sections * 16 + 64), x()])
        elif kind < 86:
            ops.append(["work"])
        elif kind < 88:
            ops.append(["on", c(), c()])
        elif kind < 89:
            ops.append(["light", c(), c()])
        else:
            ops.append(["run"])
    ops += [["run"]] + look(chunks, dimension, g, 300, sky)
    return case(name, dimension, sky, ops)


def churn(g, name, sky, count):
    """Light queued, sections told empty and not, columns' light turned on and off and kept, with
    the light read between and runs now and then: what's read before a run is what the run before
    left, and what's queued for a section that's started is the section's own light."""
    chunks = square(1)
    ops = made(chunks, OVERWORLD)
    for cx, cz in chunks:
        ops += flat_fill(cx, cz, -64)
    ops.append(["random", 0, g.seed(), 1500, POOL, -16, -60, -16, 31, -20, 31])
    ops += generate(chunks)

    def c():
        return -1 + g.below(3)

    def sy():
        return -5 + g.below(6)

    for _ in range(count):
        kind = g.below(100)
        if kind < 20:
            ops.append(["queue", g.below(2), c(), sy(), c()] + layer(g, g.below(3)))
        elif kind < 35:
            ops.append(["status", c(), sy(), c(), g.below(2)])
        elif kind < 45:
            ops.append(["enable", c(), c(), g.below(2)])
        elif kind < 52:
            ops.append(["retain", c(), c(), g.below(2)])
        elif kind < 56:
            ops.append(["propagate", c(), c()])
        elif kind < 64:
            ops.append(["set", -16 + g.below(48), -64 + g.below(64), -16 + g.below(48), POOL[g.below(len(POOL))]])
        elif kind < 80:
            ops.append(["layer", g.below(2), c(), sy(), c()])
        elif kind < 88:
            ops.append(["value", g.below(2), -16 + g.below(48), -96 + g.below(100), -16 + g.below(48)])
        elif kind < 90:
            ops.append(["light", c(), c()])
        elif kind < 92:
            ops.append(["work"])
        else:
            ops.append(["run"])
    ops += [["run"]] + look(chunks, OVERWORLD, g, 200)
    return case(name, OVERWORLD, sky, ops)


def main():
    g = Gen(SEED)
    cases = [flat(g), flat_wide(g), glow(g)]
    cases.append(terrain(g, "terrain-low", OVERWORLD, 1, 20000, -64, -1))
    cases.append(terrain(g, "terrain-surface", OVERWORLD, 1, 12000, 40, 100))
    cases.append(terrain(g, "terrain-sparse", OVERWORLD, 1, 2000, -64, 319, radius=2))
    cases += [caves(g), towers(g), alone(g), open_void(g), checks(g), emptied(g), loaded(g)]
    cases.append(edits(g, "edits", OVERWORLD, 1, 9, 300))
    cases.append(edits(g, "edits-many", OVERWORLD, 1, 4, 3000))
    cases.append(nether(g))
    cases += heights(g)
    cases.append(growing(g))
    for i in range(6):
        cases.append(chaos(g, f"chaos-{i}", OVERWORLD, 1, 3000))
    cases.append(chaos(g, "chaos-nether", NETHER, 0, 3000))
    cases.append(chaos(g, "chaos-one-section", (0, 1), 1, 2000))
    for i in range(4):
        cases.append(churn(g, f"churn-{i}", 1, 4000))
    cases.append(churn(g, "churn-no-sky", 0, 4000))
    write_file(HERE / "generated.json", "light", f"cases/light/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
