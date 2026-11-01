"""Writes cases/registries/configuration.json: the server's known packs, the synchronized
registries' entries, the tags of every registry the server sends tags for, and each synchronized
registry's entries with their contents, as a client that knows none of the server's packs is
sent them.

    py -I cases/registries/gen.py

The registries are the ones Calcite names in src/registry/registries.calx (`synced_names`) and
src/registry/builtin.calx (`builtin_names`, written from the data generator's report), so each
has a case, including those with no tags, whose result is an empty list.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "rig" / "runner"))
from cases import write_file  # noqa: E402

# The registries whose contents have maps vanilla fills in an order that changes from run to run,
# `Map.copyOf` over attributes hashed by identity: a timeline's tracks, and a dimension type's and
# a biome's attributes. Their compounds are compared sorted by key (D192).
UNORDERED = {"timeline", "dimension_type", "worldgen/biome"}


def names(path, function):
    """The string list `function` in the Calx module at `path` returns."""
    text = (CALCITE / path).read_text(encoding="utf-8")
    body = re.search(r"pub fn " + function + r"\(\) -> List<String> \{\s*return \[(.*?)\]", text, re.S)
    if not body:
        raise SystemExit(f"no {function} in {path}")
    return re.findall(r'"([^"]+)"', body.group(1))


def main():
    cases = [
        {"id": "known-packs", "input": {"op": "known_packs"}},
        {"id": "synced", "input": {"op": "synced"}},
    ]
    registries = names("src/registry/registries.calx", "synced_names") + names("src/registry/builtin.calx", "builtin_names")
    for name in registries:
        cases.append({"id": "tags-" + name.replace("/", "."), "input": {"op": "tags", "registry": "minecraft:" + name}})
    for name in names("src/registry/registries.calx", "synced_names"):
        case = {"id": "contents-" + name.replace("/", "."), "input": {"op": "contents", "registry": "minecraft:" + name}}
        if name in UNORDERED:
            case["unordered"] = True
        cases.append(case)
    write_file(HERE / "configuration.json", "registries", "cases/registries/gen.py", cases, probe_version=2)


if __name__ == "__main__":
    main()
