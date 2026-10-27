"""Writes the math, strictmath and mth case files.

    py -I cases/math/gen.py

`math` and `strictmath` get the same inputs, so their goldens can be compared (P1.5, D58).
The files hold generator specs, not values: the runner expands them (rig/README.md).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent
sys.path.insert(0, str(CASES.parent / "rig" / "runner"))
from cases import write_file  # noqa: E402

SEED = 20261027
COUNT = 2000

SPECIAL = [
    "0", "-0", "1", "-1", "0.5", "-0.5", "2", "-2", "10", "100", "1e-8", "1e-300", "1e22", "1e300", "-1e300",
    "inf", "-inf", "nan", "0x1p-1074", "-0x1p-1074", "0x1p-1022", "0x0.fffffffffffffp-1022",
    "0x1.fffffffffffffp1023", "-0x1.fffffffffffffp1023", "0x1p-30", "0x1p30", "0x1p52", "0x1p53",
    "3.141592653589793", "-3.141592653589793", "1.5707963267948966", "0.7853981633974483",
    "6.283185307179586", "2.718281828459045", "709.782712893384", "710", "-745.1332191019412", "-746",
    "0.9999999999999999", "1.0000000000000002", "-0.9999999999999999",
]
PAIR_SPECIAL = ["0", "-0", "1", "-1", "0.5", "2", "-2", "3", "inf", "-inf", "nan", "0x1p-1074", "1e300"]

# For each function, the ranges its random arguments come from.
UNARY = {
    "sin": [("-10", "10"), ("-1e6", "1e6"), ("-1e300", "1e300")],
    "cos": [("-10", "10"), ("-1e6", "1e6"), ("-1e300", "1e300")],
    "tan": [("-10", "10"), ("-1e6", "1e6")],
    "asin": [("-1", "1")],
    "acos": [("-1", "1")],
    "atan": [("-100", "100"), ("-1e300", "1e300")],
    "exp": [("-745", "710"), ("-1", "1")],
    "expm1": [("-40", "710"), ("-1e-5", "1e-5")],
    "log": [("0", "2"), ("0", "1e300")],
    "log10": [("0", "2"), ("0", "1e300")],
    "log1p": [("-1", "1"), ("-1", "1e300")],
    "sqrt": [("0", "1e300")],
    "cbrt": [("-1e300", "1e300")],
    "sinh": [("-720", "720"), ("-1", "1")],
    "cosh": [("-720", "720")],
    "tanh": [("-25", "25")],
}
BINARY = {
    "atan2": [[("-10", "10"), ("-10", "10")], [("-1e300", "1e300"), ("-1e300", "1e300")]],
    "pow": [[("0", "100"), ("-20", "20")], [("0", "2"), ("-1000", "1000")], [("-10", "0"), ("-5", "5")]],
    "hypot": [[("-1e3", "1e3"), ("-1e3", "1e3")], [("-1e300", "1e300"), ("-1e300", "1e300")]],
}


def math_cases():
    cases = []
    seed = SEED
    for fn, ranges in UNARY.items():
        cases.append({"id": f"{fn}-special", "input": {"fn": fn}, "blobs": [{"f64": SPECIAL}]})
        for i, (lo, hi) in enumerate(ranges):
            seed += 1
            cases.append({"id": f"{fn}-range-{i}", "input": {"fn": fn},
                          "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "min": lo, "max": hi}]})
        seed += 1
        cases.append({"id": f"{fn}-bits", "input": {"fn": fn},
                      "blobs": [{"gen": "f64_bits", "seed": str(seed), "count": COUNT}]})
    for fn, range_sets in BINARY.items():
        pairs = [v for a in PAIR_SPECIAL for b in PAIR_SPECIAL for v in (a, b)]
        cases.append({"id": f"{fn}-special", "input": {"fn": fn}, "blobs": [{"f64": pairs}]})
        for i, ranges in enumerate(range_sets):
            seed += 1
            cases.append({"id": f"{fn}-range-{i}", "input": {"fn": fn},
                          "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "ranges": [list(r) for r in ranges]}]})
        seed += 1
        cases.append({"id": f"{fn}-bits", "input": {"fn": fn},
                      "blobs": [{"gen": "f64_bits", "seed": str(seed), "count": 2 * COUNT}]})
    return cases


def mth_cases():
    seed = SEED + 1000
    angles = SPECIAL + ["-1e-300", "102943.70603", "-102943.70603", "1e15", "-1e15"]
    cases = [{"id": "sin-table", "input": {"fn": "sin_table"}}]
    for fn in ("sin", "cos"):
        cases.append({"id": f"{fn}-special", "input": {"fn": fn}, "blobs": [{"f64": angles}]})
        seed += 1
        cases.append({"id": f"{fn}-range", "input": {"fn": fn},
                      "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "min": "-1000", "max": "1000"}]})
    pairs = [v for a in PAIR_SPECIAL for b in PAIR_SPECIAL for v in (a, b)]
    cases.append({"id": "atan2-special", "input": {"fn": "atan2"}, "blobs": [{"f64": pairs}]})
    seed += 1
    cases.append({"id": "atan2-range", "input": {"fn": "atan2"},
                  "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "ranges": [["-10", "10"], ["-10", "10"]]}]})
    cases.append({"id": "fast-inv-sqrt-special", "input": {"fn": "fast_inv_sqrt"}, "blobs": [{"f64": SPECIAL}]})
    seed += 1
    cases.append({"id": "fast-inv-sqrt-range", "input": {"fn": "fast_inv_sqrt"},
                  "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "min": "0", "max": "1000"}]})
    wrap = ["0", "-0", "180", "-180", "179.99998", "180.00002", "360", "-360", "540", "1e10", "-1e10",
            "inf", "-inf", "nan", "0x1p-149", "3.4028235e38", "-3.4028235e38", "359.99997", "-179.99998"]
    cases.append({"id": "wrap-degrees-special", "input": {"fn": "wrap_degrees"}, "blobs": [{"f32": wrap}]})
    seed += 1
    cases.append({"id": "wrap-degrees-range", "input": {"fn": "wrap_degrees"},
                  "blobs": [{"gen": "f32_range", "seed": str(seed), "count": COUNT, "min": "-100000", "max": "100000"}]})
    seed += 1
    cases.append({"id": "wrap-degrees-bits", "input": {"fn": "wrap_degrees"},
                  "blobs": [{"gen": "f32_bits", "seed": str(seed), "count": COUNT}]})
    floors = SPECIAL + ["2147483647", "2147483648", "-2147483648", "-2147483649", "-0.5", "-1e-300", "1.9999999999999998"]
    cases.append({"id": "floor-special", "input": {"fn": "floor"}, "blobs": [{"f64": floors}]})
    seed += 1
    cases.append({"id": "floor-range", "input": {"fn": "floor"},
                  "blobs": [{"gen": "f64_range", "seed": str(seed), "count": COUNT, "min": "-3e7", "max": "3e7"}]})
    seed_points = ["0", "0", "0", "1", "2", "3", "-1", "-1", "-1", "30000000", "319", "-30000000",
                   "-2147483648", "2147483647", "-2147483648"]
    cases.append({"id": "get-seed-special", "input": {"fn": "get_seed"}, "blobs": [{"i32": seed_points}]})
    seed += 1
    cases.append({"id": "get-seed-range", "input": {"fn": "get_seed"},
                  "blobs": [{"gen": "i32_range", "seed": str(seed), "count": 3 * COUNT, "min": "-30000000", "max": "30000000"}]})
    return cases


def main():
    cases = math_cases()
    write_file(CASES / "math" / "generated.json", "math", f"cases/math/gen.py, seed {SEED}", cases)
    write_file(CASES / "strictmath" / "generated.json", "strictmath", f"cases/math/gen.py, seed {SEED}", cases)
    write_file(CASES / "mth" / "generated.json", "mth", f"cases/math/gen.py, seed {SEED}", mth_cases())


if __name__ == "__main__":
    main()
