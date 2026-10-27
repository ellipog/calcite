"""Compares java.lang.Math with StrictMath on the inputs vanilla uses (P1.5, D58).

    py -I rig/runner/mathcmp.py [--count 500000] [--fn sin ...]

Calx's std.math ports fdlibm, so it matches StrictMath. Vanilla calls Math, which HotSpot
replaces with CPU-specific intrinsics. Wherever the two differ, Calcite would differ from
vanilla. This runs both through the vanilla adapter on large sweeps and reports every
function's mismatch rate, worst ULP distance and examples, plus an exhaustive check of
Mth's sine table. Nothing is recorded: the report goes to stdout and build/rig/<platform>/.
"""

import argparse
import json
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import Case, splitmix64  # noqa: E402
from rig import OUT, PLATFORM, Session  # noqa: E402

SIN_SCALE = 10430.378350470453
CHUNK = 250_000  # values per request, to keep frames a few MB

# (function, arity, called by vanilla, [domains]). A domain is a list of (min, max) ranges, one
# per argument, or "bits" for random bit patterns. Ranges follow how vanilla calls each function.
FUNCTIONS = [
    ("sin", 1, True, [[(-2 * math.pi, 2 * math.pi)], [(-1e4, 1e4)], "bits"]),
    ("cos", 1, True, [[(-2 * math.pi, 2 * math.pi)], [(-1e4, 1e4)], "bits"]),
    ("pow", 2, True, [[(0.0, 2.0), (0.0, 4.0)], [(0.0, 1e3), (-8.0, 8.0)], "int-exponents", "bits"]),
    ("log", 1, True, [[(0.0, 1.0)], [(1.0, 1e6)], "bits"]),
    ("atan2", 2, True, [[(-10.0, 10.0), (-10.0, 10.0)], [(-1e4, 1e4), (-1e4, 1e4)], "bits"]),
    ("acos", 1, True, [[(-1.0, 1.0)], "bits"]),
    ("asin", 1, True, [[(-1.0, 1.0)], "bits"]),
    ("log1p", 1, True, [[(0.0, 10.0)], "bits"]),
    ("hypot", 2, True, [[(-1e3, 1e3), (-1e3, 1e3)], "bits"]),
    ("sqrt", 1, True, [[(0.0, 1e6)], "bits"]),
    ("tan", 1, False, [[(-2 * math.pi, 2 * math.pi)], "bits"]),
    ("exp", 1, False, [[(-745.0, 710.0)], "bits"]),
    ("log10", 1, False, [[(0.0, 1e6)], "bits"]),
    ("atan", 1, False, [[(-100.0, 100.0)], "bits"]),
    ("cbrt", 1, False, [[(-1e6, 1e6)], "bits"]),
    ("sinh", 1, False, [[(-20.0, 20.0)], "bits"]),
    ("cosh", 1, False, [[(-20.0, 20.0)], "bits"]),
    ("tanh", 1, False, [[(-20.0, 20.0)], "bits"]),
    ("expm1", 1, False, [[(-40.0, 40.0)], "bits"]),
]


def domain_name(domain):
    if isinstance(domain, str):
        return domain
    return " x ".join(f"[{lo:g}, {hi:g})" for lo, hi in domain)


def make_args(domain, arity, count, seed):
    rand = splitmix64(seed)
    out = bytearray()
    for _ in range(count):
        if domain == "bits":
            for _ in range(arity):
                out += struct.pack(">Q", next(rand))
        elif domain == "int-exponents":
            # pow(x, n) with a small integer n, as in pow(d, 2) and pow(2, octave).
            u = (next(rand) >> 11) * 2.0**-53
            out += struct.pack(">dd", -100.0 + 200.0 * u, float(next(rand) % 41 - 20))
        else:
            for lo, hi in domain:
                u = (next(rand) >> 11) * 2.0**-53
                out += struct.pack(">d", lo + (hi - lo) * u)
    return bytes(out)


def ordered(bits):
    """Maps f64 bits to integers that order like the floats, so ULP distance is a subtraction."""
    return -(bits & 0x7FFFFFFFFFFFFFFF) if bits >> 63 else bits


def is_nan(bits):
    return (bits & 0x7FF0000000000000) == 0x7FF0000000000000 and bits & 0x000FFFFFFFFFFFFF


def run_probe(session, probe, fn, args):
    case = Case(probe, 1, f"mathcmp-{fn}", {"fn": fn}, (args,), Path("mathcmp"))
    result = session.run(case)
    if result.status != "ok":
        sys.exit(f"mathcmp: {probe} {fn}: {result.status}: {result.message}")
    return result.blobs[0]


