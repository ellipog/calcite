"""The determinism check, G5.3 (D21, D283): a session the server records on many threads replays on
one to the same packets and lines.

    py -I rig/lockstep.py [--bots 4] [--seconds 20] [--workers 8] [--server EXE] [--swarm EXE]

The server is Calcite's release build, recording its inputs, in a new world of a fixed seed in
build/lockstep/<platform>/, with `chunk-workers` threads generating, reading and lighting chunks
and bots from src/rig/swarm.calx walking out from spawn from the start, so new chunks are made the
whole time. Then `--replay` plays the input log back, which runs the generator and light on its own
thread, and checks each packet sent and line logged against the recording. Any difference fails,
with where it first was. On Linux, use python3.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parent
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
from launch import find_calx  # noqa: E402

PLATFORM = "windows" if os.name == "nt" else "linux"
EXE = ".exe" if os.name == "nt" else ""
BUILD = CALCITE / "build" / "lockstep" / PLATFORM
PORT = 25643
VIEW = 8
SEED = "20261103"


def build(calx):
    BUILD.mkdir(parents=True, exist_ok=True)
    server = BUILD / f"calcite{EXE}"
    swarm = BUILD / f"swarm{EXE}"
    for source, exe in (("src/calcite.calx", server), ("src/rig/swarm.calx", swarm)):
        subprocess.run([calx, "build", "--release", source, "-o", str(exe)], cwd=CALCITE, check=True)
    return server, swarm


def prepare(world, workers):
    if world.exists():
        shutil.rmtree(world)
    world.mkdir(parents=True)
    (world / "server.properties").write_text(
        f"online-mode=false\nwhite-list=false\nserver-ip=127.0.0.1\nserver-port={PORT}\nmax-players=100\n"
        f"view-distance={VIEW}\nsimulation-distance={VIEW}\nlevel-seed={SEED}\nmotd=Calcite lockstep check\n",
        encoding="utf-8")
    (world / "calcite.properties").write_text(
        f"console-dashboard=off\nrecord-inputs=true\nchunk-workers={workers}\n", encoding="utf-8")


def record(server, swarm, world, bots, seconds):
    """Runs the server with the bots on it, and gives the input log it recorded."""
    lines = []
    ready = threading.Event()
    p = subprocess.Popen([str(server)], cwd=world, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8")

    def read():
        for line in p.stdout:
            lines.append(line.rstrip("\n"))
            if "Done (" in line:
                ready.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    if not ready.wait(300):
        p.kill()
        sys.exit("lockstep: the server didn't say it was ready:\n" + "\n".join(lines[-20:]))
    got = subprocess.run([str(swarm), str(PORT), str(bots), str(bots), str(seconds), str(VIEW), "--walk-at-once", "--speed=4"],
                         cwd=CALCITE, capture_output=True, text=True, encoding="utf-8")
    p.stdin.write("stop\n")
    p.stdin.flush()
    p.wait(300)
    reader.join(5)
    if got.returncode != 0:
        sys.exit(f"lockstep: the bots failed with status {got.returncode}:\n{got.stdout}{got.stderr}")
    if p.returncode != 0:
        sys.exit(f"lockstep: the server ended with status {p.returncode}:\n" + "\n".join(lines[-20:]))
    logs = sorted((world / "recordings").glob("*"))
    if not logs:
        sys.exit("lockstep: the server recorded no input log")
    return logs[-1], got.stdout.strip().splitlines()[-1]


def replay(server, world, log):
    """Plays the input log back, and gives whether it went as recorded, and its last lines."""
    got = subprocess.run([str(server), "--replay", str(log.relative_to(world))], cwd=world, capture_output=True,
                         text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    tail = (got.stdout + got.stderr).strip().splitlines()[-6:]
    return got.returncode == 0, tail


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bots", type=int, default=4)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--server", help="a server already built, instead of building one")
    parser.add_argument("--swarm", help="bots already built, instead of building them")
    args = parser.parse_args()
    if args.workers < 2:
        sys.exit("lockstep: the recording needs at least 2 chunk workers, or there's nothing to compare")
    if args.server and args.swarm:
        server, swarm = Path(args.server).resolve(), Path(args.swarm).resolve()
    else:
        server, swarm = build(find_calx())
    world = BUILD / "world"
    prepare(world, args.workers)
    began = time.perf_counter()
    log, bots = record(server, swarm, world, args.bots, args.seconds)
    recorded = time.perf_counter() - began
    began = time.perf_counter()
    same, tail = replay(server, world, log)
    replayed = time.perf_counter() - began
    size = log.stat().st_size
    print(f"recorded {log.name}, {size / 2**20:.1f} MiB, with {args.workers} chunk workers and {args.bots} bots in {recorded:.0f} s")
    print(f"bots: {bots}")
    print(f"replayed on one thread in {replayed:.0f} s:")
    for line in tail:
        print("  " + line)
    report = next((l for l in reversed(tail) if "Replayed " in l or "went another way" in l), None)
    if not same or report is None:
        sys.exit("lockstep: the replay went another way than the recording")
    found = re.search(r"(\d+) ticks, (\d+) packets and lines compared, (\d+) different", report)
    if not found or int(found.group(3)) != 0 or int(found.group(2)) == 0:
        sys.exit("lockstep: the replay's report isn't a match")
    print("same: one thread and many gave the same packets and lines")


main()
