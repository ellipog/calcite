"""Writes cases/world_folder/generated.json: a world's folder opened and locked, its level.dat read
with the level.dat_old fallback, its version checked as a server checks it as it starts, saved,
players' data read as they join, saved data read and written, and the files left, as vanilla's
LevelStorageSource, PlayerDataStorage and SavedDataStorage do each.

    py -I cases/world_folder/gen.py

The level.dat files are made here: NBT written as NbtIo writes a file's root, gzipped as Java's
GZIPOutputStream gzips it, then broken in the ways a file can be: cut off, with a wrong checksum or
length, more than one gzip member, a header with its optional fields, things after the stream, a
root that isn't a compound, more NBT than the quota, and folders where files should be.
"""

import base64
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTES, STRING, LIST, COMPOUND, INTS, LONGS = range(13)


def b64(data):
    return base64.b64encode(bytes(data)).decode()


def utf(s):
    b = s.encode()
    return struct.pack(">H", len(b)) + b


def payload(kind, v):
    if kind == BYTE:
        return struct.pack(">b", v)
    if kind == SHORT:
        return struct.pack(">h", v)
    if kind == INT:
        return struct.pack(">i", v)
    if kind == LONG:
        return struct.pack(">q", v)
    if kind == FLOAT:
        return struct.pack(">f", v)
    if kind == DOUBLE:
        return struct.pack(">d", v)
    if kind == STRING:
        return utf(v)
    if kind == LIST:
        inner, items = v
        return bytes([inner]) + struct.pack(">i", len(items)) + b"".join(payload(inner, i) for i in items)
    if kind == COMPOUND:
        out = b""
        for name, (k, value) in v.items():
            out += bytes([k]) + utf(name) + payload(k, value)
        return out + bytes([END])
    if kind == INTS:
        return struct.pack(">i", len(v)) + b"".join(struct.pack(">i", i) for i in v)
    raise ValueError(kind)


def root(kind, v):
    """A file's root, as NbtIo.write writes it: its type, an empty name, its payload."""
    return bytes([kind]) + utf("") + payload(kind, v)


def level(**fields):
    """level.dat's root: `Data`, holding the fields."""
    return root(COMPOUND, {"Data": (COMPOUND, fields)})


