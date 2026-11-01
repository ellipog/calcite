"""Writes cases/density/generated.json: density functions compiled by a RandomState and sampled.

    py -I cases/density/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, and the vanilla ids from the
pinned server jar in oracle/jars/, so rerunning it gives the same file.

The cases name vanilla's material by id and never copy it: every density function of the vanilla
data pack, by reference, and every field of every noise settings' router. Each is sampled where
worldgen samples it: at points near the origin, across a world, and at the ends of `int`, and
over a noise chunk's cells, a section's blocks, and volumes at random. Then synthetic functions
cover every type and its edges one at a time, and random trees of them cover how they combine:
constant folding, ranges that decide which sampler compiles, caches shared between functions and
sampled through one context, interpolation over aligned and unaligned volumes at every step, and
functions vanilla rejects as it works out their ranges or compiles them.
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

SEED = 20261102
JAR = ROOT / "oracle" / "jars" / "server-26.3.jar"
INNER = "META-INF/versions/26.3/server-26.3.jar"
WORLDGEN = "data/minecraft/worldgen/"

ROUTER = ["temperature", "vegetation", "continents", "erosion", "depth", "ridges", "chunk_surface_level", "final_density"]
LONG_SEEDS = ["0", "1", "-1", "9223372036854775807", "-9223372036854775808", "12345"]
INT_MAX = (1 << 31) - 1
INT_MIN = -(1 << 31)
# Coordinates at the edges: of `int`, of a world, and of the bits `BlockPos.asLong` packs them in.
EDGE_INTS = [0, -1, 1, 2, -2, 15, 16, -16, -17, 4, 8, -64, 320, 2031, -2032, 2047, 2048, -2048, -2049,
             30000000, -30000000, 29999999, -29999984, (1 << 25) - 1, -(1 << 25), 1 << 25, -(1 << 25) - 1,
             1 << 26, -(1 << 26), INT_MAX, INT_MIN, INT_MAX - 1, INT_MIN + 1, 1 << 30, -(1 << 30)]
CONSTANTS = [0, -0.0, 1, -1, 0.5, -0.5, 2, 1000000, -1000000, 0.25, 3, -3, 1e-7, 64, -64, 0.1]
UNARY = ["abs", "square", "cube", "sqrt", "half_negative", "quarter_negative", "reciprocal", "negate", "squeeze", "log", "sign"]
BINARY = ["add", "sub", "mul", "div", "min", "max"]
ROUND = ["floor", "round", "ceil", "truncate"]
METRICS = ["euclidean", "euclidean_squared", "manhattan", "chebyshev"]
TILINGS = ["clamp_to_edge", "repeat", "mirrored_repeat"]
AXES = ["x", "y", "z"]


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

    def pick(self, items):
        return items[self.below(len(items))]

    def chance(self, n):
        return self.below(n) == 0

    def long(self):
        x = self.u64()
        return str(x - (1 << 64) if x >= 1 << 63 else x)

    def seed(self):
        return self.pick(LONG_SEEDS) if self.chance(3) else self.long()

    def blob_seed(self):
        return str(self.u64() >> 1)

    def real(self, lo, hi):
        """A float in [lo, hi], rounded so the JSON stays short."""
        return round(lo + (hi - lo) * self.unit(), 4)


def vanilla_ids():
    """The vanilla data pack's density functions, noises and noise settings, by id."""
    with zipfile.ZipFile(JAR) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(INNER)))
    out = {"density_function": [], "noise": [], "noise_settings": []}
    for name in sorted(inner.namelist()):
        for kind, ids in out.items():
            prefix = WORLDGEN + kind + "/"
            if name.startswith(prefix) and name.endswith(".json"):
                ids.append("minecraft:" + name[len(prefix):-len(".json")])
    return out


class Case:
    """One case: functions, the ops that sample them in order, and the points those ops read."""

    def __init__(self, cid, seed, settings=None, legacy=False, cached=False):
        self.cid = cid
        self.input = {"seed": seed}
        if settings is not None:
            self.input["settings"] = settings
        else:
            self.input["legacy_random"] = legacy
        self.input["functions"] = []
        self.input["cached"] = cached
        self.input["ops"] = []
        self.parts = []

    def function(self, f):
        self.input["functions"].append({"function": f})
        return len(self.input["functions"]) - 1

    def router(self, field):
        self.input["functions"].append({"router": field})
        return len(self.input["functions"]) - 1

    def points(self, fn, part, count):
        self.input["ops"].append({"fn": fn, "points": count})
        self.parts.append(part)

    def volume(self, fn, dims):
        self.input["ops"].append({"fn": fn, "volume": dims})

    def build(self):
        return {"id": self.cid, "input": self.input, "blobs": [self.parts if self.parts else {"i32": []}]}


