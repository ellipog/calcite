"""Writes cases/packs/generated.json: a world's data packs found and picked as a server starting
finds and picks them, by vanilla's ServerPacksSource and MinecraftServer.configurePackRepository,
then their files listed by a MultiPackResourceManager over the picked packs, or the registries
loaded from them by RegistryDataLoader.

    py -I cases/packs/gen.py

Each case makes the world's `datapacks` folder, with folder packs, zips and entries that aren't
packs, then picks: as a new world does, from server.properties' `initial-enabled-packs` and
`initial-disabled-packs`, or as an old world does, from what its level.dat has on and off and its
feature flags, with or without `--safeMode`. Then it lists a folder of the picked packs' files,
which shows which pack's file wins, what filters hide and which overlays apply. Or it loads the
world's registries from them, which shows what's logged, whether they load and what each
synchronized entry sends a client.

An entry a case loads is read by vanilla with its registry's codec for the server and by Calcite
with its codec for the network, which leaves out what only the server uses. So the entries are
in registries whose two codecs read the same fields, or keep to those they share, and a broken
one is broken in a field both read.

Making a link takes a privilege Windows doesn't give everyone, so the cases with links are
Linux's. And vanilla finds what's in a folder in the order the file system lists it, so a folder
with more than one entry that logs something logs it in that order. NTFS lists a folder in the
same order on every machine, by its names; a Linux file system needn't (ext4 lists by a hash of
each name with a seed of each file system's own). So such cases are Windows', named `windows-`,
and the others keep to one entry that logs in each folder.
"""

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402
from deflate import deflate as deflated  # noqa: E402

VANILLA = "minecraft:vanilla"
REBALANCE = "minecraft:trade_rebalance"
REDSTONE = "minecraft:redstone_experiments"
MINECART = "minecraft:minecart_improvements"


def b64(data):
    return base64.b64encode(bytes(data)).decode()


def meta(description="a pack", lo=121, hi=121, **more):
    pack = {"description": description, "min_format": lo, "max_format": hi}
    data = {"pack": pack}
    data.update(more)
    return json.dumps(data)


def rebalance_meta():
    return meta(features={"enabled": [REBALANCE]})


# The time each file in a zip says it was written, fixed so the cases come out the same on every
# run: the time the committed ones were first written.
WRITTEN = (2026, 11, 1, 3, 19, 0)


def dos_time(t):
    year, month, day, hour, minute, second = t
    return hour << 11 | minute << 5 | second // 2, (year - 1980) << 9 | month << 5 | day


def zipped(files, deflate=True):
    """A zip of the files, each a name and its text or bytes, as Java's zip tools would read it,
    laid out as Python's zipfile lays one out on Windows. Written here, not by zipfile, so that
    it's the same on every machine: zipfile marks each entry with the system it ran on, and
    deflates with whichever zlib Python has, where rig/runner/deflate.py doesn't."""
    out = bytearray()
    central = bytearray()
    for name, data in files:
        data = data.encode() if isinstance(data, str) else bytes(data)
        folder = name.endswith("/")
        # Folders as `writestr(ZipInfo(name), b"")` makes them: stored, at 1980's start.
        method = 8 if deflate and not folder else 0
        when = dos_time((1980, 1, 1, 0, 0, 0) if folder else WRITTEN)
        attributes = 0o600 << 16
        stored = deflated(data) if method == 8 else data
        encoded = name.encode("ascii", "strict") if name.isascii() else name.encode("utf-8")
        flags = 0 if name.isascii() else 0x800
        crc = zlib.crc32(data)
        common = struct.pack("<HHHHHIIIHH", 20, flags, method, when[0], when[1], crc, len(stored), len(data), len(encoded), 0)
        offset = len(out)
        out += struct.pack("<I", 0x04034B50) + common + encoded + stored
        central += struct.pack("<IH", 0x02014B50, 20) + common + struct.pack("<HHHII", 0, 0, 0, attributes, offset) + encoded
    start = len(out)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(files), len(files), len(central), start, 0)
    return bytes(out)


class Case:
    """A case being built: its operations and blobs."""

    def __init__(self, name):
        self.name = name
        self.ops = []
        self.blobs = []
        self.system = None

    def blob(self, data):
        self.blobs.append(b64(data.encode() if isinstance(data, str) else data))
        return len(self.blobs) - 1

    def put(self, path, data):
        self.ops.append(["put", path, self.blob(data)])
        return self

    def dir(self, path):
        self.ops.append(["dir", path])
        return self

    def link(self, path, target):
        self.ops.append(["link", path, target])
        self.system = "linux"
        return self

    def windows(self):
        """Only on Windows, for a folder whose entries log in the order NTFS lists them."""
        self.system = "windows"
        return self

    def allow(self, text):
        self.ops.append(["allow", self.blob(text)])
        return self

    def folder_pack(self, name, mcmeta, files=()):
        self.put(f"datapacks/{name}/pack.mcmeta", mcmeta)
        for path, data in files:
            self.put(f"datapacks/{name}/{path}", data)
        return self

    def zip_pack(self, name, files, deflate=True):
        return self.put(f"datapacks/{name}", zipped(files, deflate))

    def pick(self, enabled, disabled, features, init, safe=False):
        self.ops.append(["pick", {"enabled": enabled, "disabled": disabled, "features": features, "init": init, "safe": safe}])
        return self

    def list(self, folder="dimension_type", suffix=".json"):
        self.ops.append(["list", folder, suffix])
        return self

    def load(self):
        self.ops.append(["load"])
        return self

    def done(self):
        c = {"id": self.name, "input": {"ops": self.ops}}
        if self.blobs:
            c["blobs"] = self.blobs
        if self.system:
            c["system"] = self.system
        return c


