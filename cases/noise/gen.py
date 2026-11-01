"""Writes cases/noise/generated.json: vanilla's noises sampled at points and over volumes.

    py -I cases/noise/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, and the vanilla noises'
parameters from the pinned server jar in oracle/jars/, so rerunning it gives the same file.

Each kind of noise is made from legacy and xoroshiro sources, with seeds at the ends of the
`long` range and at random, then sampled where worldgen samples it: near the origin, across the
30,000,000 blocks of a world at the scales worldgen uses, far past where `wrap` folds the input,
and at the points where it folds, as halves, integers, zeros of both signs, infinities and NaN.
Volumes are a noise chunk's cells, a section's blocks, flat ones with a `y` scale of 0, and some
at random, as `NoiseFunction` samples them. The normal noises are every one of the vanilla data
pack's, and others at random with zero amplitudes, every normalization and up to 32 octaves; the
legacy Nether ones include the two the Nether's biomes use, and parameters vanilla rejects.
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

SEED = 20261101
JAR = ROOT / "oracle" / "jars" / "server-26.3.jar"
INNER = "META-INF/versions/26.3/server-26.3.jar"
NOISES = "data/minecraft/worldgen/noise/"

# The edges of `GradientNoise.wrap`: 2^24, the largest double below it, 2^25, and around them.
EDGES = ["0", "-0", "0.5", "-0.5", "1", "-1", "0x1.fffffffffffffp-1", "-0x1.fffffffffffffp-1",
         "16777216", "-16777216", "0x1.fffffffffffffp23", "-0x1.fffffffffffffp23", "16777217.5",
         "-16777217.5", "33554432", "-33554432", "50331648", "-50331648", "1e9", "-1e9", "2147483648",
         "-2147483649", "9007199254740993", "1e20", "-1e20", "1e300", "inf", "-inf", "nan",
         "0x1p-1074", "123456.789", "-29999999.5", "29999999.5"]

LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]


class Gen:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def u64(self):
        return next(self.r)

    def below(self, n):
        return self.u64() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def unit(self):
        return (self.u64() >> 11) * 2.0**-53

    def long(self):
        x = self.u64()
        return str(x - (1 << 64) if x >= 1 << 63 else x)

    def seed(self):
        return LONG_SEEDS[self.below(len(LONG_SEEDS))] if self.below(3) == 0 else self.long()

    def blob_seed(self):
        return str(self.u64() >> 1)


def vanilla_noises():
    """The vanilla data pack's noise parameters, by name, from the pinned server jar."""
    with zipfile.ZipFile(JAR) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(INNER)))
    out = {}
    for name in sorted(inner.namelist()):
        if name.startswith(NOISES) and name.endswith(".json"):
            out[name[len(NOISES):-len(".json")]] = json.loads(inner.read(name))
    return out


def points(g, count, xz, y):
    return {"gen": "f64_range", "seed": g.blob_seed(), "count": count, "ranges": [[f"-{xz}", f"{xz}"], [f"-{y}", f"{y}"], [f"-{xz}", f"{xz}"]]}


def edge_triples(g, count):
    """Triples of the edge values, each axis drawn on its own."""
    return {"f64": [EDGES[g.below(len(EDGES))] for _ in range(count * 3)]}


def edge_pairs(g, count):
    return {"f64": [EDGES[g.below(len(EDGES))] for _ in range(count * 2)]}


def pairs(g, count, scale):
    return {"gen": "f64_range", "seed": g.blob_seed(), "count": count, "ranges": [[f"-{scale}", f"{scale}"], [f"-{scale}", f"{scale}"]]}


def case(cid, random, seed, noise, fn, blobs=None, **extra):
    c = {"id": cid, "input": {"random": random, "seed": seed, "noise": noise, "fn": fn, **extra}}
    if blobs is not None:
        c["blobs"] = [blobs]
    return c


