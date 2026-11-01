"""Writes cases/features/generated.json: chunks decorated with their biomes' features, and
features placed on their own.

    py -I cases/features/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED and from the names in vanilla's
data pack, so rerunning it gives the same file.

The cases name vanilla's features by id and never copy them. Every settings' world is decorated
near the origin and far out, and every biome on its own through a fixed source. Every feature in
`worldgen/feature` is placed under placements the cases write: on the heightmap a placed feature
of it uses, through the world's height where one ranges over it, on every layer, or at one
position. Simple blocks then try each placement modifier and block predicate on their own, and
features, placements and providers vanilla doesn't read are compared as that.
"""

import io
import json
import math
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261108
JAR = ROOT / "oracle" / "jars" / "server-26.3.jar"
INNER = "META-INF/versions/26.3/server-26.3.jar"
WORLDGEN = "data/minecraft/worldgen/"
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
NETHER = {"nether_wastes", "soul_sand_valley", "crimson_forest", "warped_forest", "basalt_deltas"}
END = {"the_end", "end_highlands", "end_midlands", "small_end_islands", "end_barrens"}
FAR = 30000


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

    def chunk(self, reach):
        return self.between(-reach, reach), self.between(-reach, reach)


def m(name):
    return "minecraft:" + name


def bare(name):
    return name[len("minecraft:"):] if name.startswith("minecraft:") else name


def preset(name):
    if name == "end":
        return {"type": "minecraft:the_end"}
    return {"type": "minecraft:multi_noise", "preset": m(name)}


def fixed(biome):
    return {"type": "minecraft:fixed", "biome": m(biome)}


def world_of(biome):
    """The settings a biome's world has."""
    if biome in NETHER:
        return "nether"
    if biome in END:
        return "end"
    return "overworld"


def vanilla():
    """Names from vanilla's data pack: each biome's placed features, each placed feature's
    feature and the modifier types and heightmap of its placement, and every feature's id."""
    with zipfile.ZipFile(JAR) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(INNER)))
    biomes, placed, features = {}, {}, []
    for name in sorted(inner.namelist()):
        if not name.endswith(".json"):
            continue
        for kind in ("biome", "placed_feature", "feature"):
            prefix = WORLDGEN + kind + "/"
            if not name.startswith(prefix):
                continue
            key = name[len(prefix):-len(".json")]
            value = json.loads(inner.read(name))
            if kind == "biome":
                biomes[key] = [bare(p) for step in value.get("features", []) for p in step if isinstance(p, str)]
            elif kind == "placed_feature":
                types, heightmap = [], None
                for mod in value.get("placement", []):
                    types.append(bare(mod.get("type", "")))
                    if mod.get("type") == "minecraft:heightmap":
                        heightmap = mod.get("heightmap")
                feature = value.get("feature")
                placed[key] = (bare(feature) if isinstance(feature, str) else None, types, heightmap)
            else:
                features.append(key)
    return biomes, placed, features


class Case:
    def __init__(self, cid, seed, settings, source, feature=None):
        level, _ = WORLDS[settings]
        self.cid = cid
        self.input = {"seed": seed, "settings": m(settings), "level": list(level), "source": source}
        if feature is not None:
            self.input["feature"] = feature
        self.input["ops"] = []

    def decorate(self, cx, cz):
        self.input["ops"].append(["decorate", cx, cz])
        return self

    def place(self, cx, cz, x, y, z, seed):
        self.input["ops"].append(["place", cx, cz, x, y, z, seed])
        return self

    def build(self):
        return {"id": self.cid, "input": self.input}


def surface(heightmap, count=4):
    return [
        {"type": "minecraft:count", "count": count},
        {"type": "minecraft:in_square"},
        {"type": "minecraft:heightmap", "heightmap": heightmap},
    ]


def through_height(count=8):
    return [
        {"type": "minecraft:count", "count": count},
        {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": {
            "type": "minecraft:uniform", "min_inclusive": {"above_bottom": 0}, "max_inclusive": {"below_top": 0}}},
    ]


