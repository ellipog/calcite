"""Writes cases/features/structured.json: chunks decorated with their structures' pieces placed
before each step's features.

    py -I cases/features/structured.py

Deterministic: everything comes from SplitMix64 seeded with SEED and from the names in vanilla's
data pack, so rerunning it gives the same file.

Each structure a set places by random spread gets a world of one biome it may start in, decorated
at a chunk its set may place it in, as the `structures` cases pick them; whether a start is made
there is vanilla's to say. Abandoned camps, which differ only by their biome, get three of the
eighteen.
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
    write_file(HERE / "structured.json", "features", f"cases/features/structured.py, seed {SEED}", cases, probe_version=4)


if __name__ == "__main__":
    main()