def new_world(c):
    """As a new world picks, with server.properties' defaults."""
    return c.pick(["vanilla"], [""], [VANILLA], True)


def world_of_packs(name):
    """A folder pack, a zip, a pack that needs trade_rebalance, and an empty zip, which isn't one.

    Only the empty zip logs as the packs are found, so what it logs is in the same order on any
    file system.
    """
    c = Case(name)
    c.folder_pack("a_folder", meta(), [("data/minecraft/dimension_type/a.json", "a")])
    c.zip_pack("b.zip", [("pack.mcmeta", meta()), ("data/minecraft/dimension_type/b.json", "b")])
    c.put("datapacks/d.zip", b"")
    c.folder_pack("f", rebalance_meta(), [("data/minecraft/dimension_type/f.json", "f")])
    return c


def picking():
    cases = []
    # Nothing in the folder, which is made.
    cases.append(new_world(Case("new-world-no-folder")).list().done())
    cases.append(Case("new-world-empty-folder").dir("datapacks").pick(["vanilla"], [""], [VANILLA], True).list().done())
    cases.append(new_world(world_of_packs("new-world-packs")).list().done())
    cases.append(world_of_packs("new-world-none-on").pick([""], [""], [VANILLA], True).list().done())
    cases.append(world_of_packs("new-world-all-off").pick(["vanilla"], ["vanilla", "file/a_folder", "file/b.zip", "file/f"], [VANILLA], True).list().done())
    cases.append(world_of_packs("new-world-feature-pack-on").pick(["vanilla", "trade_rebalance"], [""], [VANILLA], True).list().done())
    cases.append(world_of_packs("new-world-safe").pick(["vanilla", "file/a_folder"], [""], [VANILLA], True, safe=True).list().done())
    # An old world, from what its level.dat says.
    cases.append(world_of_packs("old-world-forced-feature").pick(["vanilla", "file/gone"], ["file/b.zip", "file/f"], [VANILLA, REBALANCE], False).list().done())
    cases.append(world_of_packs("old-world-without-feature").pick(["vanilla", "file/f", "file/a_folder"], ["file/b.zip"], [VANILLA], False).list().done())
    cases.append(world_of_packs("old-world-new-pack-needs-feature").pick(["vanilla"], ["file/a_folder", "file/b.zip"], [VANILLA], False).list().done())
    cases.append(world_of_packs("old-world-no-features").pick(["vanilla"], ["file/a_folder", "file/b.zip"], [], False).list().done())
    cases.append(world_of_packs("old-world-no-features-other-packs").pick(["vanilla", "file/a_folder"], [], [], False).list().done())
    cases.append(world_of_packs("old-world-vanilla-off").pick(["file/a_folder"], ["vanilla"], [VANILLA], False).list().done())
    cases.append(world_of_packs("old-world-vanilla-on-top").pick(["file/a_folder", "file/b.zip", "vanilla"], [], [VANILLA], False).list().done())
    cases.append(world_of_packs("old-world-twice").pick(["vanilla", "file/a_folder", "file/a_folder", "vanilla", "file/b.zip"], ["file/a_folder"], [VANILLA], False).list().done())
    cases.append(world_of_packs("old-world-all-features").pick(["vanilla"], [], [VANILLA, REBALANCE, REDSTONE, MINECART], False).list().done())
    cases.append(world_of_packs("old-world-feature-and-pack").pick(["vanilla", "file/f"], [], [VANILLA, REBALANCE], False).list().done())
    cases.append(world_of_packs("old-world-only-redstone").pick(["vanilla"], [], [REDSTONE], False).list().done())
    cases.append(world_of_packs("old-world-safe").pick(["vanilla", "file/a_folder"], [], [VANILLA, REBALANCE], False, safe=True).list().done())
    cases.append(world_of_packs("old-world-safe-no-features").pick(["file/a_folder"], ["vanilla"], [], False, safe=True).list().done())
    cases.append(world_of_packs("old-world-nothing-there").pick(["file/x", "file/y"], [], [VANILLA], False).list().done())
    return cases


def metadata():
    """Each pack.mcmeta in a folder pack of its own in a new world."""
    metas = {
        "plain": meta(),
        "translated": meta({"translate": "dataPack.vanilla.description"}),
        "styled": meta({"text": "red", "color": "red", "bold": True}),
        "list-description": meta(["a", {"text": "b", "italic": True}]),
        "empty-description": meta(""),
        "format-lists": meta(lo=[121, 0], hi=[121, 5]),
        "format-wide": meta(lo=82, hi=1000),
        "too-old": meta(lo=82, hi=100),
        "too-new": meta(lo=122, hi=130),
        "minor-too-new": meta(lo=[121, 1], hi=[121, 9]),
        "old-style": json.dumps({"pack": {"description": "old", "pack_format": 15}}),
        "old-style-supported": json.dumps({"pack": {"description": "old", "pack_format": 15, "supported_formats": [15, 81]}}),
        "old-style-new-format": json.dumps({"pack": {"description": "old", "pack_format": 121}}),
        "both-styles": json.dumps({"pack": {"description": "both", "pack_format": 81, "supported_formats": [15, 81], "min_format": 15, "max_format": 121}}),
        "only-min": json.dumps({"pack": {"description": "min", "min_format": 121}}),
        "only-max": json.dumps({"pack": {"description": "max", "max_format": 121}}),
        "min-above-max": meta(lo=121, hi=100),
        "no-description": json.dumps({"pack": {"min_format": 121, "max_format": 121}}),
        "no-pack": json.dumps({"features": {"enabled": [VANILLA]}}),
        "empty-object": "{}",
        "features-vanilla": meta(features={"enabled": [VANILLA]}),
        "features-several": meta(features={"enabled": [REDSTONE, REBALANCE, MINECART]}),
        "features-none": meta(features={"enabled": []}),
        "features-unknown": meta(features={"enabled": ["minecraft:nope"]}),
        "features-unknown-and-known": meta(features={"enabled": [REBALANCE, "calcite:nope", MINECART]}),
        "extra-sections": meta(language={}, calcite={"x": 1}),
    }
    cases = []
    for name, text in metas.items():
        c = Case(f"meta-{name}").folder_pack("p", text, [("data/minecraft/dimension_type/p.json", name)])
        cases.append(new_world(c).list().done())
    # Several at once, each one's lines in the order the packs are found, which is the file
    # system's.
    c = Case("windows-meta-several").windows()
    for name in ("too-old", "no-pack", "features-unknown", "plain", "too-new"):
        c.folder_pack(name, metas[name])
    cases.append(new_world(c).done())
    c = Case("windows-meta-in-zips").windows()
    for name in ("too-old", "no-pack", "features-unknown", "plain", "old-style"):
        c.zip_pack(f"{name}.zip", [("pack.mcmeta", metas[name])])
    cases.append(new_world(c).done())
    return cases


