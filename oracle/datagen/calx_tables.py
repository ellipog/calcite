"""Writes the compiled-in tables Calcite's Calx code needs from the converted tables (D61, D126).

    py -I oracle/datagen/calx_tables.py            # write them from generated/<version>/tables
    py -I oracle/datagen/calx_tables.py --check    # fail if what's committed is out of date

The modules are committed, so Calcite builds without the jar. They hold only the identifiers and
IDs the protocol needs, which every compatible server encodes:

- `protocol.ids`: the protocol version, and each state's packets in ID order.
- `registry.builtin`: the built-in registries and their entries in ID order.
- `pack.pin`: where the pinned server jar comes from, and its size and SHA-1, from versions.json.
- `world.blocks`: each block's first state ID and default state, in block ID order.
"""

import argparse
import json
import pathlib
import sys

CALCITE = pathlib.Path(__file__).resolve().parents[2]
VERSION = "26.3"

STATES = ["handshake", "status", "login", "configuration", "play"]
BOUNDS = ["serverbound", "clientbound"]


def calx_name(state):
    return state[0].upper() + state[1:]


def ids_module(index, packets):
    """The text of src/protocol/ids.calx."""
    unknown = sorted(set(packets) - set(STATES))
    if unknown:
        raise ValueError(f"packets.json has states this script doesn't know: {unknown}")
    lines = [
        f"/// Vanilla {index['game_version']}'s protocol version, and the packets of each protocol state in ID order, so a",
        "/// packet's ID is its place in its list. Written by oracle/datagen/calx_tables.py from",
        "/// packets.json (D126): don't edit it.",
        "module protocol.ids",
        "",
        "import protocol.state.{State, Bound}",
        "",
        f"/// The protocol version a {index['game_version']} client sends in its handshake.",
        f"pub const PROTOCOL_VERSION: i32 = {int(index['protocol_version'])}",
        "",
        "/// The game version, as the server list shows it.",
        f"pub fn game_version() -> String {{",
        f"    return \"{index['game_version']}\"",
        "}",
        "",
        "/// The packets in `state` that go `bound`, by their names without `minecraft:`, in ID order.",
        "pub fn packet_names(state: State, bound: Bound) -> List<String> {",
        "    match state {",
    ]
    for state in STATES:
        lists = packets.get(state, {})
        extra = sorted(set(lists) - set(BOUNDS))
        if extra:
            raise ValueError(f"packets.json's {state} has directions this script doesn't know: {extra}")
        lines.append(f"        State.{calx_name(state)} => {{")
        for bound in BOUNDS:
            names = []
            for name in lists.get(bound, []):
                if not name.startswith("minecraft:"):
                    raise ValueError(f"packet {name!r} isn't in the minecraft namespace")
                names.append(name[len("minecraft:"):])
            body = ", ".join(f'"{n}"' for n in names)
            if bound == BOUNDS[0]:
                lines.append(f"            if bound == Bound.{calx_name(bound)} {{")
                lines.append(f"                return [{body}]")
                lines.append("            }")
            else:
                lines.append(f"            return [{body}]")
        lines.append("        }")
    lines += ["    }", "}", ""]
    return "\n".join(lines)


def short(name):
    """An identifier as the modules write it: without `minecraft:`, or whole in another namespace."""
    if ":" not in name:
        raise ValueError(f"{name!r} has no namespace")
    if '"' in name or "\\" in name or "{" in name:
        raise ValueError(f"{name!r} can't be written in a Calx string")
    return name[len("minecraft:"):] if name.startswith("minecraft:") else name


def strings(names):
    return ", ".join(f'"{n}"' for n in names)


def builtin_module(index, registries):
    """The text of src/registry/builtin.calx."""
    by_id = sorted(registries.items(), key=lambda item: item[1]["id"])
    ids = [r["id"] for _, r in by_id]
    if ids != list(range(len(ids))):
        raise ValueError(f"registries.json's registry IDs don't run from 0 without gaps: {ids}")
    lines = [
        f"/// Vanilla {index['game_version']}'s built-in registries, the ones it defines in code, and their entries in ID",
        "/// order, so an entry's ID is its place in its list. Written by oracle/datagen/calx_tables.py from",
        "/// registries.json (D61): don't edit it.",
        "module registry.builtin",
        "",
        "/// The built-in registries, in the order of their own IDs, by name without `minecraft:`.",
        "pub fn builtin_names() -> List<String> {",
        f"    return [{strings(short(name) for name, _ in by_id)}]",
        "}",
        "",
        "/// The entries of the registry at `index` in `builtin_names`, in ID order, by name without",
        "/// `minecraft:` where they're in it. None for an index past the last.",
        "pub fn builtin_entries(index: usize) -> List<String> {",
        "    return match index {",
    ]
    for name, registry in by_id:
        lines.append(f"        {registry['id']} => [{strings(short(e) for e in registry['entries'])}],")
    lines += ["        _ => [],", "    }", "}", ""]
    return "\n".join(lines)


