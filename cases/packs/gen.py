"""Writes cases/packs/generated.json: a world's data packs found and picked as a server starting
finds and picks them, by vanilla's ServerPacksSource and MinecraftServer.configurePackRepository,
then their files listed by a MultiPackResourceManager over the picked packs.

    py -I cases/packs/gen.py

Each case makes the world's `datapacks` folder, with folder packs, zips and entries that aren't
packs, then picks: as a new world does, from server.properties' `initial-enabled-packs` and
`initial-disabled-packs`, or as an old world does, from what its level.dat has on and off and its
feature flags, with or without `--safeMode`. Then it lists a folder of the picked packs' files,
which shows which pack's file wins, what filters hide and which overlays apply.

Making a link takes a privilege Windows doesn't give everyone, so the cases with links are
Linux's. And vanilla finds what's in a folder in the order the file system lists it, so a folder
with more than one entry that logs something logs it in that order. NTFS lists a folder in the
same order on every machine, by its names; a Linux file system needn't (ext4 lists by a hash of
each name with a seed of each file system's own). So such cases are Windows', named `windows-`,
and the others keep to one entry that logs in each folder.
"""

import base64
import io
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

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


def zipped(files, deflate=True):
    """A zip of the files, each a name and its text or bytes, as Java's zip tools would read it."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED) as z:
        for name, data in files:
            if name.endswith("/"):
                z.writestr(zipfile.ZipInfo(name), b"")
            else:
                # As `writestr` makes it for a name, but at a fixed time.
                info = zipfile.ZipInfo(name, date_time=WRITTEN)
                info.compress_type = z.compression
                info.external_attr = 0o600 << 16
                z.writestr(info, data.encode() if isinstance(data, str) else data)
    return out.getvalue()


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


def main():
    cases = picking() + metadata() + files() + entries() + links()
    write_file(HERE / "generated.json", "packs", "cases/packs/gen.py", cases, probe_version=1)


main()
