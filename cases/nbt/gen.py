"""Writes cases/nbt/limits.json: nesting and size near vanilla's limits, too long to write by hand.

    py -I cases/nbt/gen.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402


def nested_compounds(depth):
    """`depth` compounds inside each other, in network form."""
    return "0a" + "0a000161" * (depth - 1) + "00" * depth


def nested_lists(depth):
    """`depth` lists inside each other, each holding one list, the innermost empty."""
    return "09" + "0900000001" * (depth - 1) + "0000000000"


def main():
    cases = []
    for depth in (128, 256, 511, 512, 513, 514):
        cases.append({"id": f"snbt-compound-depth-{depth}", "input": {"from": "snbt", "snbt": "{a:" * (depth - 1) + "{}" + "}" * (depth - 1)}})
        cases.append({"id": f"snbt-list-depth-{depth}", "input": {"from": "snbt", "snbt": "{a:" + "[" * (depth - 1) + "]" * (depth - 1) + "}"}})
        cases.append({"id": f"bin-compound-depth-{depth}", "input": {"from": "binary"}, "blobs": [{"hex": [nested_compounds(depth)]}]})
        cases.append({"id": f"bin-list-depth-{depth}", "input": {"from": "binary"}, "blobs": [{"hex": [nested_lists(depth)]}]})
    # A 65,535-byte string is the longest writeUTF can write.
    for n in (65535, 65536):
        cases.append({"id": f"snbt-string-{n}", "input": {"from": "snbt", "snbt": "{a:\"" + "x" * n + "\"}"}})
    write_file(HERE / "limits.json", "nbt", "cases/nbt/gen.py", cases)


if __name__ == "__main__":
    main()