def files():
    """What the picked packs' files are, listed: which pack's wins, filters and overlays."""
    cases = []
    over = [("data/minecraft/dimension_type/overworld.json", "mine"), ("data/minecraft/dimension_type/extra.json", "extra")]
    cases.append(new_world(Case("files-override-vanilla").folder_pack("p", meta(), over)).list().done())
    cases.append(new_world(Case("files-override-in-zip").zip_pack("p.zip", [("pack.mcmeta", meta())] + over)).list().done())
    cases.append(new_world(Case("files-stored-zip").zip_pack("p.zip", [("pack.mcmeta", meta())] + over, deflate=False)).list().done())
    cases.append(new_world(Case("files-zip-with-folders").zip_pack("p.zip", [("pack.mcmeta", meta()), ("data/", ""), ("data/minecraft/", ""), ("data/minecraft/dimension_type/", "")] + over)).list().done())
    # Two packs with the same file: the later, `file/b`, wins.
    two = Case("files-later-wins").folder_pack("a", meta(), [("data/minecraft/dimension_type/x.json", "from a")]).folder_pack("b", meta(), [("data/minecraft/dimension_type/x.json", "from b")])
    cases.append(new_world(two).list().done())
    two = Case("files-order-picked").folder_pack("a", meta(), [("data/minecraft/dimension_type/x.json", "from a")]).folder_pack("b", meta(), [("data/minecraft/dimension_type/x.json", "from b")])
    cases.append(two.pick(["vanilla", "file/b", "file/a"], [], [VANILLA], False).list().done())
    # Namespaces, folders in the folder listed, and files that aren't JSON.
    many = [
        ("data/calcite/dimension_type/z.json", "z"),
        ("data/a/dimension_type/deep/er/y.json", "y"),
        ("data/minecraft/dimension_type/n.txt", "not json"),
        ("data/minecraft/dimension_type.json", "not in it"),
        ("data/minecraft/dimension_type_x/q.json", "not in it either"),
        ("data/minecraft/dimension_type/m.json.mcmeta", "metadata"),
        ("data/minecraft/dimension_type/m.json", "m"),
    ]
    cases.append(new_world(Case("files-namespaces").folder_pack("p", meta(), many)).list().list("dimension_type", ".txt").list("dimension_type", "").done())
    cases.append(new_world(Case("files-namespaces-zip").zip_pack("p.zip", [("pack.mcmeta", meta())] + many)).list().list("dimension_type", ".txt").done())
    # Paths and namespaces that can't be identifiers: one of each in a folder pack, all of them
    # in one, whose lines are in the order NTFS lists them, and all of them in a zip, whose lines
    # are in the zip's order.
    ok = ("data/minecraft/dimension_type/ok.json", "ok")
    bad = [
        ("data/minecraft/dimension_type/Upper.json", "u"),
        ("data/minecraft/dimension_type/sp ace.json", "s"),
        ok,
        ("data/Bad/dimension_type/x.json", "bad namespace"),
        ("data/sp ace/dimension_type/x.json", "bad namespace"),
    ]
    for name, path in (("path-upper", "data/minecraft/dimension_type/Upper.json"), ("path-space", "data/minecraft/dimension_type/sp ace.json"),
                       ("namespace-upper", "data/Bad/dimension_type/x.json"), ("namespace-space", "data/sp ace/dimension_type/x.json")):
        cases.append(new_world(Case(f"files-bad-{name}").folder_pack("p", meta(), [(path, "bad"), ok])).list().list("worldgen", ".json").done())
    cases.append(new_world(Case("windows-files-bad-names").windows().folder_pack("p", meta(), bad)).list().list("worldgen", ".json").done())
    cases.append(new_world(Case("files-bad-names-zip").zip_pack("p.zip", [("pack.mcmeta", meta())] + bad)).list().list("worldgen", ".json").done())
    # A filter hides what's below it.
    flt = {"block": [{"namespace": "minecraft", "path": "dimension_type/overworld.*"}]}
    cases.append(new_world(Case("filter-hides-vanilla").folder_pack("p", meta(filter=flt), [("data/minecraft/dimension_type/mine.json", "mine")])).list().done())
    cases.append(new_world(Case("filter-hides-own-not").folder_pack("p", meta(filter=flt), [("data/minecraft/dimension_type/overworld_caves.json", "own")])).list().done())
    cases.append(new_world(Case("filter-namespace-only").folder_pack("p", meta(filter={"block": [{"namespace": "minecraft"}]}), [("data/calcite/dimension_type/c.json", "c")])).list().done())
    cases.append(new_world(Case("filter-path-only").folder_pack("p", meta(filter={"block": [{"path": "dimension_type/the_.*"}]}), [])).list().done())
    cases.append(new_world(Case("filter-empty").folder_pack("p", meta(filter={"block": []}), [])).list().done())
    cases.append(new_world(Case("filter-bad").folder_pack("p", meta(filter={"block": "no"}), [])).list().done())
    cases.append(new_world(Case("filter-in-zip").zip_pack("p.zip", [("pack.mcmeta", meta(filter=flt))])).list().done())
    below = Case("filter-below-not").folder_pack("a", meta(), [("data/minecraft/dimension_type/overworld.json", "a")]).folder_pack("b", meta(filter=flt), [])
    cases.append(below.pick(["vanilla", "file/b", "file/a"], [], [VANILLA], False).list().done())
    # Overlays, which apply if their formats take 26.3's, the last listed on top.
    ov = {"entries": [{"directory": "one", "min_format": 121, "max_format": 121}, {"directory": "old", "min_format": 82, "max_format": 100}, {"directory": "two", "min_format": [121, 0], "max_format": 200}]}
    ofiles = [
        ("data/minecraft/dimension_type/base.json", "base"),
        ("data/minecraft/dimension_type/x.json", "base x"),
        ("one/data/minecraft/dimension_type/x.json", "one x"),
        ("one/data/minecraft/dimension_type/y.json", "one y"),
        ("two/data/minecraft/dimension_type/y.json", "two y"),
        ("old/data/minecraft/dimension_type/x.json", "old x"),
        ("old/data/minecraft/dimension_type/old.json", "old"),
    ]
    cases.append(new_world(Case("overlays").folder_pack("p", meta(overlays=ov), ofiles)).list().done())
    cases.append(new_world(Case("overlays-zip").zip_pack("p.zip", [("pack.mcmeta", meta(overlays=ov))] + ofiles)).list().done())
    cases.append(new_world(Case("overlays-bad-name").folder_pack("p", meta(overlays={"entries": [{"directory": "Bad Name", "min_format": 121, "max_format": 121}]}), [])).list().done())
    cases.append(new_world(Case("overlays-missing-folder").folder_pack("p", meta(overlays={"entries": [{"directory": "gone", "min_format": 121, "max_format": 121}]}), [("data/minecraft/dimension_type/p.json", "p")])).list().done())
    return cases


