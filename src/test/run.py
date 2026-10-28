"""Runs Calcite's Calx tests, in debug and release builds:

- every .calx file in this folder. Each panics on a wrong result and prints `ok` at its end.
- every ```calx block in src/README.md, whose `// out: ...` comments give the lines it prints,
  so the docs' examples can't go stale (D41).
- the server, src/calcite.calx, which runs until it's stopped, so it's only built.

Debug builds also check that everything allocated is freed (Calx's D79). calx is found as
rig/calcite-adapter/launch.py finds it.

    py -I src/test/run.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
DOCS = [CALCITE / "src" / "README.md"]
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
from launch import find_calx  # noqa: E402

BLOCK = re.compile(r"^```calx\n(.*?)^```", re.M | re.S)
OUT = re.compile(r"//\s*out:\s?(.*)$")


def examples():
    """Each docs example as (name, source, expected output lines). A block becomes a module
    under src/test/, so it imports Calcite's modules as Calcite does."""
    for doc in DOCS:
        for n, m in enumerate(BLOCK.finditer(doc.read_text(encoding="utf-8")), 1):
            name = f"doc_{doc.parent.name}_{n}"
            body = m.group(1)
            want = [o.group(1).rstrip() for line in body.splitlines() if (o := OUT.search(line))]
            yield f"{doc.relative_to(CALCITE).as_posix()} block {n}", name, f"module test.{name}\n\n{body}", want


def run(calx, path, mode):
    return subprocess.run([calx, "run", *mode, path], cwd=CALCITE, capture_output=True, text=True,
                          encoding="utf-8")


def main():
    calx = find_calx()
    passed = failed = 0

    def report(name, mode, ok, result):
        nonlocal passed, failed
        label = f"{name} ({'release' if mode else 'debug'})"
        if ok:
            passed += 1
            print(f"ok   {label}")
        else:
            failed += 1
            print(f"FAIL {label}: status {result.returncode}\n{result.stdout}{result.stderr}")

    for test in sorted(HERE.glob("*.calx")):
        if test.name.startswith("doc_"):
            continue
        for mode in ([], ["--release"]):
            r = run(calx, test.relative_to(CALCITE).as_posix(), mode)
            report(test.relative_to(CALCITE).as_posix(), mode, r.returncode == 0 and r.stdout.splitlines()[-1:] == ["ok"], r)

    for label, name, source, want in examples():
        path = HERE / f"{name}.calx"
        path.write_text(source, encoding="utf-8", newline="\n")
        try:
            for mode in ([], ["--release"]):
                r = run(calx, path.relative_to(CALCITE).as_posix(), mode)
                report(label, mode, r.returncode == 0 and [l.rstrip() for l in r.stdout.splitlines()] == want, r)
        finally:
            path.unlink()

    with tempfile.TemporaryDirectory() as tmp:
        for mode in ([], ["--release"]):
            out = Path(tmp) / f"calcite{'-release' if mode else ''}{'.exe' if sys.platform == 'win32' else ''}"
            r = subprocess.run([calx, "build", *mode, "src/calcite.calx", "-o", str(out)], cwd=CALCITE,
                               capture_output=True, text=True, encoding="utf-8")
            report("src/calcite.calx builds", mode, r.returncode == 0, r)

    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
