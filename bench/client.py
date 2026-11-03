"""Runs Mojang's own client against Calcite for the numbers of chunks a real client is sent
(CAL-94): a new world's view-32 join, the server's memory, and a flight at each speed, each on a
fresh server and world, through rig/runner/realclient.py --fly.

    py -I bench/client.py [--speeds 25,100] [--seconds 30] [--record]

The server is the release build, built with calx into build/bench/<platform>/client/. Each run
joins at render and view distance 32 on a new world with C2ME's seed, then flies forward at the
speed for --seconds, and realclient.py's flight.json is kept: the join's chunks and times, the
server's memory before the join, with the player still and at the most, its ticks during the
flight, and how much of the view the client had as it flew. --record writes
bench/results/client-<platform>.json with the machine, the toolchain and the commit (D34). It
needs a desktop, a launcher's 26.3 files and Windows for the keys, as realclient.py does, and
takes the client's window to the front while it flies.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import CALCITE, EXE, PLATFORM, commit, find_calx, machine, output  # noqa: E402

BUILD = CALCITE / "build" / "bench" / PLATFORM / "client"
SEED = "114862964781274189"
FLIGHT = CALCITE / "build" / "rig" / "realclient" / "flight.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--speeds", default="25,100", help="the flying speeds, times vanilla's, comma-separated")
    parser.add_argument("--seconds", type=int, default=30, help="how long each flight goes forward")
    parser.add_argument("--record", action="store_true", help="write bench/results/client-<platform>.json")
    args = parser.parse_args()
    if args.record and (args.speeds != "25,100" or args.seconds != 30):
        sys.exit("client: only 25 and 100 for 30 seconds are recorded")

    calx = find_calx()
    BUILD.mkdir(parents=True, exist_ok=True)
    server = BUILD / f"calcite{EXE}"
    subprocess.run([calx, "build", "--release", "src/calcite.calx", "-o", str(server)], cwd=CALCITE, check=True)
    runs = []
    for speed in args.speeds.split(","):
        FLIGHT.unlink(missing_ok=True)
        print(f"client: flying at {speed} times vanilla's", flush=True)
        got = subprocess.run([sys.executable, "-I", str(CALCITE / "rig" / "runner" / "realclient.py"), "--server", str(server),
                              "--fly", speed, "--fly-seconds", str(args.seconds), "--seed", SEED],
                             cwd=CALCITE, capture_output=True, text=True)
        for line in got.stdout.splitlines():
            if line.startswith(("memory:", "flight:", "watch: flight", "watch: after", "watch: join", "FAIL", "keys:")):
                print(f"  {line}", flush=True)
        if got.returncode != 0 or not FLIGHT.is_file():
            sys.exit(f"client: the flight at {speed} failed:\n{got.stdout[-3000:]}{got.stderr[-2000:]}")
        runs.append(json.loads(FLIGHT.read_text(encoding="utf-8")))

    for r in runs:
        f, m, t = r["flight"], r["memory_mib"], r["ticks"] or {}
        print(f"{r['speed']:g}x: {f['blocks_a_second']} blocks a second, {f['chunks_a_second']} chunks a second sent, "
              f"the view {f['had_of_view'][0]}% there on average and {f['had_of_view'][1]}% at the least, "
              f"MSPT {t.get('mspt_mean')} mean, {t.get('mspt_max')} most; memory {m['idle']} MiB idle, "
              f"{m['joined']} MiB with the player still, {m['peak']} MiB at the most")

    if args.record:
        result = {
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit(CALCITE), "calx": {"version": output([calx, "version"]), "commit": commit(Path(calx).parents[3])},
            "machine": machine(), "seed": SEED, "view": 32, "flight_seconds": args.seconds, "runs": runs,
        }
        out = HERE / "results" / f"client-{PLATFORM}.json"
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nclient: wrote {out}")


if __name__ == "__main__":
    main()
