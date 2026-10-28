"""Tests for calx_tables.py, which writes the Calx modules compiled in from the tables.

    py -I -m unittest discover -s oracle/datagen/tests -v

The made-up tables need no jar. The last test checks the committed modules against the real
tables, and is skipped where they haven't been generated.
"""

import sys
import unittest
from pathlib import Path

DATAGEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATAGEN))

import calx_tables  # noqa: E402

INDEX = {"game_version": "1.0", "protocol_version": 5}


def packets(**states):
    """Every state, with no packets unless given."""
    out = {s: {"serverbound": [], "clientbound": []} for s in calx_tables.STATES}
    out.update(states)
    return out


class IdsModule(unittest.TestCase):
    def test_lists_packets_in_id_order_without_namespace(self):
        text = calx_tables.ids_module(INDEX, packets(login={
            "serverbound": ["minecraft:hello", "minecraft:key"],
            "clientbound": ["minecraft:login_disconnect"],
        }))
        self.assertIn("pub const PROTOCOL_VERSION: i32 = 5\n", text)
        self.assertIn('    return "1.0"\n', text)
        self.assertIn(
            "        State.Login => {\n"
            "            if bound == Bound.Serverbound {\n"
            '                return ["hello", "key"]\n'
            "            }\n"
            '            return ["login_disconnect"]\n'
            "        }\n", text)
        self.assertIn("        State.Play => {\n            if bound == Bound.Serverbound {\n                return []\n", text)
        self.assertTrue(text.endswith("    }\n}\n"))

    def test_every_state_has_an_arm(self):
        text = calx_tables.ids_module(INDEX, {})
        for state in ["Handshake", "Status", "Login", "Configuration", "Play"]:
            self.assertIn(f"        State.{state} => {{\n", text)

    def test_rejects_what_it_cant_represent(self):
        with self.assertRaisesRegex(ValueError, "states this script doesn't know"):
            calx_tables.ids_module(INDEX, packets(transfer={}))
        with self.assertRaisesRegex(ValueError, "directions this script doesn't know"):
            calx_tables.ids_module(INDEX, packets(play={"sideways": []}))
        with self.assertRaisesRegex(ValueError, "isn't in the minecraft namespace"):
            calx_tables.ids_module(INDEX, packets(play={"serverbound": ["other:thing"]}))

    def test_committed_modules_are_current(self):
        tables = calx_tables.CALCITE / "generated" / calx_tables.VERSION / "tables"
        if not (tables / "index.json").exists():
            self.skipTest("no generated tables")
        for path, text in calx_tables.outputs(tables).items():
            self.assertEqual(path.read_text(encoding="utf-8"), text, f"{path} is out of date: run calx_tables.py")



class BuiltinModule(unittest.TestCase):
    def test_lists_registries_and_entries_in_id_order(self):
        text = calx_tables.builtin_module(INDEX, {
            "minecraft:item": {"id": 1, "default": "minecraft:air", "entries": ["minecraft:air", "minecraft:stone"]},
            "minecraft:command_argument_type": {"id": 0, "default": None, "entries": ["brigadier:bool", "minecraft:entity"]},
        })
        self.assertIn('    return ["command_argument_type", "item"]\n', text)
        self.assertIn('        0 => ["brigadier:bool", "entity"],\n', text)
        self.assertIn('        1 => ["air", "stone"],\n', text)
        self.assertIn("        _ => [],\n", text)

    def test_rejects_what_it_cant_represent(self):
        with self.assertRaisesRegex(ValueError, "without gaps"):
            calx_tables.builtin_module(INDEX, {"minecraft:item": {"id": 1, "entries": []}})
        with self.assertRaisesRegex(ValueError, "has no namespace"):
            calx_tables.builtin_module(INDEX, {"minecraft:item": {"id": 0, "entries": ["stone"]}})
        with self.assertRaisesRegex(ValueError, "Calx string"):
            calx_tables.builtin_module(INDEX, {"minecraft:item": {"id": 0, "entries": ['minecraft:a"b']}})


class PinModule(unittest.TestCase):
    PIN = {"url": "https://example.com/server.jar", "sha1": "0123456789abcdef0123456789abcdef01234567", "size": 12}

    def test_writes_the_pin(self):
        text = calx_tables.pin_module("1.0", self.PIN)
        self.assertIn('    return "https://example.com/server.jar"\n', text)
        self.assertIn('    return "0123456789abcdef0123456789abcdef01234567"\n', text)
        self.assertIn("pub const JAR_SIZE: usize = 12\n", text)
        self.assertIn('    return "1.0"\n', text)

    def test_rejects_a_bad_pin(self):
        with self.assertRaisesRegex(ValueError, "https URL"):
            calx_tables.pin_module("1.0", dict(self.PIN, url="http://example.com/x"))
        with self.assertRaisesRegex(ValueError, "40 lowercase hex"):
            calx_tables.pin_module("1.0", dict(self.PIN, sha1="ABC"))


if __name__ == "__main__":
    unittest.main()
