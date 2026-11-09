"""Writes generated/<version>/command_tree.json: the dedicated server's command tree in the order
vanilla registers it, with each node's permission level and its argument's properties as the
commands packet sends them, which the data generator's commands.json doesn't hold (CAL-165).

    py -I oracle/datagen/command_tree.py

It runs CommandTree from the vanilla adapter, which oracle/vanilla-adapter/build.py builds, so the
adapter has to be built first. The file is beside tables/, not in it, since convert.py replaces
tables/ whole. calx_tables.py reads it for src/command/tree.calx.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys

CALCITE = pathlib.Path(__file__).resolve().parents[2]
VERSION = "26.3"
PLATFORM = "windows" if os.name == "nt" else sys.platform
ADAPTER = CALCITE / "oracle" / "vanilla-adapter" / "build" / PLATFORM / "adapter.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default=VERSION, help=f"the game version (default {VERSION})")
    args = parser.parse_args()
    if not ADAPTER.is_file():
        print("command_tree: the vanilla adapter isn't built; run py -I oracle/vanilla-adapter/build.py", file=sys.stderr)
        return 2
    adapter = json.loads(ADAPTER.read_text(encoding="utf-8"))
    out = CALCITE / "generated" / args.version / "command_tree.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    argv = adapter["argv"][:-1] + ["calcite.rig.vanilla.CommandTree", str(out)]
    r = subprocess.run(argv, cwd=adapter["cwd"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr[-4000:], end="", file=sys.stderr)
        return 1
    tree = json.loads(out.read_text(encoding="utf-8"))
    if tree["game_version"] != args.version:
        print(f"command_tree: the adapter is {tree['game_version']}, not {args.version}", file=sys.stderr)
        return 1
    nodes = tree["nodes"]
    roots = len(nodes[0]["children"])
    print(f"wrote {out.relative_to(CALCITE).as_posix()}: {len(nodes)} nodes, {roots} commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
