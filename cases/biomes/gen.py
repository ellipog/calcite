"""Writes cases/biomes/generated.json: biome sources read as a dimension writes them, and asked.

    py -I cases/biomes/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, and the vanilla ids from the
pinned server jar in oracle/jars/, so rerunning it gives the same file.

The cases name vanilla's material by id and never copy it. Each of vanilla's presets runs with the
noise settings the world presets give it, and with the others, asked for biomes where worlds have
them: near the origin, across a world, at the ends of `int`, and over whole chunks, and for the
climate there; the presets' lists are dumped entry by entry. The fixed, checkerboard and End
sources run the same way, the checkerboard at every scale, with tags, single biomes and lists that
repeat. Then lists written out at random, from one entry to past the tree's second level, with
points that tie, are searched at climate targets near and far, where the squared distances wrap;
and sources that don't read, which are compared only as that.
"""

import io
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261103
JAR = ROOT / "oracle" / "jars" / "server-26.3.jar"
INNER = "META-INF/versions/26.3/server-26.3.jar"

LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]
INT_MAX = (1 << 31) - 1
INT_MIN = -(1 << 31)
# Quarts at the edges: of `int`, of a world, and of the shifts to blocks and chunks.
EDGE_QUARTS = [0, -1, 1, 2, -2, 3, 4, -4, -5, 15, 16, -16, -17, 63, 64, -64, -65, 255, 256, -256, -257,
               7499999, -7500000, 7500000, (1 << 29) - 1, -(1 << 29), 1 << 29, -(1 << 29) - 1,
               INT_MAX, INT_MIN, INT_MAX - 1, INT_MIN + 1, 1 << 30, -(1 << 30)]
# Climate values at the edges of a parameter and of quantizing.
EDGE_TARGETS = [0, -1, 1, 10000, -10000, 20000, -20000, 9999, -9999, 30000, -30000, 3000000000 // 2,
                INT_MAX, INT_MIN, INT_MAX - 1, INT_MIN + 1, 1 << 30, -(1 << 30), 46341, -46341]
# The noise settings each preset is used with in a world, then the rest.
WORLD = {"overworld": ["overworld", "large_biomes", "amplified"], "nether": ["nether"]}
# (min_y, height) of each kind of world, and of others.
WORLDS = {"overworld": (-64, 384), "large_biomes": (-64, 384), "amplified": (-64, 384), "caves": (-64, 192),
          "floating_islands": (0, 256), "nether": (0, 128), "end": (0, 128)}


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def unit(self):
        return (self.u64() >> 11) * 2.0**-53

    def pick(self, items):
        return items[self.below(len(items))]

    def chance(self, n):
        return self.below(n) == 0

    def long(self):
        x = self.u64()
        return str(x - (1 << 64) if x >= 1 << 63 else x)

    def seed(self):
        return self.pick(LONG_SEEDS) if self.chance(3) else self.long()

    def blob_seed(self):
        return str(self.u64() >> 1)

    def real(self, lo, hi):
        """A float in [lo, hi], rounded so the JSON stays short."""
        return round(lo + (hi - lo) * self.unit(), 4)


def vanilla_ids():
    """The vanilla data pack's biomes, biome tags and noise settings, by id."""
    with zipfile.ZipFile(JAR) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(INNER)))
    out = {"worldgen/biome": [], "tags/worldgen/biome": [], "worldgen/noise_settings": []}
    for name in sorted(inner.namelist()):
        for kind, ids in out.items():
            prefix = "data/minecraft/" + kind + "/"
            if name.startswith(prefix) and name.endswith(".json"):
                ids.append("minecraft:" + name[len(prefix):-len(".json")])
    return out


