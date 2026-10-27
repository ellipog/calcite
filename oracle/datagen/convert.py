"""Converts the data generator's reports into neutral tables for Calx codegen (P2.2).

    py -I oracle/datagen/convert.py [--version 26.3]

Reads generated/<version>/datagen/reports/ and writes generated/<version>/tables/. Every table is
checked while it's converted, so a game update that breaks an assumption Calcite's codegen relies
on stops here, not at runtime. oracle/datagen/README.md describes each table.

Output is canonical, so two runs give the same bytes: UTF-8, LF, two-space indent, object keys
sorted, and every number written as the exact text the report has. Floats are never parsed into
Python floats, because the reports mix float and double text ("1.8000001", "0.10000000149011612")
and the codegen has to read each one with the right precision.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

FORMAT = 1


class ConvertError(Exception):
    pass


def check(condition, message):
    if not condition:
        raise ConvertError(message)


class Num(str):
    """A JSON number, kept as the text it was written as."""


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        check(k not in out, f"duplicate key {k!r}")
        out[k] = v
    return out


def load(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Num, parse_int=Num,
                      parse_constant=lambda c: check(False, f"{path}: {c} isn't JSON"),
                      object_pairs_hook=_pairs)


def _scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, Num):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"can't write {type(value).__name__}")


def dumps(value, indent=0):
    """Canonical JSON: keys sorted, arrays of scalars on one line, everything else two-space indented."""
    pad, inner = "  " * indent, "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{inner}{_scalar(k)}: {dumps(value[k], indent + 1)}" for k in sorted(value)]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if not any(isinstance(v, (dict, list)) for v in value):
            return "[" + ", ".join(_scalar(v) for v in value) + "]"
        return "[\n" + ",\n".join(inner + dumps(v, indent + 1) for v in value) + "\n" + pad + "]"
    return _scalar(value)


def by_id(entries, what):
    """Names ordered by protocol_id, checking the IDs run 0..n-1 with no gaps."""
    order = sorted(entries, key=lambda name: int(entries[name]["protocol_id"]))
    ids = [int(entries[name]["protocol_id"]) for name in order]
    check(ids == list(range(len(ids))), f"{what}: protocol IDs aren't 0..{len(ids) - 1}")
    return order


# Each converter takes the reports folder and returns the table's value.

def registries(reports):
    raw = load(reports / "registries.json")
    out = {}
    for name, reg in raw.items():
        out[name] = {"id": int(reg["protocol_id"]), "default": reg.get("default"),
                     "entries": by_id(reg["entries"], name)}
    check(sorted(r["id"] for r in out.values()) == list(range(len(out))), "registry IDs aren't 0..n-1")
    return out


INT_VALUE = re.compile(r"0|[1-9][0-9]*")


def property_kind(values):
    if values == ["true", "false"]:
        return {"kind": "bool"}
    if all(INT_VALUE.fullmatch(v) for v in values):
        ints = [int(v) for v in values]
        check(ints == list(range(ints[0], ints[0] + len(ints))), f"int property values {values} aren't consecutive")
        return {"kind": "int", "min": ints[0], "max": ints[-1]}
    return {"kind": "enum"}


def blocks(reports, regs):
    """Blocks in registry order, with each block's states described by arithmetic instead of listed.

    A block's states take the global IDs first_state .. first_state + state_count - 1. The state at
    first_state + i has, for its properties in name order, the mixed-radix digits of i, with the last
    property changing fastest (vanilla's StateDefinition keeps properties sorted by name and builds
    the states as their cartesian product). The report lists property keys in its own sorted order
    with "type" first, so the converter sorts them itself and checks every state against the rule.
    """
    raw = load(reports / "blocks.json")
    order = regs["minecraft:block"]["entries"]
    check(set(order) == set(raw), "blocks.json and the block registry list different blocks")
    table, index, out, next_state = [], {}, [], 0
    for block_id, name in enumerate(order):
        entry = raw[name]
        props = entry.get("properties", {})
        names = sorted(props)
        check(all(n.isascii() for n in names), f"{name}: non-ASCII property name")
        refs = []
        for p in names:
            key = (p, tuple(props[p]))
            if key not in index:
                index[key] = None
                table.append(key)
            refs.append(key)
        states = entry["states"]
        count = 1
        for p in names:
            count *= len(props[p])
        check(len(states) == count, f"{name}: {len(states)} states, expected {count}")
        first = int(states[0]["id"])
        check(first == next_state, f"{name}: states start at {first}, expected {next_state}")
        default = None
        for i, state in enumerate(states):
            check(int(state["id"]) == first + i, f"{name}: state {i} has ID {state['id']}")
            digit, rest = [], i
            for p in reversed(names):
                digit.append(props[p][rest % len(props[p])])
                rest //= len(props[p])
            check(dict(zip(reversed(names), digit)) == state.get("properties", {}),
                  f"{name}: state {state['id']} breaks the mixed-radix rule")
            if state.get("default"):
                check(default is None, f"{name}: two default states")
                default = first + i
        check(default is not None, f"{name}: no default state")
        out.append({"id": block_id, "name": name, "first_state": first, "state_count": count,
                    "default_state": default, "properties": refs})
        next_state += count
    table.sort()
    position = {key: i for i, key in enumerate(table)}
    for b in out:
        b["properties"] = [position[key] for key in b["properties"]]
    properties = [{"name": n, "values": list(v), **property_kind(list(v))} for n, v in table]
    return {"state_count": next_state, "properties": properties, "blocks": out}


def packets(reports):
    raw = load(reports / "packets.json")
    return {phase: {direction: by_id(ids, f"{phase} {direction}") for direction, ids in sides.items()}
            for phase, sides in raw.items()}


def commands(reports):
    """The command tree as the report gives it. The report sorts each node's children by name, so
    it doesn't record the order commands register in."""
    return load(reports / "commands.json")