def placement_like(types, heightmap):
    """A placement of the cases' own for a feature whose placed feature uses `types`."""
    if heightmap is not None:
        return surface(heightmap)
    if "height_range" in types:
        return through_height()
    if "count_on_every_layer" in types:
        return [{"type": "minecraft:count_on_every_layer", "count": 2}]
    return []


def decorations(g, cases, biomes):
    for settings, (_, source) in WORLDS.items():
        c = Case(f"decorate-{settings}-origin", g.seed(), settings, preset(source))
        c.decorate(0, 0)
        cases.append(c.build())
        c = Case(f"decorate-{settings}-far", g.seed(), settings, preset(source))
        cx, cz = g.chunk(FAR)
        c.decorate(cx, cz)
        cx, cz = g.chunk(FAR)
        cases.append(c.decorate(cx, cz).build())
    for biome in sorted(biomes):
        settings = world_of(biome)
        c = Case(f"decorate-biome-{biome}", g.seed(), settings, fixed(biome))
        cx, cz = g.chunk(64)
        cases.append(c.decorate(cx, cz).build())


def each_feature(g, cases, biomes, placed, features):
    """Each feature placed under a placement like its placed feature's, in a biome that lists
    one, at two chunks."""
    uses = {}
    for pid, (fid, types, heightmap) in sorted(placed.items()):
        if fid is not None and fid not in uses:
            homes = sorted(b for b, ps in biomes.items() if pid in ps)
            uses[fid] = (types, heightmap, homes[0] if homes else None)
    for fid in features:
        types, heightmap, biome = uses.get(fid, ([], "MOTION_BLOCKING", None))
        if biome is None:
            biome = "plains"
        settings = world_of(biome)
        placement = placement_like(types, heightmap)
        c = Case(f"feature-{fid.replace('/', '-')}", g.seed(), settings, fixed(biome), {"feature": m(fid), "placement": placement})
        level, _ = WORLDS[settings]
        for _ in range(2):
            cx, cz = g.chunk(200)
            y = g.between(level[0], level[0] + level[1] - 1) if not placement else 0
            c.place(cx, cz, cx * 16 + g.below(16), y if placement else 64, cz * 16 + g.below(16), g.long())
        cases.append(c.build())


def dungeons(g, cases):
    """Monster rooms tried hundreds of times a chunk, so that some are built: their walls,
    chests turned to a wall with their loot tables, and spawners with their mobs."""
    for i in range(8):
        settings = "caves" if i % 2 else "overworld"
        placement = [{"type": "minecraft:count", "count": 4096}, {"type": "minecraft:in_square"},
                     {"type": "minecraft:height_range", "height": {"type": "minecraft:uniform", "min_inclusive": {"absolute": -58}, "max_inclusive": {"absolute": 100}}}]
        c = Case(f"dungeons-{i}", g.seed(), settings, preset("overworld"), {"feature": m("monster_room"), "placement": placement})
        for _ in range(2):
            cx, cz = g.chunk(2000)
            c.place(cx, cz, cx * 16, 0, cz * 16, g.long())
        cases.append(c.build())


def stone(placement):
    return {"feature": {"type": "minecraft:simple_block", "to_place": {"id": "minecraft:stone"}}, "placement": placement}