def blocks_module(index, blocks):
    """The text of src/world/blocks.calx."""
    entries = blocks["blocks"]
    if [b["id"] for b in entries] != list(range(len(entries))):
        raise ValueError("blocks.json's block IDs don't run from 0 without gaps")
    first = 0
    for b in entries:
        if b["first_state"] != first:
            raise ValueError(f"{b['name']}'s states don't follow the block before's")
        if not b["first_state"] <= b["default_state"] < b["first_state"] + b["state_count"]:
            raise ValueError(f"{b['name']}'s default state isn't one of its states")
        first += b["state_count"]
    if first != blocks["state_count"]:
        raise ValueError(f"blocks.json's blocks have {first} states, not the {blocks['state_count']} it says")
    firsts = ", ".join(str(b["first_state"]) for b in entries)
    defaults = ", ".join(str(b["default_state"] - b["first_state"]) for b in entries)
    lines = [
        f"/// Vanilla {index['game_version']}'s block state IDs: a block's states are numbered on from the last",
        "/// state of the block before it, in block ID order, which is the order of `registry.builtin`'s",
        "/// `block` registry. Written by oracle/datagen/calx_tables.py from blocks.json (D126): don't edit",
        "/// it.",
        "module world.blocks",
        "",
        "/// How many block states there are.",
        f"pub const STATE_COUNT: u32 = {blocks['state_count']}",
        "",
        "/// The ID of each block's first state, in block ID order.",
        "pub fn first_states() -> List<u32> {",
        f"    return [{firsts}]",
        "}",
        "",
        "/// Where each block's default state is among its states, in block ID order.",
        "pub fn default_offsets() -> List<u32> {",
        f"    return [{defaults}]",
        "}",
        "",
    ]
    return "\n".join(lines)


def pin_module(version, pin):
    """The text of src/pack/pin.calx."""
    url, sha1, size = pin["url"], pin["sha1"], int(pin["size"])
    if not url.startswith("https://") or '"' in url or "{" in url or "\\" in url:
        raise ValueError(f"the pinned URL {url!r} isn't an https URL Calx can hold")
    if len(sha1) != 40 or any(c not in "0123456789abcdef" for c in sha1):
        raise ValueError(f"the pinned SHA-1 {sha1!r} isn't 40 lowercase hex digits")
    client = pin["client"]
    data = client["data"]
    client_url, data_sha256 = client["url"], data["sha256"]
    if not client_url.startswith("https://") or '"' in client_url or "{" in client_url or "\\" in client_url:
        raise ValueError(f"the pinned client URL {client_url!r} isn't an https URL Calx can hold")
    if len(data_sha256) != 64 or any(c not in "0123456789abcdef" for c in data_sha256):
        raise ValueError(f"the pinned data SHA-256 {data_sha256!r} isn't 64 lowercase hex digits")
    lines = [
        f"/// Where Mojang's {version} server jar comes from, and its size and SHA-1, and where the vanilla",
        "/// data is in the client jar, as oracle/versions.json pins them (D62, D140). Written by",
        "/// oracle/datagen/calx_tables.py: don't edit it.",
        "module pack.pin",
        "",
        "/// The game version the jar is.",
        "pub fn jar_version() -> String {",
        f'    return "{version}"',
        "}",
        "",
        "/// Mojang's URL for the jar.",
        "pub fn jar_url() -> String {",
        f'    return "{url}"',
        "}",
        "",
        "/// The jar's SHA-1, in lowercase hex.",
        "pub fn jar_sha1() -> String {",
        f'    return "{sha1}"',
        "}",
        "",
        "/// The jar's size in bytes.",
        f"pub const JAR_SIZE: usize = {size}",
        "",
        "/// Mojang's URL for the client jar, which holds the vanilla data as the server jar does, but",
        "/// with each file compressed on its own, so a stretch of it can be read alone.",
        "pub fn client_url() -> String {",
        f'    return "{client_url}"',
        "}",
        "",
        "/// The client jar's size in bytes.",
        f"pub const CLIENT_SIZE: u64 = {int(client['size'])}",
        "",
        "/// Where in the client jar the vanilla data is: from the local header of the first file",
        "/// Calcite reads, data/ and the two language files, to the end of the last.",
        f"pub const DATA_OFFSET: u64 = {int(data['offset'])}",
        f"pub const DATA_LENGTH: usize = {int(data['length'])}",
        "",
        "/// The SHA-256 of that stretch, in lowercase hex.",
        "pub fn data_sha256() -> String {",
        f'    return "{data_sha256}"',
        "}",
        "",
    ]
    return "\n".join(lines)


def outputs(tables, version=VERSION):
    index = json.loads((tables / "index.json").read_text(encoding="utf-8"))
    packets = json.loads((tables / "packets.json").read_text(encoding="utf-8"))
    registries = json.loads((tables / "registries.json").read_text(encoding="utf-8"))
    blocks = json.loads((tables / "blocks.json").read_text(encoding="utf-8"))
    pins = json.loads((CALCITE / "oracle" / "versions.json").read_text(encoding="utf-8"))
    return {
        CALCITE / "src" / "protocol" / "ids.calx": ids_module(index, packets),
        CALCITE / "src" / "registry" / "builtin.calx": builtin_module(index, registries),
        CALCITE / "src" / "pack" / "pin.calx": pin_module(version, pins[version]),
        CALCITE / "src" / "world" / "blocks.calx": blocks_module(index, blocks),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a committed module is out of date")
    parser.add_argument("--version", default=VERSION, help=f"the game version whose tables to read (default {VERSION})")
    parser.add_argument("--tables", type=pathlib.Path, help="the tables folder, instead of generated/<version>/tables")
    args = parser.parse_args()
    if args.tables is None:
        args.tables = CALCITE / "generated" / args.version / "tables"
    if not (args.tables / "index.json").exists():
        print(f"no tables at {args.tables}: run oracle/datagen/datagen.py first", file=sys.stderr)
        return 2
    stale = []
    for path, text in outputs(args.tables, args.version).items():
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old == text:
            continue
        if args.check:
            stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(CALCITE).as_posix()}")
    for path in stale:
        print(f"{path.relative_to(CALCITE).as_posix()} is out of date: run oracle/datagen/calx_tables.py", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
