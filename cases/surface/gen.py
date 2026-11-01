"""Writes cases/surface/generated.json: chunks filled and given their materials, by vanilla's rules
and by rules written out.

    py -I cases/surface/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

The cases name vanilla's material by id and never copy it. Each of vanilla's noise settings gives
chunks their materials with its own rule and the biomes its world has, near the origin and far
out. Then the Overworld's rule runs over sources that put one biome everywhere, for the biomes
whose materials are their own (badlands and their pillars, frozen oceans and their icebergs,
peaks, shores, swamps, caves), and over checkerboards that change biome every few quarts, where
the zoom between biomes counts. Then rules written out try each condition and rule on their own
and nested, with anchors of each kind; worlds that aren't the noise's; chunks at the ends of
`int`; and sources and rules vanilla doesn't read.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261105
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
# The Overworld's biomes, the ones with materials of their own first.
SPECIAL = [
    "eroded_badlands", "badlands", "wooded_badlands", "frozen_ocean", "deep_frozen_ocean",
    "frozen_peaks", "jagged_peaks", "stony_peaks", "snowy_slopes", "grove", "ice_spikes",
    "stony_shore", "mangrove_swamp", "swamp", "mushroom_fields", "desert", "beach", "snowy_beach",
    "windswept_hills", "windswept_gravelly_hills", "windswept_savanna", "old_growth_pine_taiga",
    "old_growth_spruce_taiga", "dripstone_caves", "sulfur_caves", "dappled_forest", "lush_caves",
    "deep_dark", "frozen_river", "river", "warm_ocean", "ocean", "deep_ocean", "snowy_plains",
]
OTHERS = [
    "plains", "sunflower_plains", "forest", "flower_forest", "birch_forest", "dark_forest",
    "pale_garden", "taiga", "snowy_taiga", "savanna", "savanna_plateau", "jungle", "sparse_jungle",
    "bamboo_jungle", "meadow", "cherry_grove", "cold_ocean", "lukewarm_ocean", "deep_cold_ocean",
    "deep_lukewarm_ocean", "windswept_forest", "old_growth_birch_forest",
]
NETHER = ["nether_wastes", "soul_sand_valley", "crimson_forest", "warped_forest", "basalt_deltas"]
END = ["the_end", "end_highlands", "end_midlands", "small_end_islands", "end_barrens"]
TAGS = ["is_badlands", "is_ocean", "is_deep_ocean", "is_mountain", "is_beach", "is_river", "is_taiga", "is_forest", "is_overworld", "is_nether"]
NOISES = [
    "surface", "surface_secondary", "gravel", "powder_snow", "calcite", "packed_ice", "ice",
    "surface_swamp", "sulfur_cave_gradient", "badlands_pillar", "patch", "netherrack", "nether_wart",
    "soul_sand_layer", "gravel_layer", "nether_state_selector",
]
# Vanilla's named rules and conditions.
RULES = [
    "overworld", "overworld_caves", "overworld_floating_islands", "nether", "end", "bedrock_floor",
    "bedrock_roof", "overworld/surface", "overworld/underground", "overworld/copper_ore_vein",
    "overworld/iron_ore_vein", "overworld/biome_surface", "overworld/under_biome_surface",
    "overworld/sulfur_cave_bands", "overworld/powder_snow_surface",
]
CONDITIONS = [
    "on_floor", "under_floor", "deep_under_floor", "very_deep_under_floor", "on_ceiling",
    "under_ceiling", "not_underwater", "not_under_deep_water",
]
STATES = [
    "minecraft:stone", "minecraft:dirt", "minecraft:sand", "minecraft:red_sand", "minecraft:gravel",
    "minecraft:packed_ice", "minecraft:snow_block", "minecraft:mud", "minecraft:deepslate",
    "minecraft:water", "minecraft:lava", "minecraft:air", "minecraft:cave_air",
    {"id": "minecraft:grass_block", "properties": {"snowy": "true"}},
    {"id": "minecraft:oak_log", "properties": {"axis": "x"}},
    {"id": "minecraft:water", "properties": {"level": "3"}},
    {"id": "minecraft:sea_pickle", "properties": {"waterlogged": "true", "pickles": "2"}},
    {"id": "minecraft:kelp"},
    "minecraft:seagrass",
    "minecraft:glass",
]
DENSITIES = [
    "minecraft:overworld/ore_vein/copper_density", "minecraft:overworld/ore_vein/iron_density",
    "minecraft:overworld/ore_vein/richness", "minecraft:overworld/ore_vein/gap",
    "minecraft:overworld/depth", "minecraft:overworld/continents",
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
    def __init__(self, cid, seed, settings, level, source, rule=None):
        self.cid = cid
        self.input = {"seed": seed, "settings": m(settings), "level": list(level), "source": source}
        if rule is not None:
            self.input["rule"] = rule
        self.input["ops"] = []

    def surface(self, cx, cz):
        self.input["ops"].append(["surface", cx, cz])
        return self

    def build(self):
        return {"id": self.cid, "input": self.input}


def near_chunk(g, spread=64):
    return g.between(-spread, spread), g.between(-spread, spread)


def far_chunk(g):
    return g.between(-BORDER, BORDER), g.between(-BORDER, BORDER)


# Rules written out.

def anchor(g):
    kind = g.below(4)
    if kind == 0:
        return {"absolute": g.between(-80, 330)}
    if kind == 1:
        return {"above_bottom": g.between(-10, 80)}
    if kind == 2:
        return {"below_top": g.between(-10, 300)}
    return {"relative_to_sea_level": g.between(-60, 120)}


def state(g):
    return g.pick(STATES)


def condition(g, depth):
    kind = g.below(14 if depth < 3 else 12)
    if kind == 0:
        which = g.below(3)
        if which == 0:
            biome_is = m(g.pick(SPECIAL + OTHERS))
        elif which == 1:
            biome_is = [m(g.pick(SPECIAL + OTHERS)) for _ in range(g.between(1, 4))]
        else:
            biome_is = "#" + m(g.pick(TAGS))
        return {"type": m("biome"), "biome_is": biome_is}
    if kind == 1:
        low = g.real(-1.2, 0.8)
        c = {"type": m("noise_threshold"), "noise": m(g.pick(NOISES)), "min_threshold": low, "max_threshold": round(low + g.real(0.0, 1.5), 4)}
        if g.chance(2):
            c["is_3d"] = g.chance(2)
        return c
    if kind == 2:
        return {"type": m("vertical_gradient"), "random_name": m(g.pick(["bedrock_floor", "deepslate", "gradient", "surface"])), "true_at_and_below": anchor(g), "false_at_and_above": anchor(g)}
    if kind == 3:
        return {"type": m("y_above"), "anchor": anchor(g), "surface_depth_multiplier": g.between(-20, 20), "add_stone_depth": g.chance(2)}
    if kind == 4:
        return {"type": m("water"), "offset": g.between(-12, 6), "surface_depth_multiplier": g.between(-3, 3), "add_stone_depth": g.chance(2)}
    if kind == 5:
        return {"type": m("temperature")}
    if kind == 6:
        return {"type": m("steep")}
    if kind == 7:
        return {"type": m("hole")}
    if kind == 8:
        return {"type": m("above_preliminary_surface")}
    if kind in (9, 10):
        return {"type": m("stone_depth"), "offset": g.between(-3, 12), "add_surface_depth": g.chance(2),
                "secondary_depth_range": g.pick([0, 0, 1, 6, 30, -4]), "surface_type": g.pick(["floor", "ceiling"])}
    if kind == 11:
        return m(g.pick(CONDITIONS))
    return {"type": m("not"), "invert": condition(g, depth + 1)}


def rule(g, depth):
    kind = g.below(8 if depth < 3 else 3)
    if kind in (0, 1):
        return {"type": m("block"), "result_state": state(g)}
    if kind == 2:
        return {"type": m("bandlands")} if g.chance(3) else {"type": m("block"), "result_state": state(g)}
    if kind in (3, 4, 5):
        return {"type": m("condition"), "if_true": condition(g, depth), "then_run": rule(g, depth + 1)}
    if kind == 6:
        return {"type": m("sequence"), "sequence": [rule(g, depth + 1) for _ in range(g.between(0, 4))]}
    if g.chance(2):
        return m(g.pick(RULES[5:]))
    return ore_vein(g)


def ore_vein(g):
    density = g.pick(DENSITIES[:2] + [{"type": "minecraft:constant", "value": g.real(-0.2, 1.0)}])
    return {
        "type": m("ore_vein"),
        "ore_block": state(g),
        "raw_ore_block": state(g),
        "filler_block": state(g),
        "raw_ore_chance": g.pick([0.0, 0.02, 0.5, 1.0]),
        "density": density,
        "richness": g.pick([DENSITIES[2], {"type": "minecraft:constant", "value": g.real(0.0, 1.0)}]),
        "filler_gap": g.pick([DENSITIES[3], -0.5, 0.5, "minecraft:overworld/depth"]),
    }


def written(g):
    """A rule of conditions each giving a block, as the Overworld's are built, written out."""
    steps = []
    for _ in range(g.between(3, 8)):
        steps.append({"type": m("condition"), "if_true": condition(g, 0), "then_run": rule(g, 1)})
    if g.chance(2):
        steps.append({"type": m("block"), "result_state": state(g)})
    return {"type": m("sequence"), "sequence": steps}