def gzip(data, header=b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"):
    """gzip as Java's GZIPOutputStream writes it: no name, no time, OS 255."""
    c = zlib.compressobj(6, zlib.DEFLATED, -15)
    raw = c.compress(data) + c.flush()
    return header + raw + struct.pack("<II", zlib.crc32(data), len(data))


GOOD = {
    "LevelName": (STRING, "world"),
    "version": (INT, 19133),
    "DataVersion": (INT, 5023),
    "Version": (COMPOUND, {"Name": (STRING, "26.3"), "Id": (INT, 5023), "Series": (STRING, "main"), "Snapshot": (BYTE, 0)}),
    "GameType": (INT, 1),
    "Time": (LONG, 313),
}


def good(name="world", **more):
    fields = dict(GOOD)
    fields["LevelName"] = (STRING, name)
    fields.update(more)
    return level(**fields)


def case(name, ops, blobs):
    return {"id": name, "input": {"ops": ops}, "blobs": [b64(b) for b in blobs]}


def put(name, blob):
    return ["put", name, blob]


LOAD = [["open"], ["has"], ["load"]]
CLOSE = [["close"]]


def folders():
    """A new world, one there already, saved once and twice, and folders where files go."""
    first = gzip(good("first"))
    return [
        case("new", [["open"], ["has"], ["close"]], []),
        case("saved", [put("level.dat", 0)] + LOAD + [["check"], ["save"]] + CLOSE, [first]),
        case("saved-twice", [put("level.dat", 0)] + LOAD + [["save"], ["save"]] + CLOSE, [first]),
        case("old-only", [put("level.dat_old", 0)] + LOAD + [["check"]] + CLOSE, [first]),
        case("both", [put("level.dat", 0), put("level.dat_old", 1)] + LOAD + CLOSE, [first, gzip(good("old"))]),
        case("level-is-a-folder", [["dir", "level.dat"], put("level.dat_old", 0)] + LOAD + CLOSE, [first]),
        case("level-is-a-full-folder", [put("level.dat/inside", 1), put("level.dat_old", 0)] + LOAD + CLOSE, [first, b"x"]),
        case("old-is-a-folder", [put("level.dat", 1), ["dir", "level.dat_old"]] + LOAD + CLOSE, [first, b"broken"]),
        case("save-over-folders", [put("level.dat", 0), ["dir", "level.dat_old"]] + LOAD + [["save"]] + CLOSE, [first]),
        case("lock-kept", [put("session.lock", 0), ["open"], ["close"]], [b"0123456789"]),
        case("other-files-kept", [put("level.dat", 0), put("dimensions/minecraft/overworld/region/r.0.0.mca", 1)] + LOAD + [["save"]] + CLOSE, [first, b"region"]),
    ]


def broken():
    """level.dat files that can't be read, with level.dat_old to fall back on, and some that can
    be although they look broken."""
    data = good("broken")
    raw = zlib.compressobj(6, zlib.DEFLATED, -15)
    deflated = raw.compress(data) + raw.flush()
    head = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"
    trailer = struct.pack("<II", zlib.crc32(data), len(data))
    half = len(data) // 2
    member_a = gzip(data[:half])
    member_b = gzip(data[half:])
    name_header = b"\x1f\x8b\x08\x08\x00\x00\x00\x00\x00\xff" + b"level.dat\x00"
    extra_header = b"\x1f\x8b\x08\x04\x00\x00\x00\x00\x00\xff" + struct.pack("<H", 4) + b"ab\x00\x00"
    comment_header = b"\x1f\x8b\x08\x10\x00\x00\x00\x00\x00\xff" + b"made by hand\x00"
    plain_header = b"\x1f\x8b\x08\x02\x00\x00\x00\x00\x00\xff"
    header_crc = struct.pack("<H", zlib.crc32(plain_header) & 0xFFFF)
    wrong_crc = struct.pack("<H", (zlib.crc32(plain_header) + 1) & 0xFFFF)
    # A long array that says it's longer than the quota allows, with nothing after.
    quota = bytes([COMPOUND]) + utf("") + bytes([COMPOUND]) + utf("Data") + bytes([LONGS]) + utf("Big") + struct.pack(">i", 20000000) + bytes(16)
    variants = {
        "not-gzip": data,
        "empty": b"",
        "magic-only": b"\x1f\x8b",
        "header-only": head,
        "cut-in-stream": head + deflated[: len(deflated) // 2],
        "cut-trailer": head + deflated,
        "cut-half-trailer": head + deflated + trailer[:4],
        "wrong-crc": head + deflated + struct.pack("<II", zlib.crc32(data) ^ 1, len(data)),
        "wrong-length": head + deflated + struct.pack("<II", zlib.crc32(data), len(data) + 1),
        "two-members": member_a + member_b,
        "two-members-wrong-crc": member_a[:-8] + struct.pack("<II", zlib.crc32(data[:half]) ^ 1, half) + member_b,
        "garbage-after": gzip(data) + b"not gzip at all",
        "member-after": gzip(data) + gzip(good("second")),
        "name-header": gzip(data, name_header),
        "extra-header": gzip(data, extra_header),
        "comment-header": gzip(data, comment_header),
        "header-crc": gzip(data, plain_header + header_crc),
        "wrong-header-crc": gzip(data, plain_header + wrong_crc),
        "reserved-flag": gzip(data, b"\x1f\x8b\x08\x20\x00\x00\x00\x00\x00\xff"),
        "not-deflate": gzip(data, b"\x1f\x8b\x07\x00\x00\x00\x00\x00\x00\xff"),
        "root-list": gzip(root(LIST, (INT, [1, 2, 3]))),
        "root-end": gzip(bytes([END])),
        "root-int": gzip(root(INT, 5)),
        "data-not-compound": gzip(root(COMPOUND, {"Data": (INT, 4)})),
        "no-data": gzip(root(COMPOUND, {"Other": (COMPOUND, {"LevelName": (STRING, "x")})})),
        "cut-nbt": gzip(data[:-3]),
        "nbt-then-more": gzip(data + b"\x01\x02\x03"),
        "bad-tag-type": gzip(bytes([COMPOUND]) + utf("") + bytes([COMPOUND]) + utf("Data") + bytes([42]) + utf("x") + bytes([END, END])),
        "over-quota": gzip(quota),
        "deep": gzip(bytes([COMPOUND]) + utf("") + (bytes([COMPOUND]) + utf("a")) * 600 + bytes([END]) * 601),
    }
    old = gzip(good("fallback"))
    cases = []
    for name, blob in variants.items():
        cases.append(case(name, [put("level.dat", 0), put("level.dat_old", 1)] + LOAD + CLOSE, [blob, old]))
    cases.append(case("both-broken", [put("level.dat", 0), put("level.dat_old", 0)] + LOAD + CLOSE, [variants["not-gzip"]]))
    cases.append(case("broken-no-old", [put("level.dat", 0)] + LOAD + CLOSE, [variants["not-gzip"]]))
    cases.append(case("broken-then-saved", [put("level.dat", 0), put("level.dat_old", 1)] + LOAD + [["save"]] + CLOSE, [variants["not-gzip"], old]))
    return cases


def versions():
    """The version checks `Main` makes before a world loads, as its summary reads them."""
    def check(name, **fields):
        return case(name, [put("level.dat", 0)] + LOAD + [["check"]] + CLOSE, [gzip(level(**fields))])

    version = {"Name": (STRING, "26.3"), "Id": (INT, 5023), "Series": (STRING, "main")}
    return [
        check("current", version=(INT, 19133), DataVersion=(INT, 5023), Version=(COMPOUND, version)),
        check("no-version", DataVersion=(INT, 5023)),
        check("format-0", version=(INT, 0), DataVersion=(INT, 5023)),
        check("format-negative", version=(INT, -5), DataVersion=(INT, 5023)),
        check("format-other", version=(INT, 19134), DataVersion=(INT, 5023)),
        check("format-string", version=(STRING, "19133"), DataVersion=(INT, 5023)),
        check("format-double", version=(DOUBLE, 19133.9), DataVersion=(INT, 5023)),
        check("format-long", version=(LONG, 19133 + (1 << 32)), DataVersion=(INT, 5023)),
        check("format-byte", version=(BYTE, 3), DataVersion=(INT, 5023)),
        check("mcregion", version=(INT, 19132), DataVersion=(INT, 5023)),
        check("series-other", version=(INT, 19133), DataVersion=(INT, 5023), Version=(COMPOUND, dict(version, Series=(STRING, "ooo")))),
        check("series-number", version=(INT, 19133), DataVersion=(INT, 5023), Version=(COMPOUND, dict(version, Series=(INT, 1)))),
        check("series-missing", version=(INT, 19133), DataVersion=(INT, 5023), Version=(COMPOUND, {"Id": (INT, 5023)})),
        check("version-not-compound", version=(INT, 19133), DataVersion=(INT, 5023), Version=(INT, 7)),
        check("version-empty", version=(INT, 19133), DataVersion=(INT, 5023), Version=(COMPOUND, {})),
        check("data-older", version=(INT, 19133), DataVersion=(INT, 4671), Version=(COMPOUND, version)),
        check("data-newer", version=(INT, 19133), DataVersion=(INT, 6000), Version=(COMPOUND, version)),
        check("data-missing", version=(INT, 19133), Version=(COMPOUND, version)),
        check("data-string", version=(INT, 19133), DataVersion=(STRING, "5023"), Version=(COMPOUND, version)),
        check("data-short", version=(INT, 19133), DataVersion=(SHORT, 5023), Version=(COMPOUND, version)),
        check("data-float", version=(INT, 19133), DataVersion=(FLOAT, 5023.5), Version=(COMPOUND, version)),
    ]


UUID = "069a79f4-44e9-4726-a5be-fca90e38aaf5"
PLAYER = f"players/data/{UUID}.dat"


def players():
    """A player's data read as they join: none yet, theirs, the old one when theirs can't be read,
    with a copy of theirs kept, and neither."""
    def player(**more):
        fields = {
            "DataVersion": (INT, 5023),
            "Health": (FLOAT, 20.0),
            "Pos": (LIST, (DOUBLE, [0.5, -60.0, 0.5])),
            "playerGameType": (INT, 0),
        }
        fields.update(more)
        return gzip(root(COMPOUND, fields))

    load = [["open"], ["player_load", UUID, "Notch"]]
    good = player()
    old = player(Health=(FLOAT, 7.5))
    broken = b"not a player"
    data = root(COMPOUND, {"DataVersion": (INT, 5023), "Health": (FLOAT, 1.0)})
    wrong_crc = gzip(data)[:-8] + struct.pack("<II", zlib.crc32(data) ^ 1, len(data))
    deep = gzip(bytes([COMPOUND]) + utf("") + (bytes([COMPOUND]) + utf("a")) * 600 + bytes([END]) * 601)
    return [
        case("player-new", load + CLOSE, []),
        case("player-saved", [put(PLAYER, 0)] + load + CLOSE, [good]),
        case("player-old-only", [put(PLAYER + "_old", 0)] + load + CLOSE, [old]),
        case("player-broken", [put(PLAYER, 0), put(PLAYER + "_old", 1)] + load + CLOSE, [broken, old]),
        case("player-both-broken", [put(PLAYER, 0), put(PLAYER + "_old", 0)] + load + CLOSE, [broken]),
        case("player-broken-no-old", [put(PLAYER, 0)] + load + CLOSE, [broken]),
        case("player-folder", [["dir", PLAYER], put(PLAYER + "_old", 0)] + load + CLOSE, [old]),
        case("player-root-list", [put(PLAYER, 0), put(PLAYER + "_old", 1)] + load + CLOSE, [gzip(root(LIST, (INT, [1]))), old]),
        case("player-deep", [put(PLAYER, 0), put(PLAYER + "_old", 1)] + load + CLOSE, [deep, old]),
        case("player-wrong-crc", [put(PLAYER, 0)] + load + CLOSE, [wrong_crc]),
        case("player-newer", [put(PLAYER, 0)] + load + CLOSE, [player(DataVersion=(INT, 6000))]),
        case("player-someone-else", [put("players/data/853c80ef-3c37-49fd-aa49-938b674adae6.dat", 0)] + load + CLOSE, [good]),
        case("player-data-is-a-file", [put("players/data", 0)] + load + CLOSE, [good]),
        case("player-twice", [put(PLAYER, 0)] + load + [["player_load", UUID, "Notch"]] + CLOSE, [good]),
    ]


WEATHER = "data/minecraft/weather.dat"


def saved():
    """Saved data read and written as SavedDataStorage does: gzipped or not, as its first two bytes
    say, files that can't be read, a path whose `..` leaves the folder, a dimension's folder, and
    saves over files, folders in the way and files where folders go."""
    def file(data=None, version=5023, **more):
        fields = {}
        if data is not None:
            fields["data"] = data
        if version is not None:
            fields["DataVersion"] = (INT, version)
        fields.update(more)
        return root(COMPOUND, fields)

    weather = (COMPOUND, {"clear_weather_time": (INT, 0), "raining": (BYTE, 1), "rain_time": (INT, 1200)})
    gz = gzip(file(weather))
    plain = file(weather)
    deep = gzip(bytes([COMPOUND]) + utf("") + (bytes([COMPOUND]) + utf("a")) * 600 + bytes([END]) * 601)

    def load(folder="", id="minecraft:weather"):
        return ["saved_load", folder, id]

    def save(blob, folder="", id="minecraft:weather"):
        return ["saved_save", folder, id, blob]

    def any_tag(kind, v):
        return bytes([kind]) + payload(kind, v)

    open_ = [["open"]]
    return [
        case("saved-data-none", open_ + [load()] + CLOSE, []),
        case("saved-data-gzipped", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gz]),
        case("saved-data-plain", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [plain]),
        case("saved-data-no-data", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gzip(file())]),
        case("saved-data-int-data", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gzip(file((INT, 7)))]),
        case("saved-data-newer", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gzip(file(weather, 6000))]),
        case("saved-data-more-fields", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gzip(file(weather, extra=(STRING, "kept")))]),
        case("saved-data-trailing", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [plain + b"after"]),
        case("saved-data-broken", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [b"not saved data"]),
        case("saved-data-broken-gzip", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [bytes([0x1F, 0x8B, 8, 0]) + b"junk"]),
        case("saved-data-cut-off", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [plain[:-3]]),
        case("saved-data-empty", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [b""]),
        case("saved-data-one-byte", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [bytes([COMPOUND])]),
        case("saved-data-end", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [bytes([END])]),
        case("saved-data-root-list", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [gzip(root(LIST, (INT, [1])))]),
        case("saved-data-deep", [put(WEATHER, 0)] + open_ + [load()] + CLOSE, [deep]),
        case("saved-data-folder", [["dir", WEATHER]] + open_ + [load()] + CLOSE, []),
        case("saved-data-namespace", [put("data/calcite/thing.dat", 0)] + open_ + [load(id="calcite:thing")] + CLOSE, [gz]),
        case("saved-data-nested", [put("data/minecraft/maps/last_id.dat", 0)] + open_ + [load(id="minecraft:maps/last_id")] + CLOSE, [gzip(file((COMPOUND, {"map": (INT, 3)})))]),
        case("saved-data-out", [put("level.dat", 0)] + open_ + [load(id="minecraft:../../level")] + CLOSE, [gz]),
        case("saved-data-dimension", [put("dimensions/minecraft/the_nether/data/minecraft/chunk_tickets.dat", 0)] + open_ + [load("minecraft:the_nether", "minecraft:chunk_tickets")] + CLOSE, [gz]),
        case("saved-data-other-dimension", [put("dimensions/minecraft/the_nether/data/minecraft/chunk_tickets.dat", 0)] + open_ + [load("minecraft:overworld", "minecraft:chunk_tickets")] + CLOSE, [gz]),
        case("saved-data-save", open_ + [save(0)] + CLOSE, [any_tag(*weather)]),
        case("saved-data-save-int", open_ + [save(0)] + CLOSE, [any_tag(INT, 5)]),
        case("saved-data-save-over", [put(WEATHER, 0)] + open_ + [save(1)] + CLOSE, [plain, any_tag(*weather)]),
        case("saved-data-save-then-load", open_ + [save(0), load()] + CLOSE, [any_tag(*weather)]),
        case("saved-data-save-nested", open_ + [save(0, id="minecraft:maps/last_id")] + CLOSE, [any_tag(COMPOUND, {"map": (INT, 3)})]),
        case("saved-data-save-dimension", open_ + [save(0, "minecraft:the_end", "minecraft:raids")] + CLOSE, [any_tag(*weather)]),
        case("saved-data-save-folder-in-way", [["dir", WEATHER]] + open_ + [save(0)] + CLOSE, [any_tag(*weather)]),
        case("saved-data-save-file-in-way", [put("data/minecraft", 0)] + open_ + [save(1)] + CLOSE, [b"a file", any_tag(*weather)]),
        case("saved-data-save-data-is-a-file", [put("data", 0)] + open_ + [save(1)] + CLOSE, [b"a file", any_tag(*weather)]),
        case("saved-data-save-out", open_ + [save(0, id="minecraft:../../level")] + CLOSE, [any_tag(*weather)]),
    ]


def main():
    cases = folders() + broken() + versions() + players() + saved()
    write_file(HERE / "generated.json", "world_folder", "cases/world_folder/gen.py", cases, probe_version=3)


if __name__ == "__main__":
    main()
