"""Writes cases/block_state/ranges.json: every block state ID and every block, in chunks (P2.5).

    py -I cases/block_state/gen.py

The cases hold only ID ranges, so no game data is committed. The ranges run past 26.3's 35,723
states and 1,286 blocks, so they still cover every ID after an update adds some, and the IDs
past the end, which the game reads as missing.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

STATE_CHUNK, STATE_END = 1024, 40960
BLOCK_CHUNK, BLOCK_END = 256, 1536
INT_MAX = 2**31 - 1


def main():
    cases = []
    for start in range(0, STATE_END, STATE_CHUNK):
        cases.append({"id": f"by-id-{start:05d}", "input": {"op": "by_id", "from": start, "count": STATE_CHUNK}})
    cases.append({"id": "by-id-negative", "input": {"op": "by_id", "from": -4, "count": 4}})
    cases.append({"id": "by-id-int-max", "input": {"op": "by_id", "from": INT_MAX - 3, "count": 4}})
    for start in range(0, BLOCK_END, BLOCK_CHUNK):
        cases.append({"id": f"blocks-{start:04d}", "input": {"op": "blocks", "from": start, "count": BLOCK_CHUNK}})
    cases.append({"id": "blocks-negative", "input": {"op": "blocks", "from": -4, "count": 4}})
    cases.append({"id": "blocks-int-max", "input": {"op": "blocks", "from": INT_MAX - 3, "count": 4}})
    write_file(HERE / "ranges.json", "block_state", "cases/block_state/gen.py", cases)


if __name__ == "__main__":
    main()
