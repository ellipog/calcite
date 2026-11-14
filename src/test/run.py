"""Runs Calcite's Calx tests, in debug and release builds:

- every .calx file in this folder. Each panics on a wrong result and prints `ok` at its end.
- every ```calx block in src/README.md, whose `// out: ...` comments give the lines it prints,
  so the docs' examples can't go stale (D41).
- the server, src/calcite.calx, which runs until it's stopped, and the rig's adapter,
  src/rig/adapter.calx, which the rig runs, so they're only built.
- vanilla's own codecs on every packet the network tests' clients were sent, if the vanilla
  adapter is built (oracle/check_packets.calx, D145). Without it, that's skipped.

Debug builds also check that everything allocated is freed (Calx's D79). calx is found as
rig/calcite-adapter/launch.py finds it.

The builds run side by side, `--jobs` at once, the heaviest first, as a build's weight is the
lines of every module it reaches. They're free to overlap, as calx links each program under a name
of its own and each test's files go in a temp folder of its own. A test that talks over sockets,
or writes to a fixed folder under build/, is only built then, and run alone once the rest are
done, debug then release: its clients wait for the server's answers only so long, which a machine
busy with builds can outlast, and its two runs would share the folder. calx keeps the programs it
builds, so `calx run` then runs the one just built. Its debug and release builds are dealt each
on its own, weighed with what its run costs. `--shard K/N` runs the K-th of N parts, the builds
dealt out heaviest first to the lightest part, so CI's jobs share them evenly; every part works
out the same deal.

    py -I src/test/run.py [--jobs N] [--shard K/N] [TEST ...]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
SRC = CALCITE / "src"
DOCS = [CALCITE / "src" / "README.md"]
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
from launch import find_calx  # noqa: E402

BLOCK = re.compile(r"^```calx\n(.*?)^```", re.M | re.S)
OUT = re.compile(r"//\s*out:\s?(.*)$")
IMPORT = re.compile(r"^import ([A-Za-z_][\w.]*?)(?:\.\{|\s*$)", re.M)
# A test that's run alone: one that talks over sockets, or names a folder under build/.
ALONE = re.compile(r'"build/|listen\("127|connect\("127|\.poll\(')
# What a test run alone costs on top of its build, as weight: the seconds each of its runs took
# on CI's Windows runners, the slowest, on 2026-11-10, at about as much weight a second as a
# part's builds got through there. A part waits for its tests run alone, so they're dealt by it.
RUN_SECONDS = {"play": 176, "login": 80, "configuration": 32, "server": 31, "replay": 4}
WEIGHT_PER_SECOND = 10000
MODES = ([], ["--release"])
EXE = ".exe" if sys.platform == "win32" else ""


def examples():
    """Each docs example as (name, source, expected output lines). A block becomes a module
    under src/test/, so it imports Calcite's modules as Calcite does."""
    for doc in DOCS:
        for n, m in enumerate(BLOCK.finditer(doc.read_text(encoding="utf-8")), 1):
            name = f"doc_{doc.parent.name}_{n}"
            body = m.group(1)
            want = [o.group(1).rstrip() for line in body.splitlines() if (o := OUT.search(line))]
            yield f"{doc.relative_to(CALCITE).as_posix()} block {n}", name, f"module test.{name}\n\n{body}", want


class Weights:
    """The lines of each module, read once, and of every module a source reaches through its
    imports: what a build of it costs, near enough, as calx checks and compiles all of them."""

    def __init__(self):
        self.lines = {}
        self.imports = {}

    def module(self, name):
        if name not in self.lines:
            path = SRC / (name.replace(".", "/") + ".calx")
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            self.lines[name] = text.count("\n")
            self.imports[name] = IMPORT.findall(text)
        return self.lines[name]

    def of(self, source):
        total, seen, todo = source.count("\n"), set(), IMPORT.findall(source)
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            total += self.module(name)
            todo.extend(self.imports[name])
        return total


class Task:
    """Something to build, and check: its label, its weight, and what builds it, which returns
    the results to report, each (name, mode, passed, result); and for a test run alone, what runs
    it once the builds are done, which returns its results the same way."""

    def __init__(self, label, weight, work, alone=None):
        self.label, self.weight, self.work, self.alone = label, weight, work, alone


def run(calx, path, mode):
    return subprocess.run([calx, "run", *mode, path], cwd=CALCITE, capture_output=True, text=True,
                          encoding="utf-8")


def build(calx, source, mode, target):
    return subprocess.run([calx, "build", *mode, source, "-o", str(target)], cwd=CALCITE,
                          capture_output=True, text=True, encoding="utf-8")


def passed(r):
    return r.returncode == 0 and r.stdout.splitlines()[-1:] == ["ok"]