class Case:
    """One case: a source, the ops that ask it in order, and the ints those ops read."""

    def __init__(self, cid, seed, settings, source, cached=False):
        self.cid = cid
        self.input = {"seed": seed, "settings": "minecraft:" + settings, "source": source, "cached": cached, "ops": []}
        self.parts = []

    def op(self, *op):
        self.input["ops"].append(list(op))

    def read(self, kind, part, count):
        self.op(kind, count)
        if count:
            self.parts.append(part)

    def build(self):
        return {"id": self.cid, "input": self.input, "blobs": [self.parts if self.parts else {"i32": []}]}


def near(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count, "ranges": [["-400", "400"], ["-20", "90"], ["-400", "400"]]}


def far(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count,
            "ranges": [["-7500000", "7500000"], ["-20", "90"], ["-7500000", "7500000"]]}


def anywhere(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count,
            "ranges": [[str(INT_MIN), str(INT_MAX)], [str(INT_MIN), str(INT_MAX)], [str(INT_MIN), str(INT_MAX)]]}


def edges(g, count):
    return {"i32": [g.pick(EDGE_QUARTS) for _ in range(count * 3)]}


def targets(g, count, spread=25000):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count, "ranges": [[str(-spread), str(spread)]] * 6}


def edge_targets(g, count):
    return {"i32": [g.pick(EDGE_TARGETS) for _ in range(count * 6)]}


def asked(g, c, settings, chunks=2, heavy=True):
    """Climate and biomes near and far, at the edges, and over chunks."""
    n = 1 if heavy else 0
    c.read("climate", near(g, 24), 24)
    c.read("points", near(g, 120 + 80 * n), 120 + 80 * n)
    c.read("climate", far(g, 8), 8)
    c.read("points", far(g, 40), 40)
    c.read("points", edges(g, 12), 12)
    c.read("points", anywhere(g, 6), 6)
    min_y, height = WORLDS[settings]
    for _ in range(chunks):
        if g.chance(4):
            cx, cz = g.between(-1875000, 1875000), g.between(-1875000, 1875000)
        else:
            cx, cz = g.between(-40, 40), g.between(-40, 40)
        c.op("chunk", cx, cz, min_y, height)


def preset(name):
    return {"type": "minecraft:multi_noise", "preset": "minecraft:" + name}


def number(g, v):
    """A value written as JSON writes it: some ints, some floats."""
    if v == int(v) and g.chance(2):
        return int(v)
    return v


def parameter(g, grid):
    """A climate parameter, written as one of its three forms."""
    if grid:
        a, b = sorted([g.pick(grid), g.pick(grid)])
    else:
        a, b = sorted([g.real(-2, 2), g.real(-2, 2)])
        if g.chance(4):
            b = a
    form = g.below(3)
    if a == b and form == 0:
        return number(g, a)
    if form == 1 or a == b:
        return [number(g, a), number(g, b)]
    return {"min": number(g, a), "max": number(g, b)}


FIELDS = ["temperature", "humidity", "continentalness", "erosion", "depth", "weirdness"]


def entry(g, biomes, grid):
    params = {f: parameter(g, grid) for f in FIELDS}
    params["offset"] = number(g, g.pick([0, 0, 0.375, 1, 0.5, g.real(0, 1)]) if grid else g.real(0, 1))
    return {"biome": g.pick(biomes), "parameters": params}


def written(g, biomes, n, grid):
    return {"type": "minecraft:multi_noise", "biomes": [entry(g, biomes, grid) for _ in range(n)]}