def modifiers(g, cases):
    """Simple blocks under each placement modifier on its own and in mixes."""
    on = surface("MOTION_BLOCKING", 1)
    tries = {
        "count": [{"type": "minecraft:count", "count": {"type": "minecraft:uniform", "min_inclusive": 0, "max_inclusive": 6}}, {"type": "minecraft:in_square"}, {"type": "minecraft:heightmap", "heightmap": "WORLD_SURFACE_WG"}],
        "rarity": [{"type": "minecraft:count", "count": 40}, {"type": "minecraft:rarity_filter", "chance": 3}, {"type": "minecraft:in_square"}, {"type": "minecraft:heightmap", "heightmap": "OCEAN_FLOOR"}],
        "random-chance": [{"type": "minecraft:count", "count": 40}, {"type": "minecraft:random_chance", "chance": 0.3}] + on[1:],
        "offset": on + [{"type": "minecraft:offset", "x": {"type": "minecraft:uniform", "min_inclusive": -16, "max_inclusive": 16}, "y": 3, "z": -2}],
        "cuboid": on + [{"type": "minecraft:cuboid", "xz_size": 3, "y_size": {"type": "minecraft:uniform", "min_inclusive": 1, "max_inclusive": 4}}],
        "cuboid-shell": on + [{"type": "minecraft:cuboid", "xz_size": 4, "y_size": 3, "include_interior": False}],
        "cuboid-edges": on + [{"type": "minecraft:cuboid", "xz_size": 4, "y_size": 4, "include_edges": False}],
        "scan-down": through_height(6) + [{"type": "minecraft:environment_scan", "direction_of_search": "down", "max_steps": 12,
                                           "target_condition": {"type": "minecraft:solid"},
                                           "allowed_search_condition": {"type": "minecraft:matching_blocks", "blocks": ["minecraft:air", "minecraft:cave_air"]}}],
        "scan-up": through_height(6) + [{"type": "minecraft:environment_scan", "direction_of_search": "up", "max_steps": 32,
                                         "target_condition": {"type": "minecraft:not", "predicate": {"type": "minecraft:replaceable"}}}],
        "fixed": [{"type": "minecraft:fixed_placement", "positions": [[0, 100, 0], [5, 90, 7], [16, 80, 0], [-1, 80, -1]]}],
        "noise-based": [{"type": "minecraft:noise_based_count", "noise_to_count_ratio": 12, "noise_factor": 80.0, "noise_offset": 0.5}] + on[1:],
        "noise-threshold": [{"type": "minecraft:noise_threshold_count", "noise_level": -0.3, "below_noise": 1, "above_noise": 6}] + on[1:],
        "randomly-selected": [{"type": "minecraft:count", "count": 6}, {"type": "minecraft:randomly_selected", "placements": [
            [{"type": "minecraft:in_square"}][0], {"type": "minecraft:offset", "x": 3, "y": 0, "z": 3}]}, {"type": "minecraft:heightmap", "heightmap": "MOTION_BLOCKING"}],
        "surface-relative": through_height(30) + [{"type": "minecraft:surface_relative_threshold_filter", "heightmap": "OCEAN_FLOOR_WG", "min_inclusive": -12, "max_inclusive": 4}],
        "water-depth": [{"type": "minecraft:count", "count": 6}, {"type": "minecraft:in_square"}, {"type": "minecraft:surface_water_depth_filter", "max_water_depth": 2}, {"type": "minecraft:heightmap", "heightmap": "OCEAN_FLOOR"}],
        "every-layer": [{"type": "minecraft:count_on_every_layer", "count": {"type": "minecraft:uniform", "min_inclusive": 1, "max_inclusive": 3}}],
        "height-trapezoid": [{"type": "minecraft:count", "count": 20}, {"type": "minecraft:in_square"}, {"type": "minecraft:height_range", "height": {
            "type": "minecraft:trapezoid", "min_inclusive": {"absolute": -40}, "max_inclusive": {"absolute": 120}, "plateau": 20}}],
        "biome-nested": [{"type": "minecraft:biome"}],
    }
    for name, placement in tries.items():
        for i, biome in enumerate(["plains", "ocean", "dripstone_caves"]):
            c = Case(f"modifier-{name}-{biome}", g.seed(), "overworld", fixed(biome), stone(placement))
            for _ in range(2):
                cx, cz = g.chunk(100)
                c.place(cx, cz, cx * 16, g.between(-64, 200), cz * 16, g.long())
            cases.append(c.build())


