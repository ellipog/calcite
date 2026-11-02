"""Writes cases/features/grid.json: the seed grid of Phase 5's gate (G5.1), whole chunks of each
of the three dimensions made by every stage, compared with vanilla's.

    py -I cases/features/grid.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

For each seed of the grid and each dimension, with the source its world preset gives it, the 3×3
chunks about the origin and the 3×3 about a chunk far out are made in one shared world, each with
`structured`: their structures' starts within 9, their biomes, their terrain bearded by what they
reference, filled, given materials and carved, then decorated with their structures' pieces placed
before each step's features. They're decorated in the order the server decorates them, by the rank
of each chunk's color (D214), each into what the ones before it left. The far chunk is up to 1,875
chunks out, where the End's outer islands are.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261102
# The seeds of the grid: the edge cases every worldgen case file draws on, the seed the
# generation bench uses, and three drawn here.
LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345", "20261101"]
DRAWN = 3
# Each dimension's noise settings, its world as (min_y, height), and the source its preset gives.
DIMENSIONS = [
    ("overworld", (-64, 384), {"type": "minecraft:multi_noise", "preset": "minecraft:overworld"}),
    ("nether", (0, 256), {"type": "minecraft:multi_noise", "preset": "minecraft:nether"}),
    ("end", (0, 256), {"type": "minecraft:the_end"}),
]
FAR = 1875
# Each color's rank, by `x mod 3 + 3 * (z mod 3)`, as `worldgen.generator.rank_of` has them.
RANKS = [0, 7, 8, 1, 6, 5, 2, 3, 4]


def rank_of(x, z):
    return RANKS[(x % 3) + 3 * (z % 3)]


def signed(v):
    return v - (1 << 64) if v >= 1 << 63 else v


def main():
    r = splitmix64(SEED)
    seeds = list(LONG_SEEDS) + [str(signed(next(r))) for _ in range(DRAWN)]
    cases = []
    for seed in seeds:
        for name, level, source in DIMENSIONS:
            far = (next(r) % (2 * FAR + 1) - FAR, next(r) % (2 * FAR + 1) - FAR)
            for area, (cx, cz) in (("origin", (0, 0)), ("far", far)):
                chunks = [(cx + dx, cz + dz) for dz in (-1, 0, 1) for dx in (-1, 0, 1)]
                chunks.sort(key=lambda c: rank_of(c[0], c[1]))
                ops = [["structured", x, z] for x, z in chunks]
                cases.append({"id": f"grid-{name}-{seed}-{area}", "input": {
                    "seed": seed, "settings": "minecraft:" + name, "level": list(level), "source": source,
                    "shared": True, "ops": ops,
                }})
    write_file(HERE / "grid.json", "features", f"cases/features/grid.py, seed {SEED}", cases, probe_version=4)


if __name__ == "__main__":
    main()