def invalid_sources(ids):
    """Sources vanilla doesn't read, each for a different reason."""
    point = {f: 0 for f in FIELDS}
    point["offset"] = 0

    def with_point(**changes):
        p = dict(point)
        p.update(changes)
        return {"type": "minecraft:multi_noise", "biomes": [{"biome": "minecraft:plains", "parameters": p}]}

    out = [
        ("no-type", {"biome": "minecraft:plains"}),
        ("unknown-type", {"type": "minecraft:mystery", "biome": "minecraft:plains"}),
        ("not-an-object", "minecraft:plains"),
        ("fixed-no-biome", {"type": "minecraft:fixed"}),
        ("fixed-unknown-biome", {"type": "minecraft:fixed", "biome": "minecraft:nowhere"}),
        ("fixed-bad-id", {"type": "minecraft:fixed", "biome": "Not An Id"}),
        ("fixed-tag", {"type": "minecraft:fixed", "biome": "#minecraft:is_ocean"}),
        ("fixed-number", {"type": "minecraft:fixed", "biome": 3}),
        ("checkerboard-no-biomes", {"type": "minecraft:checkerboard"}),
        ("checkerboard-scale-63", {"type": "minecraft:checkerboard", "biomes": ["minecraft:plains"], "scale": 63}),
        ("checkerboard-scale-negative", {"type": "minecraft:checkerboard", "biomes": ["minecraft:plains"], "scale": -1}),
        ("checkerboard-missing-tag", {"type": "minecraft:checkerboard", "biomes": "#minecraft:is_nowhere"}),
        ("checkerboard-unknown-biome", {"type": "minecraft:checkerboard", "biomes": ["minecraft:plains", "minecraft:nowhere"]}),
        ("checkerboard-tag-in-list", {"type": "minecraft:checkerboard", "biomes": ["#minecraft:is_ocean"]}),
        ("multi-nothing", {"type": "minecraft:multi_noise"}),
        ("multi-empty", {"type": "minecraft:multi_noise", "biomes": []}),
        ("multi-unknown-preset", preset("mystery")),
        ("multi-preset-number", {"type": "minecraft:multi_noise", "preset": 1}),
        ("multi-preset-inline-unknown", {"type": "minecraft:multi_noise", "preset": {"preset": "minecraft:end"}}),
        ("multi-no-parameters", {"type": "minecraft:multi_noise", "biomes": [{"biome": "minecraft:plains"}]}),
        ("multi-no-biome", {"type": "minecraft:multi_noise", "biomes": [{"parameters": point}]}),
        ("multi-unknown-biome", {"type": "minecraft:multi_noise", "biomes": [{"biome": "minecraft:nowhere", "parameters": point}]}),
        ("multi-no-offset", {"type": "minecraft:multi_noise", "biomes": [{"biome": "minecraft:plains", "parameters": {f: 0 for f in FIELDS}}]}),
        ("multi-above-2", with_point(temperature=2.5)),
        ("multi-below-minus-2", with_point(erosion=-2.0001)),
        ("multi-backwards", with_point(humidity=[0.5, -0.5])),
        ("multi-backwards-object", with_point(depth={"min": 1, "max": 0})),
        ("multi-backwards-zeros", with_point(weirdness=[0.0, -0.0])),
        ("multi-three", with_point(continentalness=[0, 0.5, 1])),
        ("multi-one", with_point(continentalness=[0])),
        ("multi-no-max", with_point(continentalness={"min": 0})),
        ("multi-string", with_point(temperature="0.5")),
        ("multi-offset-above-1", with_point(offset=1.5)),
        ("multi-offset-negative", with_point(offset=-0.25)),
        ("multi-offset-negative-zero", with_point(offset=-0.0)),
        ("multi-infinite", with_point(temperature=1e40)),
        ("multi-bad-entry", {"type": "minecraft:multi_noise", "biomes": [{"biome": "minecraft:plains", "parameters": point}, 7]}),
        ("multi-not-a-list", {"type": "minecraft:multi_noise", "biomes": {"biome": "minecraft:plains", "parameters": point}}),
    ]
    return out


