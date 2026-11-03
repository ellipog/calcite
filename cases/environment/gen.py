"""Writes cases/environment/generated.json: the environment attributes' dimension values, as a
level's `EnvironmentAttributeSystem` gives them, at many clocks and weathers.

    py -I cases/environment/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

The `vanilla` cases are vanilla's dimension types, with the weather's layers where a level of
that type can have weather and, for the Overworld and the Nether, also where it can't. Their
records go through the day's keyframes tick by tick, the moon's phases, the end of the early
game, negative and huge clocks, and the rain and thunder as the weather moves them and at random.
The `pack` cases are made as a data pack would make them: a map of attributes with every
modifier, and timelines with every modifier and easing, cubic Béziers among them, periods or none,
and keyframes that repeat a tick, all read at random clocks and weathers.

Each record is the ticks every clock has run, an i64, then the rain and thunder levels, f32s.
"""

import base64
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261103
I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1

# Every float and boolean attribute, with its range and whether it's a float.
FLOATS = {
    "minecraft:visual/fog_start_distance": None,
    "minecraft:visual/fog_end_distance": (0.0, float("inf")),
    "minecraft:visual/sky_fog_end_distance": (0.0, float("inf")),
    "minecraft:visual/cloud_fog_end_distance": (0.0, float("inf")),
    "minecraft:visual/water_fog_start_distance": None,
    "minecraft:visual/water_fog_end_distance": (0.0, float("inf")),
    "minecraft:visual/cloud_height": None,
    "minecraft:visual/star_brightness": (0.0, 1.0),
    "minecraft:visual/sky_light_factor": (0.0, 1.0),
    "minecraft:audio/music_volume": (0.0, 1.0),
    "minecraft:gameplay/sky_light_level": (0.0, 15.0),
    "minecraft:gameplay/turtle_egg_hatch_chance": (0.0, 1.0),
    "minecraft:gameplay/surface_slime_spawn_chance": (0.0, 1.0),
    "minecraft:gameplay/cat_waking_up_gift_chance": (0.0, 1.0),
    "minecraft:gameplay/creature_world_gen_spawn_probability": (0.0, 0.9999999),
}
BOOLEANS = [
    "minecraft:audio/firefly_bush_sounds",
    "minecraft:gameplay/can_start_raid",
    "minecraft:gameplay/water_evaporates",
    "minecraft:gameplay/respawn_anchor_works",
    "minecraft:gameplay/nether_portal_spawns_piglin",
    "minecraft:gameplay/fast_lava",
    "minecraft:gameplay/increased_fire_burnout",
    "minecraft:gameplay/piglins_zombify",
    "minecraft:gameplay/snow_golem_melts",
    "minecraft:gameplay/creaking_active",
    "minecraft:gameplay/bees_stay_in_hive",
    "minecraft:gameplay/monsters_burn",
    "minecraft:gameplay/can_pillager_patrol_spawn",
]
READ = list(FLOATS) + BOOLEANS

FLOAT_OPS = ["override", "alpha_blend", "add", "subtract", "multiply", "minimum", "maximum"]
BOOL_OPS = ["override", "and", "nand", "or", "nor", "xor", "xnor"]
EASINGS = [
    "constant", "linear", "in_back", "in_bounce", "in_circ", "in_cubic", "in_elastic", "in_expo", "in_quad",
    "in_quart", "in_quint", "in_sine", "in_out_back", "in_out_bounce", "in_out_circ", "in_out_cubic",
    "in_out_elastic", "in_out_expo", "in_out_quad", "in_out_quart", "in_out_quint", "in_out_sine", "out_back",
    "out_bounce", "out_circ", "out_cubic", "out_elastic", "out_expo", "out_quad", "out_quart", "out_quint",
    "out_sine",
]
CLOCKS = ["minecraft:overworld", "minecraft:the_end"]


class Rng:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def next(self):
        return next(self.r)

    def below(self, n):
        return self.next() % n

    def unit(self):
        return (self.next() >> 11) * 2.0**-53

    def chance(self, p):
        return self.unit() < p

    def pick(self, items):
        return items[self.below(len(items))]


def f32(x):
    """The float nearest `x`, as a Python float, which JSON writes so it reads back exactly."""
    return struct.unpack(">f", struct.pack(">f", x))[0]


def record(ticks, rain, thunder):
    return struct.pack(">qff", ticks, rain, thunder)


def blob(records):
    return base64.b64encode(b"".join(records)).decode("ascii")


def weathers(rng, n):
    """Rain and thunder as the weather moves them, by 0.01 a tick and clamped, as it is, and at
    random, thunder under rain or over it."""
    out = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    level = 0.0
    while level < 1.0:
        level = f32(level + f32(0.01))
        out.append((min(level, 1.0), 0.0))
    rain = 1.0
    thunder = 0.0
    while thunder < 1.0:
        thunder = f32(thunder + f32(0.01))
        # `getThunderLevel` is the thunder's level times the rain's.
        out.append((rain, f32(min(thunder, 1.0) * rain)))
    while len(out) < n:
        r = f32(rng.unit()) if rng.chance(0.8) else rng.pick([0.0, 1.0, f32(1e-7), f32(0.999999)])
        t = f32(rng.unit()) if rng.chance(0.5) else f32(r * f32(rng.unit()))
        out.append((r, t))
    return out


