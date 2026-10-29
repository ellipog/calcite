"""Writes the compiled-in tables Calcite's Calx code needs from the converted tables (D61, D126).

    py -I oracle/datagen/calx_tables.py            # write them from generated/<version>/tables
    py -I oracle/datagen/calx_tables.py --check    # fail if what's committed is out of date

The modules are committed, so Calcite builds without the jar. They hold only the identifiers and
IDs the protocol needs, which every compatible server encodes:

- `protocol.ids`: the protocol version, and each state's packets in ID order.
- `registry.builtin`: the built-in registries and their entries in ID order.
- `pack.pin`: where the pinned server jar comes from, and its size and SHA-1, from versions.json.
- `world.blocks`: each block's first state ID and default state, in block ID order.
- `world.block_flags`: what each block state is, as vanilla's state cache holds it, from
  block_flags.json, which oracle/datagen/block_flags.py writes beside the tables (D164).
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


# The flags block_flags.json gives each state, as calcite.rig.vanilla.BlockFlags sets them.
FLAGS = [
    ("AIR", 1, "`isAir`: air, cave air and void air"),
    ("RANDOMLY_TICKING", 1 << 1, "`isRandomlyTicking`: the state takes random ticks"),
    ("FLUID", 1 << 2, "The state's fluid isn't empty: water, lava, or a waterlogged block"),
    ("FLUID_RANDOMLY_TICKING", 1 << 3, "The state's fluid takes random ticks: lava"),
    ("PROPAGATES_SKYLIGHT_DOWN", 1 << 4, "`propagatesSkylightDown`: skylight goes down through it undimmed"),
    ("SHAPE_FOR_LIGHT_OCCLUSION", 1 << 5, "`useShapeForLightOcclusion`: light is stopped by its faces, not the whole block"),
    ("CAN_OCCLUDE", 1 << 6, "`canOcclude`"),
    ("SOLID_RENDER", 1 << 7, "`isSolidRender`: a full, opaque cube"),
    ("BLOCK_ENTITY", 1 << 8, "`hasBlockEntity`"),
]
LOW_MASK = (1 << 12) - 1
LIGHT_EMISSION_SHIFT = 12
LIGHT_DAMPENING_SHIFT = 16

# The characters the encoded flags are written in: printable ASCII but for a space and the four a
# Calx string treats specially. The last starts a pair, for the rarest values.
ALPHABET = "".join(chr(c) for c in range(0x21, 0x7F) if chr(c) not in '"\\{}')
SINGLE = len(ALPHABET) - 1
LINE = 96


def block_flags_module(index, flags):
    """The text of src/world/block_flags.calx."""
    values = flags["flags"]
    if flags["game_version"] != index["game_version"]:
        raise ValueError(f"block_flags.json is {flags['game_version']}, the tables {index['game_version']}")
    if len(values) != flags["states"]:
        raise ValueError(f"block_flags.json has {len(values)} flags for {flags['states']} states")
    known = sum(bit for _, bit, _ in FLAGS)
    for state, v in enumerate(values):
        if v & LOW_MASK & ~known or v >> 24:
            raise ValueError(f"state {state}'s flags {v:#x} have bits this script doesn't know")
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    # The commonest first, so they take one character.
    palette = sorted(counts, key=lambda v: (-counts[v], v))
    if len(palette) > SINGLE + len(ALPHABET):
        raise ValueError(f"{len(palette)} different flags are more than the encoding holds")
    where = {v: i for i, v in enumerate(palette)}
    text = []
    for v in values:
        i = where[v]
        text.append(ALPHABET[i] if i < SINGLE else ALPHABET[SINGLE] + ALPHABET[i - SINGLE])
    # Strings of up to LINE characters, with no pair split between two.
    chunks = [""]
    for t in text:
        if len(chunks[-1]) + len(t) > LINE:
            chunks.append("")
        chunks[-1] += t
    lines = [
        f"/// What each of vanilla {index['game_version']}'s block states is, as the game's state cache holds it, in state ID",
        "/// order. Written by oracle/datagen/calx_tables.py from block_flags.json (D164): don't edit it.",
        "module world.block_flags",
        "",
    ]
    for name, bit, what in FLAGS:
        lines += [f"/// {what}.", f"pub const {name}: u32 = {bit}"]
    lines += [
        "",
        "/// Where a state's light emission, 0 to 15, is in its flags.",
        f"pub const LIGHT_EMISSION_SHIFT: u32 = {LIGHT_EMISSION_SHIFT}",
        "/// Where a state's light dampening, 0 to 15, is in its flags: how much light it takes away.",
        f"pub const LIGHT_DAMPENING_SHIFT: u32 = {LIGHT_DAMPENING_SHIFT}",
        "",
        "/// Each state's flags, in state ID order.",
        "pub fn state_flags() -> List<u32> {",
        "    // The different flags, the commonest first, and an index into them for each state, a",
        f"    // character each, from `alphabet`. Its last character starts a pair, for the {len(palette) - SINGLE} rarest.",
        f"    let values: List<u32> = [{', '.join(str(v) for v in palette)}]",
        "    let lines: List<String> = [",
    ]
    lines += [f'        "{c}",' for c in chunks]
    lines += [
        "    ]",
        f'    let alphabet = "{ALPHABET}"',
        "    var digit: List<u32> = []",
        "    for _ in 0..128 {",
        "        digit.push(0)",
        "    }",
        "    for i in 0..alphabet.len() {",
        "        digit[usize(alphabet.byte_at(i))] = u32.wrap(i)",
        "    }",
        f"    let pair = alphabet.byte_at({SINGLE})",
        "    var flags: List<u32> = []",
        f"    flags.reserve({len(values)})",
        "    for line in lines {",
        "        var i: usize = 0",
        "        while i < line.len() {",
        "            let b = line.byte_at(i)",
        "            if b == pair {",
        f"                flags.push(values[usize({SINGLE} + digit[usize(line.byte_at(i + 1))])])",
        "                i += 2",
        "            } else {",
        "                flags.push(values[usize(digit[usize(b)])])",
        "                i += 1",
        "            }",
        "        }",
        "    }",
        "    return flags",
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
    flags = json.loads((tables.parent / "block_flags.json").read_text(encoding="utf-8"))
    return {
        CALCITE / "src" / "protocol" / "ids.calx": ids_module(index, packets),
        CALCITE / "src" / "registry" / "builtin.calx": builtin_module(index, registries),
        CALCITE / "src" / "pack" / "pin.calx": pin_module(version, pins[version]),
        CALCITE / "src" / "world" / "blocks.calx": blocks_module(index, blocks),
        CALCITE / "src" / "world" / "block_flags.calx": block_flags_module(index, flags),
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
    if not (args.tables.parent / "block_flags.json").exists():
        print(f"no block_flags.json beside {args.tables}: run oracle/datagen/block_flags.py first", file=sys.stderr)
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
