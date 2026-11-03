"""Lines up two RNG tapes, vanilla's from the rig's agent and Calcite's, level by level (D312).

    py -I rig/runner/tapediff.py VANILLA_TAPE CALCITE_TAPE [--show N] [--since TIME]

A tape is a line for each value a level's random drew: the level, its game time, the bits drawn,
the value, and on vanilla's, where it was drawn. Each ends with a `# end LEVEL TIME` line for each
level, the game time it had when the server stopped. For each level, the draws are compared in
order over the game times both servers ran, and the first that differs is shown with where vanilla
drew it, with the few after it, since that's where the two servers' ticks part. With --since, the
time both seeded their levels' randoms again (D316), the draws from then on are lined up too, so
what each drew while the player's chunks loaded doesn't hide the rest. It exits with 1 if any
level's draws differ.
"""

import argparse
import sys
from dataclasses import dataclass, field


@dataclass
class Level:
    draws: list = field(default_factory=list)
    end: int | None = None


def read(path):
    levels = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "#":
                if len(parts) == 4 and parts[1] == "end":
                    levels.setdefault(parts[2], Level()).end = int(parts[3])
                continue
            name, time, bits, value = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
            levels.setdefault(name, Level()).draws.append((time, bits, value, " ".join(parts[4:])))
    return levels


def shown(draw):
    if draw is None:
        return "nothing"
    time, bits, value, site = draw
    return f"at {time}, {bits} bits, {value}" + (f", {site}" if site else "")


def line_up(label, vd, cd, until, show):
    """Prints how far two lists of draws are the same, and the first that differs, with `show`
    after it; true if they differ."""
    same = 0
    while same < len(vd) and same < len(cd) and vd[same][:3] == cd[same][:3]:
        same += 1
    if same == len(vd) == len(cd):
        print(f"{label}: the same, {same} draws before game time {until}")
        return False
    print(f"{label}: {same} draws the same, then they differ (before game time {until}; vanilla {len(vd)}, Calcite {len(cd)})")
    for i in range(same, same + show):
        if i >= len(vd) and i >= len(cd):
            break
        print(f"  vanilla {shown(vd[i] if i < len(vd) else None)}")
        print(f"  calcite {shown(cd[i] if i < len(cd) else None)}")
    return True


def compare(vanilla, calcite, show, since=None):
    differ = False
    for name in sorted(set(vanilla) | set(calcite)):
        v, c = vanilla.get(name, Level()), calcite.get(name, Level())
        ends = [e for e in (v.end, c.end) if e is not None]
        if not ends:
            print(f"{name}: no end on either tape, so it's left out")
            continue
        # Draws at the last time either ran may be from a tick the other didn't finish.
        until = min(ends)
        vd = [d for d in v.draws if d[0] < until]
        cd = [d for d in c.draws if d[0] < until]
        if line_up(name, vd, cd, until, show):
            differ = True
        if since is not None and since < until:
            if line_up(f"{name} from game time {since}, seeded again", [d for d in vd if d[0] >= since],
                       [d for d in cd if d[0] >= since], until, show):
                differ = True
    return differ


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("vanilla")
    ap.add_argument("calcite")
    ap.add_argument("--show", type=int, default=3, help="the draws shown from the first that differs")
    ap.add_argument("--since", type=int, help="the game time both seeded their levels' randoms again, from which the draws are lined up too")
    args = ap.parse_args()
    return 1 if compare(read(args.vanilla), read(args.calcite), args.show, args.since) else 0


if __name__ == "__main__":
    sys.exit(main())
