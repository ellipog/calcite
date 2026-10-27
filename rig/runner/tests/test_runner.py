"""Tests for the rig's runner. Standard library only; no vanilla jar needed.

    py -I -m unittest discover -s rig/runner/tests -v
"""

import base64
import hashlib
import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
ROOT = RUNNER.parents[1]
sys.path.insert(0, str(RUNNER))

import cases  # noqa: E402
import differences  # noqa: E402
from protocol import Adapter, Result, canonical_json, read_frame, result_hash, write_frame  # noqa: E402
from store import Store  # noqa: E402

PING_ADAPTER = Path(__file__).resolve().parent / "ping-adapter"


class Frames(unittest.TestCase):
    def test_round_trip(self):
        buf = io.BytesIO()
        write_frame(buf, {"type": "run", "id": 1, "input": {"s": "é😀", "n": None}}, [b"\x00\x01", b""])
        buf.seek(0)
        header, blobs = read_frame(buf)
        self.assertEqual(header["input"], {"s": "é😀", "n": None})
        self.assertEqual(header["blobs"], [2, 0])
        self.assertEqual(blobs, [b"\x00\x01", b""])

    def test_layout(self):
        buf = io.BytesIO()
        write_frame(buf, {"type": "bye"}, [b"ab"])
        data = buf.getvalue()
        (length,) = struct.unpack(">I", data[:4])
        self.assertEqual(json.loads(data[4:4 + length]), {"type": "bye", "blobs": [2]})
        self.assertEqual(data[4 + length:], b"ab")


class Hashes(unittest.TestCase):
    def test_canonical_json(self):
        self.assertEqual(canonical_json({"b": 1, "a": [None, "é"]}), '{"a":[null,"é"],"b":1}')

    def test_floats_rejected(self):
        with self.assertRaises(ValueError):
            canonical_json({"x": float("nan")})

    def test_hash_follows_the_protocol(self):
        # PROTOCOL.md: SHA-256 over canonical JSON, then each blob's u64 length and bytes.
        # Changing this changes every committed expected hash.
        h = hashlib.sha256(b'{"echo":"x"}' + struct.pack(">Q", 2) + b"\x01\x02").hexdigest()
        self.assertEqual(result_hash({"echo": "x"}, [b"\x01\x02"]), h)

    def test_blob_boundaries_matter(self):
        self.assertNotEqual(result_hash({}, [b"ab", b"c"]), result_hash({}, [b"a", b"bc"]))


class Blobs(unittest.TestCase):
    def test_splitmix64_reference(self):
        # SplitMix64 from seed 0: the published first outputs.
        g = cases.splitmix64(0)
        self.assertEqual([next(g) for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])

    def test_literal_parts(self):
        self.assertEqual(cases.expand_blob({"hex": ["00ff", "10 20"]}), b"\x00\xff\x10\x20")
        self.assertEqual(cases.expand_blob({"i32": [1, -1]}), b"\x00\x00\x00\x01\xff\xff\xff\xff")
        self.assertEqual(cases.expand_blob({"f64": ["-0"]}), struct.pack(">d", -0.0))
        self.assertEqual(cases.expand_blob({"f64": ["0x1p-1074"]}), struct.pack(">Q", 1))
        self.assertEqual(cases.expand_blob({"f64_bits": ["7ff8000000000001"]}), bytes.fromhex("7ff8000000000001"))
        self.assertEqual(cases.expand_blob(base64.b64encode(b"hi").decode()), b"hi")
        self.assertEqual(cases.expand_blob([{"hex": ["01"]}, {"hex": ["02"]}]), b"\x01\x02")

    def test_generators_are_deterministic(self):
        spec = {"gen": "f64_range", "seed": "7", "count": 100, "min": "-1", "max": "1"}
        a, b = cases.expand_blob(spec), cases.expand_blob(spec)
        self.assertEqual(a, b)
        values = struct.unpack(">100d", a)
        self.assertTrue(all(-1 <= v < 1 for v in values))

    def test_ranges_make_tuples(self):
        blob = cases.expand_blob({"gen": "f64_range", "seed": "1", "count": 50, "ranges": [["0", "1"], ["10", "11"]]})
        values = struct.unpack(">100d", blob)
        self.assertTrue(all(0 <= v < 1 for v in values[0::2]))
        self.assertTrue(all(10 <= v < 11 for v in values[1::2]))

    def test_i32_range(self):
        values = struct.unpack(">300i", cases.expand_blob({"gen": "i32_range", "seed": "3", "count": 300, "min": "-2", "max": "2"}))
        self.assertEqual(set(values), {-2, -1, 0, 1, 2})

    def test_bad_part(self):
        with self.assertRaises(cases.CaseFileError):
            cases.expand_blob({"nope": []})


