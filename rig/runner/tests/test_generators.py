"""Each case generator, cases/*/gen.py, must reproduce its committed file exactly, on every
machine. Those that read vanilla's ids from the pinned jar are skipped where it hasn't been
fetched. Standard library only.

    py -I -m unittest discover -s rig/runner/tests -v
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class CaseFiles(unittest.TestCase):
    def test_generated_files_are_current(self):
        """Each gen.py must reproduce its committed file exactly, on every machine. Those that
        read vanilla's ids from the pinned jar are skipped where it hasn't been fetched."""
        jar = ROOT / "oracle" / "jars" / "server-26.3.jar"
        for gen in sorted((ROOT / "cases").glob("*/gen.py")):
            with self.subTest(gen=str(gen.relative_to(ROOT))):
                if not jar.is_file() and jar.name in gen.read_text(encoding="utf-8"):
                    self.skipTest(f"no {jar.relative_to(ROOT)}; oracle/fetch.calx fetches it")
                before = {p: p.read_bytes() for p in (ROOT / "cases").rglob("*.json")}
                try:
                    run = subprocess.run([sys.executable, "-I", str(gen)], capture_output=True, text=True)
                    after = {p: p.read_bytes() for p in (ROOT / "cases").rglob("*.json")}
                finally:
                    for p in set((ROOT / "cases").rglob("*.json")) - set(before):
                        p.unlink()
                    for p, data in before.items():
                        p.write_bytes(data)
                self.assertEqual(run.returncode, 0, run.stderr[-2000:])
                changed = sorted(str(p.relative_to(ROOT)) for p in after if before.get(p) != after[p])
                self.assertEqual(changed, [], f"{gen.relative_to(ROOT)} doesn't match its committed output; rerun it")


if __name__ == "__main__":
    unittest.main()