def sampled(g, prefix, noise, scales, two_d=True):
    """A noise from both sources, at points near and far, and at the edges."""
    out = []
    for random in ("legacy", "xoroshiro"):
        p = f"{prefix}-{random}"
        out.append(case(f"{p}-near", random, g.seed(), noise, "get3", points(g, 400, 64, 64)))
        for i, s in enumerate(scales):
            out.append(case(f"{p}-far-{i}", random, g.seed(), noise, "get3", points(g, 300, repr(30000000 * s), repr(320 * s))))
        out.append(case(f"{p}-huge", random, g.seed(), noise, "get3", points(g, 200, "1e12", "1e9")))
        out.append(case(f"{p}-edges", random, g.seed(), noise, "get3", edge_triples(g, 100)))
        if two_d:
            out.append(case(f"{p}-2d", random, g.seed(), noise, "get2", pairs(g, 300, 100000)))
            out.append(case(f"{p}-2d-edges", random, g.seed(), noise, "get2", edge_pairs(g, 80)))
        out.append(case(f"{p}-range", random, g.seed(), noise, "range"))
    return out


def volume(g, cid, random, noise, dims, xz_scale, y_scale, amplitude="1"):
    return case(cid, random, g.seed(), noise, "volume", volume=dims, xz_scale=xz_scale, y_scale=y_scale, amplitude=amplitude)


def volumes(g, prefix, noise, scales):
    """A noise over the volumes worldgen samples, at the scales given."""
    out = []
    for random in ("legacy", "xoroshiro"):
        p = f"{prefix}-{random}"
        for i, (xz, y) in enumerate(scales):
            cx, cz = g.between(-1875000, 1874999), g.between(-1875000, 1874999)
            # A noise chunk's cell corners: 5 by 49 by 5, 4 blocks apart across and 8 up.
            out.append(volume(g, f"{p}-cells-{i}", random, noise, [5, 49, 5, cx * 16, -64, cz * 16, 4, 8, 4], xz, y))
            # A section's blocks, one apart.
            sy = g.between(-4, 19) * 16
            out.append(volume(g, f"{p}-section-{i}", random, noise, [16, 16, 16, cx * 16, sy, cz * 16, 1, 1, 1], xz, y))
        out.append(volume(g, f"{p}-flat", random, noise, [16, 1, 16, g.between(-1000, 1000), 0, g.between(-1000, 1000), 1, 1, 1], scales[0][0], "0"))
        out.append(volume(g, f"{p}-amplified", random, noise, [7, 9, 3, -40, -64, 13, 3, 5, 7], scales[0][0], scales[0][1], "-2.5"))
        for i in range(2):
            dims = [g.between(1, 12), g.between(1, 40), g.between(1, 12), g.between(-30000000, 30000000), g.between(-2048, 2048),
                    g.between(-30000000, 30000000), g.between(1, 9), g.between(1, 9), g.between(1, 9)]
            xz = repr(g.unit() * 2)
            y = repr(g.unit() * 2)
            out.append(volume(g, f"{p}-random-{i}", random, noise, dims, xz, y, repr(g.unit() * 4 - 2)))
    return out


def random_parameters(g):
    count = g.between(1, 32)
    p = {"base_octave": g.between(-32, 32 - count) if g.below(2) else g.between(-32, 0)}
    if g.below(4):
        p["base_amplitude"] = round(0.2 + g.unit() * 3, 12)
    if count != 1 or g.below(2):
        p["octave_count"] = count
    if g.below(3):
        mods = []
        for _ in range(count):
            r = g.below(5)
            mods.append(0.0 if r == 0 else 1.0 if r == 1 else round(g.unit() * 3, 6))
        p["amplitude_modifiers"] = mods
    r = g.below(5)
    if r == 0:
        p["normalize"] = False
    elif r == 1:
        p["normalize"] = "legacy"
    elif r == 2:
        p["normalize"] = True
    return p


