"""Writes cases/features/orders.json: the same chunks decorated in different orders (CAL-33).

    py -I cases/features/orders.py

Deterministic: rerunning it gives the same file.

Vanilla decorates a chunk once the chunks around it have their terrain, so the order a server
decorates neighbouring chunks in, and so what each decoration finds its neighbours' features left,
depends on which chunks were loaded first: vanilla's results can depend on it (MC-55596,
MC-272481, MC-241546). Calcite decorates them by the rank of each chunk's color (D29, D214).

For a few seeds of the grid and the Overworld and the Nether, the 3×3 chunks about the origin and
about a chunk out at 100, -60 are decorated with `structured` in one shared world in each of four
orders: by color, as Calcite does; row by row, `z` then `x`; the reverse of that; and from the
center out, the corners last. Each case is `final`, so it's the world the decorations left,
whatever their order, and two orders give the same blob exactly when the order made no
difference. `rig.calx orders` says which.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
from cases import write_file  # noqa: E402

SEEDS = ["0", "12345", "20261101"]
DIMENSIONS = [
    ("overworld", (-64, 384), {"type": "minecraft:multi_noise", "preset": "minecraft:overworld"}),
    ("nether", (0, 256), {"type": "minecraft:multi_noise", "preset": "minecraft:nether"}),
]
AREAS = [("origin", (0, 0)), ("out", (100, -60))]
# Each color's rank, by `x mod 3 + 3 * (z mod 3)`, as `worldgen.generator.rank_of` has them.
RANKS = [0, 7, 8, 1, 6, 5, 2, 3, 4]


def orders(cx, cz):
    chunks = [(cx + dx, cz + dz) for dz in (-1, 0, 1) for dx in (-1, 0, 1)]
    colored = sorted(chunks, key=lambda c: RANKS[(c[0] % 3) + 3 * (c[1] % 3)])
    rows = list(chunks)
    reverse = list(reversed(rows))
    # The center, then its four sides, then the corners.
    out = sorted(chunks, key=lambda c: (abs(c[0] - cx) + abs(c[1] - cz), c[1], c[0]))
    return [("colored", colored), ("rows", rows), ("reverse", reverse), ("center-out", out)]


def main():
    cases = []
    for seed in SEEDS:
        for name, level, source in DIMENSIONS:
            for area, (cx, cz) in AREAS:
                for order, chunks in orders(cx, cz):
                    cases.append({"id": f"orders-{name}-{seed}-{area}-{order}", "input": {
                        "seed": seed, "settings": "minecraft:" + name, "level": list(level), "source": source,
                        "shared": True, "final": True, "ops": [["structured", x, z] for x, z in chunks],
                    }})
    write_file(HERE / "orders.json", "features", "cases/features/orders.py", cases, probe_version=4)


if __name__ == "__main__":
    main()
