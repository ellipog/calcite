"""Writes cases/structures/generated.json: where vanilla's structure sets place structures, and
the structure starts made there.

    py -I cases/structures/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED and from the names in vanilla's
data pack, so rerunning it gives the same file.

Every settings' world is asked which chunks of a square near the origin and one far out each
structure set places in, and the Overworld's worlds where their strongholds' rings are. Then each
structure in `worldgen/structure` is started in a world of one biome it may start in, at the
chunks its set's random spread picks near the origin and far out, which the cases work out with
Java's `Random` as `RandomSpreadStructurePlacement` does; whether the start is made there is
vanilla's to say. The strongholds start at their rings' first positions.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261109
JAR = ROOT / "oracle" / "jars" / "server-26.3.jar"
INNER = "META-INF/versions/26.3/server-26.3.jar"
DATA = "data/minecraft/"
LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]
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
MASK = (1 << 48) - 1
# Structures whose starts the chunks a case tries seldom make.
RARE = {"end_city", "pillager_outpost"}


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


class JavaRandom:
    """`LegacyRandomSource`: Java's `Random`."""

    def __init__(self, seed):
        self.s = (seed ^ 0x5DEECE66D) & MASK

    def next(self, bits):
        self.s = (self.s * 0x5DEECE66D + 0xB) & MASK
        r = self.s >> (48 - bits)
        # Java's int: only 32 bits can come out negative.
        return r - (1 << 32) if bits == 32 and r >= 1 << 31 else r

    def next_int(self, bound):
        if bound & (bound - 1) == 0:
            return (bound * self.next(31)) >> 31
        while True:
            sample = self.next(31)
            modulo = sample % bound
            if sample - modulo + (bound - 1) < 1 << 31:
                return modulo

    def next_float(self):
        return self.next(24) / float(1 << 24)

    def next_double(self):
        return ((self.next(26) << 27) + self.next(27)) * (1.0 / float(1 << 53))


def large_feature_with_salt(seed, x, z, salt):
    return JavaRandom(x * 341873128712 + z * 132897987541 + seed + salt)


def large_feature(seed, x, z):
    # `setLargeFeatureSeed`: two longs from the seed, mixed with the chunk.
    r = JavaRandom(seed)
    a = signed64((r.next(32) << 32) + r.next(32))
    b = signed64((r.next(32) << 32) + r.next(32))
    return JavaRandom(signed64(x * a) ^ signed64(z * b) ^ seed)


def signed64(v):
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >= 1 << 63 else v


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
    if biome in NETHER:
        return "nether"
    if biome in END:
        return "end"
    return "overworld"


def vanilla():
    """Vanilla's structure sets, structures and biome tags."""
    with zipfile.ZipFile(JAR) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(INNER)))
    sets, structures, tags = {}, {}, {}
    for name in sorted(inner.namelist()):
        if not name.endswith(".json"):
            continue
        for kind, into in (("worldgen/structure_set/", sets), ("worldgen/structure/", structures), ("tags/worldgen/biome/", tags)):
            prefix = DATA + kind
            if name.startswith(prefix):
                into[name[len(prefix):-len(".json")]] = json.loads(inner.read(name))
    return sets, structures, tags


def biomes_of(value, tags):
    """The biomes a holder set names, tags resolved, in order."""
    if isinstance(value, list):
        out = []
        for v in value:
            out += biomes_of(v, tags)
        return out
    if value.startswith("#"):
        out = []
        for v in tags[bare(value[1:])]["values"]:
            v = v["id"] if isinstance(v, dict) else v
            out += biomes_of(v, tags)
        return out
    return [bare(value)]


def spread_chunk(seed, placement, gx, gz):
    """`RandomSpreadStructurePlacement.getPotentialStructureChunk` of the grid cell."""
    spacing, separation = placement["spacing"], placement.get("separation", 0)
    r = large_feature_with_salt(seed, gx, gz, placement["salt"])
    limit = spacing - separation
    if placement.get("spread_type", "linear") == "triangular":
        x = (r.next_int(limit) + r.next_int(limit)) // 2
        z = (r.next_int(limit) + r.next_int(limit)) // 2
    else:
        x = r.next_int(limit)
        z = r.next_int(limit)
    return gx * spacing + x, gz * spacing + z


