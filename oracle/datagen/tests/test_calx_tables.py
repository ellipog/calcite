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
        if not (tables / "index.json").exists() or not (tables.parent / "block_flags.json").exists():
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
    PIN = {"url": "https://example.com/server.jar", "sha1": "0123456789abcdef0123456789abcdef01234567", "size": 12,
           "client": {"url": "https://example.com/client.jar", "sha1": "89abcdef0123456789abcdef0123456789abcdef", "size": 40,
                      "data": {"offset": 5, "length": 30, "sha256": "ab" * 32}}}

    def test_writes_the_pin(self):
        text = calx_tables.pin_module("1.0", self.PIN)
        self.assertIn('    return "https://example.com/server.jar"\n', text)
        self.assertIn('    return "0123456789abcdef0123456789abcdef01234567"\n', text)
        self.assertIn("pub const JAR_SIZE: usize = 12\n", text)
        self.assertIn('    return "1.0"\n', text)
        self.assertIn('    return "https://example.com/client.jar"\n', text)
        self.assertIn("pub const CLIENT_SIZE: u64 = 40\n", text)
        self.assertIn("pub const DATA_OFFSET: u64 = 5\npub const DATA_LENGTH: usize = 30\n", text)
        self.assertIn('    return "' + "ab" * 32 + '"\n', text)

    def test_rejects_a_bad_pin(self):
        with self.assertRaisesRegex(ValueError, "https URL"):
            calx_tables.pin_module("1.0", dict(self.PIN, url="http://example.com/x"))
        with self.assertRaisesRegex(ValueError, "40 lowercase hex"):
            calx_tables.pin_module("1.0", dict(self.PIN, sha1="ABC"))
        client = dict(self.PIN["client"], data=dict(self.PIN["client"]["data"], sha256="AB"))
        with self.assertRaisesRegex(ValueError, "64 lowercase hex"):
            calx_tables.pin_module("1.0", dict(self.PIN, client=client))


class BlocksModule(unittest.TestCase):
    @staticmethod
    def block(id, name, first, count, default):
        return {"id": id, "name": name, "first_state": first, "state_count": count, "default_state": default}

    def test_writes_first_states_and_default_offsets(self):
        text = calx_tables.blocks_module(INDEX, {"state_count": 4, "blocks": [
            self.block(0, "minecraft:air", 0, 1, 0),
            self.block(1, "minecraft:grass_block", 1, 2, 2),
            self.block(2, "minecraft:dirt", 3, 1, 3),
        ]})
        self.assertIn("pub const STATE_COUNT: u32 = 4\n", text)
        self.assertIn("    return [0, 1, 3]\n", text)
        self.assertIn("    return [0, 1, 0]\n", text)

    def test_rejects_states_that_dont_follow_on(self):
        with self.assertRaisesRegex(ValueError, "don't run from 0"):
            calx_tables.blocks_module(INDEX, {"state_count": 1, "blocks": [self.block(1, "minecraft:air", 0, 1, 0)]})
        with self.assertRaisesRegex(ValueError, "follow"):
            calx_tables.blocks_module(INDEX, {"state_count": 2, "blocks": [
                self.block(0, "minecraft:air", 0, 1, 0), self.block(1, "minecraft:stone", 2, 1, 2)]})
        with self.assertRaisesRegex(ValueError, "default state"):
            calx_tables.blocks_module(INDEX, {"state_count": 1, "blocks": [self.block(0, "minecraft:air", 0, 1, 1)]})
        with self.assertRaisesRegex(ValueError, "not the 3"):
            calx_tables.blocks_module(INDEX, {"state_count": 3, "blocks": [self.block(0, "minecraft:air", 0, 1, 0)]})


class BlockFlagsModule(unittest.TestCase):
    @staticmethod
    def decode(text):
        """The flags, read back from the module as its `state_flags` reads them."""
        lines = text.splitlines()
        values = [int(v) for v in next(l for l in lines if "let values" in l).split("[")[1].rstrip("]").split(", ")]
        alphabet = next(l for l in lines if "let alphabet" in l).split('"')[1]
        start = lines.index("    let lines: List<String> = [") + 1
        encoded = []
        for line in lines[start:lines.index("    ]", start)]:
            encoded.append(line.strip().removeprefix('"').removesuffix('",'))
        out = []
        for chunk in encoded:
            i = 0
            while i < len(chunk):
                if chunk[i] == alphabet[-1]:
                    out.append(values[len(alphabet) - 1 + alphabet.index(chunk[i + 1])])
                    i += 2
                else:
                    out.append(values[alphabet.index(chunk[i])])
                    i += 1
        return out, encoded

    def test_the_flags_read_back(self):
        # More different flags than one character holds, so the rarest take pairs, and enough
        # states to fill several lines.
        flags = [17] * 3 + [(i % 120) << 12 | (i % 120) % 7 for i in range(1000)]
        text = calx_tables.block_flags_module(INDEX, {"game_version": "1.0", "states": len(flags), "flags": flags})
        decoded, encoded = self.decode(text)
        self.assertEqual(decoded, flags)
        self.assertGreater(len(encoded), 1)
        self.assertTrue(all(len(c) <= calx_tables.LINE for c in encoded))
        self.assertTrue(any(calx_tables.ALPHABET[-1] in c for c in encoded))
        self.assertTrue(all(not c.endswith(calx_tables.ALPHABET[-1]) for c in encoded))
        self.assertIn("pub const AIR: u32 = 1\n", text)
        self.assertIn("pub const LIGHT_DAMPENING_SHIFT: u32 = 16\n", text)
        self.assertIn(f"    flags.reserve({len(flags)})\n", text)

    def test_rejects_what_it_cant_represent(self):
        with self.assertRaisesRegex(ValueError, "the tables 1.0"):
            calx_tables.block_flags_module(INDEX, {"game_version": "2.0", "states": 1, "flags": [17]})
        with self.assertRaisesRegex(ValueError, "1 flags for 2 states"):
            calx_tables.block_flags_module(INDEX, {"game_version": "1.0", "states": 2, "flags": [17]})
        with self.assertRaisesRegex(ValueError, "bits this script doesn't know"):
            calx_tables.block_flags_module(INDEX, {"game_version": "1.0", "states": 1, "flags": [1 << 9]})
        with self.assertRaisesRegex(ValueError, "bits this script doesn't know"):
            calx_tables.block_flags_module(INDEX, {"game_version": "1.0", "states": 1, "flags": [1 << 24]})
        with self.assertRaisesRegex(ValueError, "more than the encoding holds"):
            many = list(range(0, 200 << 12, 1 << 12))
            calx_tables.block_flags_module(INDEX, {"game_version": "1.0", "states": len(many), "flags": many})

    def test_the_committed_table_reads_back(self):
        path = calx_tables.CALCITE / "generated" / calx_tables.VERSION / "block_flags.json"
        if not path.exists():
            self.skipTest("no block_flags.json")
        import json
        flags = json.loads(path.read_text(encoding="utf-8"))
        text = (calx_tables.CALCITE / "src" / "world" / "block_flags.calx").read_text(encoding="utf-8")
        self.assertEqual(self.decode(text)[0], flags["flags"])


if __name__ == "__main__":
    unittest.main()
