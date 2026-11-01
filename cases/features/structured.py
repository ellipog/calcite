"""Writes cases/features/structured.json: chunks decorated with their structures' pieces placed
before each step's features.

    py -I cases/features/structured.py

Deterministic: everything comes from SplitMix64 seeded with SEED and from the names in vanilla's
data pack, so rerunning it gives the same file.

Each structure a set places by random spread gets a world of one biome it may start in, decorated
at a chunk its set may place it in, as the `structures` cases pick them; whether a start is made
there is vanilla's to say. Abandoned camps, which differ only by their biome, get three of the
eighteen.

Strongholds, End cities and Nether fortresses also get chunks their pieces fill, a start's own
chunk seldom holding much of them: each in a world of one biome with a seed of its own, at chunks
picked by asking the `structures` probe where those worlds' starts are and which chunks their
pieces reach, among them a stronghold's portal room and library, an End city's ship and a
fortress's blaze spawner.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
sys.path.insert(0, str(ROOT / "cases" / "structures"))
from cases import write_file  # noqa: E402
import gen as structures  # noqa: E402

SEED = 20261110
CAMPS = {"abandoned_camp_forest", "abandoned_camp_savanna", "abandoned_camp_snowy_taiga"}
# Worlds of one biome, and the chunks in them where a structure's pieces are, by name.
FILLED = [
    ("stronghold", "plains", "20261110", [
        ("start", -96, -36), ("portal", -95, -37), ("crossings", 85, -72), ("library", 85, -73),
        ("stairs", 86, -71), ("library2", 12, 110), ("portal2", 11, 108),
    ]),
    ("end_city", "end_highlands", "20261111", [
        ("start", 105, 3), ("towers", 104, 3), ("bridges", 104, 4), ("small", 144, 6),
        ("far", 223, 4), ("long", 263, 2), ("farthest", 362, 26),
    ]),
    ("fortress", "nether_wastes", "20261112", [
        ("start", 22, 9), ("well", 21, 9), ("corridors", 20, 6), ("spawner", 25, 10),
        ("stalks", 21, 8), ("busy", 91, 21), ("bridges", 205, 6),
    ]),
]


def main():
    g = structures.Gen(SEED)
    sets, defs, tags = structures.vanilla()
    set_of = {}
    for sid, s in sets.items():
        for entry in s["structures"]:
            set_of.setdefault(structures.bare(entry["structure"]), sid)
    cases = []
    for sid, structure in sorted(defs.items()):
        if sid.startswith("abandoned_camp_") and sid not in CAMPS:
            continue
        placement = sets[set_of[sid]]["placement"] if sid in set_of else None
        if placement is None or placement["type"] != "minecraft:random_spread":
            continue
        biomes = structures.biomes_of(structure["biomes"], tags)
        if not biomes:
            continue
        biome = g.pick(biomes)
        seed = g.seed()
        c = structures.Case(f"structured-{sid}", seed, structures.world_of(biome), structures.fixed(biome))
        x, z = structures.candidates(g, seed, placement, 1, False)[0]
        c.op("structured", x, z)
        cases.append(c.build())
    for sid, biome, seed, chunks in FILLED:
        for name, x, z in chunks:
            c = structures.Case(f"structured-{sid}-{name}", seed, structures.world_of(biome), structures.fixed(biome))
            c.op("structured", x, z)
            cases.append(c.build())
    write_file(HERE / "structured.json", "features", f"cases/features/structured.py, seed {SEED}", cases, probe_version=4)


if __name__ == "__main__":
    main()
