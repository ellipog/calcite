"""Writes cases/levels/generated.json: random operations on a chunk tracker's graph of levels,
as each of vanilla's trackers has it, and as none does.

    py -I cases/levels/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

Each case gives the graph's level count, the level of a chunk with none, the level from which a
set level is taken out, and the source level of a chunk with no source, as the loading, the
simulation, the natural spawn and the player ticket trackers have them, or at random. Its
operations change chunks' sources and tell the graph, as ticket storage and players coming and
going do, run the updates, all at once or a few at a time, and dump the levels. The `random`
cases also tell the graph what doesn't match the sources, and the `desync` cases change levels
behind the graph's back, as a chunk holder's removal does to the loading tracker, which can leave
a chunk queued twice, so their runs are bounded. The `edge` cases are next to the chunk vanilla
takes as the source, and where `x` and `z` wrap around.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261101
INT_MAX = 2147483647
INT_MIN = -2147483648
SOURCE = 1875066

# level_count, unset, keep_below, no_source: vanilla's trackers.
LOADING = (46, 45, 45, 45)
SIMULATION = (34, 33, 33, 45)
SPAWN = (10, 10, 9, INT_MAX)
PLAYER = (34, 34, 33, INT_MAX)


class Rng:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def next(self):
        return next(self.r)

    def below(self, n):
        return self.next() % n

    def chance(self, p):
        return self.below(1 << 20) < int(p * (1 << 20))

    def pick(self, items):
        return items[self.below(len(items))]


def pool(rng, size, style):
    """`size` chunks: in a small square, spread out, by the source chunk, or where `x` and `z`
    wrap."""
    out = []
    span = rng.pick([3, 6, 12, 30])
    while span * span < size * 2:
        span += 1
    while len(out) < size:
        if style == "near":
            x, z = rng.below(span) - span // 2, rng.below(span) - span // 2
        elif style == "spread":
            x, z = rng.below(3749999) - 1874999, rng.below(3749999) - 1874999
        elif style == "source":
            x, z = SOURCE - 4 + rng.below(9), SOURCE - 4 + rng.below(9)
        else:
            x = rng.pick([INT_MAX - rng.below(3), INT_MIN + rng.below(3), rng.below(5) - 2])
            z = rng.pick([INT_MAX - rng.below(3), INT_MIN + rng.below(3), rng.below(5) - 2])
        if (x, z) not in out:
            out.append((x, z))
    return out


def ticket_level(rng):
    """A ticket's level, mostly those vanilla's tickets have."""
    r = rng.below(100)
    if r < 30:
        return 31
    if r < 45:
        return 33
    if r < 85:
        return 34 + rng.below(11)
    if r < 90:
        return 22 + rng.below(9)
    return rng.below(46)


def any_level(rng, count):
    """Any level, or past either end, mostly near the top, so a source reaches a few chunks."""
    r = rng.below(100)
    if r < 5:
        return rng.pick([INT_MAX, INT_MIN, -1])
    if r < 15:
        return count + rng.below(4)
    if r < 25:
        return rng.below(count)
    return count - 1 - rng.below(min(count, 9))


def ops_for(rng, config, chunks, count, kind):
    """`count` operations on `chunks`, sources coming and going as `kind` has them: `ticket`
    levels, `player` levels of 0, or `any`, which also tells the graph what doesn't match."""
    level_count, unset, keep_below, no_source = config
    sources = {}
    ops = []
    bounded = kind == "desync"
    for _ in range(count):
        r = rng.below(1000)
        x, z = rng.pick(chunks)
        old = sources.get((x, z), no_source)
        if r < 450:
            # A source comes, goes or changes, and the graph is told as vanilla tells it.
            if kind == "player":
                new = no_source if (x, z) in sources else 0
            elif kind == "ticket":
                new = no_source if (x, z) in sources and rng.chance(0.4) else ticket_level(rng)
            else:
                new = no_source if (x, z) in sources and rng.chance(0.4) else any_level(rng, level_count)
            if new == no_source:
                sources.pop((x, z), None)
                ops.append(["unsource", x, z])
            else:
                sources[(x, z)] = new
                ops.append(["source", x, z, new])
            if new != old:
                ops.append(["update", x, z, new, new < old])
        elif r < 520 and kind in ("any", "desync"):
            # The graph told something the sources don't say.
            ops.append(["update", x, z, any_level(rng, level_count), rng.chance(0.5)])
        elif r < 560 and kind == "desync":
            ops.append(["set", x, z, any_level(rng, level_count)])
        elif r < 900:
            if bounded or rng.chance(0.15):
                ops.append(["run", 1 + rng.below(rng.pick([5, 60, 800, 3000]))])
            else:
                ops.append(["run", INT_MAX])
        elif r < 940:
            ops.append(["dump"])
    if bounded:
        ops.append(["run", 4000])
    else:
        ops.append(["run", INT_MAX])
    ops.append(["dump"])
    return ops


def case(rng, name, config, kind, style, sizes, counts):
    level_count, unset, keep_below, no_source = config
    chunks = pool(rng, rng.pick(sizes), style)
    ops = ops_for(rng, config, chunks, rng.pick(counts), kind)
    return {"id": name, "input": {"level_count": level_count, "unset": unset, "keep_below": keep_below,
                                  "no_source": no_source, "ops": ops}}


def random_config(rng):
    count = 2 + rng.below(rng.pick([8, 30, 60]))
    unset = count - 2 + rng.below(5)
    keep_below = 1 + rng.below(count + 1)
    no_source = rng.pick([count - 1, count, count + 3, INT_MAX, 45])
    return (count, unset, keep_below, no_source)


def main():
    rng = Rng(SEED)
    cases = []
    for i in range(60):
        style = rng.pick(["near", "near", "near", "spread"])
        cases.append(case(rng, f"loading-{i}", LOADING, "ticket", style, [1, 3, 8, 20], [10, 30, 80]))
    for i in range(40):
        cases.append(case(rng, f"simulation-{i}", SIMULATION, "ticket", "near", [1, 3, 8, 20], [10, 30, 80]))
    for i in range(40):
        cases.append(case(rng, f"spawn-{i}", SPAWN, "player", rng.pick(["near", "spread"]), [1, 2, 5, 12], [10, 30, 80]))
    for i in range(16):
        cases.append(case(rng, f"player-{i}", PLAYER, "player", "near", [1, 2, 4], [4, 8, 16]))
    for i in range(60):
        cases.append(case(rng, f"random-{i}", random_config(rng), "any", "near", [2, 5, 12, 30], [20, 60, 150]))
    for i in range(30):
        config = rng.pick([LOADING, SIMULATION, SPAWN, random_config(rng)])
        cases.append(case(rng, f"desync-{i}", config, "desync", "near", [2, 5, 12], [20, 60, 120]))
    for i in range(24):
        config = rng.pick([LOADING, SIMULATION, SPAWN, PLAYER])
        kind = "player" if config in (SPAWN, PLAYER) else "ticket"
        cases.append(case(rng, f"edge-{i}", config, kind, rng.pick(["source", "wrap"]), [1, 3, 8], [10, 30, 60]))
    write_file(HERE / "generated.json", "levels", f"cases/levels/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