def one_condition(name, c, then="minecraft:glass"):
    """A rule that gives glass where `c` holds, and otherwise leaves the block."""
    return {"type": m("condition"), "if_true": c, "then_run": {"type": m("block"), "result_state": then}}


def invalid_rules():
    block = {"type": m("block"), "result_state": "minecraft:stone"}
    out = [
        ("no-type", {"result_state": "minecraft:stone"}),
        ("unknown-type", {"type": "minecraft:mystery"}),
        ("unknown-reference", "minecraft:nowhere"),
        ("bad-reference", "Not An Id"),
        ("unknown-block", {"type": m("block"), "result_state": "minecraft:nope"}),
        ("bad-property", {"type": m("block"), "result_state": {"id": "minecraft:oak_log", "properties": {"axis": "w"}}}),
        ("no-result", {"type": m("block")}),
        ("sequence-not-list", {"type": m("sequence"), "sequence": block}),
        ("sequence-bad-entry", {"type": m("sequence"), "sequence": [block, 3]}),
        ("condition-no-if", {"type": m("condition"), "then_run": block}),
        ("condition-unknown", one_condition("x", {"type": "minecraft:mystery"})),
        ("condition-unknown-reference", one_condition("x", "minecraft:nowhere")),
        ("biome-unknown", one_condition("x", {"type": m("biome"), "biome_is": "minecraft:nowhere"})),
        ("biome-missing-tag", one_condition("x", {"type": m("biome"), "biome_is": "#minecraft:is_nowhere"})),
        ("y-multiplier-21", one_condition("x", {"type": m("y_above"), "anchor": {"absolute": 0}, "surface_depth_multiplier": 21, "add_stone_depth": False})),
        ("y-multiplier-minus-21", one_condition("x", {"type": m("y_above"), "anchor": {"absolute": 0}, "surface_depth_multiplier": -21, "add_stone_depth": False})),
        ("y-two-anchors", one_condition("x", {"type": m("y_above"), "anchor": {"absolute": 0, "above_bottom": 2}, "surface_depth_multiplier": 0, "add_stone_depth": False})),
        ("y-no-add", one_condition("x", {"type": m("y_above"), "anchor": {"absolute": 0}, "surface_depth_multiplier": 0})),
        ("water-multiplier-21", one_condition("x", {"type": m("water"), "offset": 0, "surface_depth_multiplier": 21, "add_stone_depth": False})),
        ("stone-depth-middle", one_condition("x", {"type": m("stone_depth"), "offset": 0, "add_surface_depth": False, "secondary_depth_range": 0, "surface_type": "middle"})),
        ("stone-depth-no-range", one_condition("x", {"type": m("stone_depth"), "offset": 0, "add_surface_depth": False, "surface_type": "floor"})),
        ("gradient-bad-name", one_condition("x", {"type": m("vertical_gradient"), "random_name": "Not An Id", "true_at_and_below": {"absolute": 0}, "false_at_and_above": {"absolute": 8}})),
        ("noise-bad-id", one_condition("x", {"type": m("noise_threshold"), "noise": "Not An Id", "min_threshold": 0, "max_threshold": 1})),
        ("noise-no-max", one_condition("x", {"type": m("noise_threshold"), "noise": "minecraft:surface", "min_threshold": 0})),
        ("not-nothing", one_condition("x", {"type": m("not")})),
        ("ore-chance-above-1", {**ore_vein(Gen(1)), "raw_ore_chance": 1.5}),
        ("ore-unknown-density", {**ore_vein(Gen(2)), "density": "minecraft:nowhere"}),
        ("ore-no-gap", {k: v for k, v in ore_vein(Gen(3)).items() if k != "filler_gap"}),
    ]
    return out


