"""Runs the worldgen benchmark with Terralith and Terratonic (CAL-92), set up as C2ME's own but over
smaller areas: the same seed and packs, a warm-up of a 512-block radius about the origin, then a
measured 1,024-block radius about 1,000,000, 1,000,000, 16,641 chunks as Chunky counts them, all in
one launch on a fresh world. C2ME's own runs a 1,536-block warm-up and a 3,072-block measured
radius, 148,225 chunks, which takes vanilla hours at 1 thread (D293).

    py -I bench/terralith.py [--threads 1,8,16,32] [--radius 1024] [--no-packs] [--record]

With --no-packs, the same runs have no packs, so they time vanilla's own worldgen, recorded as
bench/results/worldgen-<platform>.json. Each run also gives a steady rate: the chunks a second
from the progress line at 10% done to the one at 90%, without the start, as the generator's
pipeline fills, or the last chunks, which fewer workers share.

The packs are fetched from Modrinth into build/bench/packs/ and checked against their SHA-512s,
since they're Stardust Labs' and aren't ours to commit. Each thread count runs the release
server in build/bench/<platform>/terralith/ with `chunk-workers` set to it, pregenerates with its
`pregen` command and reads the chunks it logs, and the seconds the workers spent in each stage,
which `--stage-times` writes. The system gives the CPU time and the peak memory. --record writes
bench/results/terralith-<platform>.json, with the machine, the toolchain and the commit (D34). The
table puts vanilla's, Paper's and C2ME's rates beside Calcite's where others.py has recorded them on
this platform, in bench/results/others-<platform>.json, or others-worldgen-<platform>.json without
the packs, so every number in it is from the same machine.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import CALCITE, EXE, PLATFORM, commit, find_calx, machine, output, usage_windows  # noqa: E402

BUILD = CALCITE / "build" / "bench" / PLATFORM
PACKS = CALCITE / "build" / "bench" / "packs"
PORT = 25641
SEED = "114862964781274189"
WARMUP = {"x": 0, "z": 0, "radius": 512}
MEASURED = {"x": 1000000, "z": 1000000, "radius": 1024}
# The packs C2ME's benchmark names, at the versions made for 26.3.
PINS = [
    {"name": "Terralith", "version": "2.6.5+26.3", "file": "Terralith_v2.6.5+26.3.zip",
     "url": "https://cdn.modrinth.com/data/8oi3bsk5/versions/fqnsIp6d/Terralith_v2.6.5%2B26.3.zip",
     "sha512": "edc75fb0be5d009590d16d0d96ef73fc2e87c3edd3c5b4d80589070a636beeaf4ea202ee3cffaa06ad68a615bbb03e924cd3e173cbd649fb47b5ec6fc74c2482"},
    {"name": "Terratonic", "version": "3.0.31", "file": "terratonic-datapack-3.0.31.zip",
     "url": "https://cdn.modrinth.com/data/3L2L6sWL/versions/RUBbKGx8/terratonic-datapack-3.0.31.zip",
     "sha512": "82deeee38afead548bc86cc6eed5d536b164194c442abbc4f0e21092a234430484e57989fdd7750e13c3bcc47b87f7365859b899a210f97b6fe55213e6fd6912"},
]
DONE = re.compile(r"Pregen \S+ done: (\d+) chunks in ")
PROGRESS = re.compile(r"Pregen \S+: (\d+) of (\d+) chunks")
# The generator writes its stage times when it's had no work for 5 seconds (`--stage-times`).
SETTLE = 6.5


def stage_times(path):
    """The workers' seconds in each stage so far, as `--stage-times` writes them."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    return {k: float(v) for k, v in (part.split("=") for part in text.split())}


def fetch():
    """The packs, fetched where they're missing, each checked against its SHA-512."""
    PACKS.mkdir(parents=True, exist_ok=True)
    paths = []
    for pin in PINS:
        path = PACKS / pin["file"]
        if not path.is_file() or hashlib.sha512(path.read_bytes()).hexdigest() != pin["sha512"]:
            print(f"terralith: fetching {pin['name']} {pin['version']}", flush=True)
            request = urllib.request.Request(pin["url"], headers={"User-Agent": "calcite-bench (github.com/ellipog/calcite)"})
            with urllib.request.urlopen(request, timeout=120) as r:
                data = r.read()
            if hashlib.sha512(data).hexdigest() != pin["sha512"]:
                sys.exit(f"terralith: {pin['file']} doesn't match its SHA-512")
            path.write_bytes(data)
        paths.append(path)
    return paths


