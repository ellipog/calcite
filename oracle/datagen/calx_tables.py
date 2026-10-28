"""Writes the compiled-in tables Calcite's Calx code needs from the converted tables (D61, D126).

    py -I oracle/datagen/calx_tables.py            # write them from generated/<version>/tables
    py -I oracle/datagen/calx_tables.py --check    # fail if what's committed is out of date

The modules are committed, so Calcite builds without the jar. They hold only the identifiers and
IDs the protocol needs, which every compatible server encodes. For now that's `protocol.ids`: the
protocol version, and each state's packets in ID order.
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


def outputs(tables):
    index = json.loads((tables / "index.json").read_text(encoding="utf-8"))
    packets = json.loads((tables / "packets.json").read_text(encoding="utf-8"))
    return {CALCITE / "src" / "protocol" / "ids.calx": ids_module(index, packets)}


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
    for path, text in outputs(args.tables).items():
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