def entries():
    """What in the folder is a pack: each entry with a pack beside it, then all of them at once,
    in the order NTFS lists them."""
    cases = []
    each = [
        ("upper-case", lambda c: c.folder_pack("Upper Case", meta())),
        ("folder-named-zip", lambda c: c.folder_pack("dotted.zip", meta())),
        ("upper-zip-suffix", lambda c: c.put("datapacks/notzip.ZIP", zipped([("pack.mcmeta", meta())]))),
        ("meta-inside-zip", lambda c: c.put("datapacks/inner.zip", zipped([("inner/pack.mcmeta", meta())]))),
        ("text-zip", lambda c: c.put("datapacks/text.zip", "not a zip")),
        ("nested", lambda c: c.put("datapacks/nested/deeper/pack.mcmeta", meta())),
        ("loose-meta", lambda c: c.put("datapacks/pack.mcmeta", meta())),
        ("empty-folder", lambda c: c.dir("datapacks/empty")),
        ("text-file", lambda c: c.put("datapacks/c.txt", "c")),
    ]
    for name, make in each:
        c = Case(f"entries-{name}").folder_pack("p", meta(), [("data/minecraft/dimension_type/p.json", "p")])
        cases.append(new_world(make(c)).list().done())
    c = Case("windows-entries-mixed").windows()
    for _, make in each:
        make(c)
    cases.append(new_world(c).list().done())
    cases.append(new_world(Case("entries-folder-meta-is-folder").dir("datapacks/p/pack.mcmeta")).done())
    cases.append(new_world(Case("entries-datapacks-is-file").put("datapacks", "a file")).done())
    return cases


def links():
    """Links in the world's packs, checked against allowed_symlinks.txt as the packs are found."""
    cases = []
    out = [("pack.mcmeta", meta()), ("data/minecraft/dimension_type/o.json", "outside")]

    def outside(c):
        # A pack outside the world, in the universe's `outside`, made through the world: `put`
        # writes only in the world, so it goes in `world/outside` and the link leads there.
        for path, data in out:
            c.put(f"outside/{path}", data)
        return c

    cases.append(new_world(outside(Case("link-pack-forbidden")).link("datapacks/linked", "<folder>world/outside")).list().done())
    cases.append(new_world(outside(Case("link-pack-allowed")).link("datapacks/linked", "<folder>world/outside").allow("[prefix]<folder>")).list().done())
    c = Case("link-in-pack-forbidden").folder_pack("p", meta(), [("data/minecraft/dimension_type/p.json", "p")])
    c.put("elsewhere/x.json", "x").link("datapacks/p/data/minecraft/dimension_type/x.json", "<folder>world/elsewhere/x.json")
    cases.append(new_world(c).list().done())
    c = Case("link-in-pack-allowed").folder_pack("p", meta(), [("data/minecraft/dimension_type/p.json", "p")])
    c.put("elsewhere/x.json", "x").link("datapacks/p/data/minecraft/dimension_type/x.json", "<folder>world/elsewhere/x.json").allow("[prefix]<folder>")
    cases.append(new_world(c).list().done())
    c = Case("link-zip-allowed").put("elsewhere/p.zip", zipped(out)).link("datapacks/p.zip", "<folder>world/elsewhere/p.zip").allow("[prefix]<folder>")
    cases.append(new_world(c).list().done())
    c = Case("link-zip-forbidden").put("elsewhere/p.zip", zipped(out)).link("datapacks/p.zip", "<folder>world/elsewhere/p.zip")
    cases.append(new_world(c).list().done())
    cases.append(new_world(Case("link-dangling").link("datapacks/gone", "<folder>nowhere").allow("[prefix]<folder>")).done())
    return cases


