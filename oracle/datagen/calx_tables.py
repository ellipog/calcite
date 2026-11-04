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
- `world.light_faces`: the faces light sees of each block state, and which two faces light
  can't pass between, from the same file (CAL-66).
- `world.collision_shapes`: each block state's collision shape, as the spawn finder sees it, and
  the boxes of each, from the same file (CAL-75).
- `world.fluid_faces`: the faces a fluid sees of each block state, which two cover a face between
  them, and the boxes of the states vanilla offsets by their position, from the same file (D327).
- `world.entity_facts`: what natural spawning asks of each entity type and block state, from
  entity_facts.json, which oracle/datagen/entity_facts.py writes beside the tables (D317).
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
        f"/// The data version {index['game_version']} writes in its saves as `DataVersion`, which says which version wrote",
        "/// them.",
        f"pub const DATA_VERSION: i32 = {int(index['world_version'])}",
        "",
        f"/// The data pack format {index['game_version']} reads, `major.minor`, as `pack.mcmeta`'s `min_format` and",
        "/// `max_format` give it.",
        f"pub const DATA_PACK_MAJOR: i32 = {int(index['pack_version']['data_major'])}",
        f"pub const DATA_PACK_MINOR: i32 = {int(index['pack_version']['data_minor'])}",
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
    properties = blocks["properties"]
    for b in entries:
        names = [properties[i]["name"] for i in b["properties"]]
        if names != sorted(names) or len(set(names)) != len(names):
            raise ValueError(f"{b['name']}'s properties aren't in name order")
        count = 1
        for i in b["properties"]:
            count *= len(properties[i]["values"])
        if count != b["state_count"]:
            raise ValueError(f"{b['name']}'s properties make {count} states, not {b['state_count']}")
    for prop in properties:
        for v in [prop["name"], *prop["values"]]:
            if '"' in v or "\\" in v or "{" in v:
                raise ValueError(f"{v!r} can't be written in a Calx string")
    starts = [0]
    for b in entries:
        starts.append(starts[-1] + len(b["properties"]))
    listed = ", ".join(str(i) for b in entries for i in b["properties"])
    values = ", ".join(f"[{strings(prop['values'])}]" for prop in properties)
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
        "/// The properties of blocks' states, by name. Several share a name, such as `age`, with other",
        "/// values.",
        "pub fn property_names() -> List<String> {",
        f"    return [{strings(prop['name'] for prop in properties)}]",
        "}",
        "",
        "/// Each property's values, in vanilla's order, which is the order of the states: `true` before",
        "/// `false`, and an integer's from the least.",
        "pub fn property_values() -> List<List<String>> {",
        f"    return [{values}]",
        "}",
        "",
        "/// Where each block's properties start in `block_properties`, in block ID order, and where the",
        "/// last one's end.",
        "pub fn property_starts() -> List<u32> {",
        f"    return [{', '.join(str(s) for s in starts)}]",
        "}",
        "",
        "/// Each block's properties, by their index in `property_names`, in name order. A state's ID is",
        "/// its block's first state's plus, for each property, its value's index times the states the",
        "/// properties after it make, so the last one's changes fastest.",
        "pub fn block_properties() -> List<u32> {",
        f"    return [{listed}]",
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
    ("COLLISION_TOP_FULL", 1 << 9, "`Block.isFaceFull` of its collision shape on `UP`: something can stand on all of its top"),
    ("LARGE_COLLISION", 1 << 10, "`hasLargeCollisionShape`: its collision shape reaches out of its block, or changes with where it is"),
    ("OFFSET", 1 << 11, "`hasOffsetFunction`: its shapes are moved in its block by where it is, as bamboo's"),
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
        if v & LOW_MASK & ~known or v >> 20:
            raise ValueError(f"state {state}'s flags {v:#x} have bits this script doesn't know")
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
    ]
    lines += encoded_table("state_flags", "flags", values)
    return "\n".join(lines)


# The facts block_flags.json gives each state for features, as calcite.rig.vanilla.BlockFlags sets
# them.
FACTS = [
    ("SOLID", 1, "`isSolid`: the legacy solidity, from its collision shape's size"),
    ("REPLACEABLE", 1 << 1, "`canBeReplaced()`: a block placed on it replaces it"),
    ("COLLISION_EMPTY", 1 << 2, "Its collision shape at the origin of an empty world is empty"),
    ("COLLISION_FULL_BLOCK", 1 << 3, "`isCollisionShapeFullBlock` at the origin of an empty world"),
    ("LIQUID", 1 << 4, "`liquid`: the block is water or lava itself"),
    ("IGNITED_BY_LAVA", 1 << 5, "`ignitedByLava`"),
    ("REDSTONE_CONDUCTOR", 1 << 6, "`isRedstoneConductor` at the origin of an empty world"),
]
STURDY_FULL_SHIFT = 7
STURDY_CENTER_SHIFT = 13
STURDY_RIGID_SHIFT = 19
COLLISION_FACE_SHIFT = 25
COLLISION_TOP_ANY = 1 << 31
FLUID_TYPE_SHIFT = 32
FLUID_AMOUNT_SHIFT = 36
OCCLUSION_FACE_SHIFT = 40


