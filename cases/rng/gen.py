"""Writes cases/rng/generated.json: random operation sequences on every kind of source.

    py -I cases/rng/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same file.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261027
CASES_PER_KIND = 25
OPS_PER_CASE = 100
KINDS = ["legacy", "single_threaded", "xoroshiro", "xoroshiro128", "worldgen_legacy", "worldgen_xoroshiro"]


def signed64(x):
    return x - (1 << 64) if x >= 1 << 63 else x


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def i32(self, lo=-(1 << 31), hi=(1 << 31) - 1):
        return lo + self.below(hi - lo + 1)

    def seed(self):
        # Mostly random 64-bit seeds, sometimes small ones, as worlds often use.
        return str(signed64(self.u64()) if self.below(4) else self.i32(-1000, 1000))

    def bound(self):
        # Powers of two take a different path in nextInt(bound), so weight them.
        pick = self.below(4)
        if pick == 0:
            return 1 << self.below(31)
        if pick == 1:
            return self.i32(1, 64)
        return self.i32(1, (1 << 31) - 1)

    def coord(self):
        return self.i32(-30_000_000, 30_000_000)


def op(g, worldgen):
    choices = ["nextInt", "nextIntBound", "nextIntRange", "nextIntBetween", "nextLong", "nextBoolean",
               "nextFloat", "nextDouble", "nextGaussian", "triangle", "consume"]
    if worldgen:
        choices += ["setDecorationSeed", "setFeatureSeed", "setLargeFeatureSeed", "setLargeFeatureWithSalt"]
    name = choices[g.below(len(choices))]
    if name == "nextIntBound":
        return ["nextInt", g.bound()]
    if name == "nextIntRange":
        lo = g.i32(-(1 << 30), 1 << 30)
        return ["nextIntRange", lo, lo + g.i32(1, 1 << 30)]
    if name == "nextIntBetween":
        lo = g.i32(-(1 << 30), 1 << 30)
        return ["nextIntBetween", lo, lo + g.i32(0, 1 << 30)]
    if name == "triangle":
        return ["triangle", repr(g.i32(-1000, 1000) / 8), repr(g.i32(0, 1000) / 16)]
    if name == "consume":
        return ["consume", g.i32(0, 50)]
    if name == "setDecorationSeed":
        return [name, g.seed(), g.i32(-1_875_000, 1_875_000), g.i32(-1_875_000, 1_875_000)]
    if name == "setFeatureSeed":
        return [name, g.seed(), g.i32(0, 200), g.i32(0, 11)]
    if name == "setLargeFeatureSeed":
        return [name, g.seed(), g.i32(-1_875_000, 1_875_000), g.i32(-1_875_000, 1_875_000)]
    if name == "setLargeFeatureWithSalt":
        return [name, g.seed(), g.i32(-60_000, 60_000), g.i32(-60_000, 60_000), g.i32()]
    return [name]


def main():
    g = Gen(SEED)
    cases = []
    for kind in KINDS:
        worldgen = kind.startswith("worldgen")
        for n in range(CASES_PER_KIND):
            inp = {"kind": kind}
            if kind == "xoroshiro128":
                inp["seed_lo"], inp["seed_hi"] = str(signed64(g.u64())), str(signed64(g.u64()))
            else:
                inp["seed"] = g.seed()
            ops = [op(g, worldgen) for _ in range(OPS_PER_CASE)]
            # End most cases with a fork into a positional source, so those paths are covered too.
            if not worldgen and g.below(3) == 0:
                ops += [["at", g.coord(), g.i32(-64, 319), g.coord()], ["nextLong"], ["nextInt", g.bound()]]
            elif not worldgen and g.below(2) == 0:
                ops += [["fork"], ["nextLong"], ["nextDouble"]]
            inp["ops"] = ops
            cases.append({"id": f"{kind.replace('_', '-')}-{n:02d}", "input": inp})
    write_file(HERE / "generated.json", "rng", f"cases/rng/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