def painting(width=1, height=1, asset="w:a", **more):
    data = {"width": width, "height": height, "asset_id": asset}
    data.update(more)
    return json.dumps(data)


def damage(message="d", scaling="never", exhaustion=0.0, **more):
    data = {"message_id": message, "scaling": scaling, "exhaustion": exhaustion}
    data.update(more)
    return json.dumps(data)


def dimension(**more):
    """A dimension type with what it must have and no environment attributes, which only the
    server's codec reads all of."""
    data = {
        "has_skylight": True,
        "has_ceiling": False,
        "has_ender_dragon_fight": False,
        "coordinate_scale": 1.0,
        "min_y": 0,
        "height": 256,
        "logical_height": 256,
        "infiniburn": "#minecraft:infiniburn_overworld",
        "ambient_light": 0.0,
        "monster_spawn_light_level": 0,
        "monster_spawn_block_light_limit": 0,
    }
    data.update(more)
    return json.dumps(data)


def enchantment(*paths):
    """An enchantment with an effect for each of `paths`, whose chance is a number from command
    storage at that path, as `NbtPathArgument` reads it (CAL-78)."""
    effects = [{
        "affected": "attacker",
        "enchanted": "victim",
        "effect": {"type": "minecraft:change_item_damage", "amount": 1.0},
        "requirements": {"type": "minecraft:random_chance", "chance": {"type": "minecraft:storage", "storage": "w:s", "path": p}},
    } for p in paths]
    return json.dumps({
        "anvil_cost": 1,
        "description": "e",
        "effects": {"minecraft:post_attack": effects},
        "max_cost": {"base": 1, "per_level_above_first": 0},
        "max_level": 1,
        "min_cost": {"base": 1, "per_level_above_first": 0},
        "slots": ["any"],
        "supported_items": "#minecraft:enchantable/weapon",
        "weight": 1,
    })


def effects_enchantment(effects):
    """An enchantment with `effects`, each component's list of conditional effects (CAL-79)."""
    return json.dumps({
        "anvil_cost": 1,
        "description": "e",
        "effects": effects,
        "max_cost": {"base": 1, "per_level_above_first": 0},
        "max_level": 1,
        "min_cost": {"base": 1, "per_level_above_first": 0},
        "slots": ["any"],
        "supported_items": "#minecraft:enchantable/weapon",
        "weight": 1,
    })


def conditional(component, *requirements):
    """`component`'s list of effects, one for each of `requirements`, with an effect of the kind
    the component holds."""
    if component in ("tick", "hit_block", "location_changed", "post_piercing_attack", "post_attack"):
        effect = {"type": "minecraft:change_item_damage", "amount": 1.0}
    else:
        effect = {"type": "minecraft:add", "value": 1.0}
    if component == "post_attack":
        return [{"enchanted": "attacker", "affected": "victim", "effect": effect, "requirements": r} for r in requirements]
    return [{"effect": effect, "requirements": r} for r in requirements]


def check(kind, **fields):
    return {"type": f"minecraft:{kind}", **fields}


# A positional environment attribute, which needs `origin`.
POSITIONAL = {"type": "minecraft:environment_attribute", "attribute": "minecraft:gameplay/turtle_egg_hatch_chance"}