def main():
    g = Gen(SEED)
    cases = []

    perlin = {"type": "perlin"}
    cases += sampled(g, "perlin", perlin, [1, 0.25, 2.0**-10])
    cases += volumes(g, "perlin", perlin, [("0.25", "0"), ("1", "1"), ("0.015625", "0.0078125")])

    for i, fudge in enumerate(["684.412", "8.555150000000001", "1", "0.5", "1e-3", "-3"]):
        smeared = {"type": "smeared", "fudge_y_scale": fudge}
        cases += sampled(g, f"smeared-{i}", smeared, [2.0**-14, 1])
        cases += volumes(g, f"smeared-{i}", smeared, [("171.103", "85.5515"), ("1", "0.5")])

    for discard in (False, True):
        simplex = {"type": "simplex", "discard_offset": discard}
        name = "simplex-at-0" if discard else "simplex"
        cases += sampled(g, name, simplex, [1, 2.0**-3])
        cases += volumes(g, name, simplex, [("0.5", "0.5")])

    vanilla = vanilla_noises()
    for name, parameters in vanilla.items():
        normal = {"type": "normal", "parameters": parameters}
        cid = "normal-" + name.replace("/", "-")
        for random in ("legacy", "xoroshiro"):
            cases.append(case(f"{cid}-{random}", random, g.seed(), normal, "get3", points(g, 200, 30000000, 320)))
            cases.append(case(f"{cid}-{random}-near", random, g.seed(), normal, "get3", points(g, 100, 64, 64)))
        cases.append(case(f"{cid}-range", "xoroshiro", g.seed(), normal, "range"))
    for name in ("temperature", "continentalness", "spaghetti_3d_1", "aquifer_barrier"):
        cases += volumes(g, f"normal-{name}", {"type": "normal", "parameters": vanilla[name]}, [("0.25", "0"), ("1", "1")])
    for i in range(40):
        normal = {"type": "normal", "parameters": random_parameters(g)}
        random = "legacy" if i % 2 else "xoroshiro"
        cases.append(case(f"normal-random-{i}", random, g.seed(), normal, "get3", points(g, 150, 30000000, 320)))
        cases.append(case(f"normal-random-{i}-2d", random, g.seed(), normal, "get2", pairs(g, 100, 3000000)))
        cases.append(case(f"normal-random-{i}-range", random, g.seed(), normal, "range"))

    nether = [vanilla["nether/temperature"], vanilla["nether/vegetation"]]
    for i in range(12):
        parameters = random_parameters(g)
        # Vanilla rejects positive octaves here, so most keep below 0, and some don't.
        if i < 9:
            parameters["base_octave"] = min(parameters["base_octave"], 1 - parameters.get("octave_count", 1))
        nether.append(parameters)
    for i, parameters in enumerate(nether):
        noise = {"type": "legacy_nether", "parameters": parameters}
        cases.append(case(f"legacy-nether-{i}", "legacy", g.seed(), noise, "get3", points(g, 200, 30000000, 128)))
        cases.append(case(f"legacy-nether-{i}-xoroshiro", "xoroshiro", g.seed(), noise, "get3", points(g, 100, 1000, 128)))
        cases.append(case(f"legacy-nether-{i}-range", "legacy", g.seed(), noise, "range"))
    cases += volumes(g, "legacy-nether-0", {"type": "legacy_nether", "parameters": nether[0]}, [("0.25", "0")])

    # BlendedNoise's three stacks with the overworld's settings, then others.
    fbms = [(-15, "684.412", "0.9999847412109375"), (-7, "8.555150000000001", "12.75"), (0, "1", "1"), (-3, "0.5", "-2"),
            (-20, "1e4", "3.5"), (1, "1", "1")]
    for i, (first, smear, factor) in enumerate(fbms):
        fbm = {"type": "fbm", "first_octave": first, "smear_scale_y": smear, "value_factor": factor}
        cases += sampled(g, f"fbm-{i}", fbm, [171.103 / 30000000 * 4, 1], two_d=False)
        if first <= 0:
            cases += volumes(g, f"fbm-{i}", fbm, [("171.103", "85.5515"), ("2.1387875", "0.5346969")])

    write_file(HERE / "generated.json", "noise", f"cases/noise/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
