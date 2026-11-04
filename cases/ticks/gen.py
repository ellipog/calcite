"""Writes cases/ticks/generated.json: a level's scheduled ticks, through random game ticks.

    py -I cases/ticks/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

Each case is a level of a pool of chunks, few or many, near the origin, in a far corner or spread
over the world, each added with ticks it was saved with or none, then a run of game ticks: chunks
start ticking and schedule what they were saved with, ticks are scheduled, a few at the same
blocks, chunks unload and come back, and each tick runs what's due from the chunks that tick,
sometimes with a small limit. The `random` cases do a bit of everything; the `ties` cases give
many chunks one to three saved ticks, all due together, so the chunks' first ticks tie and the
table of when each is due, which fastutil's iterator goes over as it takes chunks out, decides
their order; the `crowded` cases put a hundred or more chunks in, so the table's runs are long and
wrap past its end.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261104
MAX = 65536


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


def pool(rng, size):
    """`size` chunks: near the origin, in a far corner, or spread over the world."""
    style = rng.below(3)
    out = []
    while len(out) < size:
        if style == 0:
            x, z = rng.below(41) - 20, rng.below(41) - 20
        elif style == 1:
            x, z = 1874999 - rng.below(40), -1874999 + rng.below(40)
        else:
            x, z = rng.below(3749999) - 1874999, rng.below(3749999) - 1874999
        if (x, z) not in out:
            out.append((x, z))
    return out


def priority(rng):
    return 0 if rng.chance(0.75) else rng.below(7) - 3


def block(rng, chunk, spread):
    """A block in `chunk`, among `spread` columns and three heights, so some ticks share one."""
    x, z = chunk
    return [x * 16 + rng.below(spread), rng.below(3) - 1, z * 16 + rng.below(spread)]


def saved(rng, chunk, n, delays):
    out = []
    for _ in range(n):
        out.append([rng.below(6)] + block(rng, chunk, 4) + [rng.pick(delays), priority(rng)])
    return out


class Level:
    def __init__(self, rng, chunks, time):
        self.rng = rng
        self.chunks = chunks
        self.time = time
        self.sub = 0
        self.present = []
        self.started = set()
        self.ops = []

    def add(self, chunk, ticks):
        self.ops.append(["add", chunk[0], chunk[1], ticks])
        self.present.append(chunk)
        self.started.discard(chunk)

    def remove(self, chunk):
        self.ops.append(["remove", chunk[0], chunk[1]])
        self.present.remove(chunk)
        self.started.discard(chunk)

    def schedule(self, chunk, delay):
        kind = self.rng.below(6)
        x, y, z = block(self.rng, chunk, 3)
        self.ops.append(["schedule", kind, x, y, z, str(self.time + delay), priority(self.rng), str(self.sub)])
        self.sub += 1

    def tick(self, ticking, limit):
        self.ops.append(["tick", str(self.time), limit, [list(c) for c in ticking]])
        self.time += 1


def random_case(rng):
    chunks = pool(rng, rng.pick([1, 2, 3, 6, 12, 30]))
    level = Level(rng, chunks, rng.pick([0, rng.below(24000), (1 << 40) + rng.below(1000)]))
    for c in chunks:
        if rng.chance(0.5):
            level.add(c, saved(rng, c, rng.below(7), [0, 1, 2, 3, 5, 8, 20, -1]))
        else:
            level.add(c, None)
    steps = 20 + rng.below(80)
    for _ in range(steps):
        roll = rng.below(100)
        if roll < 8 and level.present:
            gone = rng.pick(level.present)
            if rng.chance(0.5):
                level.ops.append(["pack", gone[0], gone[1], str(level.time)])
            level.remove(gone)
        elif roll < 14:
            back = [c for c in chunks if c not in level.present]
            if back:
                c = rng.pick(back)
                level.add(c, saved(rng, c, rng.below(5), [0, 1, 4, 10]) if rng.chance(0.7) else None)
        for c in list(level.present):
            if c not in level.started and rng.chance(0.4):
                level.ops.append(["unpack", c[0], c[1], str(level.time)])
                level.started.add(c)
        for _ in range(rng.below(9)):
            # Into a chunk with ticks, mostly, or one without, which drops it.
            c = rng.pick(level.present) if level.present and rng.chance(0.9) else rng.pick(chunks)
            level.schedule(c, rng.pick([0, 1, 1, 2, 3, 5, 10, 30]))
        if rng.chance(0.1) and level.present:
            c = rng.pick(level.present)
            level.ops.append(["has", rng.below(6)] + block(rng, c, 3))
        if rng.chance(0.08):
            level.ops.append(["count"])
        if rng.chance(0.06) and level.present:
            c = rng.pick(level.present)
            level.ops.append(["pack", c[0], c[1], str(level.time)])
        ticking = [c for c in chunks if rng.chance(0.85)]
        level.tick(ticking, MAX if rng.chance(0.8) else 1 + rng.below(6))
        if rng.chance(0.1):
            level.ops.append(["dump"])
    level.ops.append(["count"])
    level.ops.append(["dump"])
    return level.ops


def ties_case(rng):
    chunks = pool(rng, rng.pick([8, 20, 50, 120]))
    level = Level(rng, chunks, rng.below(100000))
    for c in chunks:
        level.add(c, saved(rng, c, 1 + rng.below(3), [0, 1]))
    for c in chunks:
        level.ops.append(["unpack", c[0], c[1], str(level.time)])
    level.ops.append(["dump"])
    for _ in range(3 + rng.below(4)):
        for _ in range(rng.below(4)):
            level.schedule(rng.pick(chunks), rng.below(2))
        level.tick([c for c in chunks if rng.chance(0.9)], MAX if rng.chance(0.6) else 1 + rng.below(40))
        level.ops.append(["dump"])
    return level.ops


def crowded_case(rng):
    chunks = pool(rng, rng.pick([120, 250]))
    level = Level(rng, chunks, rng.below(100000))
    for c in chunks:
        level.add(c, saved(rng, c, rng.below(3), [0, 1, 2]) if rng.chance(0.6) else None)
    for c in chunks:
        if rng.chance(0.8):
            level.ops.append(["unpack", c[0], c[1], str(level.time)])
            level.started.add(c)
    for _ in range(4 + rng.below(6)):
        for _ in range(rng.below(60)):
            level.schedule(rng.pick(chunks), rng.below(3))
        for c in list(level.present):
            if rng.chance(0.03):
                level.remove(c)
        level.tick([c for c in chunks if rng.chance(0.8)], MAX if rng.chance(0.7) else 1 + rng.below(200))
    level.ops.append(["dump"])
    return level.ops


def main():
    rng = Rng(SEED)
    cases = []
    for i in range(120):
        cases.append({"id": f"random-{i}", "input": {"ops": random_case(rng)}})
    for i in range(60):
        cases.append({"id": f"ties-{i}", "input": {"ops": ties_case(rng)}})
    for i in range(10):
        cases.append({"id": f"crowded-{i}", "input": {"ops": crowded_case(rng)}})
    write_file(HERE / "generated.json", "ticks", f"cases/ticks/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
