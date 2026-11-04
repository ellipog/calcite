"""Writes generated/<version>/entity_facts.json: what natural spawning asks of each entity type
and block state, from vanilla's own types and states, which the data generator's reports don't
hold (D317).

    py -I oracle/datagen/entity_facts.py

It runs EntityFacts from the vanilla adapter, which oracle/vanilla-adapter/build.py builds, so the
adapter has to be built first. The file is beside tables/, not in it, since convert.py replaces
tables/ whole. calx_tables.py reads it for src/world/entity_facts.calx.
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
        print(f"entity_facts: the vanilla adapter isn't built; run py -I oracle/vanilla-adapter/build.py", file=sys.stderr)
        return 2
    adapter = json.loads(ADAPTER.read_text(encoding="utf-8"))
    out = CALCITE / "generated" / args.version / "entity_facts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    argv = adapter["argv"][:-1] + ["calcite.rig.vanilla.EntityFacts", str(out)]
    r = subprocess.run(argv, cwd=adapter["cwd"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr[-4000:], end="", file=sys.stderr)
        return 1
    facts = json.loads(out.read_text(encoding="utf-8"))
    if facts["game_version"] != args.version:
        print(f"entity_facts: the adapter is {facts['game_version']}, not {args.version}", file=sys.stderr)
        return 1
    print(f"wrote {out.relative_to(CALCITE).as_posix()}: {len(facts['types'])} entity types, {len(facts['states'])} states")
    return 0


if __name__ == "__main__":
    sys.exit(main())