def block_facts_module(index, flags):
    """The text of src/world/block_facts.calx."""
    values = flags["facts"]
    classes = flags["classes"]
    if len(values) != flags["states"]:
        raise ValueError(f"block_flags.json has {len(values)} facts for {flags['states']} states")
    known = sum(bit for _, bit, _ in FACTS)
    for state, v in enumerate(values):
        if v & ((1 << STURDY_FULL_SHIFT) - 1) & ~known:
            raise ValueError(f"state {state}'s facts {v:#x} have bits this script doesn't know")
    parents = flags["class_parents"]
    names = sorted(set(classes) | set(parents) | {p for p in parents.values() if p})
    where = {c: i for i, c in enumerate(names)}
    none = len(names)
    lines = [
        f"/// What vanilla {index['game_version']}'s features ask of each block state and block, in state and block ID order.",
        "/// Written by oracle/datagen/calx_tables.py from block_flags.json (CAL-84): don't edit it.",
        "module world.block_facts",
        "",
    ]
    for name, bit, what in FACTS:
        lines += [f"/// {what}.", f"pub const {name}: u32 = {bit}"]
    lines += [
        "",
        "/// Where the faces that are sturdy for `SupportType.FULL` are in a state's facts, a bit each, in",
        "/// `Direction` order: down, up, north, south, west, east.",
        f"pub const STURDY_FULL_SHIFT: u32 = {STURDY_FULL_SHIFT}",
        "/// Where the faces sturdy for `SupportType.CENTER` are.",
        f"pub const STURDY_CENTER_SHIFT: u32 = {STURDY_CENTER_SHIFT}",
        "/// Where the faces sturdy for `SupportType.RIGID` are.",
        f"pub const STURDY_RIGID_SHIFT: u32 = {STURDY_RIGID_SHIFT}",
        "/// Where the faces its collision shape covers whole are: `Block.isFaceFull` of it.",
        f"pub const COLLISION_FACE_SHIFT: u32 = {COLLISION_FACE_SHIFT}",
        "/// Its collision shape touches the top of its block anywhere.",
        f"pub const COLLISION_TOP_ANY: u32 = {COLLISION_TOP_ANY}",
        "",
        "/// Each state's facts, in state ID order.",
    ]
    lines += encoded_table("state_facts", "facts", [v & 0xFFFFFFFF for v in values])
    lines += [
        "/// Each state's fluid, in state ID order: its amount, 0 to 8, in the low 4 bits, and above them",
        "/// its fluid's ID in the fluid registry.",
    ]
    fluids = [((v >> FLUID_TYPE_SHIFT) & 7) << 4 | (v >> FLUID_AMOUNT_SHIFT) & 15 for v in values]
    lines += encoded_table("state_fluids", "fluids", fluids)
    lines += [
        "/// Which of each state's faces its occlusion shape covers whole, in state ID order:",
        "/// `Block.isShapeFullBlock` of `getFaceOcclusionShape`, a bit for each face in `Direction` order.",
    ]
    lines += encoded_table("state_occlusion", "occlusion", [(v >> OCCLUSION_FACE_SHIFT) & 63 for v in values])
    # `BlockState.rotate` and `mirror`, each as how far the state it makes is from the state, so
    # that most are 0 and the rest few. Turning 180 and counterclockwise is turning clockwise twice
    # and three times, for every state, so only the clockwise turn is written.
    turned = {t[0]: t for t in flags["turns"]}
    cw = [turned[s][1] if s in turned else s for s in range(len(values))]
    for s, t in turned.items():
        if cw[cw[s]] != t[2] or cw[cw[cw[s]]] != t[3]:
            raise ValueError(f"state {s}'s turns aren't one clockwise turn made two and three times")
    for i, (fn, what, doc) in enumerate([
        ("state_turns", "turns", "turned clockwise a quarter: `rotate(Rotation.CLOCKWISE_90)`"),
        ("state_mirrors_left_right", "mirrors", "mirrored left to right: `mirror(Mirror.LEFT_RIGHT)`"),
        ("state_mirrors_front_back", "mirrors", "mirrored front to back: `mirror(Mirror.FRONT_BACK)`"),
    ]):
        column = 1 if i == 0 else i + 3
        made = [turned[s][column] if s in turned else s for s in range(len(values))]
        # src/worldgen/facts.calx keeps them as i16s.
        if any(abs(m - s) > 32767 for s, m in enumerate(made)):
            raise ValueError(f"a state is further than an i16 from what it is {doc}")
        lines += [f"/// How far each state is from what it is {doc}, in state ID order, as a u32 that wraps."]
        lines += encoded_table(fn, what, [(m - s) & 0xFFFFFFFF for s, m in enumerate(made)])
    lines += [
        "/// The names of the classes vanilla's blocks are and the classes they extend, sorted: an",
        "/// anonymous class by the class it extends.",
        "pub fn class_names() -> List<String> {",
        "    let names: List<String> = [",
    ]
    lines += [f'        "{n}",' for n in names]
    lines += [
        "    ]",
        "    return names",
        "}",
        "",
        "/// Each block's class, as an index into `class_names`, in block ID order.",
    ]
    def number_list(fn, var, values, doc):
        text = [str(v) for v in values]
        out = doc + [f"pub fn {fn}() -> List<u32> {{", f"    let {var}: List<u32> = ["]
        out += ["        " + ", ".join(text[i:i + 24]) + "," for i in range(0, len(text), 24)]
        out += ["    ]", f"    return {var}", "}", ""]
        return out

    lines += number_list("block_classes", "classes", [where[c] for c in classes], [])
    lines += number_list(
        "class_parents", "parents", [where[parents[n]] if parents.get(n) else none for n in names],
        [f"/// Each class's superclass, by its index in `class_names`, in their order: {none} for none."])
    lines += number_list(
        "survive_classes", "classes", [where[c] if c else none for c in flags["survive_classes"]],
        [f"/// The class whose `canSurvive` each block runs, by its index in `class_names`, in block ID order."])
    lines += number_list(
        "place_on_classes", "classes", [where[c] if c else none for c in flags["place_on_classes"]],
        [f"/// The class whose `mayPlaceOn` each block runs, {none} for none, in block ID order."])
    lines += number_list(
        "shape_classes", "classes", [where[c] if c else none for c in flags["shape_classes"]],
        [f"/// The class whose `updateShape` each block runs, by its index in `class_names`, in block ID order."])
    for fn, method in [("neighbour_classes", "neighborChanged"), ("place_classes", "onPlace"),
                       ("removal_classes", "affectNeighborsAfterRemoval"), ("tick_classes", "tick")]:
        lines += number_list(
            fn, "classes", [where[c] if c else none for c in flags[fn]],
            [f"/// The class whose `{method}` each block runs, by its index in `class_names`, in block ID order (D325)."])
    lines += number_list(
        "random_tick_classes", "classes", [where[c] if c else none for c in flags["random_tick_classes"]],
        ["/// The class whose `randomTick` each block runs, by its index in `class_names`, in block ID order (D338)."])
    lines += number_list(
        "precipitation_classes", "classes", [where[c] if c else none for c in flags["precipitation_classes"]],
        ["/// The class whose `handlePrecipitation` each block runs, by its index in `class_names`, in block ID order",
         "/// (D340)."])
    lines += number_list(
        "flammable_blocks", "blocks", flags["flammable_blocks"],
        ["/// The blocks fire can burn, by ID: those `FireBlock`'s ignite odds are above 0 for."])
    lines += number_list(
        "fire_odds", "odds", [v for each in flags["fire_odds"] for v in each],
        ["/// Each block either of `FireBlock`'s odds is above 0 for, by ID, then its ignite odds and its",
         "/// burn odds: three numbers a block (D339)."])
    lines += number_list(
        "waterloggable_blocks", "blocks", flags["waterloggable_blocks"],
        ["/// The blocks that are `SimpleWaterloggedBlock`s, by ID."])
    lines += number_list(
        "liquid_containers", "blocks", flags["liquid_containers"],
        ["/// The other blocks that are `LiquidBlockContainer`s, by ID."])
    lines += number_list(
        "dynamic_shape_blocks", "blocks", flags["dynamic_shape_blocks"],
        ["/// The blocks whose shape can change where they stand, by ID: `Block.hasDynamicShape`."])
    lines += number_list(
        "outline_differs", "states", flags["outline_differs"],
        ["/// The states whose shape is a full block when their collision shape isn't, or the",
         "/// other way round, by ID: `Block.isShapeFullBlock(getShape)` against",
         "/// `isCollisionShapeFullBlock`."])
    pairs = [str(v) for pair in flags["wall_cover"] for v in pair]
    lines += [
        "/// The states whose collision shape's bottom covers `WallBlock`'s test shapes otherwise than",
        "/// its face being full says, all or none, each followed by which it covers: a bit for the",
        "/// post's, then the north, east, south and west wall's. `WallBlock.isCovered`.",
        "pub fn wall_cover() -> List<u32> {",
        "    let pairs: List<u32> = [",
    ]
    lines += ["        " + ", ".join(pairs[i:i + 24]) + "," for i in range(0, len(pairs), 24)]
    lines += ["    ]", "    return pairs", "}", ""]
    lines += [
        "/// The instruments a note block plays, by name, in `NoteBlockInstrument`'s order.",
        "pub fn instrument_names() -> List<str> {",
        "    return [",
    ]
    lines += [f'        "{n}",' for n in flags["instrument_names"]]
    lines += ["    ]", "}", ""]
    lines += number_list(
        "block_instruments", "instruments", flags["instruments"],
        ["/// The instrument a note block plays over each block, by its index in `instrument_names`, in",
         "/// block ID order: `BlockState.instrument()`, which each of a block's states has."])
    lines += number_list(
        "instruments_above", "instruments", flags["instruments_above"],
        ["/// The instruments that play from above a note block, the heads', by index in",
         "/// `instrument_names`: `worksAboveNoteBlock`."])
    pairs = [str(v) for pair in flags["poi"] for v in pair]
    lines += [
        "/// The states that are points of interest, each followed by its type's ID in the",
        "/// `point_of_interest_type` registry: `PoiTypes.forState`.",
        "pub fn poi_states() -> List<u32> {",
        "    let pairs: List<u32> = [",
    ]
    lines += ["        " + ", ".join(pairs[i:i + 24]) + "," for i in range(0, len(pairs), 24)]
    lines += ["    ]", "    return pairs", "}", ""]
    types = sorted({t for _, t in flags["block_entities"]})
    at = {t: i for i, t in enumerate(types)}
    lines += [
        "/// The block entity types blocks have, by name, sorted.",
        "pub fn block_entity_names() -> List<str> {",
        "    return [",
    ]
    lines += [f'        "{t}",' for t in types]
    lines += ["    ]", "}", ""]
    pairs = [str(v) for block, t in flags["block_entities"] for v in (block, at[t])]
    lines += [
        "/// Each block with a block entity, by ID, followed by its type's index in",
        "/// `block_entity_names`: the type `BlockEntityType.isValid` holds for.",
        "pub fn block_entity_blocks() -> List<u32> {",
        "    let pairs: List<u32> = [",
    ]
    lines += ["        " + ", ".join(pairs[i:i + 24]) + "," for i in range(0, len(pairs), 24)]
    lines += ["    ]", "    return pairs", "}", ""]
    return "\n".join(lines)