def main():
    g = Gen(SEED)
    cases = []

    # Each settings in its world, with its own rule.
    for settings, (level, source) in WORLDS.items():
        c = Case(f"{settings}-origin", g.seed(), settings, level, preset(source))
        c.surface(0, 0).surface(-1, -1).surface(*near_chunk(g))
        cases.append(c.build())
        for i in range(2):
            c = Case(f"{settings}-near-{i}", g.seed(), settings, level, preset(source))
            c.surface(*near_chunk(g, 600)).surface(*near_chunk(g, 600))
            cases.append(c.build())
        c = Case(f"{settings}-far", g.seed(), settings, level, preset(source))
        c.surface(*far_chunk(g)).surface(*far_chunk(g))
        cases.append(c.build())

    # The Overworld's materials with more seeds, where worlds are.
    for i in range(16):
        settings = ["overworld", "overworld", "large_biomes", "amplified"][i % 4]
        c = Case(f"overworld-seeds-{i}", g.seed(), settings, (-64, 384), preset("overworld"))
        c.surface(*near_chunk(g, 3000)).surface(*near_chunk(g, 3000))
        cases.append(c.build())

    # One biome everywhere: each biome's own materials over the Overworld's terrain, over land
    # and sea.
    for biome in SPECIAL:
        c = Case(f"fixed-{biome}", g.seed(), "overworld", (-64, 384), fixed(biome))
        for _ in range(3):
            c.surface(*near_chunk(g, 2000))
        cases.append(c.build())
    for biome in ["frozen_ocean", "deep_frozen_ocean", "eroded_badlands"]:
        for i in range(3):
            c = Case(f"fixed-{biome}-{i}", g.seed(), "overworld", (-64, 384), fixed(biome))
            for _ in range(3):
                c.surface(*near_chunk(g, 20000))
            cases.append(c.build())
    for biome in NETHER:
        c = Case(f"fixed-{biome}", g.seed(), "nether", (0, 256), fixed(biome))
        c.surface(*near_chunk(g, 500)).surface(*near_chunk(g, 500))
        cases.append(c.build())

    # Checkerboards: the biome changes every few quarts, so the zoom picks between them.
    for i in range(12):
        biomes = [g.pick(SPECIAL + OTHERS) for _ in range(g.between(2, 6))]
        c = Case(f"checkerboard-{i}", g.seed(), "overworld", (-64, 384), checkerboard(biomes, g.between(0, 3)))
        c.surface(*near_chunk(g, 2000)).surface(*near_chunk(g, 2000))
        cases.append(c.build())
    c = Case("checkerboard-nether-in-overworld", g.seed(), "overworld", (-64, 384), checkerboard(NETHER + ["frozen_ocean"], 0))
    c.surface(*near_chunk(g, 500))
    cases.append(c.build())

    # Rules written out, over mixed biomes.
    mixed = checkerboard(["frozen_ocean", "eroded_badlands", "snowy_slopes", "plains", "desert", "swamp", "frozen_peaks"], 1)
    for i in range(40):
        settings = g.pick(["overworld", "overworld", "overworld", "amplified", "nether", "caves"])
        level = WORLDS[settings][0]
        source = mixed if g.chance(2) else preset(WORLDS[settings][1])
        c = Case(f"written-{i}", g.seed(), settings, level, source, written(g))
        c.surface(*near_chunk(g, 1000)).surface(*near_chunk(g, 1000))
        cases.append(c.build())
    # Each of vanilla's rules and conditions on its own, in the Overworld.
    for name in RULES:
        c = Case(f"rule-{name.replace('/', '-')}", g.seed(), "overworld", (-64, 384), preset("overworld"), m(name))
        c.surface(*near_chunk(g, 1000))
        cases.append(c.build())
    for name in CONDITIONS:
        c = Case(f"condition-{name}", g.seed(), "overworld", (-64, 384), mixed, one_condition(name, m(name)))
        c.surface(*near_chunk(g, 1000))
        cases.append(c.build())
    # The simplest rules: none at all, an empty sequence, one block everywhere, bands everywhere.
    simple = [
        ("empty-sequence", {"type": m("sequence"), "sequence": []}),
        ("one-in-sequence", {"type": m("sequence"), "sequence": [{"type": m("bandlands")}]}),
        ("all-glass", {"type": m("block"), "result_state": "minecraft:glass"}),
        ("all-air", {"type": m("block"), "result_state": "minecraft:air"}),
        ("all-water", {"type": m("block"), "result_state": "minecraft:water"}),
        ("bands", {"type": m("bandlands")}),
        ("temperature", one_condition("t", {"type": m("temperature")})),
        ("steep", one_condition("s", {"type": m("steep")})),
        ("hole", one_condition("h", {"type": m("hole")})),
        ("preliminary", one_condition("p", {"type": m("above_preliminary_surface")})),
        ("noise-3d", one_condition("n", {"type": m("noise_threshold"), "noise": m("surface"), "min_threshold": 0.0, "max_threshold": 1.0e308, "is_3d": True})),
        ("missing-noise", one_condition("n", {"type": m("noise_threshold"), "noise": m("nowhere"), "min_threshold": 0.0, "max_threshold": 1.0})),
        ("ceiling-secondary", one_condition("c", {"type": m("stone_depth"), "offset": 2, "add_surface_depth": True, "secondary_depth_range": 12, "surface_type": "ceiling"})),
        ("ore-everywhere", {**ore_vein(Gen(4)), "density": {"type": "minecraft:constant", "value": 2.0}}),
    ]
    for name, r in simple:
        for settings in ["overworld", "nether"]:
            level, source = WORLDS[settings]
            c = Case(f"simple-{name}-{settings}", g.seed(), settings, level, mixed if settings == "overworld" else preset(source), r)
            c.surface(*near_chunk(g, 300))
            cases.append(c.build())

    # Worlds that aren't the noise's: taller, shorter, overlapping its top or bottom, or past it.
    levels = [
        ("tall", (-128, 512)),
        ("short", (0, 128)),
        ("one-section", (-64, 16)),
        ("top-section", (304, 16)),
        ("above", (320, 64)),
        ("below", (-2032, 16)),
        ("low", (-512, 448)),
    ]
    for name, level in levels:
        for settings in ["overworld", "nether"]:
            c = Case(f"level-{name}-{settings}", g.seed(), settings, level, preset(WORLDS[settings][1]))
            c.surface(*near_chunk(g, 64))
            cases.append(c.build())
    c = Case("level-end-in-overworld", g.seed(), "end", (-64, 384), preset("end"))
    c.surface(0, 0).surface(*near_chunk(g, 200))
    cases.append(c.build())

    # The ends of `int`, where blocks and quarts wrap. (A chunk at one end in x and the other in
    # z makes an aquifer grid too big for any heap.)
    for i, (cx, cz) in enumerate([((1 << 27) - 1, (1 << 27) - 1), (-(1 << 27), -(1 << 27)), ((1 << 27) - 1, (1 << 27) - 1)]):
        c = Case(f"edge-{i}", g.seed(), "overworld", (-64, 384), fixed("eroded_badlands") if i == 2 else preset("overworld"))
        c.surface(cx, cz)
        cases.append(c.build())

    # Sources and rules vanilla doesn't read.
    for name, r in invalid_rules():
        cases.append(Case(f"invalid-rule-{name}", "0", "overworld", (-64, 384), preset("overworld"), r).surface(0, 0).build())
    for name, s in [
        ("no-type", {"biome": "minecraft:plains"}),
        ("unknown-biome", {"type": "minecraft:fixed", "biome": "minecraft:nowhere"}),
        ("unknown-preset", preset("mystery")),
    ]:
        cases.append(Case(f"invalid-source-{name}", "0", "overworld", (-64, 384), s).surface(0, 0).build())
    cases.append(Case("invalid-both", "0", "overworld", (-64, 384), {"type": "x"}, "minecraft:nowhere").surface(0, 0).build())

    write_file(HERE / "generated.json", "surface", f"cases/surface/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