def predicates(g, cases):
    """Simple blocks behind each block predicate, on the surface and through the height."""
    preds = {
        "matching-blocks": {"type": "minecraft:matching_blocks", "offset": [0, -1, 0], "blocks": ["minecraft:grass_block", "minecraft:sand"]},
        "matching-tag": {"type": "minecraft:matching_block_tag", "offset": [0, -1, 0], "tag": "minecraft:dirt"},
        "matching-fluids": {"type": "minecraft:matching_fluids", "fluids": ["minecraft:water", "minecraft:flowing_water"]},
        "replaceable": {"type": "minecraft:replaceable"},
        "solid": {"type": "minecraft:solid", "offset": [1, -1, 0]},
        "sturdy": {"type": "minecraft:has_sturdy_face", "offset": [0, -1, 0], "direction": "up"},
        "would-survive": {"type": "minecraft:would_survive", "state": {"id": "minecraft:poppy"}},
        "would-survive-cactus": {"type": "minecraft:would_survive", "state": {"id": "minecraft:cactus", "properties": {"age": "0"}}},
        "inside-world": {"type": "minecraft:inside_world_bounds", "offset": [0, 16, 0]},
        "not-air": {"type": "minecraft:not", "predicate": {"type": "minecraft:matching_blocks", "blocks": "minecraft:air"}},
        "any-of": {"type": "minecraft:any_of", "predicates": [{"type": "minecraft:solid"}, {"type": "minecraft:matching_fluids", "fluids": "minecraft:lava"}]},
        "all-of": {"type": "minecraft:all_of", "predicates": [{"type": "minecraft:replaceable"}, {"type": "minecraft:solid", "offset": [0, -1, 0]}]},
        "true": {"type": "minecraft:true"},
        "unobstructed": {"type": "minecraft:unobstructed"},
        "height-range": {"type": "minecraft:height_range", "min_inclusive": {"absolute": 0}, "max_inclusive": {"below_top": 100}},
        "volume": {"type": "minecraft:volume_match", "min": [-1, -1, -1], "max": [1, 0, 1], "match": {"type": "minecraft:solid"}},
    }
    for name, pred in preds.items():
        placement = through_height(24) + [{"type": "minecraft:block_predicate_filter", "predicate": pred}]
        c = Case(f"predicate-{name}", g.seed(), "overworld", fixed(g.pick(["plains", "lush_caves", "beach", "warm_ocean"])), stone(placement))
        cx, cz = g.chunk(100)
        cases.append(c.place(cx, cz, cx * 16, 0, cz * 16, g.long()).build())


def providers(g, cases):
    """Simple blocks from each block state provider."""
    noise = {"base_octave": -3, "octave_count": 2}
    states = ["minecraft:stone", "minecraft:andesite", "minecraft:granite", {"id": "minecraft:oak_log", "properties": {"axis": "x"}}]
    provs = {
        "state": {"id": "minecraft:glass"},
        "simple": {"type": "minecraft:simple", "state": {"id": "minecraft:glass"}},
        "weighted": {"type": "minecraft:weighted", "entries": [{"data": {"id": "minecraft:dirt"}, "weight": 3}, {"data": {"id": "minecraft:stone"}, "weight": 1}]},
        "randomized-int": {"type": "minecraft:randomized_int", "source": {"id": "minecraft:candle"}, "property": "candles",
                           "values": {"type": "minecraft:uniform", "min_inclusive": 1, "max_inclusive": 4}},
        "rotated": {"type": "minecraft:rotated", "state": {"id": "minecraft:oak_log"}},
        "noise": {"type": "minecraft:noise", "seed": 2345, "noise": noise, "scale": 0.02, "states": states},
        "noise-threshold": {"type": "minecraft:noise_threshold", "seed": 7, "noise": noise, "scale": 0.05, "threshold": 0.1, "high_chance": 0.4,
                            "default_state": {"id": "minecraft:moss_block"}, "low_states": states[:2], "high_states": states[2:]},
        "dual-noise": {"type": "minecraft:dual_noise", "seed": 9, "noise": noise, "scale": 0.03, "states": states,
                       "variety": [2, 4], "slow_noise": noise, "slow_scale": 0.7},
        "random-block": {"type": "minecraft:random_block", "blocks": "#minecraft:flowers"},
        "copy-properties": {"type": "minecraft:copy_properties", "source": {"id": "minecraft:mossy_cobblestone_slab"}},
        "rule-based": {"type": "minecraft:rule_based", "fallback": {"id": "minecraft:dirt"}, "rules": [
            {"if_true": {"type": "minecraft:matching_blocks", "offset": [0, -1, 0], "blocks": "minecraft:sand"}, "then": {"id": "minecraft:cactus"}}]},
    }
    for name, prov in provs.items():
        feature = {"feature": {"type": "minecraft:simple_block", "to_place": prov}, "placement": surface("WORLD_SURFACE", 12)}
        c = Case(f"provider-{name}", g.seed(), "overworld", fixed(g.pick(["plains", "desert", "swamp"])), feature)
        cx, cz = g.chunk(100)
        cases.append(c.place(cx, cz, cx * 16, 0, cz * 16, g.long()).build())


