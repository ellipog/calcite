"""Runs the bot benchmark (P4.10, D154): Calcite's release build, and a swarm of bots that join it,
walk and chat, measured from both sides.

    py -I bench/run.py [--runs 5] [--bots 100] [--rate 20] [--seconds 45] [--record]

Each run starts the server fresh in build/bench/<platform>/world/, waits for it to say it's
ready, runs src/rig/swarm.calx against it, then types `stop` and waits for it to end. The
server's `--tick-times` file gives each tick's work, and the system gives its CPU time and peak
memory. A run's numbers are over its steady part, from 2 seconds after the last bot had all its
chunks to the end, and its joins. The result is the median of the runs. --record writes
bench/results/bots-<platform>.json, with the machine, the toolchain and the commit beside the
numbers (D34); with one already there, each number is compared with it. On Linux, use python3.
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parent
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
from launch import find_calx  # noqa: E402

PLATFORM = "windows" if os.name == "nt" else "linux"
EXE = ".exe" if os.name == "nt" else ""
BUILD = CALCITE / "build" / "bench" / PLATFORM
PORT = 25640
VIEW = 10
# The scenario that's recorded. Other values are for a look, and aren't recorded.
SCENARIO = {"bots": 100, "rate": 20, "seconds": 45}


def output(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw).stdout.strip()


def build(calx):
    BUILD.mkdir(parents=True, exist_ok=True)
    server = BUILD / f"calcite{EXE}"
    swarm = BUILD / f"swarm{EXE}"
    for source, exe in (("src/calcite.calx", server), ("src/rig/swarm.calx", swarm)):
        subprocess.run([calx, "build", "--release", source, "-o", str(exe)], cwd=CALCITE, check=True)
    return server, swarm


def prepare(world):
    world.mkdir(parents=True, exist_ok=True)
    (world / "server.properties").write_text(
        f"online-mode=false\nserver-ip=127.0.0.1\nserver-port={PORT}\nmax-players=1000\n"
        f"view-distance={VIEW}\nsimulation-distance={VIEW}\nmotd=Calcite bot benchmark\n", encoding="utf-8")
    (world / "calcite.properties").write_text("console-dashboard=off\nrecord-inputs=false\n", encoding="utf-8")


def usage_windows(handle):
    """The process's CPU time, in seconds, and its peak working set, in bytes."""
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    class COUNTERS(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    times = [FILETIME() for _ in range(4)]
    ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(int(handle)), *[ctypes.byref(t) for t in times])
    cpu = sum(((t.high << 32) | t.low) for t in times[2:]) / 1e7
    counters = COUNTERS()
    counters.cb = ctypes.sizeof(COUNTERS)
    ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(int(handle)), ctypes.byref(counters), counters.cb)
    return cpu, counters.PeakWorkingSetSize


