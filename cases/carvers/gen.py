"""Writes cases/carvers/generated.json: chunks filled, given their materials and then carved, by
the carvers of their biomes and by carvers written out.

    py -I cases/carvers/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

The cases name vanilla's carvers by id and never copy them. Each of vanilla's noise settings
carves chunks with the carvers of the biomes its world has, near the origin and far out. Then
sources that put one biome everywhere carve under each biome's materials, where a cave through
grass gives the dirt under it the biome's top material; carvers written out try each value
provider, room, split, floor and canyon width on their own, over worlds that aren't the noise's;
chunks at the ends of `int`; rules written out for the top material; and carvers vanilla doesn't
read, or that throw.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261107
LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]
# Each settings' world, as (min_y, height), and the source its world preset gives it.
WORLDS = {
    "overworld": ((-64, 384), "overworld"),
    "large_biomes": ((-64, 384), "overworld"),
    "amplified": ((-64, 384), "overworld"),
    "caves": ((-64, 384), "overworld"),
    "floating_islands": ((-64, 384), "overworld"),
    "nether": ((0, 256), "nether"),
    "end": ((0, 256), "end"),
}
BORDER = 1874999
# Biomes whose materials differ, so a cave through their grass gives the dirt under it its own.
OVERWORLD = [
    "plains", "desert", "badlands", "eroded_badlands", "mushroom_fields", "frozen_ocean", "ocean",
    "deep_ocean", "swamp", "mangrove_swamp", "snowy_slopes", "frozen_peaks", "stony_peaks",
    "windswept_gravelly_hills", "beach", "river", "lush_caves", "deep_dark", "dripstone_caves",
    "sulfur_caves", "old_growth_pine_taiga", "forest", "jungle", "savanna",
]
NETHER = ["nether_wastes", "soul_sand_valley", "crimson_forest", "warped_forest", "basalt_deltas"]
CARVERS = ["cave", "cave_extra_underground", "canyon", "nether_cave"]
STATES = [
    "minecraft:stone", "minecraft:glass", "minecraft:grass_block", "minecraft:mycelium",
    "minecraft:water", "minecraft:lava", "minecraft:sand",
    {"id": "minecraft:sea_pickle", "properties": {"waterlogged": "true", "pickles": "2"}},
    "minecraft:air",
]


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

    def unit(self):
        return self.u64() / float(1 << 64)

    def real(self, lo, hi):
        return round(lo + (hi - lo) * self.unit(), 4)

    def long(self):
        v = self.u64()
        return str(v - (1 << 64) if v >= 1 << 63 else v)

    def seed(self):
        return self.pick(LONG_SEEDS) if self.chance(4) else self.long()


def m(name):
    return "minecraft:" + name


def preset(name):
    if name == "end":
        return {"type": "minecraft:the_end"}
    return {"type": "minecraft:multi_noise", "preset": m(name)}


def fixed(biome):
    return {"type": "minecraft:fixed", "biome": m(biome)}


def checkerboard(biomes, scale):
    return {"type": "minecraft:checkerboard", "biomes": [m(b) for b in biomes], "scale": scale}


class Case:
    def __init__(self, cid, seed, settings, level, source, carvers=None, rule=None):
        self.cid = cid
        self.input = {"seed": seed, "settings": m(settings), "level": list(level), "source": source}
        if carvers is not None:
            self.input["carvers"] = carvers
        if rule is not None:
            self.input["rule"] = rule
        self.input["ops"] = []

    def carve(self, cx, cz):
        self.input["ops"].append(["carve", cx, cz])
        return self

    def build(self):
        return {"id": self.cid, "input": self.input}


def near_chunk(g, spread=64):
    return g.between(-spread, spread), g.between(-spread, spread)


def far_chunk(g):
    return g.between(-BORDER, BORDER), g.between(-BORDER, BORDER)


# Value providers.

def anchor(g):
    kind = g.below(4)
    if kind == 0:
        return {"absolute": g.between(-70, 200)}
    if kind == 1:
        return {"above_bottom": g.between(-4, 80)}
    if kind == 2:
        return {"below_top": g.between(0, 300)}
    return {"relative_to_sea_level": g.between(-90, 100)}


def height(g, depth=0):
    kind = g.below(7 if depth == 0 else 6)
    if kind == 0:
        return anchor(g)
    if kind == 1:
        return {"type": m("constant"), "value": anchor(g)}
    if kind == 2:
        return {"type": m("uniform"), "min_inclusive": anchor(g), "max_inclusive": anchor(g)}
    if kind == 3:
        h = {"type": m(g.pick(["biased_to_bottom", "very_biased_to_bottom"])), "min_inclusive": {"above_bottom": g.between(0, 20)}, "max_inclusive": anchor(g)}
        if g.chance(2):
            h["inner"] = g.between(1, 12)
        return h
    if kind == 4:
        h = {"type": m("trapezoid"), "min_inclusive": anchor(g), "max_inclusive": anchor(g)}
        if g.chance(2):
            h["plateau"] = g.between(-4, 60)
        return h
    if kind == 5:
        return {"type": m("uniform"), "min_inclusive": {"above_bottom": 8}, "max_inclusive": {"absolute": g.between(40, 180)}}
    return {"type": m("weighted_list"), "distribution": [{"data": height(g, 1), "weight": g.between(0, 5)} for _ in range(g.between(1, 3))] + [{"data": height(g, 1), "weight": 1}]}


def count(g, depth=0):
    kind = g.below(8 if depth == 0 else 7)
    lo = g.between(0, 2)
    hi = lo + g.between(0, 4)
    if kind == 0:
        return g.between(0, 4)
    if kind == 1:
        return {"type": m("constant"), "value": g.between(0, 4)}
    if kind == 2:
        return {"type": m(g.pick(["uniform", "biased_to_bottom", "very_biased_to_bottom"])), "min_inclusive": lo, "max_inclusive": hi}
    if kind == 3:
        return {"type": m("clamped"), "source": count(g, 1), "min_inclusive": lo, "max_inclusive": hi}
    if kind == 4:
        return {"type": m("clamped_normal"), "mean": g.real(-1, 5), "deviation": g.real(0, 3), "min_inclusive": lo, "max_inclusive": hi}
    if kind == 5:
        return {"type": m("trapezoid"), "min": lo, "max": hi, "plateau": g.between(0, hi - lo)}
    if kind == 6:
        return {"type": m("very_biased_to_bottom"), "min_inclusive": 0, "max_inclusive": g.between(2, 14)}
    return {"type": m("weighted_list"), "distribution": [{"data": count(g, 1), "weight": g.between(1, 4)} for _ in range(g.between(1, 3))]}


def floats(g, lo, hi, minimum=None):
    """A float provider whose values stay within [lo, hi]."""
    kind = g.below(5)
    a = g.real(lo, hi)
    b = g.real(lo, hi)
    a, b = min(a, b), max(a, b)
    if b == a:
        b = round(a + 0.01, 4) if a + 0.01 <= hi else a
        a = round(b - 0.01, 4)
    if kind == 0:
        return a
    if kind == 1:
        return {"type": m("constant"), "value": b}
    if kind == 2:
        return {"type": m("uniform"), "min_inclusive": a, "max_exclusive": b}
    if kind == 3:
        return {"type": m("clamped_normal"), "mean": round((a + b) / 2, 4), "deviation": g.real(0, hi - lo), "min": a, "max": b}
    return {"type": m("trapezoid"), "min": a, "max": b, "plateau": round((b - a) * g.unit() * 0.9, 4)}


def cave(g):
    c = {
        "type": m("cave"),
        "probability": g.pick([0.15, 0.3, 0.6, 1.0, g.real(0.0, 1.0)]),
        "y": height(g),
        "count": count(g),
        "thickness": floats(g, 0.0, 6.0),
        "room_vertical_radius_multiplier": floats(g, 0.0, 2.0),
        "horizontal_radius_multiplier": floats(g, 0.3, 2.5),
        "vertical_radius_multiplier": floats(g, 0.3, 2.5),
        "floor_level": floats(g, -1.0, 1.0),
    }
    if g.chance(2):
        c["weird_thickness_bias"] = g.chance(2)
    if g.chance(2):
        c["start_vertical_radius_multiplier"] = floats(g, 0.2, 6.0)
    return c


def canyon(g):
    return {
        "type": m("canyon"),
        "probability": g.pick([0.01, 0.05, 0.2, 1.0, g.real(0.0, 0.3)]),
        "y": height(g),
        "vertical_rotation": floats(g, -0.5, 0.5),
        "shape": {
            "distance_factor": floats(g, 0.1, 1.5),
            "thickness": floats(g, 0.0, 8.0),
            "width_smoothness": g.pick([1, 2, 3, 5, 40]),
            "horizontal_radius_factor": floats(g, 0.5, 1.5),
            "vertical_radius_default_factor": g.real(0.0, 2.0),
            "vertical_radius_center_factor": g.real(-1.0, 2.0),
            "y_scale": floats(g, 0.5, 5.0),
        },
    }


def carver(g):
    return cave(g) if g.chance(3) or g.chance(2) else canyon(g)


def written(g):
    if g.chance(4):
        return [m(g.pick(CARVERS)) for _ in range(g.between(1, 3))]
    return [carver(g) for _ in range(g.between(1, 3))]


def invalid_carvers():
    good_cave = cave(Gen(1))
    good_canyon = canyon(Gen(2))
    good_canyon["probability"] = 0.5

    def cave_with(**fields):
        c = dict(good_cave)
        for k, v in fields.items():
            if v is None:
                c.pop(k, None)
            else:
                c[k] = v
        return [c]

    def shape_with(**fields):
        c = dict(good_canyon)
        shape = dict(c["shape"])
        for k, v in fields.items():
            if v is None:
                shape.pop(k, None)
            else:
                shape[k] = v
        c["shape"] = shape
        return [c]

    return [
        ("no-type", [{k: v for k, v in good_cave.items() if k != "type"}]),
        ("unknown-type", [{**good_cave, "type": "minecraft:mystery"}]),
        ("unknown-reference", ["minecraft:nowhere"]),
        ("unknown-single-reference", "minecraft:nowhere"),
        ("missing-tag", "#minecraft:nowhere"),
        ("not-a-carver", [3]),
        ("mixed-kinds-unknown", ["minecraft:cave", good_cave, "minecraft:nowhere"]),
        ("probability-above-1", cave_with(probability=1.5)),
        ("probability-below-0", cave_with(probability=-0.1)),
        ("probability-minus-0", cave_with(probability=-0.0)),
        ("no-y", cave_with(y=None)),
        ("y-two-anchors", cave_with(y={"absolute": 0, "above_bottom": 2})),
        ("y-bad-inner", cave_with(y={"type": m("biased_to_bottom"), "min_inclusive": {"absolute": 0}, "max_inclusive": {"absolute": 40}, "inner": 0})),
        ("count-negative", cave_with(count=-1)),
        ("count-uniform-negative", cave_with(count={"type": m("uniform"), "min_inclusive": -1, "max_inclusive": 3})),
        ("count-uniform-backwards", cave_with(count={"type": m("uniform"), "min_inclusive": 3, "max_inclusive": 1})),
        ("count-empty-weights", cave_with(count={"type": m("weighted_list"), "distribution": []})),
        ("count-zero-weights", cave_with(count={"type": m("weighted_list"), "distribution": [{"data": 1, "weight": 0}]})),
        ("count-negative-weight", cave_with(count={"type": m("weighted_list"), "distribution": [{"data": 1, "weight": -1}]})),
        ("count-plateau-past-span", cave_with(count={"type": m("trapezoid"), "min": 0, "max": 2, "plateau": 3})),
        ("thickness-negative", cave_with(thickness={"type": m("uniform"), "min_inclusive": -1.0, "max_exclusive": 2.0})),
        ("thickness-uniform-empty", cave_with(thickness={"type": m("uniform"), "min_inclusive": 2.0, "max_exclusive": 2.0})),
        ("thickness-normal-backwards", cave_with(thickness={"type": m("clamped_normal"), "mean": 1.0, "deviation": 1.0, "min": 3.0, "max": 1.0})),
        ("floor-above-1", cave_with(floor_level=1.5)),
        ("floor-uniform-below-minus-1", cave_with(floor_level={"type": m("uniform"), "min_inclusive": -1.5, "max_exclusive": 0.0})),
        ("no-floor", cave_with(floor_level=None)),
        ("bad-start-vertical", cave_with(start_vertical_radius_multiplier="wide")),
        ("bad-weird", cave_with(weird_thickness_bias="yes")),
        ("unknown-float-type", cave_with(horizontal_radius_multiplier={"type": m("mystery")})),
        ("canyon-no-shape", [{k: v for k, v in good_canyon.items() if k != "shape"}]),
        ("canyon-smoothness-0", shape_with(width_smoothness=0)),
        ("canyon-no-y-scale", shape_with(y_scale=None)),
        ("canyon-factor-not-number", shape_with(vertical_radius_center_factor="big")),
        ("canyon-bad-rotation", [{**good_canyon, "vertical_rotation": {"type": m("uniform"), "min_inclusive": 1.0, "max_exclusive": 0.0}}]),
    ]


def main():
    g = Gen(SEED)
    cases = []

    # Each settings in its world, with its biomes' carvers.
    for settings, (level, source) in WORLDS.items():
        c = Case(f"{settings}-origin", g.seed(), settings, level, preset(source))
        c.carve(0, 0).carve(-1, -1).carve(*near_chunk(g))
        cases.append(c.build())
        for i in range(2):
            c = Case(f"{settings}-near-{i}", g.seed(), settings, level, preset(source))
            c.carve(*near_chunk(g, 600)).carve(*near_chunk(g, 600))
            cases.append(c.build())
        c = Case(f"{settings}-far", g.seed(), settings, level, preset(source))
        c.carve(*far_chunk(g)).carve(*far_chunk(g))
        cases.append(c.build())

    # The Overworld's carvers with more seeds, where worlds are.
    for i in range(16):
        settings = ["overworld", "overworld", "large_biomes", "amplified"][i % 4]
        c = Case(f"overworld-seeds-{i}", g.seed(), settings, (-64, 384), preset("overworld"))
        c.carve(*near_chunk(g, 3000)).carve(*near_chunk(g, 3000))
        cases.append(c.build())

    # One biome everywhere: caves through each biome's materials.
    for biome in OVERWORLD:
        c = Case(f"fixed-{biome}", g.seed(), "overworld", (-64, 384), fixed(biome))
        for _ in range(2):
            c.carve(*near_chunk(g, 2000))
        cases.append(c.build())
    for biome in NETHER:
        c = Case(f"fixed-{biome}", g.seed(), "nether", (0, 256), fixed(biome))
        c.carve(*near_chunk(g, 500)).carve(*near_chunk(g, 500))
        cases.append(c.build())
    for biome in ["nether_wastes", "plains"]:
        other = "overworld" if biome == "nether_wastes" else "nether"
        level = WORLDS[other][0]
        c = Case(f"fixed-{biome}-in-{other}", g.seed(), other, level, fixed(biome))
        c.carve(*near_chunk(g, 500)).carve(*near_chunk(g, 500))
        cases.append(c.build())
    # Checkerboards: the chunks around have the carvers of different biomes.
    for i in range(6):
        biomes = [g.pick(OVERWORLD + NETHER + ["the_end", "small_end_islands"]) for _ in range(g.between(2, 5))]
        c = Case(f"checkerboard-{i}", g.seed(), "overworld", (-64, 384), checkerboard(biomes, g.between(0, 3)))
        c.carve(*near_chunk(g, 2000)).carve(*near_chunk(g, 2000))
        cases.append(c.build())

    # Carvers written out, over the Overworld's terrain and others.
    for i in range(48):
        settings = g.pick(["overworld", "overworld", "overworld", "amplified", "nether", "caves", "end", "floating_islands"])
        level = WORLDS[settings][0]
        source = preset(WORLDS[settings][1]) if g.chance(2) else fixed(g.pick(OVERWORLD))
        c = Case(f"written-{i}", g.seed(), settings, level, source, written(g))
        c.carve(*near_chunk(g, 1000))
        cases.append(c.build())
    # Vanilla's carvers on their own and together.
    for name in CARVERS:
        c = Case(f"carver-{name}", g.seed(), "overworld", (-64, 384), preset("overworld"), [m(name)])
        c.carve(*near_chunk(g, 1000)).carve(*near_chunk(g, 1000))
        cases.append(c.build())
    c = Case("carver-single", g.seed(), "overworld", (-64, 384), preset("overworld"), m("canyon"))
    c.carve(*near_chunk(g, 1000))
    cases.append(c.build())
    c = Case("carver-single-written", g.seed(), "overworld", (-64, 384), preset("overworld"), {**canyon(g), "probability": 1.0})
    c.carve(*near_chunk(g, 1000))
    cases.append(c.build())
    c = Case("carver-none", g.seed(), "overworld", (-64, 384), preset("overworld"), [])
    c.carve(*near_chunk(g, 1000))
    cases.append(c.build())
    c = Case("carver-repeated", g.seed(), "overworld", (-64, 384), preset("overworld"), [m("cave"), m("cave"), m("canyon"), m("cave")])
    c.carve(*near_chunk(g, 1000))
    cases.append(c.build())
    c = Case("carver-mixed", g.seed(), "overworld", (-64, 384), preset("overworld"), [m("canyon"), {**cave(g), "probability": 0.5}, "cave"])
    c.carve(*near_chunk(g, 1000))
    cases.append(c.build())
    # Many caves near the surface: grass cut to dirt, and the dirt's top material.
    for i in range(6):
        shallow = {**cave(g), "probability": 1.0, "y": {"type": m("uniform"), "min_inclusive": {"absolute": 55}, "max_inclusive": {"absolute": 110}}, "count": g.between(1, 3)}
        c = Case(f"shallow-{i}", g.seed(), "overworld", (-64, 384), fixed(g.pick(["plains", "mushroom_fields", "snowy_slopes", "swamp", "badlands", "frozen_ocean"])), [shallow])
        c.carve(*near_chunk(g, 1000))
        cases.append(c.build())
    # Rooms and splits: thick tunnels split, rooms of every height.
    for i in range(4):
        thick = {**cave(g), "probability": 1.0, "count": 1, "thickness": {"type": m("uniform"), "min_inclusive": 1.5, "max_exclusive": 6.0}, "weird_thickness_bias": True}
        c = Case(f"thick-{i}", g.seed(), "overworld", (-64, 384), preset("overworld"), [thick])
        c.carve(*near_chunk(g, 1000))
        cases.append(c.build())
    # Canyons always, through land, sea and the bottom of the world.
    for i in range(4):
        deep = {**canyon(g), "probability": 1.0}
        settings = "overworld" if i % 2 == 0 else "nether"
        c = Case(f"canyon-{i}", g.seed(), settings, WORLDS[settings][0], preset(WORLDS[settings][1]), [deep])
        c.carve(*near_chunk(g, 1000))
        cases.append(c.build())
    # The bottom and top of the generated world: bedrock isn't carved, the top 7 blocks never.
    edges = {**cave(g), "probability": 1.0, "count": 2, "y": {"type": m("uniform"), "min_inclusive": {"above_bottom": -4}, "max_inclusive": {"above_bottom": 6}}}
    tops = {**cave(g), "probability": 1.0, "count": 2, "y": {"type": m("uniform"), "min_inclusive": {"below_top": 6}, "max_inclusive": {"below_top": -4}}}
    for name, cv in [("bottom", edges), ("top", tops)]:
        for settings in ["overworld", "nether"]:
            c = Case(f"edge-{name}-{settings}", g.seed(), settings, WORLDS[settings][0], preset(WORLDS[settings][1]), [cv])
            c.carve(*near_chunk(g, 300))
            cases.append(c.build())

    # Rules written out for the top material.
    rules = [
        ("all-glass", {"type": m("block"), "result_state": "minecraft:glass"}),
        ("all-water", {"type": m("block"), "result_state": "minecraft:water"}),
        ("empty", {"type": m("sequence"), "sequence": []}),
        ("water-condition", {"type": m("condition"), "if_true": {"type": m("water"), "offset": 0, "surface_depth_multiplier": 0, "add_stone_depth": False}, "then_run": {"type": m("block"), "result_state": "minecraft:mycelium"}}),
        ("pickles", {"type": m("block"), "result_state": STATES[7]}),
    ]
    for name, r in rules:
        shallow = {**cave(g), "probability": 1.0, "y": {"type": m("uniform"), "min_inclusive": {"absolute": 58}, "max_inclusive": {"absolute": 100}}, "count": 2}
        c = Case(f"rule-{name}", g.seed(), "overworld", (-64, 384), fixed("plains"), [shallow], r)
        c.carve(*near_chunk(g, 500))
        cases.append(c.build())
    c = Case("rule-overworld-in-nether", g.seed(), "nether", (0, 256), fixed("plains"), None, m("overworld"))
    c.carve(*near_chunk(g, 300))
    cases.append(c.build())

    # Worlds that aren't the noise's: taller, shorter, overlapping its top or bottom, or past it.
    levels = [
        ("tall", (-128, 512)),
        ("short", (0, 128)),
        ("one-section", (-64, 16)),
        ("top-section", (304, 16)),
        ("above", (320, 64)),
        ("low", (-512, 448)),
        ("partial", (-32, 48)),
    ]
    for name, level in levels:
        for settings in ["overworld", "nether"]:
            c = Case(f"level-{name}-{settings}", g.seed(), settings, level, preset(WORLDS[settings][1]))
            c.carve(*near_chunk(g, 64))
            cases.append(c.build())
    for settings in ["end", "nether"]:
        c = Case(f"level-partial-written-{settings}", g.seed(), settings, (-32, 48), preset(WORLDS[settings][1]), [{**cave(g), "probability": 1.0, "count": 3, "y": {"absolute": 0}}])
        c.carve(*near_chunk(g, 64))
        cases.append(c.build())

    # The ends of `int`, where blocks and quarts wrap.
    for i, (cx, cz) in enumerate([((1 << 27) - 1, (1 << 27) - 1), (-(1 << 27), -(1 << 27)), ((1 << 27) - 5, -(1 << 27) + 3)]):
        c = Case(f"int-edge-{i}", g.seed(), "overworld", (-64, 384), preset("overworld") if i < 2 else fixed("plains"), None if i < 2 else [{**cave(g), "probability": 1.0, "count": 2}])
        c.carve(cx, cz)
        cases.append(c.build())

    # Carvers that throw: a count whose bound wraps past an int.
    wrapping = {**cave(Gen(5)), "probability": 1.0, "count": {"type": m("uniform"), "min_inclusive": 0, "max_inclusive": 2147483647}}
    cases.append(Case("throws-count-bound", "0", "overworld", (-64, 384), preset("overworld"), [wrapping]).carve(0, 0).build())
    wrapping_height = {**cave(Gen(6)), "probability": 1.0, "count": 1, "y": {"type": m("uniform"), "min_inclusive": {"absolute": -2032}, "max_inclusive": {"absolute": 2031}}}
    cases.append(Case("height-wide", "0", "overworld", (-64, 384), preset("overworld"), [wrapping_height]).carve(0, 0).build())
    empty_height = {**cave(Gen(7)), "probability": 1.0, "count": 1, "y": {"type": m("uniform"), "min_inclusive": {"absolute": 100}, "max_inclusive": {"absolute": 20}}}
    cases.append(Case("height-empty", "0", "overworld", (-64, 384), preset("overworld"), [empty_height]).carve(0, 0).build())

    # Carvers vanilla doesn't read.
    for name, cv in invalid_carvers():
        cases.append(Case(f"invalid-carvers-{name}", "0", "overworld", (-64, 384), preset("overworld"), cv).carve(0, 0).build())
    cases.append(Case("invalid-rule-first", "0", "overworld", (-64, 384), preset("overworld"), ["minecraft:nowhere"], "minecraft:nowhere").carve(0, 0).build())

    write_file(HERE / "generated.json", "carvers", f"cases/carvers/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
