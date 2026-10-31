"""Writes cases/entities_poi/generated.json: chunks of a world's `entities/` and `poi/` folders, as
SNBT, read as vanilla's EntityStorage reads an entity chunk before it makes the entities, written
as it stores one, and read and written back as SectionStorage reads and writes a chunk of points
of interest for PoiManager.

    py -I cases/entities_poi/gen.py

The entity cases cover the chunk's position, written well, badly, in the wrong place and in every
kind of list and array, and its `Entities`, as a list of compounds, of other tags, empty, and
missing. The POI cases cover sections by height, inside the world and outside it, their `Valid`
flag in every kind of number and in others, and their records: positions, types by name, with and
without a namespace, unknown and malformed, tickets, records at the same place in a section, and
enough of them to fill a section's map in the order vanilla's keeps them.

Every chunk is from 26.3, or newer, since an older one is upgraded by vanilla and read as it is by
Calcite (D169).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261031
OVERWORLD = (-64, 24)
NETHER = (0, 16)

PIG = '{id:"minecraft:pig",Pos:[0.5d,64.0d,0.5d],Motion:[0.0d,0.0d,0.0d],Rotation:[0.0f,0.0f],UUID:[I;1,2,3,4]}'
ZOMBIE = '{id:"minecraft:zombie",Pos:[17.5d,-20.0d,-3.5d],Health:20.0f,Passengers:[{id:"minecraft:chicken"}]}'
ITEM = '{id:"minecraft:item",Item:{id:"minecraft:stone",count:3},Age:5s}'


def load(name, snbt=None, x=0, z=0):
    data = {"op": "entities_load", "x": x, "z": z}
    if snbt is not None:
        data["snbt"] = snbt
    return {"id": f"load-{name}", "input": data}


def entity_chunk(entities=None, position="[I;0,0]", version="5023", extra=""):
    parts = []
    if version is not None:
        parts.append(f"DataVersion:{version}")
    if position is not None:
        parts.append(f"Position:{position}")
    if entities is not None:
        parts.append(f"Entities:{entities}")
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}"


def loads():
    return [
        load("none"),
        load("one", entity_chunk(f"[{PIG}]")),
        load("three", entity_chunk(f"[{PIG},{ZOMBIE},{ITEM}]")),
        load("placed", entity_chunk(f"[{PIG}]", "[I;5,-7]"), 5, -7),
        load("far", entity_chunk(f"[{PIG}]", "[I;-1875000,1874999]"), -1875000, 1874999),
        load("empty-list", entity_chunk("[]")),
        load("no-entities", entity_chunk()),
        load("empty-root", "{DataVersion:5023}"),
        load("only-entities", entity_chunk(f"[{PIG}]", None)),
        load("entities-int", entity_chunk("5")),
        load("entities-compound", entity_chunk(f"{PIG}")),
        load("entities-string", entity_chunk('"pig"')),
        load("entities-int-array", entity_chunk("[I;1,2]")),
        load("entities-long-array", entity_chunk("[L;1L]")),
        load("entities-byte-array", entity_chunk("[B;1b]")),
        load("entities-mixed", entity_chunk(f'[{PIG},5,"x",{ZOMBIE},[1,2],{{}}]')),
        load("entities-not-compounds", entity_chunk("[1,2,3]")),
        load("entities-lists", entity_chunk("[[{a:1}],[]]")),
        load("entities-empty-compounds", entity_chunk("[{},{},{a:1b}]")),
        load("entities-nested-lists", entity_chunk(f"[{PIG},[{PIG}]]")),
        load("entities-all-kinds", entity_chunk('[1b,2s,3,4L,5.0f,6.0d,[B;1b],"s",[1],{a:1},[I;1],[L;1L]]')),
        load("misplaced", entity_chunk(f"[{PIG}]", "[I;3,4]")),
        load("misplaced-elsewhere", entity_chunk(f"[{PIG}]", "[I;0,0]"), 9, -9),
        load("misplaced-and-bad", entity_chunk("[1]", "[I;3,4]")),
        load("no-position", entity_chunk(f"[{PIG}]", None)),
        load("no-position-bad", entity_chunk("5", None)),
        load("position-list", entity_chunk(f"[{PIG}]", "[0,0]")),
        load("position-list-placed", entity_chunk(f"[{PIG}]", "[2,3]"), 2, 3),
        load("position-bytes", entity_chunk(f"[{PIG}]", "[B;1b,2b]"), 1, 2),
        load("position-longs", entity_chunk(f"[{PIG}]", "[L;1L,2L]"), 1, 2),
        load("position-longs-wrap", entity_chunk(f"[{PIG}]", "[L;4294967297L,-4294967298L]"), 1, -2),
        load("position-doubles", entity_chunk(f"[{PIG}]", "[1.9d,-2.9d]"), 1, -2),
        load("position-floats", entity_chunk(f"[{PIG}]", "[1.5f,2.5f]")),
        load("position-mixed-numbers", entity_chunk(f"[{PIG}]", "[1b,2L]"), 1, 2),
        load("position-three", entity_chunk(f"[{PIG}]", "[I;0,0,7]")),
        load("position-three-misplaced", entity_chunk(f"[{PIG}]", "[I;1,0,0]")),
        load("position-four-list", entity_chunk(f"[{PIG}]", "[0,0,1,2]")),
        load("position-one", entity_chunk(f"[{PIG}]", "[I;0]")),
        load("position-empty", entity_chunk(f"[{PIG}]", "[I;]")),
        load("position-empty-list", entity_chunk(f"[{PIG}]", "[]")),
        load("position-string", entity_chunk(f"[{PIG}]", '"0,0"')),
        load("position-int", entity_chunk(f"[{PIG}]", "0")),
        load("position-compound", entity_chunk(f"[{PIG}]", "{x:0,z:0}")),
        load("position-strings", entity_chunk(f"[{PIG}]", '["a","b"]')),
        load("position-some-strings", entity_chunk(f"[{PIG}]", '[0,"b"]')),
        load("position-compounds", entity_chunk(f"[{PIG}]", "[{a:1},{b:2}]")),
        load("position-lists", entity_chunk(f"[{PIG}]", "[[0],[0]]")),
        load("position-quotes", entity_chunk(f"[{PIG}]", "[\"it's\",'\"x\"']")),
        load("bad-position-bad-entities", entity_chunk('[1,"x"]', "[I;0]")),
        load("newer", entity_chunk(f"[{PIG}]", version="9999")),
        load("newer-misplaced", entity_chunk(f"[{PIG}]", "[I;1,1]", version="6000")),
        load("extra-keys", entity_chunk(f"[{PIG}]", extra='Other:"kept",Level:{}')),
        load("many-bad", entity_chunk("[" + ",".join(str(i) for i in range(12)) + "]"), 3, 4),
    ]


def save(name, snbt, x=0, z=0):
    return {"id": f"save-{name}", "input": {"op": "entities_save", "x": x, "z": z, "snbt": snbt}}


def saves():
    return [
        save("none", "{}"),
        save("none-other-keys", "{Other:1}"),
        save("declined", "{Entities:[]}"),
        save("one", f"{{Entities:[{PIG}]}}"),
        save("three", f"{{Entities:[{PIG},{ZOMBIE},{ITEM}]}}", 7, -8),
        save("far", f"{{Entities:[{ITEM}]}}", 1874999, -1875000),
        save("min", f"{{Entities:[{ITEM}]}}", -2147483648, 2147483647),
    ]


def poi(name, snbt=None, x=0, z=0, height=OVERWORLD):
    data = {"op": "poi", "x": x, "z": z, "min_y": height[0], "sections": height[1]}
    if snbt is not None:
        data["snbt"] = snbt
    return {"id": f"poi-{name}", "input": data}


def record(pos, kind='"minecraft:home"', tickets=None, extra=""):
    """A record; `kind` is SNBT, a quoted name or any other tag."""
    parts = [f"pos:{pos}", f"type:{kind}"]
    if tickets is not None:
        parts.append(f"free_tickets:{tickets}")
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}"


def named(name):
    return f'"{name}"'


def section(records, valid="1b"):
    parts = []
    if valid is not None:
        parts.append(f"Valid:{valid}")
    if records is not None:
        parts.append(f"Records:[{','.join(records)}]" if isinstance(records, list) else f"Records:{records}")
    return "{" + ",".join(parts) + "}"


def poi_chunk(sections, version="5023", extra=""):
    parts = []
    if version is not None:
        parts.append(f"DataVersion:{version}")
    if sections is not None:
        if isinstance(sections, dict):
            parts.append("Sections:{" + ",".join(f'"{y}":{s}' for y, s in sections.items()) + "}")
        else:
            parts.append(f"Sections:{sections}")
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}"


HOME = record("[I;1,2,3]")
BELL = record("[I;4,5,6]", named("minecraft:meeting"), 32)
KINDS = ["armorer", "butcher", "cartographer", "cleric", "farmer", "fisherman", "fletcher", "leatherworker",
         "librarian", "mason", "shepherd", "toolsmith", "weaponsmith", "home", "meeting", "beehive",
         "bee_nest", "nether_portal", "lodestone", "test_instance", "lightning_rod"]


def pois():
    g = splitmix64(SEED)
    many = []
    for _ in range(40):
        v = next(g)
        many.append(record(f"[I;{v & 15},{(v >> 4) & 15},{(v >> 8) & 15}]", named("minecraft:" + KINDS[(v >> 12) % len(KINDS)]), (v >> 20) % 3))
    full = [record(f"[I;{x},{32 + y},{z}]", named("minecraft:nether_portal")) for x in range(16) for z in range(16) for y in (0, 15)]
    return [
        poi("none"),
        poi("none-nether", height=NETHER),
        poi("one", poi_chunk({0: section([HOME])})),
        poi("two", poi_chunk({0: section([HOME, BELL])})),
        poi("sections", poi_chunk({-4: section([record("[I;0,-64,0]")]), 3: section([BELL]), 19: section([record("[I;15,319,15]", named("minecraft:lodestone"))])})),
        poi("sections-placed", poi_chunk({1: section([record("[I;-31,16,47]")])}), -2, 2),
        poi("outside", poi_chunk({-5: section([HOME]), 20: section([BELL]), 0: section([HOME])})),
        poi("nether", poi_chunk({-1: section([HOME]), 0: section([HOME]), 15: section([BELL]), 16: section([BELL])}), height=NETHER),
        poi("odd-keys", poi_chunk({"01": section([HOME]), "+1": section([HOME]), " 2": section([HOME]), "x": section([HOME]), "3": section([BELL])})),
        poi("no-sections", poi_chunk(None)),
        poi("empty-sections", poi_chunk({})),
        poi("empty-root", "{DataVersion:5023}"),
        poi("sections-int", poi_chunk("5")),
        poi("sections-list", poi_chunk("[{Valid:1b,Records:[]}]")),
        poi("section-int", poi_chunk({0: "5", 1: section([HOME])})),
        poi("section-list", poi_chunk({0: "[1,2]"})),
        poi("section-string", poi_chunk({0: '"x"'})),
        poi("section-empty", poi_chunk({0: "{}"})),
        poi("records-empty", poi_chunk({0: section([])})),
        poi("records-empty-invalid", poi_chunk({0: section([], None)})),
        poi("records-missing", poi_chunk({0: section(None), 1: section([HOME])})),
        poi("records-int", poi_chunk({0: section("5")})),
        poi("records-compound", poi_chunk({0: section(HOME)})),
        poi("records-string", poi_chunk({0: section('"x"')})),
        poi("records-int-array", poi_chunk({0: section("[I;1,2]")})),
        poi("valid-missing", poi_chunk({0: section([HOME], None)})),
        poi("valid-false", poi_chunk({0: section([HOME], "0b")})),
        poi("valid-two", poi_chunk({0: section([HOME], "2b")})),
        poi("valid-int", poi_chunk({0: section([HOME], "1")})),
        poi("valid-256", poi_chunk({0: section([HOME], "256")})),
        poi("valid-257", poi_chunk({0: section([HOME], "257s")})),
        poi("valid-half", poi_chunk({0: section([HOME], "0.5d")})),
        poi("valid-float", poi_chunk({0: section([HOME], "1.9f")})),
        poi("valid-long", poi_chunk({0: section([HOME], "4294967297L")})),
        poi("valid-negative", poi_chunk({0: section([HOME], "-1b")})),
        poi("valid-string", poi_chunk({0: section([HOME], '"true"')})),
        poi("valid-list", poi_chunk({0: section([HOME], "[1b]")})),
        poi("valid-string-no-records", poi_chunk({0: section(None, '"true"')})),
        poi("type-short", poi_chunk({0: section([record("[I;1,2,3]", named("home"))])})),
        poi("type-unknown", poi_chunk({0: section([HOME, record("[I;2,2,3]", named("minecraft:nope")), BELL])})),
        poi("type-other-namespace", poi_chunk({0: section([record("[I;2,2,3]", named("mod:home"))])})),
        poi("type-malformed", poi_chunk({0: section([record("[I;2,2,3]", named("Bad Name")), HOME])})),
        poi("type-malformed-namespace", poi_chunk({0: section([record("[I;2,2,3]", named("a b:c"))])})),
        poi("type-int", poi_chunk({0: section([record("[I;2,2,3]", "5"), HOME])})),
        poi("type-compound", poi_chunk({0: section([record("[I;2,2,3]", "{id:home}")])})),
        poi("type-missing", poi_chunk({0: section(["{pos:[I;2,2,3]}", HOME])})),
        poi("types", poi_chunk({0: section([record(f"[I;{i % 16},{i // 16},0]", named("minecraft:" + k)) for i, k in enumerate(KINDS)])})),
        poi("pos-list", poi_chunk({0: section([record("[1,2,3]")])})),
        poi("pos-longs", poi_chunk({0: section([record("[L;1L,2L,4294967299L]")])})),
        poi("pos-bytes", poi_chunk({0: section([record("[B;1b,2b,3b]")])})),
        poi("pos-doubles", poi_chunk({0: section([record("[1.5d,2.5d,-3.5d]")])})),
        poi("pos-four", poi_chunk({0: section([record("[I;1,2,3,4]")])})),
        poi("pos-four-bad-type", poi_chunk({0: section([record("[I;1,2,3,4]", named("minecraft:nope"))])})),
        poi("pos-two", poi_chunk({0: section([record("[I;1,2]"), BELL])})),
        poi("pos-empty", poi_chunk({0: section([record("[I;]")])})),
        poi("pos-string", poi_chunk({0: section([record('"1,2,3"')])})),
        poi("pos-strings", poi_chunk({0: section([record('["1","2","3"]')])})),
        poi("pos-missing", poi_chunk({0: section(['{type:"minecraft:home"}', BELL])})),
        poi("pos-and-type-bad", poi_chunk({0: section([record("[I;1]", named("minecraft:nope"))])})),
        poi("pos-and-type-missing", poi_chunk({0: section(["{free_tickets:1}"])})),
        poi("all-bad", poi_chunk({0: section([record("[I;1]", named("minecraft:nope"), '"x"')])})),
        poi("pos-outside", poi_chunk({0: section([record("[I;100,-200,300]")])})),
        poi("pos-in-another-section", poi_chunk({0: section([record("[I;1,18,3]")]), 1: section([record("[I;1,2,3]")])})),
        poi("tickets-zero", poi_chunk({0: section([record("[I;1,2,3]", tickets="0")])})),
        poi("tickets-byte", poi_chunk({0: section([record("[I;1,2,3]", tickets="3b")])})),
        poi("tickets-double", poi_chunk({0: section([record("[I;1,2,3]", tickets="1.9d")])})),
        poi("tickets-negative", poi_chunk({0: section([record("[I;1,2,3]", tickets="-5")])})),
        poi("tickets-long", poi_chunk({0: section([record("[I;1,2,3]", tickets="4294967297L")])})),
        poi("tickets-string", poi_chunk({0: section([record("[I;1,2,3]", tickets='"1"'), BELL])})),
        poi("tickets-list", poi_chunk({0: section([record("[I;1,2,3]", tickets="[1]")])})),
        poi("extra-fields", poi_chunk({0: '{Valid:1b,Records:[{pos:[I;1,2,3],type:"minecraft:home",free_tickets:1,extra:5}],More:1}'})),
        poi("record-int", poi_chunk({0: section(["5", HOME])})),
        poi("record-list", poi_chunk({0: section(["[1,2,3]", HOME])})),
        poi("record-empty", poi_chunk({0: section(["{}", HOME])})),
        poi("records-all-bad", poi_chunk({0: section(["5", "{}", record("[I;1]")])})),
        poi("same-place", poi_chunk({0: section([HOME, record("[I;1,2,3]", tickets="1")])})),
        poi("same-place-other-type", poi_chunk({0: section([HOME, record("[I;1,2,3]", named("minecraft:meeting"))])})),
        poi("same-place-short-name", poi_chunk({0: section([HOME, record("[I;1,2,3]", named("home"))])})),
        poi("same-relative-place", poi_chunk({0: section([HOME, record("[I;17,2,3]")])})),
        poi("same-relative-other-type", poi_chunk({0: section([HOME, record("[I;17,-14,35]", named("minecraft:farmer"), 2)])})),
        poi("same-place-three", poi_chunk({0: section([HOME, record("[I;1,2,3]", named("minecraft:meeting")), record("[I;1,2,3]", named("minecraft:farmer")), record("[I;1,2,3]", named("minecraft:farmer"))])})),
        poi("zero-key", poi_chunk({0: section([record("[I;5,5,5]"), record("[I;0,0,0]"), record("[I;16,16,16]", named("minecraft:meeting"))])})),
        poi("many", poi_chunk({0: section(many), 5: section(list(reversed(many)))})),
        poi("full", poi_chunk({2: section(full, "0b")})),
        poi("newer", poi_chunk({0: section([HOME])}, version="9999")),
        poi("no-other-root", poi_chunk({0: section([HOME])}, extra='Other:"dropped"')),
        poi("bad-sections-and-good", poi_chunk({-4: section(None), -3: "5", -2: section([record("[I;1]")]), -1: section([HOME, "1"]), 0: section([BELL]), 7: section([], "1b")})),
    ]


def main():
    cases = loads() + saves() + pois()
    write_file(HERE / "generated.json", "entities_poi", "cases/entities_poi/gen.py", cases)


if __name__ == "__main__":
    main()