def warm_up(server, world):
    """Starts the server once and stops it, unmeasured, so a new build makes its boot cache, and
    reads the vanilla data the first time, before any run counts."""
    prepare(world)
    p = subprocess.Popen([str(server)], cwd=world, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    for line in p.stdout:
        if "Done (" in line:
            p.stdin.write("stop\n")
            p.stdin.flush()
    if p.wait(60) != 0:
        sys.exit(f"run: the warm-up start ended with status {p.returncode}")


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


def one_run(server, swarm, world, bots, rate, seconds):
    prepare(world)
    ticks_path = world / "tick-times.txt"
    ticks_path.unlink(missing_ok=True)
    lines = []
    ready = threading.Event()
    began = time.perf_counter()
    p = subprocess.Popen([str(server), "--tick-times", str(ticks_path)], cwd=world, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")

    def read():
        for line in p.stdout:
            lines.append(line.rstrip("\n"))
            if "Done (" in line:
                ready.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    if not ready.wait(120):
        p.kill()
        sys.exit("run: the server didn't say it was ready:\n" + "\n".join(lines[-20:]))
    started = time.perf_counter()
    got = subprocess.run([str(swarm), str(PORT), str(bots), str(rate), str(seconds), str(VIEW)], cwd=CALCITE,
                         capture_output=True, text=True, encoding="utf-8")
    if got.returncode != 0:
        p.kill()
        sys.exit(f"run: the swarm failed with status {got.returncode}:\n{got.stdout}{got.stderr}")
    result = json.loads(got.stdout.strip().splitlines()[-1])
    p.stdin.write("stop\n")
    p.stdin.flush()
    if os.name == "nt":
        p.wait(60)
        cpu, peak = usage_windows(p._handle)
    else:
        _, status, usage = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        cpu, peak = usage.ru_utime + usage.ru_stime, usage.ru_maxrss * 1024
    reader.join(5)
    if p.returncode != 0:
        sys.exit(f"run: the server ended with status {p.returncode}:\n" + "\n".join(lines[-20:]))
    if result["kicked"] or result["joined"] != bots or result["all_loaded_ms"] is None:
        sys.exit(f"run: not every bot joined and stayed: {result}")

    # The swarm's times are from its start; the server's from its own, a little after it was
    # started. The difference between the two is what the runner measured between them.
    offset = (started - began) * 1e9
    ticks = []
    for line in ticks_path.read_text(encoding="utf-8").splitlines():
        at, busy = line.split()
        ticks.append((int(at) - offset, int(busy)))
    steady_from = result["all_loaded_ms"] * 1e6 + 2e9
    steady_to = result["end_ms"] * 1e6
    steady = [busy for at, busy in ticks if steady_from <= at < steady_to]
    joining = [busy for at, busy in ticks if 0 <= at < result["all_loaded_ms"] * 1e6]
    if len(steady) < 100:
        sys.exit(f"run: only {len(steady)} ticks in the steady part; run longer")
    span = (steady_to - steady_from) / 1e9
    return {
        "mspt_mean": statistics.fmean(steady) / 1e6,
        "mspt_p99": percentile(steady, 0.99) / 1e6,
        "mspt_max": max(steady) / 1e6,
        "tps": len(steady) / span,
        "joining_mspt_mean": statistics.fmean(joining) / 1e6 if joining else None,
        "joining_mspt_max": max(joining) / 1e6 if joining else None,
        "join_ms_median": statistics.median(result["join_ms"]),
        "join_ms_max": max(result["join_ms"]),
        "all_loaded_ms": result["all_loaded_ms"],
        "cpu_seconds": cpu,
        "cpu_percent_of_one_core": cpu / (seconds + (started - began)) * 100,
        "peak_memory_mib": peak / 2**20,
        "chunks_sent": result["chunks"],
        "chats_received": result["chats_received"],
        "mib_received": result["bytes"] / 2**20,
    }


# What each number is, how it's shown, and whether more is worse.
SHOWN = [
    ("mspt_mean", "MSPT, mean", "{:.3f} ms", True),
    ("mspt_p99", "MSPT, p99", "{:.3f} ms", True),
    ("mspt_max", "MSPT, max", "{:.3f} ms", True),
    ("tps", "TPS", "{:.2f}", False),
    ("joining_mspt_mean", "MSPT while joining, mean", "{:.3f} ms", True),
    ("joining_mspt_max", "MSPT while joining, max", "{:.3f} ms", True),
    ("join_ms_median", "Join to all chunks, median", "{:.0f} ms", True),
    ("join_ms_max", "Join to all chunks, max", "{:.0f} ms", True),
    ("cpu_seconds", "CPU time", "{:.2f} s", True),
    ("peak_memory_mib", "Peak memory", "{:.1f} MiB", True),
    ("chunks_sent", "Chunks sent", "{:.0f}", False),
    ("mib_received", "Bytes to the bots", "{:.1f} MiB", False),
]


def machine():
    info = {"platform": PLATFORM, "python": platform.python_version(), "os": platform.platform()}
    if os.name == "nt":
        ps = ("$c = Get-CimInstance Win32_Processor; $m = Get-CimInstance Win32_ComputerSystem; "
              "\"$($c.Name)|$(($c | Measure-Object NumberOfCores -Sum).Sum)|"
              "$(($c | Measure-Object NumberOfLogicalProcessors -Sum).Sum)|$($m.TotalPhysicalMemory)\"")
        name, cores, threads, memory = output(["powershell", "-NoProfile", "-Command", ps]).split("|")
        info.update(cpu=name.strip(), cores=int(cores), threads=int(threads), memory_gib=round(int(memory) / 2**30, 1))
    else:
        cpuinfo = Path("/proc/cpuinfo").read_text()
        name = next((l.split(":", 1)[1].strip() for l in cpuinfo.splitlines() if l.startswith("model name")), "")
        mem = next((l for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal")), "0 0")
        info.update(cpu=name, threads=os.cpu_count(), memory_gib=round(int(mem.split()[1]) / 2**20, 1),
                    kernel=platform.release())
    return info


def commit(cwd):
    try:
        return output(["git", "rev-parse", "HEAD"], cwd=cwd)
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--bots", type=int, default=SCENARIO["bots"])
    parser.add_argument("--rate", type=int, default=SCENARIO["rate"])
    parser.add_argument("--seconds", type=int, default=SCENARIO["seconds"])
    parser.add_argument("--record", action="store_true", help="write bench/results/bots-<platform>.json")
    args = parser.parse_args()
    scenario = {"bots": args.bots, "rate": args.rate, "seconds": args.seconds}
    if args.record and scenario != SCENARIO:
        sys.exit(f"run: only the scenario {SCENARIO} is recorded")

    calx = find_calx()
    server, swarm = build(calx)
    warm_up(server, BUILD / "world")
    runs = []
    for i in range(args.runs):
        r = one_run(server, swarm, BUILD / "world", args.bots, args.rate, args.seconds)
        runs.append(r)
        print(f"  run {i + 1}/{args.runs}: MSPT {r['mspt_mean']:.3f} ms mean, {r['mspt_p99']:.3f} ms p99, "
              f"joins {r['join_ms_median']:.0f} ms median, CPU {r['cpu_seconds']:.2f} s, "
              f"peak {r['peak_memory_mib']:.1f} MiB, {r['chats_received']} chats received", flush=True)
    medians = {key: statistics.median(r[key] for r in runs if r[key] is not None) for key, *_ in SHOWN}

    out = HERE / "results" / f"bots-{PLATFORM}.json"
    before = json.loads(out.read_text(encoding="utf-8"))["medians"] if out.exists() and scenario == SCENARIO else None
    print(f"\n{args.bots} bots joining {args.rate} a second, {args.seconds} s, view {VIEW}, {args.runs} runs, medians:")
    print("| Measure | Median |" + (" Recorded | Change |" if before else ""))
    print("| --- | --- |" + (" --- | --- |" if before else ""))
    flagged = []
    for key, label, fmt, worse_up in SHOWN:
        row = f"| {label} | {fmt.format(medians[key])} |"
        if before and before.get(key):
            change = (medians[key] - before[key]) / before[key] * 100
            row += f" {fmt.format(before[key])} | {change:+.1f}% |"
            if worse_up and change > 5:
                flagged.append(label)
        print(row)
    if flagged:
        print(f"\nrun: more than 5% worse than recorded, to look into before more work lands (D34): {', '.join(flagged)}")

    if args.record:
        result = {
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit(CALCITE), "calx": {"version": output([calx, "version"]), "commit": commit(Path(calx).parents[3])},
            "machine": machine(), "scenario": dict(scenario, view=VIEW, simulation=VIEW, compression=256),
            "runs": args.runs, "medians": medians, "each_run": runs,
        }
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nrun: wrote {out}")


if __name__ == "__main__":
    main()
