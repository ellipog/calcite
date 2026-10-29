"""Writes cases/palette/generated.json: vanilla's paletted containers grown through every kind of
palette, sent, saved and loaded, and the bit storage under them.

    py -I cases/palette/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.

The containers start with the flat world's bottom section and with values set one at a time past
each size where the palette changes kind, for block states and biomes, over registries from 1
value to 26.3's 35,723 block states. Others overwrite one value until most entries are unused, so
the next resize drops them. The unpack cases give palettes and longs as a region file holds them,
with random bits above the values in each long, which vanilla keeps for a palette and drops when
it turns indices into IDs, and data that's missing or the wrong length. The rest are random sets
over spans of values that grow, with what's sent and saved looked at between them. A palette is
never empty and its data never indexes past its end, where vanilla doesn't fail but Calcite does
(std.palette, D163).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261029
BLOCK_STATES = 35723
BIOMES = 65
SIZES = {"block_states": 4096, "biomes": 64}
# Where a palette of each strategy moves to the next kind or size, as a count of entries.
STEPS = {"block_states": [1, 2, 16, 17, 32, 33, 64, 65, 128, 129, 256, 257, 300],
         "biomes": [1, 2, 3, 4, 5, 8, 9, 12]}
LOOK = [["bits"], ["write"], ["pack"]]


def signed64(x):
    x &= (1 << 64) - 1
    return x - (1 << 64) if x >= 1 << 63 else x


def ceil_log2(n):
    return max(0, (n - 1).bit_length())


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n


def pack(values, bits, g=None):
    """The longs SimpleBitStorage packs `values` in, with random bits wherever no value is when
    `g` is given."""
    per = 64 // bits
    longs = []
    for c in range((len(values) + per - 1) // per):
        x = 0
        used = 0
        for k in range(per):
            i = c * per + k
            if i < len(values):
                x |= values[i] << (k * bits)
                used = (k + 1) * bits
        if g is not None and used < 64:
            x |= (g.u64() >> used) << used
        longs.append(str(signed64(x)))
    return longs


def container(name, strategy, registry, value, ops):
    return {"id": name, "input": {"of": "container", "strategy": strategy, "registry": registry, "value": value, "ops": ops}}


def flat_section():
    ops = []
    for y, v in enumerate([88, 10, 10, 9]):
        for i in range(256):
            ops.append(["set", y * 256 + i, v])
    return container("flat-bottom-section", "block_states", BLOCK_STATES, 0, ops + LOOK + [["counts"], ["repack"]] + LOOK)


def growth(strategy, registry):
    """Index i set to i + 1, so after it the container holds i + 2 values, past each step."""
    ops = []
    looked = set()
    for i in range(min(STEPS[strategy][-1], registry - 1)):
        ops.append(["set", i, i + 1])
        if i + 2 in STEPS[strategy] or i + 1 in STEPS[strategy]:
            ops += LOOK
            looked.add(i)
    ops += [["counts"], ["get", 0], ["get", SIZES[strategy] - 1], ["get_and_set", 0, 0], ["repack"]] + LOOK
    return container(f"{strategy.replace('_', '-')}-growth-{registry}", strategy, registry, 0, ops)


def dropped(strategy, registry, rounds):
    """One value overwritten again and again: each one leaves an entry nothing refers to, until
    the palette is full and the resize keeps only what's there."""
    ops = []
    for v in range(1, rounds + 1):
        ops.append(["set", 5, v])
        ops.append(["bits"])
    return container(f"{strategy.replace('_', '-')}-dropped-{rounds}", strategy, registry, 0, ops + LOOK + [["counts"]])


def get_and_set(g):
    ops = []
    for _ in range(200):
        ops.append(["get_and_set", int(g.below(4096)), int(g.below(40))])
    return container("block-states-get-and-set", "block_states", BLOCK_STATES, 7, ops + LOOK)