def near(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count, "ranges": [["-300", "300"], ["-80", "340"], ["-300", "300"]]}


def far(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count,
            "ranges": [["-30000000", "30000000"], ["-2100", "2100"], ["-30000000", "30000000"]]}


def anywhere(g, count):
    return {"gen": "i32_range", "seed": g.blob_seed(), "count": count,
            "ranges": [[str(INT_MIN), str(INT_MAX)], [str(INT_MIN), str(INT_MAX)], [str(INT_MIN), str(INT_MAX)]]}


def edges(g, count):
    return {"i32": [g.pick(EDGE_INTS) for _ in range(count * 3)]}


def listed(triples):
    return {"i32": [v for t in triples for v in t]}


def cells(g):
    """A noise chunk's cell corners: 5 by 49 by 5, 4 blocks apart across and 8 up."""
    return [5, 49, 5, g.between(-1875000, 1874999) * 16, -64, g.between(-1875000, 1874999) * 16, 4, 8, 4]


def section(g):
    return [16, 16, 16, g.between(-1875000, 1874999) * 16, g.between(-4, 19) * 16, g.between(-1875000, 1874999) * 16, 1, 1, 1]


def column(g):
    return [16, 1, 16, g.between(-100000, 100000), g.between(-64, 320), g.between(-100000, 100000), 1, 1, 1]


def random_volume(g, limit=2000):
    while True:
        sx, sy, sz = g.between(1, 12), g.between(1, 40), g.between(1, 12)
        if sx * sy * sz <= limit:
            break
    far_out = g.chance(4)
    span = 30000000 if far_out else 2000
    return [sx, sy, sz, g.between(-span, span), g.between(-2100, 2100), g.between(-span, span),
            g.between(1, 9), g.between(1, 9), g.between(1, 9)]


def inside(g, dims, count):
    """Points on the grid of a volume, and some just off it."""
    sx, sy, sz, mx, my, mz, tx, ty, tz = dims
    out = []
    for _ in range(count):
        p = [mx + g.below(sx) * tx, my + g.below(sy) * ty, mz + g.below(sz) * tz]
        if g.chance(4):
            p[g.below(3)] += g.pick([-1, 1])
        out.append(p)
    return out


def sampled(g, c, fn, heavy=True):
    """A function at points near, far and at the edges, and over the volumes worldgen uses."""
    c.points(fn, near(g, 120), 120)
    c.points(fn, far(g, 100), 100)
    c.points(fn, edges(g, 30), 30)
    c.volume(fn, cells(g))
    if heavy:
        c.volume(fn, section(g))
    c.volume(fn, column(g))
    c.volume(fn, random_volume(g))


def cached_ops(g, c, fns):
    """Ops that reach every cache cell's paths: a volume, points on it and off it, a point twice,
    another volume, then the first again, across all the functions in turn."""
    first = cells(g)
    second = random_volume(g, 600)
    for fn in fns:
        c.volume(fn, first)
        pts = inside(g, first, 40)
        pts += [pts[0], pts[0], pts[1]]
        c.points(fn, listed(pts), len(pts))
    for fn in fns:
        c.volume(fn, second)
        pts = inside(g, first, 20) + inside(g, second, 20)
        # Points that `BlockPos.asLong` packs to the same key as the one before.
        x, y, z = pts[-1]
        pts += [[x + (1 << 26), y, z], [x, y + 4096, z], [x, y, z - (1 << 26)]]
        c.points(fn, listed(pts), len(pts))
        c.volume(fn, first)


# Synthetic functions.

def constant(g):
    v = g.pick(CONSTANTS) if g.chance(2) else g.real(-10, 10)
    return v if g.chance(3) else {"type": "constant", "value": v}


def noise_id(g, ids):
    return g.pick(ids["noise"])


def noise_fn(g, ids, depth=1):
    f = {"type": "noise", "noise": noise_id(g, ids),
         "xz_scale": g.pick([0, 0.25, 1, 0.5, g.real(0, 3), 1000]), "y_scale": g.pick([0, 0.25, 1, g.real(0, 3)])}
    for axis in "xyz":
        if g.chance(3):
            f["shift_" + axis] = leaf(g, ids) if depth > 0 else constant(g)
    return f


def gradient(g):
    a, b = g.between(-400, 400), g.between(-400, 400)
    if g.chance(8):
        a, b = g.pick([INT_MIN, INT_MAX, 0, -30000000]), g.pick([INT_MAX, INT_MIN, 1, 30000000])
    if a == b:
        b = a + 1 if a < INT_MAX else a - 1
    f = {"type": "gradient", "axis": g.pick(AXES), "from_coordinate": a, "to_coordinate": b,
         "from_value": g.pick([1, -1, 0, 1000000, g.real(-5, 5)]), "to_value": g.pick([-1, 1, 0, -1000000, g.real(-5, 5)])}
    if not g.chance(3):
        f["tiling"] = g.pick(TILINGS)
    return f