def encoded_table(fn, what, values):
    """A Calx function `fn` giving `values`, u32s, compactly: each an index into the different
    values, the commonest first, as a character or two."""
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
        f"pub fn {fn}() -> List<u32> {{",
        f"    // The different {what}, the commonest first, and an index into them for each, a",
        f"    // character each, from `alphabet`. Its last character starts a pair, for the {max(0, len(palette) - SINGLE)} rarest.",
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
        f"    var {what}: List<u32> = []",
        f"    {what}.reserve({len(values)})",
        "    for line in lines {",
        "        var i: usize = 0",
        "        while i < line.len() {",
        "            let b = line.byte_at(i)",
        "            if b == pair {",
        f"                {what}.push(values[usize({SINGLE} + digit[usize(line.byte_at(i + 1))])])",
        "                i += 2",
        "            } else {",
        f"                {what}.push(values[usize(digit[usize(b)])])",
        "                i += 1",
        "            }",
        "        }",
        "    }",
        f"    return {what}",
        "}",
        "",
    ]
    return lines


# The directions, in vanilla's `Direction` order, which a state's faces are in.
DIRECTIONS = ["down", "up", "north", "south", "west", "east"]
FACE_BITS = 6


def light_faces_module(index, flags):
    """The text of src/world/light_faces.calx."""
    faces = flags["light_faces"]
    occludes = flags["face_occludes"]
    shapes = len(flags["face_boxes"])
    if len(faces) != flags["states"]:
        raise ValueError(f"block_flags.json has {len(faces)} states' faces for {flags['states']} states")
    if shapes > 1 << FACE_BITS or len(occludes) != shapes or any(len(row) != shapes for row in occludes):
        raise ValueError(f"{shapes} face shapes don't fit {FACE_BITS} bits, or the table of which occlude isn't square")
    if any(occludes[i][j] != occludes[j][i] for i in range(shapes) for j in range(shapes)):
        raise ValueError("faceShapeOccludes isn't the same both ways round")
    if any(len(f) != len(DIRECTIONS) or not all(0 <= s < shapes for s in f) for f in faces):
        raise ValueError("a state's faces aren't six shapes of the table")
    # Each state's six faces packed into one number, and the different ones, the commonest first.
    packed = [sum(s << (FACE_BITS * d) for d, s in enumerate(f)) for f in faces]
    counts = {}
    for v in packed:
        counts[v] = counts.get(v, 0) + 1
    palette = sorted(counts, key=lambda v: (-counts[v], v))
    if palette[0] != 0:
        raise ValueError("most states' faces aren't all empty")
    if len(palette) > SINGLE:
        raise ValueError(f"{len(palette)} different sets of faces are more than a character each holds")
    where = {v: i for i, v in enumerate(palette)}
    text = "".join(ALPHABET[where[v]] for v in packed)
    chunks = [text[i:i + LINE] for i in range(0, len(text), LINE)]
    rows = [sum(1 << j for j in range(shapes) if occludes[i][j]) for i in range(shapes)]
    lines = [
        f"/// The faces light sees of each of vanilla {index['game_version']}'s block states, as `LightEngine.getOcclusionShape`",
        "/// gives them, and which two faces light can't pass between, as `Shapes.faceShapeOccludes` says.",
        "/// Written by oracle/datagen/calx_tables.py from block_flags.json (D164, CAL-66): don't edit it.",
        "///",
        "/// The faces are numbered shapes, 0 the empty one and 1 the whole face. A state that isn't",
        "/// `canOcclude` or doesn't use its shape for light has every face empty.",
        "module world.light_faces",
        "",
        "/// How many bits each face's shape takes in a state's faces, packed down, up, north, south,",
        "/// west, east from the lowest.",
        f"pub const FACE_BITS: u32 = {FACE_BITS}",
        "/// How many different shapes the faces have.",
        f"pub const FACE_SHAPES: u32 = {shapes}",
        "",
        "/// The different sets of faces, packed, and for each state, in state ID order, which it has.",
        "pub fn state_faces() -> (List<u64>, List<u8>) {",
        f"    let palette: List<u64> = [{', '.join(str(v) for v in palette)}]",
        "    let lines: List<String> = [",
    ]
    lines += [f'        "{c}",' for c in chunks]
    lines += [
        "    ]",
        f'    let alphabet = "{ALPHABET}"',
        "    var digit: List<u8> = []",
        "    for _ in 0..128 {",
        "        digit.push(0)",
        "    }",
        "    for i in 0..alphabet.len() {",
        "        digit[usize(alphabet.byte_at(i))] = u8.wrap(i)",
        "    }",
        "    var states: List<u8> = []",
        f"    states.reserve({len(packed)})",
        "    for line in lines {",
        "        for i in 0..line.len() {",
        "            states.push(digit[usize(line.byte_at(i))])",
        "        }",
        "    }",
        "    return (palette, states)",
        "}",
        "",
        "/// For each shape, the shapes it and light can't pass between, bit `j` for shape `j`.",
        "pub fn face_occludes() -> List<u64> {",
        f"    return [{', '.join(str(r) for r in rows)}]",
        "}",
        "",
    ]
    return "\n".join(lines)


