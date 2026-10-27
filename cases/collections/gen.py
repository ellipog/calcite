"""Writes cases/collections/generated.json: random operations on every collection, with every
key type, and the iteration order checked as they go.

    py -I cases/collections/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.

Each case alternates phases that mostly add, which grow the table, with phases that mostly remove,
which shrink fastutil's, and looks at the order every few operations. The keys come from one of a
few styles: random over a span, a dense run from 0, and keys whose Java hashes collide, so
HashMap's bins turn into trees. Strings are ASCII, which Java and Calcite order the same.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261028
CASES_PER_PAIR = 6
KEYS = ["int", "long", "string"]
COLLECTIONS = ["hash_map", "linked_hash_map", "tree_map", "open_hash_map", "hash_set", "linked_hash_set",
               "tree_set", "open_hash_set", "priority_queue", "array_deque"]
MAPS = {"hash_map", "linked_hash_map", "tree_map", "open_hash_map"}
SIZED = {"hash_map", "hash_set", "open_hash_map", "open_hash_set"}
WORDS = ["stone", "dirt", "grass_block", "oak_log", "water", "lava", "sand", "gravel", "iron_ore", "chest",
         "furnace", "torch", "glass", "wool", "bedrock", "obsidian", "ice", "snow", "cactus", "pumpkin"]


def signed64(x):
    return x - (1 << 64) if x >= 1 << 63 else x


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def chance(self, percent):
        return self.below(100) < percent


class Keys:
    """A case's keys: a style and a span, so most operations hit keys the case has seen."""

    def __init__(self, g, kind):
        self.g = g
        self.kind = kind
        self.style = ["random", "dense", "collide"][g.below(3)]
        self.span = [8, 40, 300, 2000][g.below(4)]

    def key(self):
        g, n = self.g, self.below_span()
        if self.kind == "int":
            if self.style == "dense":
                return str(n)
            if self.style == "collide":
                # (i << 16) | i: the high and low halves cancel in HashMap's spread, so every key
                # lands in bin 0 of any table under 65,536 bins.
                return str(signed32((n << 16) | n))
            return str(signed32(g.u64() & 0xFFFFFFFF) if g.chance(20) else n * [1, -1][g.below(2)] * 7919)
        if self.kind == "long":
            if self.style == "dense":
                return str(n - self.span // 2)
            if self.style == "collide":
                # (i << 32) | i: Long.hashCode xors the halves, so every one hashes to 0.
                return str(signed64((n << 32) | n))
            return str(signed64(g.u64())) if g.chance(20) else str(signed64((n * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)))
        if self.style == "dense":
            return f"minecraft:{WORDS[n % len(WORDS)]}_{n // len(WORDS)}"
        if self.style == "collide":
            # "Aa" and "BB" have the same hashCode, so every string of them of one length does.
            parts = []
            for i in range(6):
                parts.append("Aa" if (n >> i) & 1 else "BB")
            return "".join(parts) + str(n >> 6)
        return f"k{n}"

    def below_span(self):
        return self.g.below(self.span)

    def bounds(self):
        """Two keys for a range, the first not after the second."""
        a, b = self.key(), self.key()
        return (a, b) if order(self.kind, a) <= order(self.kind, b) else (b, a)


def signed32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >= 1 << 31 else x


def order(kind, key):
    """A key's natural order: numbers by value, ASCII strings by their characters."""
    return int(key) if kind != "string" else key


def value(g):
    return int(g.below(2000)) - 1000


def ops_for(g, collection, keys, count):
    ops = []
    adding = True
    phase = 0
    for i in range(count):
        if phase == 0:
            adding = not adding if i else True
            phase = 20 + g.below(200)
        phase -= 1
        if i % 37 == 36:
            ops.append(["iter"])
            continue
        ops.append(op(g, collection, keys, adding))
    ops.append(["size"])
    ops.append(["iter"])
    return ops


def op(g, collection, keys, adding):
    roll = g.below(100)
    if collection == "priority_queue":
        if roll < (55 if adding else 15):
            return ["add", keys.key()]
        if roll < 70:
            return ["poll"]
        if roll < 75:
            return ["peek"]
        if roll < 85:
            return ["remove", keys.key()]
        if roll < 92:
            return ["contains", keys.key()]
        if roll < 95:
            return ["remove_iter", 2 + int(g.below(5)), int(g.below(2))]
        if roll < 99:
            return ["size"]
        return ["clear"] if g.chance(30) else ["iter"]
    if collection == "array_deque":
        if roll < (55 if adding else 15):
            return [["add_first", "add_last"][g.below(2)], keys.key()]
        if roll < 75:
            return [["poll_first", "poll_last"][g.below(2)]]
        if roll < 82:
            return [["first", "last"][g.below(2)]]
        if roll < 92:
            return ["contains", keys.key()]
        if roll < 99:
            return ["size"]
        return ["clear"] if g.chance(30) else ["iter"]
    is_map = collection in MAPS
    if roll < (60 if adding else 15):
        return ["put", keys.key(), value(g)] if is_map else ["add", keys.key()]
    if roll < 78:
        return ["remove", keys.key()]
    if roll < 86:
        return ["get" if is_map else "contains", keys.key()]
    if roll < 89:
        return ["contains", keys.key()]
    if roll < 90:
        return ["clear"] if g.chance(25) else ["size"]
    if collection.startswith("open"):
        return ["trim"] if roll < 93 else ["size"]
    if collection.startswith("linked"):
        pick = g.below(6)
        if pick < 2:
            name = ["put_first", "put_last"][pick] if is_map else ["add_first", "add_last"][pick]
            return [name, keys.key(), value(g)] if is_map else [name, keys.key()]
        return [["first", "last", "poll_first", "poll_last"][pick - 2]]
    if collection.startswith("tree"):
        pick = g.below(9)
        if pick < 4:
            return [["first", "last", "poll_first", "poll_last"][pick]]
        if pick < 8:
            return [["floor", "ceiling", "lower", "higher"][pick - 4], keys.key()]
        a, b = keys.bounds()
        return ["range", a, b]
    return ["size"]


def main():
    g = Gen(SEED)
    cases = []
    for collection in COLLECTIONS:
        for kind in KEYS:
            for n in range(CASES_PER_PAIR):
                keys = Keys(g, kind)
                # Mostly short cases, and one long one per pair, which grows big tables.
                count = 1500 if n == 0 else 150 + int(g.below(350))
                if n == 0:
                    keys.span = 2000
                inp = {"collection": collection, "key": kind}
                if collection in SIZED and g.chance(40):
                    inp["capacity"] = [0, 1, 3, 12, 17, 64, 100, 1000][g.below(8)]
                inp["ops"] = ops_for(g, collection, keys, count)
                name = f"{collection.replace('_', '-')}-{kind}-{keys.style}-{n}"
                cases.append({"id": name, "input": inp})
    write_file(HERE / "generated.json", "collections", f"cases/collections/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
