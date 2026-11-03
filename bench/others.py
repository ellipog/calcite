"""Runs the worldgen benchmark on vanilla, Paper and C2ME, on this machine (CAL-94), set up as C2ME's own
benchmark sets them up, so Calcite's numbers from terralith.py have theirs beside them from the same
machine: Chunky generates terralith.py's warm-up, a 512-block radius about the origin, then its
measured area, a 1,024-block radius about 1,000,000, 1,000,000, in one launch on an emptied world,
with C2ME's seed and Terralith and Terratonic.

    py -I bench/others.py [--servers vanilla,paper,c2me] [--threads 1,8,16,32] [--no-packs] [--record]
    py -I bench/others.py --servers c2me --threads 8 --radius 512     # a quick look, not recorded

- vanilla is Fabric with Fabric API and Chunky, and `-Dmax.bg.threads` set to the thread count.
- paper is Paper with Chunky, `chunk-system.worker-threads` set to it and `io-threads` to 4.
- c2me is Fabric with C2ME and the mods its benchmark runs with it, Lithium, ScalableLux, VMP and
  zfastnoise, with the zconfig zfastnoise needs, and C2ME's `globalExecutorParallelism` set to it.

Each runs on the JDK the rig finds, with C2ME's JVM flags but large pages, which Windows only gives a
process with a privilege it doesn't have. Everything is fetched into build/bench/jars/ and checked
against its hash, since none of it is ours to commit; Fabric and Paper then fetch Mojang's server
themselves. Each server keeps its folder in build/bench/<platform>/java/<server>/, with its configs
and what it fetched, and its worlds are emptied before each launch. A run's rate is the chunks over
the seconds from Chunky's start to its finish, and its steady rate is from its progress line at 10%
done to the one at 90%, as terralith.py measures Calcite's. --record writes
bench/results/others-<platform>.json, or with --no-packs, others-worldgen-<platform>.json, keeping
the runs recorded there of servers and thread counts not run this time.
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
from run import CALCITE, PLATFORM, commit, machine, usage_windows  # noqa: E402
from terralith import MEASURED, PINS as PACK_PINS, SEED, WARMUP, fetch as fetch_packs  # noqa: E402

sys.path.insert(0, str(CALCITE / "oracle"))
from jdk import EXE as JAVA_EXE, find_java_home  # noqa: E402

JARS = CALCITE / "build" / "bench" / "jars"
ROOT = CALCITE / "build" / "bench" / PLATFORM / "java"
PORT = 25642
UA = {"User-Agent": "calcite-bench (github.com/ellipog/calcite)"}

# What each server runs, fetched from Modrinth, PaperMC and Fabric.
FILES = {
    "fabric": {"version": "loader 0.20.1, installer 1.1.2", "file": "fabric-server-launch.jar",
               "url": "https://meta.fabricmc.net/v2/versions/loader/26.3/0.20.1/1.1.2/server/jar",
               "sha256": "70446947655b4f8f286aba896aa4c19a255e8ca8a730636ef2a6017ae4415d95"},
    "paper": {"version": "26.3-238", "file": "paper-26.3-238.jar",
              "url": "https://fill-data.papermc.io/v1/objects/989f93c29d5b61fe52804f834ea6b3a0a5775d05412e238ec78107197a6b5be6/paper-26.3-238.jar",
              "sha256": "989f93c29d5b61fe52804f834ea6b3a0a5775d05412e238ec78107197a6b5be6"},
    "fabric-api": {"version": "0.165.0+26.3", "file": "fabric-api-0.165.0+26.3.jar",
                   "url": "https://cdn.modrinth.com/data/P7dR8mSH/versions/EQKgpeKu/fabric-api-0.165.0%2B26.3.jar",
                   "sha512": "0a4b8a14e847b71567b557b43d906c2167fa263eeeef37454a821ba286996e3da1616dc2d9647736d28a250d5ecf400541cae808359b29a62324a8a6f2ad5e30"},
    "chunky-fabric": {"version": "1.5.3", "file": "Chunky-Fabric-1.5.3.jar",
                      "url": "https://cdn.modrinth.com/data/fALzjamp/versions/4Eotm6ov/Chunky-Fabric-1.5.3.jar",
                      "sha512": "b83bfe7b218d0aa6232af977ae741dc1f82b10e50cd12bb759f65cf416b8b62beccb543e587ef0b9670abe03815660f8e091bc6823624d65cf07300571573516"},
    "chunky-bukkit": {"version": "1.5.3", "file": "Chunky-Bukkit-1.5.3.jar",
                      "url": "https://cdn.modrinth.com/data/fALzjamp/versions/MdY6JATr/Chunky-Bukkit-1.5.3.jar",
                      "sha512": "43ffecc6e6a734b752da41575bbb316526c124c3f878942437d5133c377bfbd9b78bda975520dc074d7158c15dade58a444ccd0fd8d8a25d165b6fc450140422"},
    "c2me": {"version": "0.4.2-alpha.0.115+26.3", "file": "c2me-fabric-mc26.3-0.4.2-alpha.0.115.jar",
             "url": "https://cdn.modrinth.com/data/VSNURh3q/versions/Vhj7rn6M/c2me-fabric-mc26.3-0.4.2-alpha.0.115.jar",
             "sha512": "95582ffc5ed0963ab37fe7b62dca25373e69fbdac3ccb37f6cffd89bfd0dfb7c7ff39a79085f7d4652822f3a471c99c9fd36e475f926cdc93be50e4e908d7549"},
    "lithium": {"version": "0.26.3+mc26.3", "file": "lithium-fabric-0.26.3+mc26.3.jar",
                "url": "https://cdn.modrinth.com/data/gvQqBUqZ/versions/fWv5bnZk/lithium-fabric-0.26.3%2Bmc26.3.jar",
                "sha512": "2ca92fb530135d2baddf0ba4cc4f93976234876a38c4aa02b487b2552400f005afcfbeebf5373fb4396fe2020537a42d7597b8da5a52b904355ef51d5fef07ad"},
    "scalablelux": {"version": "0.3.0-alpha.0.6+26.3", "file": "ScalableLux-fabric-mc26.3-0.3.0-alpha.0.6-all.jar",
                    "url": "https://cdn.modrinth.com/data/Ps1zyz6x/versions/g4eqNSKd/ScalableLux-fabric-mc26.3-0.3.0-alpha.0.6-all.jar",
                    "sha512": "ded5a939fb20ab81c1f33b147ca9b98050773dbb28dff16df939c7d567b626809522994ec8dbfb99e7f498dc6a4e62f25e141a87d18efb43f73fc5ad1569ccc9"},
    "vmp": {"version": "0.2.0+beta.7.238+26.3", "file": "vmp-fabric-mc26.3-0.2.0+beta.7.238-all.jar",
            "url": "https://cdn.modrinth.com/data/wnEe9KBa/versions/2TFDVjDf/vmp-fabric-mc26.3-0.2.0%2Bbeta.7.238-all.jar",
            "sha512": "c8658ccf8818a258e1160a2d394c80fd52708611570dc28d6bc391671a23e193760766ef77ddc5907e1a3a757cf20f4def67ae2bc184269effa547da1f377667"},
    "zconfig": {"version": "1.0.0+26.x", "file": "zconfig-1.0.0+26.x.jar",
                "url": "https://cdn.modrinth.com/data/4qmvXRB9/versions/tsgt79sG/zconfig-1.0.0%2B26.x.jar",
                "sha512": "baf87ac023fd0297f531897f0dcdcac3b0b35960683090adb3350a2281a211c5134a5373730a10628300caf5711b912705f16b33a1d1a73a3a86f346bcd7c6f5"},
    "zfastnoise": {"version": "1.1.2+26.3", "file": "zfastnoise-1.1.2+26.3.jar",
                   "url": "https://cdn.modrinth.com/data/OnlVIpq5/versions/71NgK90F/zfastnoise-1.1.2%2B26.3.jar",
                   "sha512": "fc64a40626b2e76d7fe56ddd7c9d81761819750cb12f9c5229273fd046d04936f299ebe2a4ff7bcb11345903ea7d413079eab49f29dfb1ff41a441775f7c1c7f"},
}
# Each server: the jar it starts from, and the mods or plugins in its folder.
SERVERS = {
    "vanilla": {"jar": "fabric", "mods": ["fabric-api", "chunky-fabric"], "folder": "mods"},
    "paper": {"jar": "paper", "mods": ["chunky-bukkit"], "folder": "plugins"},
    "c2me": {"jar": "fabric", "mods": ["fabric-api", "chunky-fabric", "c2me", "lithium", "scalablelux", "vmp", "zfastnoise", "zconfig"],
             "folder": "mods"},
}
# C2ME's JVM flags for its 1-to-16-thread runs, but large pages.
FLAGS = ["-Xmx16G", "-Xms16G", "-Xss4m", "-Xshare:off", "-XX:+DisableExplicitGC", "-XX:+UseNUMA", "-XX:+UseZGC",
         "-XX:-ZUncommit", "-XX:+UseCompactObjectHeaders", "-XX:+AlwaysPreTouch", "-XX:+UnlockExperimentalVMOptions",
         "-XX:+UnlockDiagnosticVMOptions", "-XX:+DebugNonSafepoints", "-XX:-OmitStackTraceInFastThrow",
         "-XX:+ExitOnOutOfMemoryError", "-Dchunky.maxWorkingCount=256"]
# Vanilla's server, with Chunky going, puts off unloading chunks while its ticks are behind, as
# `processUnloads` does without time, until its 16 GiB heap is full and it all but stops: C2ME's
# benchmark gives vanilla a patched Chunky that forces chunks to unload. Here vanilla's own
# `save-all flush`, typed every FLUSH_SECONDS, unloads them: every 120 seconds holds its heap after each
# major collection to 3 to 4.5 GiB, where without it it passes 14 GiB in 400 seconds, and costs it less
# than every 30 (D293).
FLUSHED = {"vanilla"}
FLUSH_SECONDS = 120
HEAP_EVERY = 15
RUNNING = re.compile(r"Task running for \S+\. Processed: ([\d,]+) chunks \(([\d.,]+)%\)")
FINISHED = re.compile(r"Task finished for \S+\. Processed: ([\d,]+) chunks")


def fetch(name):
    """`name`'s file, fetched where it's missing, checked against its hash."""
    pin = FILES[name]
    JARS.mkdir(parents=True, exist_ok=True)
    path = JARS / pin["file"]
    algo = "sha512" if "sha512" in pin else "sha256"

    def good(data):
        return hashlib.new(algo, data).hexdigest() == pin[algo]

    if not path.is_file() or not good(path.read_bytes()):
        print(f"others: fetching {pin['file']}", flush=True)
        with urllib.request.urlopen(urllib.request.Request(pin["url"], headers=UA), timeout=300) as r:
            data = r.read()
        if not good(data):
            sys.exit(f"others: {pin['file']} doesn't match its {algo}")
        path.write_bytes(data)
    return path


class Server:
    """A server process whose console is read on a thread of its own."""

    def __init__(self, argv, folder):
        self.lines = []
        self.seen = threading.Condition()
        self.typing = threading.Lock()
        self.log = open(folder / "console.txt", "w", encoding="utf-8")
        self.p = subprocess.Popen(argv, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            line = line.rstrip("\n")
            self.log.write(line + "\n")
            self.log.flush()
            with self.seen:
                self.lines.append((time.perf_counter(), line))
                self.seen.notify_all()
        with self.seen:
            self.seen.notify_all()

    def wait_for(self, pattern, start=0, timeout=600):
        """The index just past the first line from `start` on matching `pattern`, a regex."""
        end = time.monotonic() + timeout
        rx = re.compile(pattern)
        with self.seen:
            while True:
                for i in range(start, len(self.lines)):
                    if rx.search(self.lines[i][1]):
                        return i + 1
                start = len(self.lines)
                left = end - time.monotonic()
                if left <= 0 or self.p.poll() is not None:
                    tail = "\n".join(line for _, line in self.lines[-25:])
                    sys.exit(f"others: no line matching {pattern!r}:\n{tail}")
                self.seen.wait(min(left, 5))

    def type(self, *commands):
        with self.typing:
            for c in commands:
                self.p.stdin.write(c + "\n")
            self.p.stdin.flush()

    def stop(self, timeout=600):
        running = self.p.poll() is None
        if running:
            self.type("stop")
        cpu, peak = None, None
        if PLATFORM == "windows":
            self.p.wait(timeout)
            cpu, peak = usage_windows(self.p._handle)
        elif running:
            # wait4 reaps the process and gives its usage; once poll() has reaped it, nothing does.
            import os
            _, status, usage = os.wait4(self.p.pid, 0)
            self.p.returncode = os.waitstatus_to_exitcode(status)
            cpu, peak = usage.ru_utime + usage.ru_stime, usage.ru_maxrss * 1024
        self.log.close()
        return cpu, peak


def set_line(path, pattern, value):
    """Sets the value of the one line in `path` that `pattern`, a regex with the key and its
    separator as its group, matches."""
    text = path.read_text(encoding="utf-8")
    rx = re.compile(pattern, re.M)
    found = rx.findall(text)
    if len(found) != 1:
        sys.exit(f"others: {len(found)} lines in {path} match {pattern!r}")
    path.write_text(rx.sub(lambda m: m.group(1) + value, text), encoding="utf-8")


def empty_worlds(folder):
    for name in ("world", "world_nether", "world_the_end", "logs", "crash-reports"):
        if (folder / name).exists():
            shutil.rmtree(folder / name)


def prepare(name, java, packs):
    """The server's folder, with its jar, its mods or plugins, its properties and its configs,
    made by a first start if it hasn't made them yet."""
    s = SERVERS[name]
    folder = ROOT / name
    (folder / s["folder"]).mkdir(parents=True, exist_ok=True)
    jar = fetch(s["jar"])
    shutil.copyfile(jar, folder / jar.name)
    for old in (folder / s["folder"]).glob("*.jar"):
        old.unlink()
    for mod in s["mods"]:
        path = fetch(mod)
        shutil.copyfile(path, folder / s["folder"] / path.name)
    # Elliot accepted Mojang's EULA for the rig's and the benchmarks' own scratch servers (CAL-42).
    (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (folder / "server.properties").write_text(
        f"online-mode=false\nserver-ip=127.0.0.1\nserver-port={PORT}\nlevel-seed={SEED}\n"
        "view-distance=10\nsimulation-distance=10\nmotd=Calcite worldgen benchmark\n", encoding="utf-8")
    configs = [chunky_config(name, folder)] + ([threads_config(name, folder)] if name != "vanilla" else [])
    if not all(c.is_file() for c in configs):
        print(f"  {name}: a first start, to make its configs", flush=True)
        empty_worlds(folder)
        server = Server(argv(java, name, folder, 1), folder)
        server.wait_for(r"Done \(", timeout=1800)
        server.stop()
    # Chunky generates chunks saved already again, as C2ME's benchmark has it.
    if name == "paper":
        set_line(chunky_config(name, folder), r"^(\s*force-load-existing-chunks:\s*).*$", "true")
    else:
        set_line(chunky_config(name, folder), r'^(\s*"forceLoadExistingChunks":\s*)[a-z]+', "true")
    return folder


def chunky_config(name, folder):
    return folder / "plugins" / "Chunky" / "config.yml" if name == "paper" else folder / "config" / "chunky" / "config.json"


def threads_config(name, folder):
    return folder / "config" / "paper-global.yml" if name == "paper" else folder / "config" / "c2me.toml"


def set_threads(name, folder, threads):
    if name == "paper":
        set_line(threads_config(name, folder), r"^(\s*worker-threads:\s*).*$", str(threads))
        set_line(threads_config(name, folder), r"^(\s*io-threads:\s*).*$", "4")
    elif name == "c2me":
        set_line(threads_config(name, folder), r"^(\s*globalExecutorParallelism\s*=\s*).*$", str(threads))


def argv(java, name, folder, threads):
    jar = FILES[SERVERS[name]["jar"]]["file"]
    flags = FLAGS + ([f"-Dmax.bg.threads={threads}"] if name == "vanilla" else [])
    return [str(java / "bin" / f"java{JAVA_EXE}")] + flags + ["-jar", jar, "nogui"]


def flush_every(server, done):
    """Types `save-all flush` every FLUSH_SECONDS until `done`, which unloads every chunk vanilla's
    ticks put off unloading (`ChunkMap.saveAllChunks(true)` runs `processUnloads` with time)."""
    while not done.wait(FLUSH_SECONDS):
        server.type("save-all flush")


def sample_heap(java, server, done, heap):
    """The server's heap used, in MiB, from `jcmd GC.heap_info` every HEAP_EVERY seconds until
    `done`."""
    jcmd = str(java / "bin" / f"jcmd{JAVA_EXE}")
    while not done.wait(HEAP_EVERY):
        try:
            out = subprocess.run([jcmd, str(server.p.pid), "GC.heap_info"], capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            continue
        if m := re.search(r"used (\d+)M", out):
            heap.append(int(m.group(1)))


def one_run(name, java, packs, threads, warmup, measured, watch_heap=False):
    folder = ROOT / name
    empty_worlds(folder)
    (folder / "world" / "datapacks").mkdir(parents=True)
    for pack in packs:
        shutil.copyfile(pack, folder / "world" / "datapacks" / pack.name)
    set_threads(name, folder, threads)
    server = Server(argv(java, name, folder, threads), folder)
    try:
        at = server.wait_for(r"Done \(", timeout=1800)

        def chunky(area, at):
            began = time.perf_counter()
            server.type(f"chunky center {area['x']} {area['z']}", f"chunky radius {area['radius']}", "chunky start")
            done = threading.Event()
            helpers = []
            if name in FLUSHED:
                helpers.append(threading.Thread(target=flush_every, args=(server, done), daemon=True))
            heap = []
            if watch_heap:
                helpers.append(threading.Thread(target=sample_heap, args=(java, server, done, heap), daemon=True))
            for h in helpers:
                h.start()
            try:
                end = server.wait_for(FINISHED.pattern, at, timeout=8 * 3600)
            finally:
                done.set()
                for h in helpers:
                    h.join()
            took = time.perf_counter() - began
            chunks = int(FINISHED.search(server.lines[end - 1][1]).group(1).replace(",", ""))
            progress = []
            for t, line in server.lines[at:end]:
                if m := RUNNING.search(line):
                    progress.append((t, int(m.group(1).replace(",", "")), float(m.group(2).replace(",", "."))))
            middle = [(t, n) for t, n, pct in progress if 10.0 <= pct <= 90.0]
            steady = (middle[-1][1] - middle[0][1]) / (middle[-1][0] - middle[0][0]) if len(middle) >= 2 else None
            out = {"chunks": chunks, "seconds": took, "chunks_per_second": chunks / took, "steady_chunks_per_second": steady}
            if heap:
                out["heap_used_mib"] = heap
                print(f"    heap used, MiB, every {HEAP_EVERY} s: {' '.join(str(h) for h in heap)}", flush=True)
            return end, out

        at, warm = chunky(warmup, at)
        print(f"  {name}, {threads} threads: warm-up {warm['chunks']} chunks, {warm['chunks_per_second']:.1f} a second", flush=True)
        at, result = chunky(measured, at)
    finally:
        cpu, peak = server.stop()
    errors = [line for _, line in server.lines if "ERROR]" in line or "Exception" in line][:50]
    result.update(threads=threads, warmup=warm, cpu_seconds=cpu, peak_memory_mib=peak / 2**20 if peak else None, problems=errors)
    steady = result["steady_chunks_per_second"]
    print(f"  {name}, {threads} threads: {result['chunks']} chunks in {result['seconds']:.1f} s, "
          f"{result['chunks_per_second']:.1f} a second" + (f", {steady:.1f} steady" if steady else ""), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--servers", default="vanilla,paper,c2me")
    parser.add_argument("--threads", default="1,8,16,32")
    parser.add_argument("--no-packs", action="store_true", help="vanilla's own worldgen, without the packs")
    parser.add_argument("--radius", type=int, help="a measured radius of its own, for a quick look, not recorded, with a warm-up half as wide")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--flush-seconds", type=int, help="vanilla's `save-all flush` this often instead, for a look, not recorded")
    parser.add_argument("--no-flush", action="store_true", help="vanilla without its `save-all flush` every 120 seconds, for a look, not recorded")
    parser.add_argument("--watch-heap", action="store_true", help="the heap used every 15 seconds, from jcmd, printed and kept with each run")
    args = parser.parse_args()
    if (args.radius or args.no_flush or args.flush_seconds) and args.record:
        sys.exit("others: a run with --radius, --no-flush or --flush-seconds isn't recorded")
    if args.flush_seconds:
        global FLUSH_SECONDS
        FLUSH_SECONDS = args.flush_seconds
    if args.no_flush:
        FLUSHED.clear()
    measured = dict(MEASURED, radius=args.radius) if args.radius else MEASURED
    warmup = dict(WARMUP, radius=args.radius // 2) if args.radius else WARMUP
    servers = args.servers.split(",")
    threads = [int(t) for t in args.threads.split(",")]
    java = find_java_home()
    packs = [] if args.no_packs else fetch_packs()
    results = {}
    for name in servers:
        if name not in SERVERS:
            sys.exit(f"others: no server {name}; they're {', '.join(SERVERS)}")
        prepare(name, java, packs)
        results[name] = [one_run(name, java, packs, t, warmup, measured, args.watch_heap) for t in threads]

    what = "Vanilla's worldgen" if args.no_packs else "Terralith + Terratonic"
    print(f"\n{what}, seed {SEED}, {measured['radius']}-block radius about {measured['x']}, {measured['z']}, chunks a second:")
    print("| Threads | " + " | ".join(servers) + " |")
    print("| --- |" + " --- |" * len(servers))
    for i, t in enumerate(threads):
        print(f"| {t} | " + " | ".join(f"{results[s][i]['chunks_per_second']:.1f}" for s in servers) + " |")
    if args.record:
        java_version = subprocess.run([str(java / "bin" / f"java{JAVA_EXE}"), "-version"], capture_output=True, text=True).stderr.strip()
        record = {
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit(CALCITE),
            "machine": machine(),
            "java": java_version,
            "jvm_flags": FLAGS,
            "seed": SEED,
            "packs": [] if args.no_packs else [{"name": p["name"], "version": p["version"]} for p in PACK_PINS],
            "warmup": WARMUP,
            "measured": MEASURED,
            "files": {k: {"version": v["version"], "file": v["file"]} for k, v in FILES.items()},
            "flushed": {"servers": sorted(FLUSHED), "every_seconds": FLUSH_SECONDS},
            "servers": {name: {"mods": SERVERS[name]["mods"], "runs": results[name]} for name in servers},
        }
        out = HERE / "results" / (f"others-worldgen-{PLATFORM}.json" if args.no_packs else f"others-{PLATFORM}.json")
        # The runs recorded already, of servers and thread counts not run now, are kept, if they ran
        # the same files with the same flags, seed, packs and areas.
        same = ("jvm_flags", "seed", "packs", "warmup", "measured", "files", "flushed")
        if out.is_file():
            old = json.loads(out.read_text(encoding="utf-8"))
            if all(old.get(k) == record[k] for k in same):
                for name, kept in old.get("servers", {}).items():
                    runs = record["servers"].setdefault(name, {"mods": kept["mods"], "runs": []})["runs"]
                    ran = {r["threads"] for r in runs}
                    runs.extend(r for r in kept["runs"] if r["threads"] not in ran)
                    runs.sort(key=lambda r: r["threads"])
            else:
                print(f"others: {out.name} was recorded with other files or settings, so its runs are replaced")
        out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nothers: wrote {out}")


if __name__ == "__main__":
    main()
