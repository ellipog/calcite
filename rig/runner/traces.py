"""Lines up the entity traces of a rig session (CAL-159): what the rig's agent wrote of vanilla's
living entities to entities.txt, with `trace`, and what Calcite wrote with `--entity-trace`, a line
each time an entity's tick is done:

    TIME ID x y z dx dy dz yRot xRot yHeadRot yBodyRot zza xxa speed onGround

    py -I rig/runner/traces.py FOLDER [ID] [--after N] [--by-place]

FOLDER is a configuration's session folder, such as build/rig/sessions/zombie, holding vanilla/
and calcite/. For each entity, or only ID, it finds the first tick where the two differ in any
value, read as numbers, so Java's 1.0E-4 and Calcite's 0.0001 are the same, and prints the tick
before it, it, and the N after (default 4) on both sides, each value that differs marked. Its
vanilla trace holds the players too, which Calcite's doesn't, so an ID only one side has is said
once and passed over. With --by-place, each of vanilla's entities is lined up with Calcite's that
was first traced at the same game time and place, whatever its ID, for a session whose servers
loaded its entities' chunks in another order and so gave them other IDs (CAL-188); ID is
vanilla's.
"""

import argparse
import sys
from pathlib import Path

FIELDS = ("x", "y", "z", "dx", "dy", "dz", "yRot", "xRot", "yHeadRot", "yBodyRot", "zza", "xxa", "speed", "onGround")


def read(path):
    """Each entity's ticks in order: {id: [(time, values)]}, its values numbers but onGround."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 + len(FIELDS):
            continue
        values = [float(v) for v in parts[2:-1]] + [parts[-1] == "true"]
        out.setdefault(int(parts[1]), []).append((int(parts[0]), values))
    return out


def show(side, tick, other):
    time, values = tick
    marked = []
    for k, v in enumerate(values):
        text = repr(v)
        if other is not None and other[1][k] != v:
            text = f"*{text}*"
        marked.append(f"{FIELDS[k]}={text}")
    print(f"  {side:8} t{time} " + " ".join(marked))


def compare(id, a, b, after):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            print(f"entity {id}: parts at its tick {i}, game time {a[i][0]} vs {b[i][0]}")
            for j in range(max(0, i - 1), min(len(a), len(b), i + after + 1)):
                show("vanilla", a[j], b[j])
                show("calcite", b[j], a[j])
            return
    print(f"entity {id}: the same for {min(len(a), len(b))} ticks ({len(a)} vs {len(b)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("id", type=int, nargs="?")
    ap.add_argument("--after", type=int, default=4)
    ap.add_argument("--by-place", action="store_true", help="pair entities by where they were first traced")
    args = ap.parse_args()
    va = read(args.folder / "vanilla" / "entities.txt")
    ca = read(args.folder / "calcite" / "entities.txt")
    if args.by_place:
        firsts = {(ticks[0][0], tuple(ticks[0][1][:3])): id for id, ticks in ca.items()}
        paired = {}
        for id, ticks in va.items():
            other = firsts.get((ticks[0][0], tuple(ticks[0][1][:3])))
            if other is not None:
                paired[id] = ca[other]
                if other != id:
                    print(f"entity {id}: Calcite's {other}")
        ca = paired
    ids = [args.id] if args.id is not None else sorted(set(va) | set(ca))
    for id in ids:
        if id not in va or id not in ca:
            print(f"entity {id}: only {'vanilla' if id in va else 'Calcite'} traced it")
            continue
        compare(id, va[id], ca[id], args.after)


if __name__ == "__main__":
    sys.exit(main())