def main():
    g = Gen(SEED)
    ids = vanilla_ids()
    biomes = ids["worldgen/biome"]
    tags = ids["tags/worldgen/biome"]
    settings_names = [s.split(":")[1] for s in ids["worldgen/noise_settings"]]
    cases = []

    # Vanilla's presets, with the settings worlds give them, then with every other settings.
    for name, worlds in WORLD.items():
        c = Case(f"preset-{name}-list", g.seed(), worlds[0], preset(name))
        c.op("list")
        asked(g, c, worlds[0], chunks=1, heavy=False)
        cases.append(c.build())
        for settings in worlds:
            for i in range(5):
                c = Case(f"preset-{name}-{settings}-{i}", g.seed(), settings, preset(name), cached=i % 2 == 1)
                asked(g, c, settings, chunks=3)
                cases.append(c.build())
        for settings in settings_names:
            if settings not in worlds:
                c = Case(f"preset-{name}-with-{settings}", g.seed(), settings, preset(name), cached=g.chance(2))
                asked(g, c, settings)
                cases.append(c.build())
        # The preset written out as its file is.
        c = Case(f"preset-{name}-inline", g.seed(), worlds[0], {"type": "multi_noise", "preset": {"preset": name}})
        c.op("list")
        asked(g, c, worlds[0], chunks=1, heavy=False)
        cases.append(c.build())

    # Searching the presets directly: near their entries, far from all of them, and where the
    # squared distances wrap.
    for name in WORLD:
        for i in range(3):
            c = Case(f"preset-{name}-search-{i}", g.seed(), WORLD[name][0], preset(name))
            c.read("search", targets(g, 300, 12000), 300)
            c.read("search", targets(g, 60, 40000), 60)
            c.read("search", targets(g, 20, INT_MAX), 20)
            c.read("search", edge_targets(g, 40), 40)
            c.read("points", near(g, 40), 40)
            cases.append(c.build())

    # The End: the central island, then the outer islands, with the End's settings and others.
    end = {"type": "minecraft:the_end"}
    for settings in ["end"] * 6 + ["overworld", "nether", "floating_islands"]:
        c = Case(f"end-{settings}-{len(cases)}", g.seed(), settings, end, cached=g.chance(2))
        c.read("points", near(g, 80), 80)
        c.read("points", {"gen": "i32_range", "seed": g.blob_seed(), "count": 200,
                          "ranges": [["-20000", "20000"], ["-16", "80"], ["-20000", "20000"]]}, 200)
        c.read("points", far(g, 40), 40)
        c.read("points", edges(g, 12), 12)
        c.read("climate", near(g, 8), 8)
        min_y, height = WORLDS[settings]
        for cx, cz in [(0, 0), (64, 0), (65, 0), (-46, 46), (g.between(-1000, 1000), g.between(-1000, 1000)),
                       (g.between(-1000, 1000), g.between(-1000, 1000))]:
            c.op("chunk", cx, cz, min_y, height)
        cases.append(c.build())

    # Fixed: one biome everywhere, for a handful of biomes and settings.
    for i in range(10):
        b = g.pick(biomes)
        written_type = g.pick(["minecraft:fixed", "fixed"])
        settings = g.pick(settings_names)
        c = Case(f"fixed-{i}", g.seed(), settings, {"type": written_type, "biome": b})
        c.read("points", near(g, 20), 20)
        c.read("points", edges(g, 5), 5)
        c.op("chunk", g.between(-100, 100), g.between(-100, 100), *WORLDS[settings])
        cases.append(c.build())

    # The checkerboard at every scale, its shift past 31 as Java masks it, with each way of
    # naming its biomes.
    for scale in list(range(0, 63)) + [None]:
        form = g.below(4)
        if form == 0:
            listed = "#" + g.pick(tags)
        elif form == 1:
            listed = g.pick(biomes)
        else:
            listed = [g.pick(biomes) for _ in range(g.between(1, 9))]
            if len(listed) > 2 and g.chance(2):
                listed[1] = listed[0]
        source = {"type": "minecraft:checkerboard", "biomes": listed}
        if scale is not None:
            source["scale"] = scale
        settings = g.pick(settings_names)
        c = Case(f"checkerboard-{'default' if scale is None else scale}", g.seed(), settings, source)
        c.read("points", near(g, 40), 40)
        c.read("points", far(g, 20), 20)
        c.read("points", edges(g, 10), 10)
        c.read("points", anywhere(g, 10), 10)
        c.op("chunk", g.between(-100, 100), g.between(-100, 100), *WORLDS[settings])
        cases.append(c.build())
    # No biomes at all: reads, then throws at the first biome asked for.
    c = Case("checkerboard-empty", g.seed(), "overworld", {"type": "minecraft:checkerboard", "biomes": []})
    c.read("points", near(g, 3), 3)
    cases.append(c.build())
    c = Case("checkerboard-empty-chunk", g.seed(), "overworld", {"type": "minecraft:checkerboard", "biomes": []})
    c.op("chunk", 0, 0, -64, 384)
    cases.append(c.build())
    c = Case("checkerboard-empty-unasked", g.seed(), "overworld", {"type": "minecraft:checkerboard", "biomes": []})
    cases.append(c.build())

    # Lists written out: sizes either side of a node's 19 children and of the tree's levels,
    # points from a coarse grid so many tie, and from anywhere.
    sizes = [1, 2, 3, 5, 18, 19, 20, 21, 37, 38, 40, 100, 360, 361, 362, 363, 400, 722, 723, 1500]
    grids = [None, [-1, 0, 1], [-2, -1, -0.5, 0, 0.5, 1, 2], [0], [-0.25, 0.25]]
    for i, n in enumerate(sizes + [n for n in sizes if n <= 400]):
        grid = grids[i % len(grids)]
        settings = g.pick(["overworld", "overworld", "nether", "large_biomes", "end"])
        c = Case(f"written-{n}-{i}", g.seed(), settings, written(g, biomes[: g.between(2, len(biomes))], n, grid),
                 cached=g.chance(2))
        c.op("list")
        c.read("search", targets(g, 200, 22000), 200)
        c.read("search", targets(g, 30, INT_MAX), 30)
        c.read("search", edge_targets(g, 20), 20)
        c.read("points", near(g, 60), 60)
        c.read("search", targets(g, 50, 3), 50)
        if n <= 400:
            c.op("chunk", g.between(-60, 60), g.between(-60, 60), *WORLDS[settings])
        cases.append(c.build())
    # Quantizing: values a ten-thousandth apart, and halves of one, either side of 0.
    fine = [-0.0001, -0.00005, -0.00004, 0, 0.00004, 0.00005, 0.0001, 0.00015, -0.00015, 1.99995, -1.99995, 2, -2]
    for i in range(6):
        c = Case(f"written-quantized-{i}", g.seed(), "overworld", written(g, biomes, 40, fine))
        c.op("list")
        c.read("search", targets(g, 100, 3), 100)
        c.read("search", edge_targets(g, 20), 20)
        cases.append(c.build())
    # Booleans, which `JsonOps` doesn't read as numbers.
    point = {f: 0 for f in FIELDS}
    c = Case("invalid-booleans", g.seed(), "overworld", {"type": "minecraft:multi_noise", "biomes": [
        {"biome": "minecraft:plains", "parameters": dict(point, temperature=True, offset=False)},
        {"biome": "minecraft:desert", "parameters": dict(point, humidity=[False, True], offset=True)},
    ]})
    c.op("list")
    c.read("search", targets(g, 40, 15000), 40)
    cases.append(c.build())
    # Both a list and a preset: the list wins when it reads, and the preset when it doesn't.
    c = Case("written-and-preset", g.seed(), "nether", dict(written(g, biomes, 5, None), preset="minecraft:nether"))
    c.op("list")
    cases.append(c.build())
    bad = written(g, biomes, 3, None)
    bad["biomes"][1]["biome"] = "minecraft:nowhere"
    bad["preset"] = "minecraft:nether"
    c = Case("written-bad-then-preset", g.seed(), "nether", bad)
    c.op("list")
    cases.append(c.build())

    for name, source in invalid_sources(ids):
        c = Case(f"invalid-{name}", g.seed(), "overworld", source)
        c.read("points", near(g, 2), 2)
        cases.append(c.build())

    write_file(HERE / "generated.json", "biomes", f"cases/biomes/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