def unpacks(g):
    cases = []
    b, n = "block_states", 4096

    def case(name, strategy, registry, ops):
        cases.append(container(f"unpack-{name}", strategy, registry, 0, ops))

    def unpack(palette, values, bits, garbage=True):
        return ["unpack", palette, pack(values, bits, g if garbage else None)]

    case("single", b, BLOCK_STATES, [["unpack", [5], None]] + LOOK + [["set", 0, 6]] + LOOK)
    case("single-with-data", b, BLOCK_STATES, [["unpack", [5], ["1", "2"]]] + LOOK)
    case("missing-data", b, BLOCK_STATES, [["set", 0, 3], ["unpack", [1, 2], None]] + LOOK)
    case("short-data", b, BLOCK_STATES, [["unpack", [1, 2], ["0", "0", "0"]]] + LOOK)
    case("long-data", b, BLOCK_STATES, [["unpack", [1, 2, 3], ["0"] * 257]] + LOOK)
    linear = [int(g.below(3)) for _ in range(n)]
    case("linear", b, BLOCK_STATES, [unpack([40, 41, 42], linear, 4)] + LOOK + [["get", 9], ["set", 0, 43], ["set", 1, 41]] + LOOK + [["counts"]])
    case("linear-unused", b, BLOCK_STATES, [unpack([40, 41, 42, 43, 44], [int(g.below(2)) * 3 for _ in range(n)], 4)] + LOOK + [["counts"]])
    case("linear-duplicates", b, BLOCK_STATES, [unpack([7, 7, 8], [int(g.below(3)) for _ in range(n)], 4), ["set", 0, 7], ["get", 1]] + LOOK)
    case("linear-full", b, BLOCK_STATES, [unpack(list(range(100, 116)), [int(g.below(16)) for _ in range(n)], 4), ["set", 3, 116]] + LOOK)
    for count in [17, 33, 100, 256]:
        bits = ceil_log2(count)
        values = [int(g.below(count)) for _ in range(n)]
        palette = [int(g.below(BLOCK_STATES)) for _ in range(count)]
        palette = list(dict.fromkeys(palette))
        while len(palette) < count:
            palette.append(len(palette) + 1000)
        case(f"hash-{count}", b, BLOCK_STATES, [unpack(palette, values, bits)] + LOOK + [["random_sets", str(g.u64() >> 1), 50, 0, 300]] + LOOK + [["counts"]])
    for count in [257, 300, 1000, 4096]:
        bits = ceil_log2(count)
        values = [int(g.below(count)) for _ in range(n)]
        palette = [int(x) for x in sorted({int(g.below(BLOCK_STATES)) for _ in range(count * 2)})][:count]
        case(f"global-{count}", b, BLOCK_STATES, [unpack(palette, values, bits)] + LOOK + [["counts"], ["get_and_set", 17, 3]] + LOOK)
    case("global-short-data", b, BLOCK_STATES, [["unpack", list(range(300)), ["0"] * 10]] + LOOK)
    for count, bits in [(2, 1), (3, 2), (4, 2), (5, 3), (8, 3)]:
        values = [int(g.below(count)) for _ in range(64)]
        case(f"biomes-{count}", "biomes", BIOMES, [unpack(list(range(20, 20 + count)), values, bits)] + LOOK + [["set", 0, 60]] + LOOK)
    for count in [9, 20, 64]:
        values = [int(g.below(count)) for _ in range(64)]
        case(f"biomes-global-{count}", "biomes", BIOMES, [unpack(list(range(count)), values, ceil_log2(count))] + LOOK + [["counts"]])
    case("biomes-short-data", "biomes", BIOMES, [["unpack", [1, 2], []]] + LOOK)
    return cases


def randoms(g):
    cases = []
    spans = {"block_states": [4, 16, 17, 40, 256, 300, 3000], "biomes": [2, 3, 8, 9, 40]}
    for strategy, registries in [("block_states", [BLOCK_STATES, 300, 70000, 1 << 20]), ("biomes", [BIOMES, 9, 17, 300])]:
        for registry in registries:
            for k in range(3):
                ops = []
                low = int(g.below(max(1, registry - 3000)))
                for span in spans[strategy]:
                    high = min(registry, low + span)
                    ops.append(["random_sets", str(g.u64() >> 1), int(g.below(SIZES[strategy] * 2)) + 1, low, high])
                    ops += LOOK
                    if g.below(2):
                        ops += [["counts"], ["repack"], ["write"]]
                    ops.append(["get", int(g.below(SIZES[strategy]))])
                name = f"{strategy.replace('_', '-')}-random-{registry}-{k}"
                cases.append(container(name, strategy, registry, int(g.below(registry)), ops))
    return cases


def storages(g):
    cases = []
    for bits in range(1, 33):
        top = min((1 << bits) - 1, (1 << 31) - 1)
        # Containers use up to 4,096 values of up to 20 bits, and heightmaps 256 of 9.
        sizes = [0, 1, 64, 256] if bits in (1, 5, 9, 32) else [256]
        for size in sizes + [4096] if bits <= 16 else sizes:
            ops = [["longs"]]
            if size:
                ops += [["random_sets", str(g.u64() >> 1), size, 0, top + 1 if top < (1 << 31) - 1 else top],
                        ["values"], ["longs"], ["get", int(g.below(size))], ["get_and_set", size - 1, int(g.below(top + 1))],
                        ["get", size - 1]]
            ops += [["fill", int(g.below(top + 1))], ["longs"], ["fill", top], ["longs"], ["values"]]
            if size <= 256:
                per = 64 // bits
                need = (size + per - 1) // per
                ops += [["load", [str(signed64(g.u64())) for _ in range(need + 1)]], ["longs"],
                        ["load", [str(signed64(g.u64())) for _ in range(need)]], ["longs"], ["values"]]
            cases.append({"id": f"storage-{bits}-{size}", "input": {"of": "storage", "bits": bits, "size": size, "ops": ops}})
    return cases


def main():
    g = Gen(SEED)
    cases = [flat_section()]
    for strategy, registries in [("block_states", [BLOCK_STATES, 1, 2, 17, 300]), ("biomes", [BIOMES, 1, 2, 4, 5, 8, 9, 16, 17])]:
        for registry in registries:
            cases.append(growth(strategy, registry))
    cases += [dropped("block_states", BLOCK_STATES, 40), dropped("biomes", BIOMES, 12), get_and_set(g)]
    cases += unpacks(g)
    cases += randoms(g)
    cases += storages(g)
    write_file(HERE / "generated.json", "palette", f"cases/palette/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