# Conditions an effect's context doesn't have the parameters for, by component, each failing to
# load as vanilla's `validatedListCodec` fails it.
BAD_REQUIREMENTS = {
    "tool-in-damage": {"minecraft:damage": conditional("damage", check("match_tool"))},
    "origin-in-item": {"minecraft:item_damage": conditional("item_damage", check("location_check"))},
    "killer-in-tick": {"minecraft:tick": conditional("tick", check("killed_by_player"))},
    "explosion-in-post-attack": {"minecraft:post_attack": conditional("post_attack", check("survives_explosion"))},
    "active-in-tick": {"minecraft:tick": conditional("tick", check("enchantment_active_check", active=True))},
    "attacker-in-tick": {"minecraft:tick": conditional("tick", check("entity_properties", entity="attacker"))},
    "block-entity-in-hit-block": {"minecraft:hit_block": conditional("hit_block", check("match_block", nbt="{a:1b}"))},
    "bonus-in-item": {"minecraft:block_experience": conditional("block_experience", check("random_chance_with_enchanted_bonus", unenchanted_chance=0.5, enchanted_chance=0.5, enchantment="minecraft:sharpness"))},
    "inverted": {"minecraft:item_damage": conditional("item_damage", check("inverted", term=check("survives_explosion")))},
    "all-of": {"minecraft:tick": conditional("tick", check("all_of", terms=[check("location_check"), check("killed_by_player")]))},
    "one-term": {"minecraft:tick": conditional("tick", check("any_of", terms=check("match_tool")))},
    "three-terms": {"minecraft:tick": conditional("tick", check("all_of", terms=[check("match_tool"), check("killed_by_player"), check("survives_explosion")]))},
    "two-effects": {"minecraft:fishing_luck_bonus": conditional("fishing_luck_bonus", check("match_tool"), check("weather_check"), check("survives_explosion"))},
    "two-components": {
        "minecraft:damage": conditional("damage", check("match_tool")),
        "minecraft:ammo_use": conditional("ammo_use", check("killed_by_player")),
    },
    "attribute-value": {"minecraft:item_damage": conditional("item_damage", check("float_value_check", value=POSITIONAL, test={"min": 0.0}))},
    "attribute-range": {"minecraft:item_damage": conditional("item_damage", check("float_value_check", value=1.0, test={"min": POSITIONAL, "max": {"type": "minecraft:add", "inputs": [1.0, POSITIONAL]}}))},
    "empty-inputs": {"minecraft:tick": conditional("tick", check("float_value_check", value={"type": "minecraft:max", "inputs": []}, test=1.0))},
    "score-target": {"minecraft:tick": conditional("tick", check("int_value_check", value={"type": "minecraft:score", "target": "attacker", "score": "s"}, test=1))},
    "time-range": {"minecraft:item_damage": conditional("item_damage", check("time_check", clock="minecraft:overworld", value={"min": {"type": "minecraft:environment_attribute", "attribute": "minecraft:gameplay/turtle_egg_hatch_chance"}}))},
    "time-line": {"minecraft:item_damage": conditional("item_damage", check("time_check", clock="minecraft:overworld", value={"min": 1, "max": {"type": "minecraft:score", "target": "attacker", "score": "s"}}))},
    "conditional-number": {"minecraft:tick": conditional("tick", check("int_value_check", value={"type": "minecraft:conditional", "condition": check("match_tool"), "on_true": 1}, test=1))},
    "dispatcher": {"minecraft:item_damage": conditional("item_damage", check("float_value_check", value={"type": "minecraft:number_dispatcher", "cases": [{"condition": check("weather_check"), "value": 1.0}, {"condition": check("killed_by_player"), "value": 2.0}], "default": {"type": "minecraft:abs", "input": POSITIONAL}}, test=1.0))},
    "scores": {"minecraft:item_damage": conditional("item_damage", check("entity_scores", entity="this", scores={"a": {"min": {"type": "minecraft:score", "target": "this", "score": "a"}}}))},
}

# Conditions their contexts have the parameters for, or that vanilla doesn't check, which load.
ALLOWED_REQUIREMENTS = {
    "minecraft:damage": conditional("damage", check("damage_source_properties"), check("entity_properties", entity="attacker"), check("location_check")),
    "minecraft:item_damage": conditional("item_damage", check("match_tool"), check("weather_check"), check("float_value_check", value={"type": "minecraft:enchantment_level", "amount": 1.0}, test={"min": 1.0})),
    "minecraft:hit_block": conditional("hit_block", check("match_block"), check("location_check")),
    "minecraft:location_changed": conditional("location_changed", check("enchantment_active_check", active=True)),
    # `random_chance` checks nothing of its chance, so a chance that needs `origin` loads anywhere.
    "minecraft:block_experience": conditional("block_experience", check("random_chance", chance=POSITIONAL)),
    "minecraft:tick": conditional("tick", check("float_value_check", value={"type": "minecraft:environment_attribute", "attribute": "minecraft:gameplay/sky_light_level"}, test=1.0)),
}


# NBT paths that don't read, by what's wrong with them.
BAD_PATHS = {
    "double-dot": "a..b",
    "no-dot": "a]",
    "after-index": "[0]x",
    "not-an-index": "[x]",
    "fraction-index": "[1.5]",
    "unclosed-index": "[1",
    "unclosed-pattern-index": "[{a:1}",
    "empty-name": '""',
    "unclosed-quote": '"abc',
    "bad-escape": '"a\\x"',
    "bad-pattern": "abc{a:1",
    "pattern-not-first": "a.{b:1}",
    "two-roots": "{a:1}{b:2}",
    "ends-in-bracket": "[",
    "ends-in-bracket-after": "a[",
}


def tag(*values, replace=None):
    data = {"values": list(values)}
    if replace is not None:
        data["replace"] = replace
    return json.dumps(data)


def cat(*conditions, **more):
    """A cat variant, with `conditions` as its spawn conditions, unless `more` gives them."""
    fields = {"asset_id": "w:entity/cat/c", "baby_asset_id": "w:entity/cat/c_baby"}
    fields["spawn_conditions"] = list(conditions)
    fields.update(more)
    return json.dumps({k: v for k, v in fields.items() if v is not None})


def void_biome(features=None, carvers=None):
    """Vanilla's `the_void`, with `features` in its last step and `carvers`."""
    steps = [[] for _ in range(10)] + [features if features is not None else ["minecraft:void_start_platform"]]
    return json.dumps({
        "attributes": {"minecraft:visual/sky_color": "#7ba4ff"},
        "carvers": carvers if carvers is not None else [],
        "downfall": 0.5,
        "effects": {"water_color": "#3f76e4"},
        "features": steps,
        "has_precipitation": False,
        "temperature": 0.5,
    })