class CaseFiles(unittest.TestCase):
    def test_repo_cases_load(self):
        by_probe = cases.load_all(ROOT / "cases")
        self.assertGreater(sum(len(v) for v in by_probe.values()), 0)
        for probe, items in by_probe.items():
            ids = [c.id for c in items]
            self.assertEqual(len(ids), len(set(ids)), probe)

    def test_generated_files_are_current(self):
        """Each gen.py must reproduce its committed file exactly."""
        for gen in sorted((ROOT / "cases").glob("*/gen.py")):
            before = {p: p.read_bytes() for p in (ROOT / "cases").rglob("*.json")}
            try:
                subprocess.run([sys.executable, "-I", str(gen)], check=True, capture_output=True)
                after = {p: p.read_bytes() for p in (ROOT / "cases").rglob("*.json")}
            finally:
                for p in set((ROOT / "cases").rglob("*.json")) - set(before):
                    p.unlink()
                for p, data in before.items():
                    p.write_bytes(data)
            changed = sorted(str(p.relative_to(ROOT)) for p in after if before.get(p) != after[p])
            self.assertEqual(changed, [], f"{gen.relative_to(ROOT)} doesn't match its committed output; rerun it")

    def test_expected_hashes_cover_cases(self):
        store = Store(ROOT, "26.3")
        quarantine = store.quarantine()
        for probe, items in cases.load_all(ROOT / "cases").items():
            expected = store.expected(probe)
            missing = [c.id for c in items if c.id not in expected and c.key not in quarantine]
            self.assertEqual(missing, [], f"{probe}: cases without an expected hash; run `rig.py record --config all`")


class Differences(unittest.TestCase):
    def test_repo_registry_loads(self):
        for d in differences.load(ROOT / "rig" / "differences"):
            self.assertTrue(d.cases)

    def test_globs(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.md").write_text("---\ntitle: X\nkind: bug\ncases:\n  - nbt:deep-51?\n---\nbody\n", encoding="utf-8")
            (d,) = differences.load(tmp)
            self.assertTrue(d.covers("nbt:deep-512"))
            self.assertFalse(d.covers("nbt:deep-256"))

    def test_bad_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.md").write_text("---\ntitle: X\nkind: whim\ncases:\n  - a:b\n---\n", encoding="utf-8")
            with self.assertRaises(differences.DifferenceError):
                differences.load(tmp)


class StoreFiles(unittest.TestCase):
    def test_configs_and_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref, other = Store(tmp, "26.3"), Store(tmp, "26.3", "intrinsics")
            ref.save_expected("rng", 1, {}, {"b": "2", "a": "1"})
            other.save_expected("rng", 1, {}, {"a": "9"})
            self.assertEqual(ref.expected("rng"), {"a": "1", "b": "2"})
            self.assertEqual(other.expected("rng"), {"a": "9"})
            self.assertTrue((Path(tmp) / "expected" / "26.3" / "intrinsics" / "rng.json").is_file())
            self.assertNotIn(b"\r\n", (Path(tmp) / "expected" / "26.3" / "rng.json").read_bytes())
            ref.save_golden("rng", [("a", Result("ok", {"x": 1}, [b"\x01"]))])
            self.assertEqual(ref.golden("rng", "a")["blobs"], [b"\x01"])


class PingAdapter(unittest.TestCase):
    def test_protocol(self):
        with Adapter([sys.executable, "-I", "adapter.py"], cwd=str(PING_ADAPTER)) as a:
            self.assertEqual(a.name, "ping-only")
            r = a.run("ping", "p", {"echo": {"k": [1, None]}}, [b"\x09"])
            self.assertEqual((r.status, r.output, r.blobs), ("ok", {"echo": {"k": [1, None]}}, [b"\x09"]))
            self.assertEqual(a.run("rng", "r", {}).status, "unimplemented")

    def test_score_end_to_end(self):
        out = subprocess.run([sys.executable, "-I", str(RUNNER / "rig.py"), "score", "--strict",
                              "--adapter", str(PING_ADAPTER / "adapter.json")],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("| ping (rig) | 5 | 5 |", out.stdout)
        # Every game case is unimplemented here, so none passes.
        game = sum(len(c) for probe, c in cases.load_all(ROOT / "cases").items() if probe != "ping")
        self.assertIn(f"| **All game probes** | {game} | 0 |", out.stdout)


if __name__ == "__main__":
    unittest.main()
