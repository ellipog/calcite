"""Times the light engines, Calcite's against vanilla's, through the `light` probe.

    py -I rig/runner/light_timing.py [runs]

Each workload is a case run twice: once whole, and once with only its chunks and blocks, so the
difference is the light. Each adapter runs both a few times to warm up, then `runs` times each,
alternating, and the median of each is taken.
"""

import dataclasses
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rig" / "runner"))
sys.path.insert(0, str(ROOT / "cases" / "light"))
import rig  # noqa: E402
import gen  # noqa: E402

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 15
BLOCKS = {"chunk", "fill", "random"}


def workload(name, radius, count, edits, seed):
    g = gen.Gen(seed)
    chunks = gen.square(radius)
    ops = gen.made(chunks, gen.OVERWORLD)
    for cx, cz in chunks:
        ops += gen.flat_fill(cx, cz, -64)
    lo, hi = -radius * 16, radius * 16 + 15
    ops.append(["fill", lo, -60, lo, hi, -20, hi, gen.STONE])
    ops.append(["random", 0, g.seed(), count, gen.POOL, lo, -60, lo, hi, 40, hi])
    ops += gen.generate(chunks)
    if edits:
        ops.append(["random", 1, g.seed(), edits, gen.POOL, lo, -60, lo, hi, 40, hi])
        ops.append(["run"])
    ops.append(["light", 0, 0])
    # Without light: the same chunks and blocks, every `random` quiet so it sets the same blocks.
    plain = [op if op[0] != "random" else ["random", 0] + op[2:] for op in ops if op[0] in BLOCKS]
    return name, gen.case(name, gen.OVERWORLD, 1, ops)["input"], gen.case(name, gen.OVERWORLD, 1, plain)["input"]


WORKLOADS = [
    workload("flat 9x9", 4, 0, 0, 1),
    workload("terrain 7x7", 3, 40000, 0, 2),
    workload("terrain 7x7, 5000 edits", 3, 40000, 5000, 3),
]

case0 = rig.load_cases(["light"])["light"][0]


def timed(session, inp):
    c = dataclasses.replace(case0, input=inp)
    t = time.perf_counter()
    r = session.run(c)
    dt = time.perf_counter() - t
    if r.status != "ok":
        raise SystemExit(f"{r.status}: {r.message}")
    return dt, r.blobs[0] if r.blobs else b""


results = {}
for adapter in ("vanilla", "calcite"):
    s = rig.Session(adapter, config="strict-math") if adapter == "vanilla" else rig.Session(adapter)
    for name, whole, plain in WORKLOADS:
        for _ in range(5):
            timed(s, whole)
            timed(s, plain)
        a, b = [], []
        for _ in range(RUNS):
            a.append(timed(s, whole)[0])
            b.append(timed(s, plain)[0])
        results[(adapter, name)] = (statistics.median(a), statistics.median(b), timed(s, whole)[1])
    s.close()

print(f"{'workload':28} {'vanilla light':>14} {'calcite light':>14} {'ratio':>7}   (whole / blocks only, ms)")
for name, _, _ in WORKLOADS:
    va, vb, vblob = results[("vanilla", name)]
    ca, cb, cblob = results[("calcite", name)]
    same = "same" if vblob == cblob else "DIFFERENT"
    vl, cl = (va - vb) * 1000, (ca - cb) * 1000
    print(f"{name:28} {vl:14.2f} {cl:14.2f} {vl / cl if cl > 0 else 0:6.2f}x   "
          f"({va * 1000:.1f}/{vb * 1000:.1f}, {ca * 1000:.1f}/{cb * 1000:.1f}; results {same})")