def unread(g, cases):
    """Features and placements vanilla doesn't read."""
    bad = {
        "unknown-type": {"feature": {"type": "minecraft:no_such_feature"}, "placement": []},
        "unknown-placed": "minecraft:no_such_placed_feature",
        "unknown-feature": {"feature": "minecraft:no_such_feature", "placement": []},
        "unknown-modifier": stone([{"type": "minecraft:no_such_modifier"}]),
        "ore-too-big": {"feature": {"type": "minecraft:ore", "size": 65, "discard_chance_on_air_exposure": 0.0, "targets": []}, "placement": []},
        "count-too-big": stone([{"type": "minecraft:count", "count": 4097}]),
        "rarity-zero": stone([{"type": "minecraft:rarity_filter", "chance": 0}]),
        "scan-sideways": stone([{"type": "minecraft:environment_scan", "direction_of_search": "north", "max_steps": 4, "target_condition": {"type": "minecraft:solid"}}]),
        "weighted-empty": {"feature": {"type": "minecraft:simple_block", "to_place": {"type": "minecraft:weighted", "entries": []}}, "placement": []},
        "sequence-empty": {"feature": {"type": "minecraft:sequence", "features": []}, "placement": []},
        "missing-tag": {"feature": {"type": "minecraft:simple_block", "to_place": {"type": "minecraft:random_block", "blocks": "#minecraft:no_such_tag"}}, "placement": []},
    }
    for name, feature in bad.items():
        c = Case(f"unread-{name}", g.seed(), "overworld", fixed("plains"), feature)
        cases.append(c.place(0, 0, 0, 64, 0, "0").build())
    c = Case("decorate-without-feature", "0", "overworld", fixed("plains"))
    cases.append(c.decorate(0, 0).build())


def end_spikes(g, cases):
    """The End's ten spikes, each placed from its own chunk, so that each is built with its cage
    and its end crystal, an entity; and spikes of a config's own, with a beam target and
    crystals that can't be hurt."""
    for i in range(3):
        c = Case(f"end-spikes-{i}", g.seed(), "end", fixed("the_end"), {"feature": m("end_spike"), "placement": []})
        for n in range(10):
            # `EndSpikeFeature.getSpikesForLevel`: centers on a ring of 42 about the origin.
            angle = 2.0 * (-math.pi + math.pi / 10.0 * n)
            x = math.floor(42.0 * math.cos(angle))
            z = math.floor(42.0 * math.sin(angle))
            c.place(x >> 4, z >> 4, x, 64, z, g.long())
        cases.append(c.build())
    spikes = [{"centerX": 3, "centerZ": 5, "radius": 3, "height": 80, "guarded": True},
              {"centerX": -20, "centerZ": 9, "radius": 2, "height": 70}]
    feature = {"feature": {"type": "minecraft:end_spike", "crystal_invulnerable": True, "crystal_beam_target": [0, 128, 0], "spikes": spikes}, "placement": []}
    c = Case("end-spikes-config", g.seed(), "end", fixed("the_end"), feature)
    for s in spikes:
        c.place(s["centerX"] >> 4, s["centerZ"] >> 4, s["centerX"], 64, s["centerZ"], g.long())
    cases.append(c.build())


def main():
    g = Gen(SEED)
    biomes, placed, features = vanilla()
    cases = []
    decorations(g, cases, biomes)
    each_feature(g, cases, biomes, placed, features)
    dungeons(g, cases)
    modifiers(g, cases)
    predicates(g, cases)
    providers(g, cases)
    unread(g, cases)
    end_spikes(g, cases)
    write_file(HERE / "generated.json", "features", f"cases/features/gen.py, seed {SEED}", cases, probe_version=4)


if __name__ == "__main__":
    main()
