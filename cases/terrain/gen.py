"""Writes cases/terrain/generated.json: chunks filled by vanilla's noise settings, and base columns.

    py -I cases/terrain/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

Each of vanilla's noise settings fills chunks of the world it's made for, near the origin and far
out, and gives base columns and heights there; the Overworld's runs with many seeds, as its
aquifers are where the most can differ. Then the settings fill worlds taller and shorter than
their noise, worlds that only overlap it, and worlds it doesn't reach, where nothing is filled; and
chunks and columns at the ends of `int`, where the aquifer's grid wraps.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261104
LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]
INT_MAX = (1 << 31) - 1
INT_MIN = -(1 << 31)
# Each settings' world, as (min_y, height).
WORLDS = {
    "overworld": (-64, 384),
    "large_biomes": (-64, 384),
    "amplified": (-64, 384),
    "caves": (-64, 384),
    "floating_islands": (-64, 384),
    "nether": (0, 256),
    "end": (0, 256),
}
# The world border, in chunks.
BORDER = 1874999


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def chance(self, n):
        return self.below(n) == 0

    def pick(self, items):
        return items[self.below(len(items))]

    def long(self):
        v = self.u64()
        return str(v - (1 << 64) if v >= 1 << 63 else v)

    def seed(self):
        return self.pick(LONG_SEEDS) if self.chance(4) else self.long()


class Case:
    def __init__(self, cid, seed, settings, level):
        self.cid = cid
        self.input = {"seed": seed, "settings": "minecraft:" + settings, "level": list(level), "ops": []}

    def fill(self, cx, cz):
        self.input["ops"].append(["fill", cx, cz])

    def column(self, x, z):
        self.input["ops"].append(["column", x, z])

    def build(self):
        return {"id": self.cid, "input": self.input}


def near_chunk(g, spread=64):
    return g.between(-spread, spread), g.between(-spread, spread)


def far_chunk(g):
    return g.between(-BORDER, BORDER), g.between(-BORDER, BORDER)


def columns(g, c, count, spread):
    for _ in range(count):
        c.column(g.between(-spread, spread), g.between(-spread, spread))


def main():
    g = Gen(SEED)
    cases = []

    # Each settings in its world: the chunks at the origin, one near it, and columns around them.
    for settings, level in WORLDS.items():
        c = Case(f"{settings}-origin", g.seed(), settings, level)
        c.fill(0, 0)
        c.fill(-1, -1)
        c.fill(*near_chunk(g))
        c.column(0, 0)
        c.column(-1, -1)
        columns(g, c, 6, 1024)
        cases.append(c.build())
        c = Case(f"{settings}-far", g.seed(), settings, level)
        c.fill(*far_chunk(g))
        x, z = far_chunk(g)
        c.column(x * 16 + g.below(16), z * 16 + g.below(16))
        columns(g, c, 3, 30000000)
        cases.append(c.build())
        c = Case(f"{settings}-columns", g.seed(), settings, level)
        columns(g, c, 48, 4096)
        cases.append(c.build())

    # The Overworld and its kin with more seeds, for aquifers: oceans, caves and lava below.
    for i in range(24):
        settings = ["overworld", "overworld", "large_biomes", "amplified"][i % 4]
        c = Case(f"aquifers-{i}", g.seed(), settings, WORLDS[settings])
        c.fill(*near_chunk(g, 400))
        c.fill(*near_chunk(g, 400))
        cases.append(c.build())

    # The same chunk twice, and its neighbours: each fill is a chunk of its own.
    c = Case("overworld-repeated", "20261104", "overworld", WORLDS["overworld"])
    for cx, cz in [(3, 5), (3, 5), (4, 5), (3, 6)]:
        c.fill(cx, cz)
    cases.append(c.build())

    # Worlds that aren't the noise's: taller, shorter, overlapping its top or bottom, or past it.
    levels = [
        ("tall", (-128, 512)),
        ("short", (0, 128)),
        ("one-section", (-64, 16)),
        ("top-section", (304, 16)),
        ("above", (320, 64)),
        ("below", (-2032, 16)),
        ("whole", (-2032, 4064)),
        ("low", (-512, 448)),
    ]
    for name, level in levels:
        for settings in ["overworld", "nether"]:
            c = Case(f"level-{name}-{settings}", g.seed(), settings, level)
            c.fill(*near_chunk(g, 16))
            c.column(g.between(-256, 256), g.between(-256, 256))
            cases.append(c.build())
    c = Case("level-end-in-overworld", g.seed(), "end", WORLDS["overworld"])
    c.fill(0, 0)
    c.fill(*near_chunk(g, 200))
    c.column(0, 0)
    cases.append(c.build())

    # The ends of `int`, where blocks, quarts and the aquifer's grid wrap.
    edge_chunks = [((1 << 27) - 1, (1 << 27) - 1), (-(1 << 27), -(1 << 27))]
    for i, (cx, cz) in enumerate(edge_chunks):
        c = Case(f"edge-{i}", g.seed(), "overworld", WORLDS["overworld"])
        c.fill(cx, cz)
        cases.append(c.build())
    # A column each, as the first that throws ends its case.
    for i, x in enumerate([INT_MAX, INT_MIN, INT_MAX - 5, INT_MIN + 4, INT_MAX - 40, INT_MIN + 40]):
        for j, z in enumerate([INT_MAX, INT_MIN, 7]):
            c = Case(f"edge-column-{i}-{j}", g.seed(), "overworld", WORLDS["overworld"])
            c.column(x, z)
            cases.append(c.build())

    write_file(HERE / "generated.json", "terrain", f"cases/terrain/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