def compare(session, fn, arity, domain, count, seed):
    stats = {"count": 0, "mismatches": 0, "nan_payload_only": 0, "max_ulps": 0, "examples": []}
    done = 0
    while done < count:
        n = min(CHUNK, count - done)
        args = make_args(domain, arity, n, seed + done)
        got_math = run_probe(session, "math", fn, args)
        got_strict = run_probe(session, "strictmath", fn, args)
        a = struct.unpack(f">{n}Q", got_math)
        b = struct.unpack(f">{n}Q", got_strict)
        xs = struct.unpack(f">{n * arity}d", args)
        for i in range(n):
            if a[i] == b[i]:
                continue
            if is_nan(a[i]) and is_nan(b[i]):
                stats["nan_payload_only"] += 1
                continue
            stats["mismatches"] += 1
            ulps = abs(ordered(a[i]) - ordered(b[i]))
            stats["max_ulps"] = max(stats["max_ulps"], ulps)
            if len(stats["examples"]) < 5:
                arg = xs[i * arity:(i + 1) * arity]
                stats["examples"].append({
                    "args": [x.hex() for x in arg],
                    "math": struct.unpack(">d", struct.pack(">Q", a[i]))[0].hex(),
                    "strictmath": struct.unpack(">d", struct.pack(">Q", b[i]))[0].hex(),
                    "ulps": ulps,
                })
        done += n
    stats["count"] = done
    return stats


def sin_table(session):
    """Mth's 65,536-entry table against (float) StrictMath.sin and (float) Math.sin of each index."""
    table = struct.unpack(">65536I", session.run(Case("mth", 1, "mathcmp-sin-table", {"fn": "sin_table"}, (), Path("mathcmp"))).blobs[0])
    args = b"".join(struct.pack(">d", i / SIN_SCALE) for i in range(65536))
    out = {}
    for probe in ("strictmath", "math"):
        doubles = struct.unpack(">65536d", run_probe(session, probe, "sin", args))
        floats = [struct.unpack(">I", struct.pack(">f", d))[0] for d in doubles]
        bad = [i for i in range(65536) if floats[i] != table[i]]
        out[probe] = {"mismatches": len(bad), "first": bad[:10]}
    return out


def main():
    parser = argparse.ArgumentParser(description="Compare Math with StrictMath on vanilla's inputs.")
    parser.add_argument("--count", type=int, default=500_000, help="arguments per domain (default 500,000)")
    parser.add_argument("--fn", action="append", help="only these functions")
    parser.add_argument("--config", default="intrinsics",
                        help="vanilla configuration (default intrinsics: HotSpot's defaults, the case in question)")
    parser.add_argument("--jvm-arg", action="append", default=[], help="extra JVM flag, such as -Xint")
    args = parser.parse_args()

    session = Session("vanilla", args.jvm_arg, log_name="vanilla-mathcmp", config=args.config)
    started = time.time()
    report = {"platform": PLATFORM, "about": session.about, "config": args.config, "jvm_args": args.jvm_arg,
              "count_per_domain": args.count, "functions": {}}
    try:
        print(f"Math against StrictMath, {args.count:,} arguments per domain, on {PLATFORM}"
              f" ({session.about.get('java.vm.version')}, {session.about.get('os.arch')}, {args.config})\n")
        print("| Function | Vanilla calls it | Domain | Mismatches | Worst ULPs |")
        print("|---|---|---|---|---|")
        seed = 20261027
        for fn, arity, called, domains in FUNCTIONS:
            if args.fn and fn not in args.fn:
                continue
            rows = []
            for domain in domains:
                seed += 1_000_003
                stats = compare(session, fn, arity, domain, args.count, seed)
                rows.append({"domain": domain_name(domain), **stats})
                rate = f"{stats['mismatches']:,} ({100 * stats['mismatches'] / stats['count']:.3f}%)"
                print(f"| `{fn}` | {'yes' if called else 'no'} | {domain_name(domain)} | {rate} | {stats['max_ulps']} |", flush=True)
            report["functions"][fn] = {"called_by_vanilla": called, "domains": rows}
        table = sin_table(session)
        report["mth_sin_table"] = table
        print(f"\nMth sine table, 65,536 entries: {table['strictmath']['mismatches']} differ from"
              f" (float) StrictMath.sin, {table['math']['mismatches']} from (float) Math.sin")
    finally:
        session.close()

    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "".join(a.strip("-").replace(":", "").replace("=", "") for a in args.jvm_arg)
    path = OUT / f"mathcmp-{args.config}{'-' + suffix if suffix else ''}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n{time.time() - started:.0f}s. Full report, with examples: {path}")


if __name__ == "__main__":
    main()
