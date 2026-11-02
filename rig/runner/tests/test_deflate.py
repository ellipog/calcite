"""Tests for deflate.py, the streams the case generators compress with. Standard library only.

    py -I -m unittest discover -s rig/runner/tests -v
"""

import sys
import unittest
import zlib
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))

import deflate  # noqa: E402
from cases import splitmix64  # noqa: E402


def noise(n, seed=1):
    r = splitmix64(seed)
    return bytes(next(r) & 0xFF for _ in range(n))


SAMPLES = {
    "empty": b"",
    "one": b"x",
    "short": b"abcabcabcabc",
    "text": b"the quick brown fox jumps over the lazy dog " * 300,
    # A run past the longest match, matches across the whole window, and bytes past 143, which
    # take 9-bit codes.
    "run": b"a" * 1000,
    "window": noise(40000, 7) + noise(40000, 7)[:30000],
    "high": bytes(range(256)) * 9,
    "noise": noise(5000),
    # More than a stored block holds.
    "big": noise(70000, 3) + b"z" * 70000,
}


class Deflate(unittest.TestCase):
    def test_inflates_back(self):
        for name, data in SAMPLES.items():
            for level in (0, 1, 2, 6, 9, -1):
                with self.subTest(sample=name, level=level):
                    self.assertEqual(zlib.decompress(deflate.deflate(data, level), -15), data)
                    self.assertEqual(zlib.decompress(deflate.zlib_stream(data, level)), data)
                    self.assertEqual(zlib.decompress(deflate.gzip_stream(data, level), 31), data)

    def test_levels(self):
        data = SAMPLES["text"]
        stored, literals, matched = (deflate.deflate(data, level) for level in (0, 1, 6))
        # One stored block, the last: its header, its length and the length's complement.
        self.assertEqual(stored[:5], bytes([1]) + len(data).to_bytes(2, "little") + (len(data) ^ 0xFFFF).to_bytes(2, "little"))
        self.assertEqual(stored[5:], data)
        big = deflate.deflate(SAMPLES["big"], 0)
        self.assertEqual((big[0], big[5 + 65535]), (0, 0))  # the first two of three aren't last
        self.assertEqual(len(big), len(SAMPLES["big"]) + 3 * 5)
        self.assertLess(len(matched), len(literals))
        self.assertEqual(deflate.deflate(data, 9), matched)
        self.assertEqual(deflate.deflate(b"", 0), b"\x01\x00\x00\xff\xff")
        # An empty fixed block: its header and the end code, 10 bits.
        self.assertEqual(deflate.deflate(b""), b"\x03\x00")

    def test_zlib_headers_mark_the_level_as_zlib_does(self):
        for level, mark in ((0, b"\x78\x01"), (1, b"\x78\x01"), (2, b"\x78\x5e"), (5, b"\x78\x5e"),
                            (6, b"\x78\x9c"), (-1, b"\x78\x9c"), (7, b"\x78\xda"), (9, b"\x78\xda")):
            self.assertEqual(deflate.zlib_stream(b"abc", level)[:2], mark)

    def test_gzip_member(self):
        g = deflate.gzip_stream(b"level.dat")
        self.assertEqual(g[:10], deflate.GZIP_HEADER)
        self.assertEqual(g[-4:], (9).to_bytes(4, "little"))
        named = deflate.gzip_stream(b"x", header=b"\x1f\x8b\x08\x08\x00\x00\x00\x00\x00\xffname\x00")
        self.assertEqual(zlib.decompress(named, 31), b"x")

    def test_bytes_are_pinned(self):
        """The case files hold these streams; a change here changes them, and vanilla's hashes."""
        # Three literals, then 9 bytes from 3 back.
        self.assertEqual(deflate.deflate(b"abcabcabcabc").hex(), "4b4c4a862300")
        self.assertEqual(deflate.zlib_stream(b"hello hello hello", 6).hex(), "789ccb48cdc9c9574022013a2e067d")


if __name__ == "__main__":
    unittest.main()