def build(calx):
    BUILD.mkdir(parents=True, exist_ok=True)
    server = BUILD / f"calcite{EXE}"
    subprocess.run([calx, "build", "--release", "src/calcite.calx", "-o", str(server)], cwd=CALCITE, check=True)
    return server


def prepare(folder, packs, threads):
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "world" / "datapacks").mkdir(parents=True)
    for pack in packs:
        shutil.copyfile(pack, folder / "world" / "datapacks" / pack.name)
    (folder / "server.properties").write_text(
        f"online-mode=false\nserver-ip=127.0.0.1\nserver-port={PORT}\nlevel-seed={SEED}\n"
        "view-distance=10\nsimulation-distance=10\nmotd=Calcite worldgen benchmark\n", encoding="utf-8")
    (folder / "calcite.properties").write_text(
        f"console-dashboard=off\nrecord-inputs=false\nchunk-workers={threads}\n", encoding="utf-8")


def one_run(server, packs, threads, measured):
    folder = BUILD / "terralith"
    prepare(folder, packs, threads)
    lines = []
    # Each progress line's time and chunks done, as it came.
    progress = []
    ready = threading.Event()
    finished = threading.Event()
    stages_file = folder / "stage-times.txt"
    p = subprocess.Popen([str(server), "--stage-times", str(stages_file)], cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8")

    def read():
        for line in p.stdout:
            lines.append(line.rstrip("\n"))
            if "Done (" in line:
                ready.set()
            if m := PROGRESS.search(line):
                progress.append((time.perf_counter(), int(m.group(1)), int(m.group(2))))
            if DONE.search(line):
                finished.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def say(*commands):
        for c in commands:
            p.stdin.write(c + "\n")
        p.stdin.flush()

    def pregen(area):
        finished.clear()
        first = len(lines)
        seen = len(progress)
        began = time.perf_counter()
        say(f"pregen center {area['x']} {area['z']}", f"pregen radius {area['radius']}", "pregen start")
        if not finished.wait(4 * 3600):
            p.kill()
            sys.exit("terralith: the pregeneration didn't finish:\n" + "\n".join(lines[-20:]))
        took = time.perf_counter() - began
        done = next(DONE.search(line) for line in lines[first:] if DONE.search(line))
        # The steady rate: from the first progress line at 10% done or more to the last at 90% or
        # less, leaving out the start, as the first starts and biomes fill the generator's
        # pipeline, and the last few chunks, which fewer workers share.
        lines_here = progress[seen:]
        middle = [(t, n) for t, n, total in lines_here if total * 0.1 <= n <= total * 0.9]
        steady = (middle[-1][1] - middle[0][1]) / (middle[-1][0] - middle[0][0]) if len(middle) >= 2 else None
        # The workers' seconds in each stage, once the generator has settled and written them.
        time.sleep(SETTLE)
        return {"chunks": int(done.group(1)), "seconds": took, "chunks_per_second": int(done.group(1)) / took,
                "steady_chunks_per_second": steady, "stages_total": stage_times(stages_file)}

    if not ready.wait(300):
        p.kill()
        sys.exit("terralith: the server didn't say it was ready:\n" + "\n".join(lines[-20:]))
    warm = pregen(WARMUP)
    print(f"  {threads} threads: warm-up {warm['chunks']} chunks, {warm['chunks_per_second']:.1f} a second", flush=True)
    result = pregen(measured)
    before, after = warm["stages_total"], result["stages_total"]
    result["stage_seconds"] = {k: after[k] - before.get(k, 0.0) for k in after} if after else None
    say("stop")
    if PLATFORM == "windows":
        p.wait(600)
        cpu, peak = usage_windows(p._handle)
    else:
        import os
        _, status, usage = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        cpu, peak = usage.ru_utime + usage.ru_stime, usage.ru_maxrss * 1024
    reader.join(5)
    if p.returncode != 0:
        sys.exit(f"terralith: the server ended with status {p.returncode}:\n" + "\n".join(lines[-20:]))
    problems = [line for line in lines if "WARN]" in line or "ERROR]" in line]
    problems = [line for line in problems if "OFFLINE" not in line and "online-mode" not in line
                and "no attempt to authenticate" not in line and "hackers" not in line]
    result.update(threads=threads, warmup=warm, cpu_seconds=cpu, peak_memory_mib=peak / 2**20, problems=problems[:50])
    steady = result["steady_chunks_per_second"]
    print(f"  {threads} threads: {result['chunks']} chunks in {result['seconds']:.1f} s, "
          f"{result['chunks_per_second']:.1f} a second" + (f", {steady:.1f} steady" if steady else "")
          + f", peak {result['peak_memory_mib']:.0f} MiB"
          + (f", {len(problems)} warnings" if problems else ""), flush=True)
    if stages := result["stage_seconds"]:
        total = sum(stages.values()) or 1.0
        print("    the workers' time: " + ", ".join(f"{k} {v / total * 100:.0f}%" for k, v in stages.items()), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--threads", default="1,8,16,32", help="the thread counts, comma-separated")
    parser.add_argument("--radius", type=int, default=MEASURED["radius"], help="the measured run's radius in blocks")
    parser.add_argument("--record", action="store_true", help="write bench/results/terralith-<platform>.json")
    parser.add_argument("--no-packs", action="store_true",
                        help="vanilla's own worldgen, the same runs without the packs, recorded as worldgen-<platform>.json")
    args = parser.parse_args()
    measured = dict(MEASURED, radius=args.radius)
    if args.record and measured != MEASURED:
        sys.exit(f"terralith: only the measured area {MEASURED} is recorded")

    packs = [] if args.no_packs else fetch()
    calx = find_calx()
    server = build(calx)
    runs = [one_run(server, packs, int(t), measured) for t in args.threads.split(",")]

    what = "Vanilla's worldgen" if args.no_packs else "Terralith + Terratonic"
    print(f"\n{what}, seed {SEED}, {measured['radius']}-block radius about "
          f"{measured['x']}, {measured['z']}, chunks a second:")
    # The Java servers' rates on this platform, from others.py, for the same area only.
    others = HERE / "results" / f"{'others-worldgen' if args.no_packs else 'others'}-{PLATFORM}.json"
    theirs = {}
    if others.is_file() and measured == MEASURED:
        recorded = json.loads(others.read_text(encoding="utf-8"))
        theirs = {name: {r["threads"]: r["chunks_per_second"] for r in server["runs"]}
                  for name, server in recorded["servers"].items()}
    names = [n for n in ("c2me", "paper", "vanilla") if n in theirs]

    def row(cells):
        print("| " + " | ".join(cells) + " |")

    row(["Threads", "Calcite", "Steady"] + [{"c2me": "C2ME", "paper": "Paper", "vanilla": "Vanilla"}[n] for n in names])
    row(["---"] * (3 + len(names)))
    for r in runs:
        t, steady = r["threads"], r["steady_chunks_per_second"]
        row([str(t), f"{r['chunks_per_second']:.1f}", f"{steady:.1f}" if steady else ""]
            + [f"{theirs[n][t]:.1f}" if t in theirs[n] else "" for n in names])
    if names:
        print(f"\nThe Java servers' are from {others.relative_to(CALCITE).as_posix()}, recorded on this platform by others.py.")

    if args.record:
        result = {
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit(CALCITE), "calx": {"version": output([calx, "version"]), "commit": commit(Path(calx).parents[3])},
            "machine": machine(), "packs": [{k: pin[k] for k in ("name", "version", "sha512")} for pin in PINS if packs],
            "seed": SEED, "warmup": WARMUP, "measured": measured, "runs": runs,
        }
        out = HERE / "results" / f"{'worldgen' if args.no_packs else 'terralith'}-{PLATFORM}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nterralith: wrote {out}")


if __name__ == "__main__":
    main()