def tasks(calx, tmp):
    weights = Weights()
    out = []
    for test in sorted(HERE.glob("*.calx")):
        if test.name.startswith("doc_"):
            continue
        rel = test.relative_to(CALCITE).as_posix()
        source = test.read_text(encoding="utf-8")
        weight = weights.of(source)
        if ALONE.search(source):
            extra = RUN_SECONDS.get(test.stem, 0) * WEIGHT_PER_SECOND
            for mode in MODES:
                built = {}

                def make(rel=rel, mode=mode, built=built):
                    r = build(calx, rel, mode, Path(tmp) / f"{Path(rel).stem}{'-release' if mode else ''}{EXE}")
                    built["ok"] = r.returncode == 0
                    return [] if r.returncode == 0 else [(f"{rel} builds", mode, False, r)]

                def alone(rel=rel, mode=mode, built=built):
                    return [(rel, mode, passed(r), r) for r in [run(calx, rel, mode)]] if built.get("ok") else []

                out.append(Task(f"{rel} {'release' if mode else 'debug'}", weight + extra, make, alone))
        else:
            for mode in MODES:
                out.append(Task(f"{rel} {'release' if mode else 'debug'}", weight,
                                lambda rel=rel, mode=mode: [(rel, mode, passed(r), r) for r in [run(calx, rel, mode)]]))

    for label, name, source, want in examples():
        def example(label=label, name=name, source=source, want=want):
            path = HERE / f"{name}.calx"
            path.write_text(source, encoding="utf-8", newline="\n")
            results = []
            try:
                for mode in MODES:
                    r = run(calx, path.relative_to(CALCITE).as_posix(), mode)
                    results.append((label, mode, r.returncode == 0 and [l.rstrip() for l in r.stdout.splitlines()] == want, r))
            finally:
                path.unlink()
            return results
        out.append(Task(label, 2 * weights.of(source), example))

    def only_built(source, mode, name):
        r = build(calx, source, mode, Path(tmp) / f"{name}{EXE}")
        return [(f"{source} builds", mode, r.returncode == 0, r)]

    server = weights.of((SRC / "calcite.calx").read_text(encoding="utf-8"))
    adapter = weights.of((SRC / "rig" / "adapter.calx").read_text(encoding="utf-8"))
    out.append(Task("src/calcite.calx builds (debug)", server, lambda: only_built("src/calcite.calx", [], "calcite")))
    out.append(Task("src/calcite.calx builds (release)", server, lambda: only_built("src/calcite.calx", ["--release"], "calcite-release")))
    out.append(Task("src/rig/adapter.calx builds", adapter, lambda: only_built("src/rig/adapter.calx", ["--release"], "calcite-adapter")))
    return out


def deal(all_tasks, parts):
    """The tasks dealt into `parts` parts, heaviest first, each to the part with the least weight
    so far, ties to the first."""
    shares = [[] for _ in range(parts)]
    loads = [0] * parts
    for t in sorted(all_tasks, key=lambda t: (-t.weight, t.label)):
        k = loads.index(min(loads))
        shares[k].append(t)
        loads[k] += t.weight
    return shares


def main():
    parser = argparse.ArgumentParser(description="Runs Calcite's Calx tests.")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 1, 8),
                        help="builds at once (default: the cores, at most 8)")
    parser.add_argument("--shard", default="1/1", help="run the K-th of N parts, as K/N")
    parser.add_argument("only", nargs="*", help="run only the tests named, such as play or mob")
    args = parser.parse_args()
    k, n = (int(x) for x in args.shard.split("/"))
    if not 1 <= k <= n:
        parser.error("--shard is K/N with 1 <= K <= N")

    calx = find_calx()
    passes = fails = 0
    lock = threading.Lock()

    def report(name, mode, ok, result, seconds):
        nonlocal passes, fails
        label = f"{name} ({'release' if mode else 'debug'})"
        with lock:
            if ok:
                passes += 1
                print(f"ok   {label} [{seconds:.0f}s]", flush=True)
            else:
                fails += 1
                print(f"FAIL {label}: status {result.returncode}\n{result.stdout}{result.stderr}", flush=True)

    start = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        chosen = tasks(calx, tmp)
        if args.only:
            names = {f"src/test/{name}.calx" for name in args.only}
            chosen = [t for t in chosen if t.label.split(" ")[0] in names]
        mine = deal(chosen, n)[k - 1]
        later = [t for t in mine if t.alone]
        print(f"part {k} of {n}: {len(mine)} builds, {max(1, args.jobs)} at once, then {len(later)} tests alone", flush=True)

        def timed(work):
            began = time.monotonic()
            return work(), time.monotonic() - began

        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            futures = [pool.submit(timed, t.work) for t in mine]
            for f in as_completed(futures):
                results, seconds = f.result()
                for name, mode, ok, r in results:
                    report(name, mode, ok, r, seconds)

        for t in sorted(later, key=lambda t: t.label):
            results, seconds = timed(t.alone)
            for name, mode, ok, r in results:
                report(name, mode, ok, r, seconds)

    check = subprocess.run([calx, "oracle/check_packets.calx"],
                           cwd=CALCITE, capture_output=True, text=True, encoding="utf-8")
    if check.returncode == 2:
        print(f"skip vanilla reads the tests' packets: {check.stdout.strip()}")
    else:
        lines = check.stdout.splitlines()
        report(f"vanilla reads the tests' packets: {lines[-1] if lines else 'no output'}", ["--release"],
               check.returncode == 0, check, 0)

    print(f"{passes} passed, {fails} failed, in {time.monotonic() - start:.0f}s")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
