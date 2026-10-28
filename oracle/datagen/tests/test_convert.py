"""Tests for the converter and the jar fetch step. Standard library only; no vanilla jar needed.

    py -I -m unittest discover -s oracle/datagen/tests -v
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

DATAGEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATAGEN))
sys.path.insert(0, str(DATAGEN.parent))

import convert  # noqa: E402
import fetch  # noqa: E402


def write(folder, name, value):
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def stairs_report():
    """A block shaped like a stair: four properties, listed out of name order on purpose."""
    props = {"waterlogged": ["true", "false"], "facing": ["north", "south"], "half": ["top", "bottom"]}
    names = sorted(props)
    states, i = [], 0
    for f in props["facing"]:
        for h in props["half"]:
            for w in props["waterlogged"]:
                state = {"id": 1 + i, "properties": {"facing": f, "half": h, "waterlogged": w}}
                if (f, h, w) == ("north", "bottom", "false"):
                    state["default"] = True
                states.append(state)
                i += 1
    assert names == ["facing", "half", "waterlogged"]
    return {"minecraft:air": {"states": [{"id": 0, "default": True}]},
            "minecraft:stair": {"properties": props, "states": states}}


def registry(*names):
    return {"minecraft:block": {"protocol_id": 0, "default": names[0],
                                "entries": {n: {"protocol_id": i} for i, n in enumerate(names)}}}


class Numbers(unittest.TestCase):
    def test_text_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n.json"
            path.write_text('{"f": 1.8000001, "d": 0.10000000149011612, "e": 1e-7, "i": 12, "z": -0.0}', encoding="utf-8")
            self.assertEqual(convert.dumps(convert.load(path)),
                             '{\n  "d": 0.10000000149011612,\n  "e": 1e-7,\n  "f": 1.8000001,\n  "i": 12,\n  "z": -0.0\n}')

    def test_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.json"
            path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaises(convert.ConvertError):
                convert.load(path)


class Canonical(unittest.TestCase):
    def test_layout(self):
        value = {"b": [1, "x", None, True], "a": {"z": [], "y": {}}, "c": [{"k": 1}]}
        self.assertEqual(convert.dumps(value),
                         '{\n  "a": {\n    "y": {},\n    "z": []\n  },\n  "b": [1, "x", null, true],\n'
                         '  "c": [\n    {\n      "k": 1\n    }\n  ]\n}')

    def test_floats_refused(self):
        with self.assertRaises(TypeError):
            convert.dumps({"x": 0.5})

    def test_non_ascii_written_as_itself(self):
        self.assertEqual(convert.dumps(["é"]), '["é"]')


class Ids(unittest.TestCase):
    def test_gap_rejected(self):
        with self.assertRaises(convert.ConvertError):
            convert.by_id({"a": {"protocol_id": 0}, "b": {"protocol_id": 2}}, "test")

    def test_ordered(self):
        self.assertEqual(convert.by_id({"b": {"protocol_id": 1}, "a": {"protocol_id": 0}}, "test"), ["a", "b"])


class Blocks(unittest.TestCase):
    def convert(self, report, names=("minecraft:air", "minecraft:stair")):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "blocks.json", report)
            write(tmp, "registries.json", registry(*names))
            reports = Path(tmp)
            return convert.blocks(reports, convert.registries(reports))

    def test_mixed_radix(self):
        table = self.convert(stairs_report())
        self.assertEqual(table["state_count"], 9)
        stair = table["blocks"][1]
        self.assertEqual((stair["first_state"], stair["state_count"], stair["default_state"]), (1, 8, 4))
        names = [table["properties"][i]["name"] for i in stair["properties"]]
        self.assertEqual(names, ["facing", "half", "waterlogged"])
        self.assertEqual(table["properties"][stair["properties"][2]], {"name": "waterlogged", "values": ["true", "false"], "kind": "bool"})

    def test_state_out_of_order_rejected(self):
        report = stairs_report()
        states = report["minecraft:stair"]["states"]
        states[0]["properties"], states[1]["properties"] = states[1]["properties"], states[0]["properties"]
        with self.assertRaises(convert.ConvertError):
            self.convert(report)

    def test_registry_mismatch_rejected(self):
        with self.assertRaises(convert.ConvertError):
            self.convert(stairs_report(), names=("minecraft:air", "minecraft:other"))

    def test_two_defaults_rejected(self):
        report = stairs_report()
        report["minecraft:stair"]["states"][0]["default"] = True
        with self.assertRaises(convert.ConvertError):
            self.convert(report)

    def test_property_kinds(self):
        self.assertEqual(convert.property_kind(["0", "1", "2"]), {"kind": "int", "min": 0, "max": 2})
        self.assertEqual(convert.property_kind(["1", "2"]), {"kind": "int", "min": 1, "max": 2})
        self.assertEqual(convert.property_kind(["north", "south"]), {"kind": "enum"})
        with self.assertRaises(convert.ConvertError):
            convert.property_kind(["0", "2"])


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = fetch.JARS, fetch.VERSIONS
        fetch.JARS = Path(self.tmp.name) / "jars"
        fetch.VERSIONS = Path(self.tmp.name) / "versions.json"
        self.data = b"not really a jar"
        fetch.VERSIONS.write_text(json.dumps({"9.9": {"sha1": hashlib.sha1(self.data).hexdigest(),
                                                       "size": len(self.data), "url": "http://invalid/"}}))

    def tearDown(self):
        fetch.JARS, fetch.VERSIONS = self.saved
        self.tmp.cleanup()

    def test_pinned_jar_is_checked_offline(self):
        fetch.JARS.mkdir()
        fetch.jar_path("9.9").write_bytes(self.data)
        self.assertEqual(fetch.ensure("9.9", download=False), fetch.jar_path("9.9"))

    def test_wrong_jar_refused(self):
        fetch.JARS.mkdir()
        fetch.jar_path("9.9").write_bytes(b"something else")
        with self.assertRaises(SystemExit):
            fetch.ensure("9.9", download=False)

    def test_local_jar_installed(self):
        source = Path(self.tmp.name) / "mine.jar"
        source.write_bytes(self.data)
        self.assertEqual(fetch.install("9.9", source).read_bytes(), self.data)
        source.write_bytes(b"something else")
        with self.assertRaises(SystemExit):
            fetch.install("9.9", source)

    def test_unpinned_version_refused(self):
        with self.assertRaises(SystemExit):
            fetch.ensure("1.0", download=False)

    def test_repo_pins_are_well_formed(self):
        pins = json.loads((DATAGEN.parent / "versions.json").read_text(encoding="utf-8"))
        for version, pin in pins.items():
            self.assertRegex(pin["sha1"], r"^[0-9a-f]{40}$", version)
            self.assertIn(pin["sha1"], pin["url"], version)
            self.assertGreater(pin["size"], 0, version)
            client = pin["client"]
            self.assertIn(client["sha1"], client["url"], version)
            self.assertRegex(client["data"]["sha256"], r"^[0-9a-f]{64}$", version)
            self.assertLess(client["data"]["offset"] + client["data"]["length"], client["size"], version)


if __name__ == "__main__":
    unittest.main()
