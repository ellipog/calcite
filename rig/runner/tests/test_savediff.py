"""Tests for savediff.py, which compares what two servers saved of the same chunks (CAL-145).
Standard library only.

    py -I -m unittest discover -s rig/runner/tests -v
"""

import sys
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))

import savediff  # noqa: E402


def packed(indices, bits):
    """`indices` packed as `SimpleBitStorage` packs them, none across two longs, as signed longs."""
    per = 64 // bits
    longs = [0] * ((len(indices) + per - 1) // per)
    for i, v in enumerate(indices):
        longs[i // per] |= v << ((i % per) * bits)
    return [v - (1 << 64) if v >= 1 << 63 else v for v in longs]


def section(y, palette, indices=None, **light):
    states = {"palette": palette}
    if indices is not None:
        states["data"] = packed(indices, max(4, (len(palette) - 1).bit_length()))
    return dict({"Y": y, "block_states": states}, **light)


def chunk(sections, entities=(), **rest):
    return dict({"sections": sections, "block_entities": list(entities), "Status": "minecraft:full"}, **rest)


class SaveDiffTest(unittest.TestCase):
    def test_states_by_place_not_palette(self):
        # The same blocks with their palettes in another order are the same.
        stone_first = [1] + [0] * 4095
        a = chunk([section(0, [{"": "minecraft:air"}, {"": "minecraft:stone"}], stone_first)])
        b = chunk([section(0, [{"": "minecraft:stone"}, "minecraft:air"], [0] + [1] * 4095)])
        self.assertEqual(savediff.chunk_differences(0, 0, a, b, 5), [])

    def test_a_block_that_differs(self):
        a = chunk([section(-1, ["minecraft:air"])])
        oak = {"id": "minecraft:oak_log", "properties": {"axis": "x"}}
        b = chunk([section(-1, ["minecraft:air", oak], [0] * 17 + [1] + [0] * 4078)])
        got = savediff.chunk_differences(2, 3, a, b, 5)
        self.assertEqual(got, ["block 33, -16, 49: minecraft:air vs minecraft:oak_log[axis=x]"])

    def test_block_entities_and_ticks(self):
        chest = {"id": "minecraft:chest", "x": 1, "y": 2, "z": 3, "Items": []}
        full = dict(chest, Items=[{"id": "minecraft:stone", "count": 1, "Slot": 0}])
        tick = {"i": "minecraft:water", "x": 1, "y": 2, "z": 3, "t": 5, "p": 0}
        a = chunk([], [chest], block_ticks=[tick])
        b = chunk([], [full], block_ticks=[])
        got = savediff.chunk_differences(0, 0, a, b, 5)
        self.assertEqual(len(got), 3)
        self.assertTrue(got[0].startswith("block entity 1, 2, 3: "))
        self.assertEqual(got[1], "block_ticks: 1 only vanilla's, 0 only Calcite's")
        self.assertEqual(got[2], "  only vanilla's: i minecraft:water, p 0, t 5, x 1, y 2, z 3")

    def test_ticks_by_when_due(self):
        # The same tick, due at game time 223, saved 17 ticks off at 206 and 18 off at 205, is
        # the same (D541); one due at another time isn't.
        tick = {"i": "minecraft:big_dripleaf", "x": 1, "y": 2, "z": 3, "p": 0}
        a = chunk([], block_ticks=[dict(tick, t=17)], LastUpdate=206)
        b = chunk([], block_ticks=[dict(tick, t=18)], LastUpdate=205)
        self.assertEqual(savediff.chunk_differences(0, 0, a, b, 5), [])
        late = chunk([], block_ticks=[dict(tick, t=19)], LastUpdate=205)
        self.assertEqual(len(savediff.chunk_differences(0, 0, a, late, 5)), 3)

    def test_times_left_out(self):
        a = chunk([], LastUpdate=254, InhabitedTime=40)
        b = chunk([], LastUpdate=274, InhabitedTime=12)
        self.assertEqual(savediff.chunk_differences(0, 0, a, b, 5), [])

    def test_the_sky_under_the_world(self):
        # A sky layer of 0s under the world is as none, which vanilla gives some chunks and not
        # others; one elsewhere, or with light in it, isn't.
        zeros = [0] * 2048
        a = chunk([section(-5, ["minecraft:air"], SkyLight=zeros), section(-4, ["minecraft:air"])])
        b = chunk([section(-4, ["minecraft:air"])])
        self.assertEqual(savediff.chunk_differences(0, 0, a, b, 5), [])
        lit = chunk([section(-5, ["minecraft:air"], SkyLight=[0x11] * 2048), section(-4, ["minecraft:air"])])
        self.assertEqual(len(savediff.chunk_differences(0, 0, lit, b, 5)), 1)
        dark = chunk([section(-5, ["minecraft:air"]), section(-4, ["minecraft:air"], SkyLight=zeros)])
        self.assertEqual(len(savediff.chunk_differences(0, 0, dark, b, 5)), 1)


if __name__ == "__main__":
    unittest.main()