def passes_frequency(seed, placement, x, z):
    """`applyAdditionalChunkRestrictions`."""
    frequency = placement.get("frequency", 1.0)
    if frequency >= 1.0:
        return True
    method = placement.get("frequency_reduction_method", "default")
    salt = placement["salt"]
    if method == "default":
        return large_feature_with_salt(seed, x, z, salt).next_float() < frequency
    if method == "legacy_type_2":
        return large_feature_with_salt(seed, x, z, 10387320).next_float() < frequency
    if method == "legacy_type_3":
        return large_feature(seed, x, z).next_double() < frequency
    r = JavaRandom(signed64((x >> 4) ^ ((z >> 4) << 4) ^ seed))
    r.next(32)
    return r.next_int(int(1.0 / frequency)) == 0


def candidates(g, seed, placement, count, far):
    """Chunks the placement may place in: near the origin, or far out."""
    seed = int(seed)
    found = []
    spacing = placement["spacing"]
    reach = 30000 if far else 6
    cx, cz = g.between(-reach, reach), g.between(-reach, reach)
    if spacing == 1:
        tries = 0
        while len(found) < count and tries < 20000:
            x, z = cx + tries % 141, cz + tries // 141
            if passes_frequency(seed, placement, x, z):
                found.append((x, z))
            tries += 1
        return found
    # Grid cells about the chunk, those whose chunk the frequency keeps.
    k = 0
    while len(found) < count and k < 400:
        gx = (cx * 16) // (spacing * 16) + k % 20
        gz = (cz * 16) // (spacing * 16) + k // 20
        x, z = spread_chunk(seed, placement, gx, gz)
        if passes_frequency(seed, placement, x, z):
            found.append((x, z))
        k += 1
    return found


class Case:
    def __init__(self, cid, seed, settings, source):
        level, _ = WORLDS[settings]
        self.cid = cid
        self.input = {"seed": seed, "settings": m(settings), "level": list(level), "source": source, "ops": []}

    def op(self, *args):
        self.input["ops"].append(list(args))
        return self

    def build(self):
        return {"id": self.cid, "input": self.input}


def placements(g, cases):
    for settings, (_, source) in WORLDS.items():
        for i in range(2):
            c = Case(f"placement-{settings}-{i}", g.seed(), settings, preset(source))
            c.op("placement", -32, -32, 64)
            c.op("placement", g.between(-1900, 1900), g.between(-1900, 1900), 32)
            cases.append(c.build())


def rings(g, cases):
    for settings in ("overworld", "large_biomes", "amplified"):
        for i in range(2):
            cases.append(Case(f"rings-{settings}-{i}", g.seed(), settings, preset("overworld")).op("rings").build())
    cases.append(Case("rings-fixed-plains", g.seed(), "overworld", fixed("plains")).op("rings").build())
    cases.append(Case("rings-fixed-desert", g.seed(), "overworld", fixed("desert")).op("rings").build())


def starts(g, cases, sets, structures, tags):
    set_of = {}
    for sid, s in sets.items():
        for entry in s["structures"]:
            set_of.setdefault(bare(entry["structure"]), sid)
    for sid, structure in sorted(structures.items()):
        biomes = biomes_of(structure["biomes"], tags)
        if not biomes:
            continue
        biome = g.pick(biomes)
        settings = world_of(biome)
        placement = sets[set_of[sid]]["placement"] if sid in set_of else None
        seed = g.seed()
        c = Case(f"starts-{sid}", seed, settings, fixed(biome))
        if placement is None or placement["type"] != "minecraft:random_spread":
            if placement is not None and placement["type"] == "minecraft:concentric_rings":
                c.op("ring_starts", 3)
                cases.append(c.build())
            continue
        # Structures that start rarely where they may get more chunks to try.
        near, far = (16, 8) if sid in RARE else (4, 2)
        for x, z in candidates(g, seed, placement, near, False) + candidates(g, seed, placement, far, True):
            c.op("starts", x, z)
        cases.append(c.build())
    for i in range(3):
        cases.append(Case(f"starts-strongholds-{i}", g.seed(), "overworld", preset("overworld")).op("ring_starts", 4).build())


def main():
    g = Gen(SEED)
    sets, structures, tags = vanilla()
    cases = []
    placements(g, cases)
    rings(g, cases)
    starts(g, cases, sets, structures, tags)
    write_file(HERE / "generated.json", "structures", f"cases/structures/gen.py, seed {SEED}", cases, probe_version=1)


if __name__ == "__main__":
    main()