def distance(g):
    span = g.pick([100, 30000000, INT_MAX])
    return {"type": "distance_to_point", "point": [g.between(-span, span), g.between(-span, span), g.between(-span, span)],
            "metric": g.pick(METRICS)}


def blended(g):
    return {"type": "old_blended_noise", "xz_scale": g.pick([0.25, 1, g.real(0.001, 4), 1000, 0.001]),
            "y_scale": g.pick([0.125, 1, g.real(0.001, 4), 1000]), "xz_factor": g.pick([80, 160, g.real(0.001, 400), 1000]),
            "y_factor": g.pick([160, 90, g.real(0.001, 400), 0.001]), "smear_scale_multiplier": g.pick([8, 4, 1, g.real(1, 8)])}


def leaf(g, ids):
    k = g.below(16)
    if k < 4:
        return constant(g)
    if k < 6:
        return noise_fn(g, ids, depth=0)
    if k < 8:
        return gradient(g)
    if k == 8:
        return distance(g)
    if k == 9:
        return {"type": g.pick(["shift_a", "shift_b", "shift"]), "noise": noise_id(g, ids)}
    if k == 10:
        return g.pick(["minecraft:y", "minecraft:zero", "minecraft:shift_x", "minecraft:shift_z",
                       "minecraft:overworld/continents", "minecraft:overworld/erosion", "minecraft:overworld/ridges"])
    if k == 11:
        return {"type": g.pick(["blend_alpha", "blend_offset", "beardifier"])}
    if k == 12:
        return {"type": "end_outer_islands"}
    if k == 13:
        return blended(g)
    return constant(g)


def spline(g, ids, depth):
    if depth <= 0 or g.chance(3):
        return g.pick([0, 1, -1, 0.5, g.real(-2, 2)])
    n = g.between(1, 5)
    locations = sorted(g.real(-1.5, 1.5) for _ in range(n))
    if g.chance(8):
        g_order = locations[:]
        locations = [g_order[i] for i in reversed(range(n))]
    return {"coordinate": tree(g, ids, depth - 1) if g.chance(3) else leaf(g, ids),
            "points": [{"location": loc, "value": spline(g, ids, depth - 1),
                        "derivative": g.pick([0, 0, 1, -1, g.real(-3, 3)])} for loc in locations]}


def tree(g, ids, depth):
    if depth <= 0 or g.chance(5):
        return leaf(g, ids)
    k = g.below(20)
    sub = lambda: tree(g, ids, depth - 1)  # noqa: E731
    if k < 5:
        return {"type": g.pick(BINARY), "left": sub(), "right": sub()}
    if k < 8:
        return {"type": g.pick(UNARY), "input": sub()}
    if k == 8:
        f = {"type": g.pick(ROUND), "input": sub()}
        if g.chance(2):
            f["multiple"] = g.pick([1, 0, 0.5, 2, 16]) if g.chance(2) else sub()
        return f
    if k == 9:
        lo = g.real(-2, 2)
        return {"type": "clamp", "input": sub(), "min": lo, "max": lo + g.pick([0, g.real(0, 3)])}
    if k == 10:
        return {"type": "lerp", "alpha": sub(), "first": sub(), "second": sub()}
    if k == 11:
        lo = g.real(-1.5, 1.5)
        return {"type": "range_choice", "input": sub(), "min_inclusive": lo, "max_exclusive": lo + g.real(-0.5, 2),
                "when_in_range": sub(), "when_out_of_range": sub()}
    if k == 12:
        n = g.between(2, 5)
        return {"type": "interval_select", "input": sub(), "thresholds": sorted(g.real(-1.5, 1.5) for _ in range(n - 1)),
                "functions": [sub() for _ in range(n)]}
    if k == 13:
        return {"type": "pow", "base": sub(), "exponent": g.pick([0.5, 1, 2, 3, -0.5, -1, -2, -3, 0, 1.5]) if g.chance(2) else sub()}
    if k == 14:
        return {"type": "spline", "spline": spline(g, ids, depth)}
    if k == 15:
        return {"type": "cache", "input": sub()}
    if k == 16:
        return {"type": "interpolated", "input": sub(), "cell_size_xz": g.pick([4, 1, 2, 3, 8]), "cell_size_y": g.pick([8, 4, 1, 3, 16])}
    if k == 17:
        return {"type": "slice", "axis": g.pick(AXES), "coordinate": g.between(-100, 100), "input": sub()}
    if k == 18:
        return {"type": "blend_density", "input": sub()}
    lower = g.between(-200, 100)
    return {"type": "find_top_surface", "density": sub(), "upper_bound": g.pick([lower + g.between(0, 300), {"type": "clamp", "input": sub(), "min": -200, "max": 400}]),
            "lower_bound": lower, "cell_height": g.pick([8, 4, 16, 1, 5])}