def items(reports, regs):
    folder = reports / "minecraft" / "components" / "item"
    order = regs["minecraft:item"]["entries"]
    files = {f"minecraft:{p.stem}" for p in folder.glob("*.json")}
    check(files == set(order), "the item component reports and the item registry list different items")
    out = []
    for item_id, name in enumerate(order):
        raw = load(folder / f"{name.split(':', 1)[1]}.json")
        check(set(raw) == {"components"}, f"{name}: unexpected keys {sorted(raw)}")
        out.append({"id": item_id, "name": name, "components": raw["components"]})
    return out


def biome_parameters(reports):
    """The multi-noise biome parameter lists that are defined in code, not in the data pack."""
    folder = reports / "biome_parameters" / "minecraft"
    return {f"minecraft:{p.stem}": load(p) for p in sorted(folder.glob("*.json"))}


def version_info(version):
    with zipfile.ZipFile(fetch.ensure(version, download=False)) as jar:
        info = json.loads(jar.read("version.json"))
    check(info["id"] == version, f"the jar is version {info['id']}, not {version}")
    return {"game_version": info["id"], "world_version": info["world_version"],
            "protocol_version": info["protocol_version"], "pack_version": info["pack_version"],
            "java_version": info["java_version"]}


def convert(version, reports, out):
    """Writes every table into out, replacing what's there, and returns the index."""
    regs = registries(reports)
    tables = {
        "registries.json": regs,
        "blocks.json": blocks(reports, regs),
        "items.json": items(reports, regs),
        "packets.json": packets(reports),
        "commands.json": commands(reports),
        "biome_parameters.json": biome_parameters(reports),
        "datapack_registries.json": load(reports / "datapack.json"),
        "management_api.json": load(reports / "json-rpc-api-schema.json"),
    }
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    index = {"format": FORMAT, **version_info(version),
             "jar_sha1": fetch.pins()[version]["sha1"], "tables": {}}
    for name, value in tables.items():
        data = (dumps(value) + "\n").encode("utf-8")
        (tmp / name).write_bytes(data)
        index["tables"][name] = hashlib.sha256(data).hexdigest()
    (tmp / "index.json").write_bytes((dumps(index) + "\n").encode("utf-8"))
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    return index


def main():
    parser = argparse.ArgumentParser(description="Convert the data generator's reports into tables.")
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    base = ROOT / "generated" / args.version
    try:
        index = convert(args.version, base / "datagen" / "reports", base / "tables")
    except ConvertError as e:
        sys.exit(f"convert: {e}")
    print(f"convert: wrote {len(index['tables'])} tables to {base / 'tables'}")


if __name__ == "__main__":
    main()