def vanilla_ticks(rng):
    """The day's keyframes tick by tick, the moon's phases, the early game's end, and clocks that
    are negative, past the period many times, or near a long's ends."""
    ticks = list(range(0, 400))
    for k in (11867, 13670, 22330, 23999):
        ticks += range(k - 60, k + 60)
    for phase in range(9):
        ticks += [phase * 24000 - 1, phase * 24000, phase * 24000 + 1]
    ticks += range(119990, 120011)
    ticks += [-1, -133, -1670, -24000, -24001, -192000, 2147483647, 2147483648, -2147483648, -2147483649]
    ticks += [I64_MAX, I64_MIN, I64_MAX - 23999, I64_MIN + 1, 1 << 40, -(1 << 40)]
    for _ in range(400):
        ticks.append(rng.below(400000) - 20000)
    for _ in range(40):
        ticks.append((rng.next() & ((1 << 64) - 1)) - (1 << 63))
    return ticks


def vanilla_case(rng, n, type_id, weather):
    ticks = vanilla_ticks(rng)
    ws = weathers(rng, len(ticks))
    records = []
    for i, t in enumerate(ticks):
        # The clear sky for most, every weather over the day's dusk.
        r, th = ws[i] if weather and (i % 3 == 0 or 11800 <= t % 24000 <= 13800) else (0.0, 0.0)
        records.append(record(t, r, th))
    for (r, th) in ws:
        records.append(record(rng.pick([6000, 12000, 13000, 18000, 23000, 100]), r, th))
    return {"id": f"vanilla-{n}", "input": {"type": type_id, "weather": weather, "read": READ}, "blobs": [blob(records)]}


def float_value(rng, attr, op):
    """A value of the float attribute `attr`, within its range where an override needs it."""
    bounds = FLOATS[attr]
    if op == "override" and bounds is not None:
        lo, hi = bounds
        if hi == float("inf"):
            hi = 4096.0
        return f32(rng.pick([lo, hi, lo + (hi - lo) * rng.unit(), lo + (hi - lo) * rng.unit()]))
    return f32(rng.pick([0.0, 1.0, -1.0, 0.5, 2.0, 15.0, rng.unit() * 32 - 16, rng.unit() * 2, -rng.unit() * 600]))


def argument(rng, attr, op):
    if attr in BOOLEANS:
        return rng.chance(0.5)
    if op == "alpha_blend":
        value = float_value(rng, attr, op)
        if rng.chance(0.3):
            return value
        return {"value": value, "alpha": f32(rng.pick([0.0, 1.0, 0.5, rng.unit(), rng.unit()]))}
    return float_value(rng, attr, op)


def ops_of(attr):
    return BOOL_OPS if attr in BOOLEANS else FLOAT_OPS


def easing(rng):
    if rng.chance(0.15):
        x1, x2 = f32(rng.unit()), f32(rng.unit())
        y1, y2 = f32(rng.unit() * 3 - 1), f32(rng.unit() * 3 - 1)
        return {"cubic_bezier": [x1, y1, x2, y2]}
    return rng.pick(EASINGS)


def track(rng, attr, period):
    op = rng.pick(ops_of(attr))
    span = period if period is not None else rng.pick([10, 100, 24000, 200000])
    count = rng.pick([1, 2, 2, 3, 4, 6])
    ticks = sorted(rng.below(span + 1) for _ in range(count))
    # A tick may come twice, never three times in a row.
    for i in range(2, len(ticks)):
        if ticks[i] == ticks[i - 1] == ticks[i - 2]:
            ticks[i] = min(span, ticks[i] + 1)
    ticks.sort()
    for i in range(2, len(ticks)):
        if ticks[i] == ticks[i - 1] == ticks[i - 2]:
            ticks = ticks[:i]
            break
    out = {"keyframes": [{"ticks": t, "value": argument(rng, attr, op)} for t in ticks], "ease": easing(rng)}
    if op != "override" or rng.chance(0.5):
        out["modifier"] = op
    return out


def pack_case(rng, n):
    attrs = rng.pick([READ, list(FLOATS), BOOLEANS])
    mapping = {}
    for attr in attrs:
        if rng.chance(0.4):
            op = rng.pick(ops_of(attr))
            arg = argument(rng, attr, op)
            mapping[attr] = arg if op == "override" and rng.chance(0.5) else {"modifier": op, "argument": arg}
    timelines = []
    periods = []
    for _ in range(rng.pick([0, 1, 1, 2, 3])):
        period = rng.pick([None, 24000, 100, 7, 192000, 1])
        tracks = {}
        for attr in attrs:
            if rng.chance(0.35):
                tracks[attr] = track(rng, attr, period)
        t = {"clock": rng.pick(CLOCKS), "tracks": tracks}
        if period is not None:
            t["period_ticks"] = period
        timelines.append(t)
        periods.append(period or 200000)
    records = []
    longest = max(periods + [1000])
    for (r, th) in weathers(rng, 300)[::3]:
        records.append(record(rng.below(longest * 3) - longest, r, th))
    for _ in range(300):
        t = rng.below(longest + 2) if rng.chance(0.8) else (rng.next() & ((1 << 64) - 1)) - (1 << 63)
        records.append(record(t, 0.0, 0.0) if rng.chance(0.5) else record(t, f32(rng.unit()), f32(rng.unit())))
    inp = {"weather": rng.chance(0.6), "read": READ}
    if mapping or rng.chance(0.5):
        inp["attributes_map"] = mapping
    if timelines or rng.chance(0.5):
        inp["timelines"] = timelines
    return {"id": f"pack-{n}", "input": inp, "blobs": [blob(records)]}


def main():
    rng = Rng(SEED)
    cases = []
    vanilla = [
        ("minecraft:overworld", True), ("minecraft:overworld", False), ("minecraft:overworld_caves", False),
        ("minecraft:the_nether", False), ("minecraft:the_nether", True), ("minecraft:the_end", False),
    ]
    for n, (type_id, weather) in enumerate(vanilla):
        cases.append(vanilla_case(rng, n, type_id, weather))
    for n in range(40):
        cases.append(pack_case(rng, n))
    write_file(HERE / "generated.json", "environment", f"cases/environment/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