def loading():
    """The registries loaded from the picked packs, in a new world with one folder pack, `p`."""
    cases = [new_world(Case("load-vanilla")).load().done()]
    cases.append(Case("load-feature-pack").pick(["vanilla", "trade_rebalance"], [""], [VANILLA], True).load().done())

    def world(name, files, mcmeta=None):
        return new_world(Case(name).folder_pack("p", mcmeta or meta(), files)).load().done()

    # New entries in several registries and namespaces, in vanilla's order of identifiers, by
    # path and then namespace, among vanilla's.
    cases.append(world("load-new-entries", [
        ("data/w/painting_variant/a.json", painting(2, 1, "w:a", title={"text": "A", "color": "gold"}, author="me")),
        ("data/w/painting_variant/b.json", painting(16, 16, "b")),
        ("data/a/painting_variant/z.json", painting(1, 2, "a:z", title=["x", {"text": "y", "italic": True}])),
        ("data/w/banner_pattern/x.json", json.dumps({"asset_id": "w:x", "translation_key": "block.w.x"})),
        ("data/w/damage_type/d.json", damage("d", "never", 0.5)),
        ("data/w/damage_type/e.json", damage("e", "always", 0, effects="burning", death_message_type="fall_variants")),
        ("data/w/jukebox_song/s.json", json.dumps({"sound_event": "minecraft:music_disc.cat", "description": {"translate": "jukebox_song.w.s"}, "length_in_seconds": 12.5, "comparator_output": 3})),
        ("data/w/jukebox_song/t.json", json.dumps({"sound_event": {"sound_id": "w:t", "range": 16.0}, "description": "T", "length_in_seconds": 1, "comparator_output": 15})),
        ("data/w/world_clock/c.json", "{}"),
        ("data/w/timeline/t.json", json.dumps({"clock": "w:c", "period_ticks": 100, "time_markers": {"w:m": 5, "w:n": {"ticks": 7, "show_in_commands": True}}})),
        ("data/w/timeline/u.json", json.dumps({"clock": "minecraft:overworld"})),
        ("data/w/tags/timeline/all.json", tag("w:t", {"id": "w:gone", "required": False})),
        ("data/w/dimension_type/d.json", dimension(timelines="#w:all", default_clock="w:c")),
        ("data/w/dimension_type/e.json", dimension(timelines=["w:t", "w:u"], min_y=-64, height=384, logical_height=384, coordinate_scale=8, has_ceiling=True)),
    ]))
    # Vanilla's own entries, from the world's pack instead, which a client is sent.
    cases.append(world("load-override", [
        ("data/minecraft/painting_variant/kebab.json", painting(3, 3, "minecraft:kebab")),
        ("data/minecraft/damage_type/generic.json", damage("generic", "never", 0.0)),
        ("data/minecraft/dimension_type/overworld.json", dimension()),
    ]))
    # What a codec has a default for, given, which isn't written; and numbers in other shapes.
    cases.append(world("load-defaults-given", [
        ("data/w/damage_type/d.json", damage("d", "when_caused_by_living_non_player", 1, effects="hurt", death_message_type="default")),
        ("data/w/dimension_type/d.json", dimension(has_fixed_time=False, skybox="overworld", cardinal_light="default", timelines=[], attributes={})),
        ("data/w/timeline/t.json", json.dumps({"clock": "minecraft:overworld", "tracks": {}, "time_markers": {}})),
        ("data/w/painting_variant/p.json", painting(2.0, 1.5, "w:p")),
        ("data/w/jukebox_song/s.json", json.dumps({"sound_event": "minecraft:music_disc.cat", "description": "s", "length_in_seconds": 3e2, "comparator_output": 1.9})),
    ]))
    # Tags of the world's: a synchronized registry's, which may name what's optional and missing,
    # and a built-in one's that names a block there isn't, which is logged, and isn't built.
    cases.append(world("load-world-tags", [
        ("data/w/painting_variant/a.json", painting()),
        ("data/w/tags/painting_variant/t.json", tag("w:a", "#minecraft:placeable", {"id": "w:gone", "required": False}, {"id": "#w:nope", "required": False})),
        ("data/minecraft/tags/painting_variant/placeable.json", tag("w:a")),
        ("data/w/tags/block/bad.json", tag("minecraft:stone", "minecraft:nope")),
        ("data/w/tags/block/good.json", tag("minecraft:stone", {"id": "minecraft:nope", "required": False})),
    ]))

    # What stops the registries loading.
    bad = "data/w/painting_variant/bad.json"
    broken = {
        "bad-json": [(bad, "{")],
        "not-json": [(bad, "not json")],
        "trailing": [(bad, "{} {}")],
        "empty-file": [(bad, "")],
        "null": [(bad, "null")],
        "array": [(bad, "[]")],
        "missing-field": [(bad, json.dumps({"asset_id": "w:a", "width": 1}))],
        "missing-fields": [(bad, json.dumps({"asset_id": "w:a"}))],
        "out-of-range": [(bad, painting(17, 0))],
        "bad-identifier": [(bad, painting(asset="W:A"))],
        "wrong-types": [("data/w/damage_type/bad.json", damage(5, "never", "x"))],
        "bad-enum": [("data/w/damage_type/bad.json", damage("m", "sometimes"))],
        "bad-height": [("data/w/dimension_type/bad.json", dimension(height=20, logical_height=20))],
        "missing-clock": [("data/w/timeline/bad.json", json.dumps({"clock": "w:nowhere"}))],
        "missing-default-clock": [("data/w/dimension_type/bad.json", dimension(default_clock="w:nowhere"))],
        "missing-block-tag": [("data/w/dimension_type/bad.json", dimension(infiniburn="#w:absent"))],
        "missing-timeline-tag": [("data/w/dimension_type/bad.json", dimension(timelines="#w:missing"))],
        "missing-timeline": [("data/w/dimension_type/bad.json", dimension(timelines=["w:gone", "w:gone_too"]))],
        "duplicate-marker": [
            ("data/w/world_clock/c.json", "{}"),
            ("data/w/timeline/a.json", json.dumps({"clock": "w:c", "time_markers": {"w:m": 1}})),
            ("data/w/timeline/b.json", json.dumps({"clock": "w:c", "time_markers": {"w:m": 2, "w:n": 3}})),
            ("data/w/timeline/c.json", json.dumps({"clock": "w:c", "time_markers": {"w:n": 4}})),
        ],
        "tag-of-broken": [(bad, "{"), ("data/w/tags/painting_variant/t.json", tag("w:bad"))],
        "tag-missing-entry": [("data/w/tags/painting_variant/t.json", tag("w:gone", "w:gone_too"))],
        "several": [
            (bad, "{"),
            ("data/w/painting_variant/worse.json", json.dumps({"width": 1})),
            ("data/w/damage_type/bad.json", damage("m", "sometimes")),
            ("data/w/banner_pattern/bad.json", json.dumps({"asset_id": "w:x"})),
            ("data/w/timeline/bad.json", json.dumps({"clock": "w:nowhere"})),
            ("data/w/dimension_type/bad.json", dimension(timelines="#w:missing")),
        ],
    }
    variant = "data/w/cat_variant/bad.json"
    broken.update({
        "variant-no-spawn-conditions": [(variant, cat(spawn_conditions=None))],
        "variant-no-priority": [(variant, cat({"condition": {"type": "minecraft:moon_brightness", "range": 1}}))],
        "variant-bad-condition-type": [(variant, cat({"priority": 0, "condition": {"type": "minecraft:weather"}}))],
        "variant-bad-moon": [(variant, cat({"priority": 0, "condition": {"type": "minecraft:moon_brightness", "range": "bright"}}))],
        "variant-missing-structure": [(variant, cat({"priority": 0, "condition": {"type": "minecraft:structure", "structures": ["w:gone", "minecraft:swamp_hut", "a:gone"]}}))],
        "variant-missing-structure-tag": [(variant, cat({"priority": 0, "condition": {"type": "minecraft:structure", "structures": "#w:gone"}}))],
        "variant-missing-biome": [(variant, cat({"priority": 0, "condition": {"type": "minecraft:biome", "biomes": "w:gone"}}))],
        "biome-missing-feature": [("data/w/worldgen/biome/v.json", void_biome(["w:gone", "minecraft:oak_checked"]))],
        "biome-missing-carver": [("data/w/worldgen/biome/v.json", void_biome(carvers=["w:gone"]))],
        "world-tag-missing-entry": [("data/w/tags/worldgen/structure/t.json", tag("w:gone", "minecraft:igloo"))],
        "world-and-synced-unbound": [
            ("data/w/worldgen/biome/v.json", void_biome(["w:gone"])),
            ("data/w/dimension_type/bad.json", dimension(timelines=["w:gone"])),
            (variant, cat({"priority": 0, "condition": {"type": "minecraft:structure", "structures": "#w:gone"}})),
        ],
    })
    for name, path in BAD_PATHS.items():
        broken[f"nbt-path-{name}"] = [("data/w/enchantment/bad.json", enchantment(path))]
    for name, effects in BAD_REQUIREMENTS.items():
        broken[f"requirements-{name}"] = [("data/w/enchantment/bad.json", effects_enchantment(effects))]
    for name, files in broken.items():
        cases.append(world(f"load-{name}", files))
    # NBT paths that read, each written back as the text it was read from, which stops at a space.
    cases.append(world("load-nbt-paths", [("data/w/enchantment/paths.json", enchantment(
        "a", "a.b[0]", "a[-1][]", "{x:1b}.y", "a{x:1b}", "a[{x:1b}]", "\"q r\".'s\\'t'", "x-y_z:w+", "a b", "a.", "", " a",
    ))]))
    cases.append(world("load-requirements-allowed", [("data/w/enchantment/allowed.json", effects_enchantment(ALLOWED_REQUIREMENTS))]))
    # Spawn conditions of each kind, naming the world registries' entries and tags, vanilla's and
    # the pack's own, which a client isn't sent; and a biome naming placed features and carvers.
    cases.append(world("load-world-references", [
        ("data/w/cat_variant/c.json", cat(
            {"priority": 0},
            {"priority": 3, "condition": {"type": "minecraft:structure", "structures": "#w:huts"}},
            {"priority": 2, "condition": {"type": "minecraft:structure", "structures": ["minecraft:swamp_hut", "minecraft:igloo"]}},
            {"priority": 1, "condition": {"type": "minecraft:moon_brightness", "range": {"min": 0.25}}},
            {"priority": 4, "condition": {"type": "minecraft:moon_brightness", "range": 0.5}},
            {"priority": 5, "condition": {"type": "minecraft:biome", "biomes": ["minecraft:plains", "w:v"]}},
            {"priority": 6, "condition": {"type": "biome", "biomes": "#minecraft:is_ocean"}},
        )),
        ("data/w/tags/worldgen/structure/huts.json", tag("minecraft:swamp_hut", "#minecraft:cats_spawn_in")),
        ("data/w/worldgen/placed_feature/p.json", json.dumps({"feature": "minecraft:oak", "placement": []})),
        ("data/w/worldgen/biome/v.json", void_biome(["w:p", "minecraft:oak_checked"], ["minecraft:cave", "minecraft:canyon"])),
    ]))
    # A registry of variants left empty, by a filter that hides vanilla's paintings and their tags.
    hide = {"block": [{"namespace": "minecraft", "path": "(tags/)?painting_variant/.*"}]}
    cases.append(world("load-no-paintings", [], meta(filter=hide)))
    return cases


def main():
    cases = picking() + metadata() + files() + entries() + links() + loading()
    write_file(HERE / "generated.json", "packs", "cases/packs/gen.py", cases, probe_version=2)


main()