def synthetic(g, ids):
    """Functions that cover each type and its edges, in a list of (name, function)."""
    out = []
    n = lambda: noise_fn(g, ids, depth=0)  # noqa: E731
    for v in CONSTANTS:
        out.append((f"constant-{v}", v))
        out.append((f"constant-typed-{v}", {"type": "constant", "value": v}))
    for name in UNARY:
        out.append((f"{name}-noise", {"type": name, "input": n()}))
        out.append((f"{name}-gradient", {"type": name, "input": {"type": "gradient", "axis": "y", "from_coordinate": -64, "to_coordinate": 320, "from_value": 2, "to_value": -2}}))
        for v in [0, -0.0, 1, -1, 0.5, -1000000, 1000000]:
            out.append((f"{name}-const-{v}", {"type": name, "input": v}))
        out.append((f"{name}-beardifier", {"type": name, "input": {"type": "beardifier"}}))
        out.append((f"{name}-distance", {"type": name, "input": {"type": "sub", "left": {"type": "distance_to_point", "point": [0, 64, 0], "metric": "chebyshev"}, "right": 100}}))
    for name in BINARY:
        out.append((f"{name}-noises", {"type": name, "left": n(), "right": n()}))
        out.append((f"{name}-const-left", {"type": name, "left": g.pick([0, 2, -0.5]), "right": n()}))
        out.append((f"{name}-const-right", {"type": name, "left": n(), "right": g.pick([0, 2, -0.5])}))
        out.append((f"{name}-consts", {"type": name, "left": g.real(-3, 3), "right": g.real(-3, 3)}))
        out.append((f"{name}-zero", {"type": name, "left": n(), "right": 0}))
        # Ranges that don't meet: min and max pick a side as they compile.
        out.append((f"{name}-apart", {"type": name, "left": {"type": "add", "left": n(), "right": 10}, "right": n()}))
        out.append((f"{name}-apart-2", {"type": name, "left": n(), "right": {"type": "add", "left": n(), "right": 10}}))
        out.append((f"{name}-touch", {"type": name, "left": {"type": "clamp", "input": n(), "min": 0, "max": 1},
                                      "right": {"type": "clamp", "input": n(), "min": 1, "max": 2}}))
        out.append((f"{name}-infinite", {"type": name, "left": {"type": "reciprocal", "input": n()}, "right": {"type": "beardifier"}}))
    for name in ROUND:
        for m in [None, 1, 0, 0.5, 4, -2]:
            f = {"type": name, "input": {"type": "mul", "left": n(), "right": 40}}
            if m is not None:
                f["multiple"] = m
            out.append((f"{name}-multiple-{'default' if m is None else m}", f))
        out.append((f"{name}-multiple-fn", {"type": name, "input": {"type": "mul", "left": n(), "right": 40}, "multiple": n()}))
        out.append((f"{name}-halves", {"type": name, "input": {"type": "gradient", "axis": "x", "from_coordinate": -8, "to_coordinate": 8, "from_value": -4, "to_value": 4}}))
    for lo, hi in [(0, 1), (-1, 1), (0.5, 0.5), (-1000000, 1000000), (2, 3)]:
        out.append((f"clamp-{lo}-{hi}", {"type": "clamp", "input": {"type": "mul", "left": n(), "right": 3}, "min": lo, "max": hi}))
    out.append(("lerp", {"type": "lerp", "alpha": n(), "first": n(), "second": n()}))
    out.append(("lerp-const-first", {"type": "lerp", "alpha": n(), "first": 2, "second": n()}))
    out.append(("lerp-const-second", {"type": "lerp", "alpha": n(), "first": n(), "second": -1}))
    out.append(("lerp-alpha-clamped", {"type": "lerp", "alpha": {"type": "clamp", "input": {"type": "mul", "left": n(), "right": 4}, "min": 0, "max": 1}, "first": n(), "second": n()}))
    out.append(("lerp-alpha-const", {"type": "lerp", "alpha": 0.25, "first": n(), "second": n()}))
    out.append(("lerp-alpha-gradient", {"type": "lerp", "alpha": {"type": "gradient", "axis": "y", "from_coordinate": 0, "to_coordinate": 64, "from_value": -0.5, "to_value": 1.5}, "first": n(), "second": n()}))
    out.append(("lerp-infinite", {"type": "lerp", "alpha": n(), "first": {"type": "beardifier"}, "second": {"type": "reciprocal", "input": n()}}))
    for (lo, hi) in [(-0.2, 0.3), (0, 0), (0.5, 0.1), (-1000000, 1000000)]:
        out.append((f"range-choice-{lo}-{hi}", {"type": "range_choice", "input": n(), "min_inclusive": lo, "max_exclusive": hi, "when_in_range": n(), "when_out_of_range": n()}))
        out.append((f"range-choice-const-{lo}-{hi}", {"type": "range_choice", "input": n(), "min_inclusive": lo, "max_exclusive": hi, "when_in_range": 1, "when_out_of_range": -1}))
    out.append(("range-choice-one-const", {"type": "range_choice", "input": n(), "min_inclusive": 0, "max_exclusive": 1, "when_in_range": 1, "when_out_of_range": n()}))
    out.append(("interval-select-1", {"type": "interval_select", "input": n(), "thresholds": [0.1], "functions": [n(), n()]}))
    out.append(("interval-select-1-const", {"type": "interval_select", "input": n(), "thresholds": [0], "functions": [1, -1]}))
    out.append(("interval-select-4", {"type": "interval_select", "input": n(), "thresholds": [-0.5, 0, 0, 0.5], "functions": [n(), 1, n(), 2, n()]}))
    for e in [0.5, 1, 2, 3, -0.5, -1, -2, -3, 0, 1.5, -1.5, 10]:
        out.append((f"pow-exponent-{e}", {"type": "pow", "base": {"type": "abs", "input": n()}, "exponent": e}))
        out.append((f"pow-signed-{e}", {"type": "pow", "base": n(), "exponent": e}))
    for b in [2, 0.5, 0, -2, 1]:
        out.append((f"pow-base-{b}", {"type": "pow", "base": b, "exponent": {"type": "mul", "left": n(), "right": 3}}))
    out.append(("pow-both", {"type": "pow", "base": {"type": "add", "left": {"type": "abs", "input": n()}, "right": 0.5}, "exponent": n()}))
    out.append(("pow-zero-base", {"type": "pow", "base": {"type": "clamp", "input": n(), "min": 0, "max": 0}, "exponent": n()}))
    out.append(("pow-negative-base", {"type": "pow", "base": {"type": "sub", "left": {"type": "clamp", "input": n(), "min": -1, "max": 0}, "right": 1}, "exponent": n()}))
    for axis in AXES:
        for tiling in TILINGS:
            for (a, b) in [(-64, 320), (320, -64), (0, 1), (INT_MIN, INT_MAX), (5, -5)]:
                out.append((f"gradient-{axis}-{tiling}-{a}-{b}", {"type": "gradient", "axis": axis, "tiling": tiling, "from_coordinate": a, "to_coordinate": b, "from_value": 1.5, "to_value": -1.5}))
        out.append((f"gradient-{axis}-default", {"type": "gradient", "axis": axis, "from_coordinate": 0, "to_coordinate": 16, "from_value": 0, "to_value": 1}))
        out.append((f"slice-{axis}", {"type": "slice", "axis": axis, "coordinate": g.between(-50, 50), "input": n()}))
        out.append((f"slice-{axis}-far", {"type": "slice", "axis": axis, "coordinate": g.pick([INT_MAX, INT_MIN, 30000000]), "input": n()}))
    out.append(("slice-xz", {"type": "slice", "axis": "x", "coordinate": 7, "input": {"type": "slice", "axis": "z", "coordinate": -3, "input": n()}}))
    out.append(("slice-zx", {"type": "slice", "axis": "z", "coordinate": 12, "input": {"type": "slice", "axis": "x", "coordinate": 100, "input": n()}}))
    out.append(("slice-yx", {"type": "slice", "axis": "y", "coordinate": 64, "input": {"type": "slice", "axis": "x", "coordinate": 2, "input": n()}}))
    out.append(("slice-xx", {"type": "slice", "axis": "x", "coordinate": 1, "input": {"type": "slice", "axis": "x", "coordinate": 2, "input": n()}}))
    out.append(("slice-uniform", {"type": "slice", "axis": "y", "coordinate": 0, "input": {"type": "add", "left": {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1, "y_scale": 0}, "right": {"type": "gradient", "axis": "x", "from_coordinate": 0, "to_coordinate": 10, "from_value": 0, "to_value": 1}}}))
    for metric in METRICS:
        for point in [[0, 0, 0], [100, -64, -100], [INT_MAX, INT_MIN, INT_MAX], [-30000000, 2031, 30000000]]:
            out.append((f"distance-{metric}-{point[0]}", {"type": "distance_to_point", "point": point, "metric": metric}))
    out.append(("end-islands", {"type": "end_outer_islands"}))
    out.append(("end-islands-scaled", {"type": "mul", "left": {"type": "end_outer_islands"}, "right": 0.5}))
    for name in ["shift_a", "shift_b", "shift"]:
        out.append((f"{name}", {"type": name, "noise": noise_id(g, ids)}))
        out.append((f"{name}-offset", {"type": name, "noise": "minecraft:offset"}))
    for name in ["blend_alpha", "blend_offset", "beardifier"]:
        out.append((name, {"type": name}))
    out.append(("blend-density", {"type": "blend_density", "input": n()}))
    out.append(("noise-plain", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1, "y_scale": 1}))
    out.append(("noise-flat", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 0.25, "y_scale": 0}))
    out.append(("noise-zero", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 0, "y_scale": 0}))
    out.append(("noise-shift-xz", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 0.25, "y_scale": 0, "shift_x": "minecraft:shift_x", "shift_z": "minecraft:shift_z"}))
    out.append(("noise-shift-xyz", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1, "y_scale": 1, "shift_x": n(), "shift_y": n(), "shift_z": n()}))
    out.append(("noise-shift-zero", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1, "y_scale": 1, "shift_x": 0, "shift_y": 0.0, "shift_z": {"type": "constant", "value": 0}}))
    out.append(("noise-shift-negative-zero", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1, "y_scale": 1, "shift_x": -0.0, "shift_y": -0.0, "shift_z": -0.0}))
    out.append(("noise-huge-scale", {"type": "noise", "noise": noise_id(g, ids), "xz_scale": 1e9, "y_scale": 1e9}))
    out.append(("noise-nether-temperature", {"type": "noise", "noise": "minecraft:nether/temperature", "xz_scale": 1, "y_scale": 1}))
    out.append(("noise-nether-vegetation", {"type": "noise", "noise": "minecraft:nether/vegetation", "xz_scale": 0.25, "y_scale": 0}))
    for i in range(4):
        out.append((f"blended-{i}", blended(g)))
    out.append(("blended-overworld", {"type": "old_blended_noise", "xz_scale": 0.25, "y_scale": 0.125, "xz_factor": 80, "y_factor": 160, "smear_scale_multiplier": 8}))
    out.append(("blended-extremes", {"type": "old_blended_noise", "xz_scale": 1000, "y_scale": 1000, "xz_factor": 0.001, "y_factor": 0.001, "smear_scale_multiplier": 1}))
    for i, (xz, y) in enumerate([(4, 8), (1, 1), (2, 3), (8, 16), (3, 5), (16, 1)]):
        out.append((f"interpolated-{xz}-{y}", {"type": "interpolated", "input": {"type": "add", "left": n(), "right": n()}, "cell_size_xz": xz, "cell_size_y": y}))
    out.append(("interpolated-cached-input", {"type": "interpolated", "input": {"type": "cache", "input": n()}, "cell_size_xz": 4, "cell_size_y": 8}))
    out.append(("interpolated-nested", {"type": "interpolated", "input": {"type": "interpolated", "input": n(), "cell_size_xz": 2, "cell_size_y": 4}, "cell_size_xz": 4, "cell_size_y": 8}))
    out.append(("spline-const", {"type": "spline", "spline": 0.5}))
    out.append(("spline-one", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": 0, "value": 1, "derivative": 2}]}}))
    out.append(("spline-flat", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": -0.5, "value": -1, "derivative": 0}, {"location": 0.5, "value": 1, "derivative": 0}]}}))
    out.append(("spline-same-location", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": 0, "value": -1, "derivative": 1}, {"location": 0, "value": 1, "derivative": -1}, {"location": 0.5, "value": 0, "derivative": 0}]}}))
    out.append(("spline-reversed", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": 0.5, "value": -1, "derivative": 1}, {"location": -0.5, "value": 1, "derivative": 3}]}}))
    out.append(("spline-huge", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": -3e38, "value": 1e39, "derivative": 1e30}, {"location": 3e38, "value": -2, "derivative": 0}]}}))
    shared = n()
    out.append(("spline-shared-coordinate", {"type": "spline", "spline": {"coordinate": shared, "points": [
        {"location": -0.5, "value": {"coordinate": shared, "points": [{"location": 0, "value": 1, "derivative": 0.5}, {"location": 1, "value": 2, "derivative": 0}]}, "derivative": 0},
        {"location": 0.5, "value": {"coordinate": n(), "points": [{"location": -1, "value": -1, "derivative": 0}, {"location": 1, "value": 0.5, "derivative": 1}]}, "derivative": -1}]}}))
    out.append(("spline-nan-coordinate", {"type": "spline", "spline": {"coordinate": {"type": "log", "input": n()}, "points": [{"location": -1, "value": 0, "derivative": 1}, {"location": 1, "value": 1, "derivative": 0}]}}))
    out.append(("spline-overworld-offset", "minecraft:overworld/offset"))
    for cell in [8, 4, 1, 16]:
        out.append((f"find-top-surface-{cell}", {"type": "find_top_surface", "density": {"type": "add", "left": {"type": "gradient", "axis": "y", "from_coordinate": -64, "to_coordinate": 320, "from_value": 1, "to_value": -1}, "right": {"type": "mul", "left": n(), "right": 0.5}},
                                                   "upper_bound": 320, "lower_bound": -64, "cell_height": cell}))
    out.append(("find-top-surface-low", {"type": "find_top_surface", "density": n(), "upper_bound": -100, "lower_bound": -64, "cell_height": 8}))
    out.append(("find-top-surface-bound-fn", {"type": "find_top_surface", "density": n(), "upper_bound": {"type": "add", "left": {"type": "mul", "left": n(), "right": 100}, "right": 64}, "lower_bound": -64, "cell_height": 8}))
    out.append(("find-top-surface-limits", {"type": "find_top_surface", "density": {"type": "gradient", "axis": "y", "from_coordinate": 0, "to_coordinate": 1, "from_value": 1, "to_value": -1}, "upper_bound": 4100, "lower_bound": -4064, "cell_height": 64}))
    out.append(("cache", {"type": "cache", "input": n()}))
    out.append(("cache-nested", {"type": "cache", "input": {"type": "cache", "input": n()}}))
    out.append(("reference-zero", "minecraft:zero"))
    out.append(("reference-y", "minecraft:y"))
    return out


def rejected(g, ids):
    """Functions vanilla rejects as it works out their ranges or compiles them."""
    n = lambda: noise_fn(g, ids, depth=0)  # noqa: E731
    inline = {"base_octave": -3, "octave_count": 2}
    return [
        ("inline-noise", {"type": "noise", "noise": {"base_octave": -3, "octave_count": 2}, "xz_scale": 1, "y_scale": 1}),
        ("inline-shift", {"type": "shift_a", "noise": inline}),
        ("nan-range-add", {"type": "add", "left": {"type": "beardifier"}, "right": {"type": "negate", "input": {"type": "beardifier"}}}),
        ("nan-range-mul", {"type": "mul", "left": {"type": "reciprocal", "input": n()}, "right": {"type": "beardifier"}}),
        ("nan-monotonic", {"type": "cube", "input": {"type": "add", "left": {"type": "beardifier"}, "right": {"type": "beardifier"}}}),
        ("top-surface-nan-bound", {"type": "find_top_surface", "density": n(), "upper_bound": {"type": "add", "left": {"type": "beardifier"}, "right": {"type": "negate", "input": {"type": "beardifier"}}}, "lower_bound": 0, "cell_height": 8}),
        ("spline-backwards-range", {"type": "spline", "spline": {"coordinate": n(), "points": [{"location": 1, "value": 5, "derivative": 100}, {"location": 0, "value": -5, "derivative": 100}]}}),
        ("log-negative", {"type": "log", "input": {"type": "sub", "left": {"type": "clamp", "input": n(), "min": -1, "max": 0}, "right": 2}}),
        ("sqrt-negative", {"type": "sqrt", "input": {"type": "sub", "left": {"type": "clamp", "input": n(), "min": -1, "max": 0}, "right": 2}}),
        ("reciprocal-zero", {"type": "reciprocal", "input": 0}),
        ("pow-infinite", {"type": "pow", "base": {"type": "beardifier"}, "exponent": {"type": "beardifier"}}),
        ("lerp-infinite-alpha", {"type": "lerp", "alpha": {"type": "beardifier"}, "first": {"type": "beardifier"}, "second": 1}),
        ("div-zero", {"type": "div", "left": n(), "right": 0}),
    ]


def main():
    g = Gen(SEED)
    ids = vanilla_ids()
    cases = []

    # Every vanilla density function, by reference.
    for fid in ids["density_function"]:
        name = fid.split(":")[1].replace("/", "-")
        c = Case(f"vanilla-{name}", g.seed())
        sampled(g, c, c.function(fid))
        cases.append(c.build())
        c = Case(f"vanilla-{name}-legacy-cached", g.seed(), legacy=True, cached=True)
        cached_ops(g, c, [c.function(fid)])
        cases.append(c.build())

    # Every noise settings' router, one case each, then cached with the fields sharing caches.
    for sid in ids["noise_settings"]:
        name = sid.split(":")[1]
        for field in ROUTER:
            c = Case(f"router-{name}-{field}", g.seed(), settings=sid)
            sampled(g, c, c.router(field), heavy=field == "final_density")
            cases.append(c.build())
        c = Case(f"router-{name}-cached", g.seed(), settings=sid, cached=True)
        cached_ops(g, c, [c.router(field) for field in ROUTER])
        cases.append(c.build())
        c = Case(f"router-{name}-uncached", g.seed(), settings=sid)
        fns = [c.router(field) for field in ROUTER]
        first = cells(g)
        for fn in fns:
            c.volume(fn, first)
            c.points(fn, near(g, 40), 40)
        cases.append(c.build())

    # Each type and its edges.
    for name, f in synthetic(g, ids):
        legacy = g.chance(3)
        c = Case(f"type-{name}", g.seed(), legacy=legacy, cached=g.chance(4))
        fn = c.function(f)
        c.points(fn, near(g, 60), 60)
        c.points(fn, far(g, 40), 40)
        c.points(fn, edges(g, 20), 20)
        c.points(fn, anywhere(g, 10), 10)
        c.volume(fn, cells(g))
        c.volume(fn, [8, 8, 8, g.between(-1000, 1000), g.between(-100, 300), g.between(-1000, 1000), 1, 1, 1])
        c.volume(fn, column(g))
        c.volume(fn, random_volume(g, 800))
        cases.append(c.build())

    # Interpolation over every kind of volume: aligned at the cell's step, unaligned, at block
    # steps, at other steps, and one block thick.
    for i in range(24):
        xz, y = g.pick([(4, 8), (1, 1), (2, 4), (3, 5), (8, 2), (16, 16)])
        f = {"type": "interpolated", "input": tree(g, ids, 2), "cell_size_xz": xz, "cell_size_y": y}
        c = Case(f"interpolated-volumes-{i}", g.seed(), cached=g.chance(2))
        fn = c.function(f)
        bx, by, bz = g.between(-300, 300), g.between(-64, 256), g.between(-300, 300)
        ax, ay, az = bx - bx % xz, by - by % y, bz - bz % xz
        c.volume(fn, [5, 9, 5, ax, ay, az, xz, y, xz])
        c.volume(fn, [5, 9, 5, bx, by, bz, xz, y, xz])
        c.volume(fn, [1, 9, 1, bx, by, bz, xz, y, xz])
        c.volume(fn, [9, 1, 9, ax, by, az, xz, 1, xz])
        c.volume(fn, [10, 12, 7, bx, by, bz, 1, 1, 1])
        c.volume(fn, [6, 6, 6, bx, by, bz, g.between(1, 5), g.between(1, 5), g.between(1, 5)])
        c.volume(fn, [3, 4, 5, ax, ay, az, 1, 1, 1])
        c.points(fn, listed(inside(g, [5, 9, 5, ax, ay, az, xz, y, xz], 30)), 30)
        c.points(fn, near(g, 30), 30)
        cases.append(c.build())

    # Random trees, alone and several to a case sharing caches.
    for i in range(160):
        c = Case(f"tree-{i}", g.seed(), legacy=g.chance(3), cached=g.chance(2))
        fn = c.function(tree(g, ids, g.between(2, 4)))
        c.points(fn, near(g, 50), 50)
        c.points(fn, far(g, 30), 30)
        c.points(fn, edges(g, 10), 10)
        c.volume(fn, cells(g))
        c.volume(fn, random_volume(g, 600))
        cases.append(c.build())
    for i in range(24):
        c = Case(f"trees-shared-{i}", g.seed(), legacy=g.chance(3), cached=True)
        common = {"type": "cache", "input": tree(g, ids, 2)}
        fns = []
        for _ in range(g.between(2, 4)):
            f = tree(g, ids, 2)
            fns.append(c.function({"type": g.pick(BINARY), "left": common, "right": f}))
        cached_ops(g, c, fns)
        cases.append(c.build())

    for name, f in rejected(g, ids):
        c = Case(f"rejected-{name}", g.seed())
        fn = c.function(f)
        c.points(fn, near(g, 10), 10)
        c.volume(fn, cells(g))
        cases.append(c.build())
    # A rejection after other functions have compiled: the earlier ones' answers are never written.
    c = Case("rejected-after-others", g.seed())
    c.function("minecraft:overworld/continents")
    fn = c.function({"type": "noise", "noise": {"base_octave": -3}, "xz_scale": 1, "y_scale": 1})
    c.points(fn, near(g, 5), 5)
    cases.append(c.build())

    write_file(HERE / "generated.json", "density", f"cases/density/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