# How a collision shape's boxes are stored: each coordinate in 32nds of a block, which every one
# of vanilla's is, from BOX_FLOOR up, so they fit a byte.
BOX_UNIT = 32
BOX_FLOOR = -16


def box_units(c):
    """A coordinate as BOX_UNITs above BOX_FLOOR, which must be whole and fit a byte."""
    v = c * BOX_UNIT
    if v != round(v) or not 0 <= round(v) - BOX_FLOOR < 256:
        raise ValueError(f"the coordinate {c} isn't a 32nd of a block from {BOX_FLOOR / BOX_UNIT} to {(255 + BOX_FLOOR) / BOX_UNIT}")
    return round(v) - BOX_FLOOR


def numbers(values, per=24):
    """Numbers as rows of a Calx list literal, `per` a row."""
    rows = [", ".join(str(v) for v in values[i:i + per]) for i in range(0, len(values), per)]
    return ",\n".join(f"        {r}" for r in rows)


# How many bits each of a state's six fluid faces takes, packed down, up, north, south, west, east.
FLUID_FACE_BITS = 8


def fluid_faces_module(index, flags):
    """The text of src/world/fluid_faces.calx."""
    faces = flags["fluid_faces"]
    boxes = flags["fluid_face_boxes"]
    covers = flags["fluid_covers"]
    count = len(boxes)
    if len(faces) != flags["states"]:
        raise ValueError(f"block_flags.json has {len(faces)} states' fluid faces for {flags['states']} states")
    if count > 1 << FLUID_FACE_BITS or len(covers) != count or any(len(row) != count for row in covers):
        raise ValueError(f"{count} fluid faces don't fit {FLUID_FACE_BITS} bits, or the table of which cover isn't square")
    if any(covers[i][j] != covers[j][i] for i in range(count) for j in range(count)):
        raise ValueError("mergedFaceOccludes isn't the same both ways round")
    if boxes[0] != [] or boxes[1] != [[0.0, 0.0, 0.0, 1.0, 1.0, 1.0]]:
        raise ValueError("fluid face 0 isn't empty, or 1 isn't the whole face")
    if any(len(f) != len(DIRECTIONS) or not all(0 <= s < count for s in f) for f in faces):
        raise ValueError("a state's fluid faces aren't six of the table's")
    # Each face's rectangles: its boxes, one block deep along z, as u, v from and to.
    starts = []
    rects = []
    for face in boxes:
        starts.append(len(rects) // 4)
        for box in face:
            if len(box) != 6 or box[2] != 0.0 or box[5] != 1.0:
                raise ValueError(f"a fluid face's box {box} isn't one block deep along z")
            rects += [box_units(box[0]), box_units(box[1]), box_units(box[3]), box_units(box[4])]
    starts.append(len(rects) // 4)
    words = (count + 63) // 64
    rows = []
    for i in range(count):
        for w in range(words):
            rows.append(sum(1 << (j - 64 * w) for j in range(64 * w, min(count, 64 * w + 64)) if covers[i][j]))
    # Each state's six faces packed, the different sets the commonest first, and an index into
    # them for each state, a character each or, for the rarest, a pair.
    packed = [sum(s << (FLUID_FACE_BITS * d) for d, s in enumerate(f)) for f in faces]
    counts = {}
    for v in packed:
        counts[v] = counts.get(v, 0) + 1
    palette = sorted(counts, key=lambda v: (-counts[v], v))
    pairs = 1
    while len(ALPHABET) - pairs + pairs * len(ALPHABET) < len(palette):
        pairs += 1
    single = len(ALPHABET) - pairs
    where = {v: i for i, v in enumerate(palette)}
    text = []
    for v in packed:
        i = where[v]
        if i < single:
            text.append(ALPHABET[i])
        else:
            i -= single
            text.append(ALPHABET[single + i // len(ALPHABET)] + ALPHABET[i % len(ALPHABET)])
    chunks = [""]
    for c in text:
        if len(chunks[-1]) + len(c) > LINE:
            chunks.append("")
        chunks[-1] += c
    # The states that move: each one's grid's ends, then its boxes.
    moving = flags["fluid_moving"]
    moving_states = []
    grids = []
    box_starts = []
    moving_boxes = []
    for state, grid, shape in moving:
        if len(grid) != 6:
            raise ValueError(f"state {state}'s grid has {len(grid)} ends")
        moving_states.append(state)
        grids += [box_units(c) for c in grid]
        box_starts.append(len(moving_boxes) // 6)
        for box in shape:
            if len(box) != 6:
                raise ValueError(f"a box of {len(box)} numbers")
            moving_boxes += [box_units(c) for c in box]
    box_starts.append(len(moving_boxes) // 6)
    if moving_states != sorted(moving_states):
        raise ValueError("the states that move aren't in ID order")
    offsets = []
    for block, xyz, horizontal, vertical in flags["offsets"]:
        offsets += [block, xyz, horizontal, vertical]
    cases = []
    for case in flags["fluid_cases"]:
        if len(case) != 7:
            raise ValueError(f"a fluid case of {len(case)} numbers")
        cases += case
    offset_cases = []
    for case in flags["offset_cases"]:
        if len(case) != 6:
            raise ValueError(f"an offset case of {len(case)} numbers")
        offset_cases += case
    lines = [
        f"/// The faces a fluid sees of each of vanilla {index['game_version']}'s block states, as `FlowingFluid.canPassThroughWall`",
        "/// asks them, and which two cover a face of a block between them, as `Shapes.mergedFaceOccludes`",
        "/// says. Written by oracle/datagen/calx_tables.py from block_flags.json (D327, CAL-91): don't",
        "/// edit it.",
        "///",
        "/// A face is a state's collision shape's slice toward a side, laid flat on that side's other two",
        "/// axes, x before y before z: 0 is the empty face and 1 the whole one. A state vanilla offsets by",
        "/// its position whose collision shape isn't empty, as pointed dripstone, moves: its faces here",
        "/// are its shape's before it's offset, and it has its boxes and where its shape's grid starts and",
        "/// ends, which `mergedFaceOccludes` slices at, so its faces where it is can be worked out.",
        "/// Vanilla's own `canPassThroughWall` agreed with these for every two shapes, and for each state",
        "/// that moves at 24 places, as they were written.",
        "module world.fluid_faces",
        "",
        "/// How many bits each face takes in a state's faces, packed down, up, north, south, west, east",
        "/// from the lowest.",
        f"pub const FLUID_FACE_BITS: u32 = {FLUID_FACE_BITS}",
        "/// How many different faces there are, and how many words each face's row of `fluid_covers`",
        "/// takes.",
        f"pub const FLUID_FACES: u32 = {count}",
        f"pub const COVER_WORDS: u32 = {words}",
        "/// How many 32nds of a block a coordinate is from, and above, `FACE_FLOOR`.",
        f"pub const FACE_UNIT: i32 = {BOX_UNIT}",
        f"pub const FACE_FLOOR: i32 = {BOX_FLOOR}",
        "",
        "/// The different sets of six faces, packed, and for each state, in state ID order, which it has.",
        "pub fn state_fluid_faces() -> (List<u64>, List<u16>) {",
        f"    // The sets, the commonest first, and an index into them for each state, a character",
        f"    // each, from `alphabet`, or for the {max(0, len(palette) - single)} rarest a pair, whose first is one of its last {pairs}.",
        f"    let palette: List<u64> = [{', '.join(str(v) for v in palette)}]",
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
        "    var states: List<u16> = []",
        f"    states.reserve({len(packed)})",
        "    for line in lines {",
        "        var i: usize = 0",
        "        while i < line.len() {",
        "            let d = digit[usize(line.byte_at(i))]",
        f"            if d >= {single} {{",
        f"                states.push(u16.wrap({single} + (d - {single}) * {len(ALPHABET)} + digit[usize(line.byte_at(i + 1))]))",
        "                i += 2",
        "            } else {",
        "                states.push(u16.wrap(d))",
        "                i += 1",
        "            }",
        "        }",
        "    }",
        "    return (palette, states)",
        "}",
        "",
        "/// For each face, `COVER_WORDS` words of the faces it and a fluid can't pass between, bit `j`",
        "/// of a row's words for face `j`.",
        "pub fn fluid_covers() -> List<u64> {",
        "    return [",
        numbers(rows, 6),
        "    ]",
        "}",
        "",
        "/// Where each face's rectangles start in `face_rects`, counted in rectangles, and where the last",
        "/// ends.",
        "pub fn face_starts() -> List<u16> {",
        "    return [",
        numbers(starts),
        "    ]",
        "}",
        "",
        "/// Every face's rectangles, four coordinates each, from u, v to u, v, in `FACE_UNIT`s above",
        "/// `FACE_FLOOR`.",
        "pub fn face_rects() -> List<u8> {",
        "    return [",
        numbers(rects),
        "    ]",
        "}",
        "",
        "/// The states that move, in state ID order.",
        "pub fn moving_states() -> List<u32> {",
        "    return [",
        numbers(moving_states, 12),
        "    ]",
        "}",
        "",
        "/// Where each state that moves has its shape's grid start, on x, y, z, then end, in `FACE_UNIT`s",
        "/// above `FACE_FLOOR`.",
        "pub fn moving_grids() -> List<u8> {",
        "    return [",
        numbers(grids),
        "    ]",
        "}",
        "",
        "/// Where each state that moves has its boxes start in `moving_boxes`, counted in boxes, and",
        "/// where the last ends.",
        "pub fn moving_starts() -> List<u16> {",
        "    return [",
        numbers(box_starts),
        "    ]",
        "}",
        "",
        "/// The boxes of the states that move, before they're offset, six coordinates each, min x, y, z",
        "/// then max x, y, z, in `FACE_UNIT`s above `FACE_FLOOR`.",
        "pub fn moving_boxes() -> List<u8> {",
        "    return [",
        numbers(moving_boxes),
        "    ]",
        "}",
        "",
        "/// Each block vanilla offsets by its position, four numbers each: the block, 1 if it's offset up",
        "/// and down too, and the bits of the `f32`s it's offset at most across and up and down,",
        "/// `getMaxHorizontalOffset` and `getMaxVerticalOffset`.",
        "pub fn offset_blocks() -> List<u32> {",
        "    return [",
        numbers(offsets, 8),
        "    ]",
        "}",
        "",
        "/// What vanilla's `canPassThroughWall` said where a state that moves meets another, seven numbers",
        "/// each: x, y, z of the first, the direction toward the second, the two states, and 1 if a",
        "/// fluid passes. Most are where moving changes the answer. For Calcite's tests.",
        "pub fn wall_cases() -> List<i32> {",
        "    return [",
        numbers(cases, 7),
        "    ]",
        "}",
        "",
        "/// Where vanilla offsets a state that moves, six numbers each: the state, x, z, and the bits of",
        "/// the offset's x, y and z. For Calcite's tests.",
        "pub fn offset_cases() -> List<i64> {",
        "    return [",
        numbers(offset_cases, 6),
        "    ]",
        "}",
        "",
    ]
    return "\n".join(lines)


def collision_module(index, flags):
    """The text of src/world/collision_shapes.calx."""
    shapes = flags["collision"]
    boxes = flags["collision_boxes"]
    if len(shapes) != flags["states"]:
        raise ValueError(f"block_flags.json has {len(shapes)} states' collision shapes for {flags['states']} states")
    if not all(0 <= s < len(boxes) for s in shapes):
        raise ValueError("a state's collision shape isn't one of the table's")
    if boxes[0] != [] or boxes[1] != [[0.0, 0.0, 0.0, 1.0, 1.0, 1.0]]:
        raise ValueError("collision shape 0 isn't empty, or 1 isn't the whole block")
    coords = []
    starts = []
    for shape in boxes:
        starts.append(len(coords) // 6)
        for box in shape:
            if len(box) != 6:
                raise ValueError(f"a box of {len(box)} numbers")
            for c in box:
                v = c * BOX_UNIT
                if v != round(v) or not 0 <= round(v) - BOX_FLOOR < 256:
                    raise ValueError(f"the coordinate {c} isn't a 32nd of a block from {BOX_FLOOR / BOX_UNIT} to {(255 + BOX_FLOOR) / BOX_UNIT}")
                coords.append(round(v) - BOX_FLOOR)
    starts.append(len(coords) // 6)
    # Each state's shape as a character of `alphabet`, the commonest shapes first, or a pair for
    # the rest, from the last `pairs` characters.
    counts = {}
    for s in shapes:
        counts[s] = counts.get(s, 0) + 1
    palette = sorted(counts, key=lambda s: (-counts[s], s))
    pairs = 1
    while len(ALPHABET) - pairs + pairs * len(ALPHABET) < len(palette):
        pairs += 1
    single = len(ALPHABET) - pairs
    where = {s: i for i, s in enumerate(palette)}
    text = []
    for s in shapes:
        i = where[s]
        if i < single:
            text.append(ALPHABET[i])
        else:
            i -= single
            text.append(ALPHABET[single + i // len(ALPHABET)] + ALPHABET[i % len(ALPHABET)])
    chunks = [""]
    for c in text:
        if len(chunks[-1]) + len(c) > LINE:
            chunks.append("")
        chunks[-1] += c

    def numbers(values, per=24):
        rows = [", ".join(str(v) for v in values[i:i + per]) for i in range(0, len(values), per)]
        return ",\n".join(f"        {r}" for r in rows)

    lines = [
        f"/// Each of vanilla {index['game_version']}'s block states' collision shapes, as the spawn finder sees them:",
        "/// `getCollisionShape` with an empty context that collides with fluids, so a liquid is a whole",
        "/// block. A state vanilla offsets by its position, as bamboo, has the shape it has before it's",
        "/// offset. Written by oracle/datagen/calx_tables.py from block_flags.json (CAL-75): don't edit it.",
        "///",
        "/// The shapes are numbered, 0 the empty one and 1 the whole block, and each is a list of boxes,",
        "/// as `toAabbs` gives them.",
        "module world.collision_shapes",
        "",
        "/// How many 32nds of a block a box's coordinate is from, and above, `BOX_FLOOR`.",
        f"pub const BOX_UNIT: i32 = {BOX_UNIT}",
        f"pub const BOX_FLOOR: i32 = {BOX_FLOOR}",
        "/// How many different shapes there are.",
        f"pub const SHAPES: u32 = {len(boxes)}",
        "",
        "/// Each state's shape, in state ID order.",
        "pub fn state_shapes() -> List<u16> {",
        f"    // The shapes, the commonest first, and an index into them for each state, a character",
        f"    // each, from `alphabet`, or for the {len(palette) - single} rarest a pair, whose first is one of its last {pairs}.",
        f"    let values: List<u16> = [{', '.join(str(v) for v in palette)}]",
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
        "    var shapes: List<u16> = []",
        f"    shapes.reserve({len(shapes)})",
        "    for line in lines {",
        "        var i: usize = 0",
        "        while i < line.len() {",
        "            let d = digit[usize(line.byte_at(i))]",
        f"            if d >= {single} {{",
        f"                shapes.push(values[usize({single} + (d - {single}) * {len(ALPHABET)} + digit[usize(line.byte_at(i + 1))])])",
        "                i += 2",
        "            } else {",
        "                shapes.push(values[usize(d)])",
        "                i += 1",
        "            }",
        "        }",
        "    }",
        "    return shapes",
        "}",
        "",
        "/// Where each shape's boxes start in `shape_boxes`, counted in boxes, and where the last ends.",
        "pub fn shape_starts() -> List<u16> {",
        "    return [",
        numbers(starts),
        "    ]",
        "}",
        "",
        "/// Every shape's boxes, six coordinates each, min x, y, z then max x, y, z, in `BOX_UNIT`s",
        "/// above `BOX_FLOOR`.",
        "pub fn shape_boxes() -> List<u8> {",
        "    return [",
        numbers(coords),
        "    ]",
        "}",
        "",
    ]
    return "\n".join(lines)

# What entity_facts.json gives each type, as calcite.rig.vanilla.EntityFacts sets them, a bit each.
TYPE_FLAGS = [
    ("SUMMON", "summon", "`canSummon`"),
    ("FIRE_IMMUNE", "fire_immune", "`fireImmune`"),
    ("FAR", "far", "`canSpawnFarFromPlayer`: it spawns however far it is from players"),
    ("PEACEFUL", "peaceful", "`isAllowedInPeaceful`"),
]
# Vanilla's spawn placement types, as entity_facts.json names them.
PLACEMENTS = ["no_restrictions", "in_water", "in_lava", "on_ground"]
# `Heightmap.Types`, in its order, which world.chunk's kinds are in.
HEIGHTMAPS = ["WORLD_SURFACE_WG", "WORLD_SURFACE", "OCEAN_FLOOR_WG", "OCEAN_FLOOR", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES"]


def calx_float(v):
    """A float as a Calx f32 literal that reads back as the same float."""
    text = repr(float(v))
    if "e" not in text and "." not in text:
        text += ".0"
    return text + "f32"


def entity_facts_module(index, facts):
    """The text of src/world/entity_facts.calx."""
    if facts["game_version"] != index["game_version"]:
        raise ValueError(f"entity_facts.json is {facts['game_version']}, the tables {index['game_version']}")
    groups = facts["spawn_groups"]
    for state, v in enumerate(facts["states"]):
        if v >> (1 + groups):
            raise ValueError(f"state {state}'s spawn facts {v:#x} have bits this script doesn't know")
    categories = facts["categories"]
    rules = sorted({t["rule"] for t in facts["types"] if "rule" in t})
    immune = []
    for t in facts["types"]:
        if t["immune_to"] not in immune:
            immune.append(t["immune_to"])
    quoted = ", ".join('"' + c + '"' for c in categories)
    serialized = ", ".join('"' + c.lower() + '"' for c in categories)
    lines = [
        f"/// What vanilla {index['game_version']}'s natural spawning asks of each entity type, in type ID order, and of each",
        "/// block state, in state ID order. Written by oracle/datagen/calx_tables.py from entity_facts.json",
        "/// (D317): don't edit it.",
        "module world.entity_facts",
        "",
        "/// The mob categories, in `MobCategory` order, which a type's `category` is a place in.",
        "pub fn categories() -> List<String> {",
        f"    return [{quoted}]",
        "}",
        "",
        "/// The categories' serialized names, as codecs read and write them, in the same order.",
        "pub fn category_names() -> List<String> {",
        f"    return [{serialized}]",
        "}",
        "",
    ]
    for i, c in enumerate(categories):
        lines += [f"pub const {c}: i32 = {i}"]
    lines += [""]
    for i, (name, _, what) in enumerate(TYPE_FLAGS):
        lines += [f"/// {what}.", f"pub const {name}: u32 = {1 << i}"]
    lines += [""]
    for i, p in enumerate(PLACEMENTS):
        lines += [f"/// `SpawnPlacementTypes.{p.upper()}`.", f"pub const {p.upper()}: i32 = {i}"]
    lines += [
        "",
        "/// A state is a signal source, in its spawn facts.",
        "pub const SIGNAL_SOURCE: u32 = 1",
        "/// Where the spawn groups' bits are in a state's spawn facts: `isValidSpawn` holds on the state",
        "/// for the types of group `g` where bit `VALID_SPAWN_SHIFT + g` is set.",
        "pub const VALID_SPAWN_SHIFT: u32 = 1",
        "/// How many spawn groups there are.",
        f"pub const SPAWN_GROUPS: i32 = {groups}",
        "",
        "/// The methods the types' spawn rules call, as `Owner.method`, which a type's `rule` is a place",
        "/// in.",
        "pub fn rules() -> List<String> {",
        "    return [",
    ]
    lines += [f'        "{r}",' for r in rules]
    lines += [
        "    ]",
        "}",
        "",
        "/// The block tags the types are immune to, as `isBlockDangerous` reads them, in the order the",
        "/// types first name them, which a type's `immune_to` is a place in.",
        "pub fn immune_tags() -> List<String> {",
        "    return [",
    ]
    lines += [f'        "{name}",' for name in immune]
    lines += [
        "    ]",
        "}",
        "",
        "/// What natural spawning asks of an entity type.",
        "pub struct TypeFacts {",
        "    /// Its place in `categories`.",
        "    pub category: i32",
        "    /// Its flags, from those above.",
        "    pub flags: u32",
        "    /// The block tag it's immune to, as its place in `immune_tags`.",
        "    pub immune_to: i32",
        "    /// Half its spawn box's width, and its height, as `getSpawnAABB` works them out.",
        "    pub half_width: f32",
        "    pub height: f32",
        "    /// Its spawn group: which states `isValidSpawn` holds on for it.",
        "    pub spawn_group: i32",
        "    /// Where `SpawnPlacements` registers it, its placement type and its place in `rules`, or",
        "    /// none where it isn't; and its heightmap, of world.chunk's kinds.",
        "    pub placement: i32?",
        "    pub heightmap: i32",
        "    pub rule: i32?",
        "}",
        "",
        "/// Each type's facts, in type ID order.",
        "pub fn types() -> List<TypeFacts> {",
        "    return [",
    ]
    for t in facts["types"]:
        flags = sum(1 << i for i, (_, key, _) in enumerate(TYPE_FLAGS) if t[key])
        placed = "rule" in t
        placement = f"some({PLACEMENTS.index(t['placement'])})" if placed else "none"
        heightmap = HEIGHTMAPS.index(t["heightmap"]) if placed else HEIGHTMAPS.index("MOTION_BLOCKING_NO_LEAVES")
        rule = f"some({rules.index(t['rule'])})" if placed else "none"
        lines.append(f"        // {t['id']}")
        lines.append(
            f"        TypeFacts {{ category: {categories.index(t['category'])}, flags: {flags}, immune_to: {immune.index(t['immune_to'])}, "
            f"half_width: {calx_float(t['half_width'])}, height: {calx_float(t['height'])}, spawn_group: {t['spawn_group']}, "
            f"placement: {placement}, heightmap: {heightmap}, rule: {rule} }},"
        )
    lines += [
        "    ]",
        "}",
        "",
        "/// Each state's spawn facts, in state ID order.",
    ]
    lines += encoded_table("state_spawn_facts", "facts", facts["states"])
    return "\n".join(lines)


def outputs(tables, version=VERSION):
    index = json.loads((tables / "index.json").read_text(encoding="utf-8"))
    packets = json.loads((tables / "packets.json").read_text(encoding="utf-8"))
    registries = json.loads((tables / "registries.json").read_text(encoding="utf-8"))
    blocks = json.loads((tables / "blocks.json").read_text(encoding="utf-8"))
    pins = json.loads((CALCITE / "oracle" / "versions.json").read_text(encoding="utf-8"))
    flags = json.loads((tables.parent / "block_flags.json").read_text(encoding="utf-8"))
    entities = json.loads((tables.parent / "entity_facts.json").read_text(encoding="utf-8"))
    return {
        CALCITE / "src" / "protocol" / "ids.calx": ids_module(index, packets),
        CALCITE / "src" / "registry" / "builtin.calx": builtin_module(index, registries),
        CALCITE / "src" / "pack" / "pin.calx": pin_module(version, pins[version]),
        CALCITE / "src" / "world" / "blocks.calx": blocks_module(index, blocks),
        CALCITE / "src" / "world" / "block_flags.calx": block_flags_module(index, flags),
        CALCITE / "src" / "world" / "block_facts.calx": block_facts_module(index, flags),
        CALCITE / "src" / "world" / "light_faces.calx": light_faces_module(index, flags),
        CALCITE / "src" / "world" / "collision_shapes.calx": collision_module(index, flags),
        CALCITE / "src" / "world" / "fluid_faces.calx": fluid_faces_module(index, flags),
        CALCITE / "src" / "world" / "entity_facts.calx": entity_facts_module(index, entities),
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
    if not (args.tables.parent / "entity_facts.json").exists():
        print(f"no entity_facts.json beside {args.tables}: run oracle/datagen/entity_facts.py first", file=sys.stderr)
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
