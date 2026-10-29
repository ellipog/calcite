"""The protocol suites (P4.8, CAL-42): the rig's protocol bot runs the same scenarios against
vanilla 26.3 and against Calcite, and the two sessions are compared packet by packet.

    py -I rig/runner/sessions.py [--config NAME] [--scenario NAME] [--compare-only] [--show N]

For each configuration, a set of server.properties, this starts vanilla in a fresh folder under
build/rig/sessions/, sets what vanilla draws at random to fixed values from its console, runs
src/rig/session.calx once for each scenario, and stops it; then the same for Calcite's release
build. Vanilla runs from the jar's own classes, which oracle/vanilla-adapter/build.py unpacks,
with Mojang's EULA accepted in its scratch folder only. The vanilla adapter's SessionDump reads
both servers' packets with vanilla's codecs, and the comparison lines them up a step at a time
(rig/README.md, "Protocol suites"). It exits with 1 if the login, configuration or status suite
has a difference no file in rig/differences/ explains.

--compare-only reads and compares what the last run recorded, without starting either server.
"""

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
sys.path.insert(0, str(HERE))
from launch import find_calx  # noqa: E402
import sessiondiff  # noqa: E402

PLATFORM = "windows" if os.name == "nt" else "linux"
EXE = ".exe" if os.name == "nt" else ""
BUILD = CALCITE / "build" / "rig" / PLATFORM
SESSIONS = CALCITE / "build" / "rig" / "sessions"
ADAPTER = CALCITE / "oracle" / "vanilla-adapter" / "build" / PLATFORM / "adapter.json"
VIEW = 4

# What both servers are given. Everything else is the default. The flat world has no structures,
# so vanilla places no village; peaceful spawns no monsters, which vanilla places at random.
BASE = {
    "online-mode": "false",
    "server-ip": "127.0.0.1",
    "level-type": "minecraft\\:flat",
    "generate-structures": "false",
    "level-seed": "calcite",
    "difficulty": "peaceful",
    "view-distance": str(VIEW),
    "simulation-distance": str(VIEW),
}
CONFIGS = {
    "compressed": {},
    "uncompressed": {"network-compression-threshold": "-1"},
}
SCENARIOS = ["status", "outdated", "bad-name", "stranger", "join"]
# The bot's name in `join`, which the whitelist lets in. The default `white-list=true` stays, so
# `stranger`, whom it doesn't list, is turned away.
BOT = "Bot"
# Typed into vanilla's console once it's up, with what it answers. A player joins at a random
# place within `respawn_radius` of the spawn, drawn from a thread-local random, which Calcite
# doesn't do yet.
VANILLA_COMMANDS = [("gamerule respawn_radius 0", "respawn_radius")]


def offline_uuid(name):
    """The UUID an offline server gives a name, Java's `UUID.nameUUIDFromBytes`."""
    h = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_calcite(calx):
    BUILD.mkdir(parents=True, exist_ok=True)
    server, bot = BUILD / f"calcite{EXE}", BUILD / f"session{EXE}"
    for source, exe in (("src/calcite.calx", server), ("src/rig/session.calx", bot)):
        subprocess.run([calx, "build", "--release", source, "-o", str(exe)], cwd=CALCITE, check=True)
    return server, bot


def adapter():
    if not ADAPTER.is_file():
        sys.exit(f"sessions: the vanilla adapter isn't built; run py -I oracle/vanilla-adapter/build.py")
    return json.loads(ADAPTER.read_text(encoding="utf-8"))


def vanilla_argv(a):
    """The adapter's java and class path, running vanilla's server with its own logging."""
    argv = a["argv"]
    cp = argv[argv.index("-cp") + 1]
    return [argv[0], "-Xmx2G", "-Dfile.encoding=UTF-8", "-cp", cp, "net.minecraft.server.Main", "--nogui"]


def prepare(folder, config, port, vanilla):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    props = dict(BASE, **CONFIGS[config])
    props["server-port"] = str(port)
    (folder / "server.properties").write_text("".join(f"{k}={v}\n" for k, v in props.items()), encoding="utf-8")
    listed = [{"uuid": offline_uuid(BOT), "name": BOT}]
    (folder / "whitelist.json").write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
    if vanilla:
        # Elliot accepted Mojang's EULA for the rig's own scratch servers (CAL-42).
        (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    else:
        (folder / "calcite.properties").write_text("console-dashboard=off\nrecord-inputs=false\n", encoding="utf-8")


class Server:
    """A server process whose console is read on a thread of its own."""

    def __init__(self, argv, folder, name):
        self.name = name
        self.lines = []
        self.seen = threading.Condition()
        self.log = open(folder / "console.txt", "w", encoding="utf-8")
        self.p = subprocess.Popen(argv, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.log.write(line)
            self.log.flush()
            with self.seen:
                self.lines.append(line.rstrip("\n"))
                self.seen.notify_all()
        with self.seen:
            self.seen.notify_all()

    def wait_for(self, text, after=0, timeout=180):
        end = time.monotonic() + timeout
        with self.seen:
            while True:
                for i in range(after, len(self.lines)):
                    if text in self.lines[i]:
                        return i + 1
                left = end - time.monotonic()
                if left <= 0 or self.p.poll() is not None:
                    tail = "\n".join(self.lines[-20:])
                    sys.exit(f"sessions: {self.name} never said {text!r}:\n{tail}")
                self.seen.wait(left)

    def type(self, command):
        self.p.stdin.write(command + "\n")
        self.p.stdin.flush()

    def stop(self):
        try:
            self.type("stop")
            self.p.wait(60)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()
            self.p.wait()
        self.log.close()


def record(config, side, argv, bot, scenarios):
    folder = SESSIONS / config / side
    port = free_port()
    prepare(folder, config, port, side == "vanilla")
    began = time.monotonic()
    server = Server(argv, folder, side)
    at = server.wait_for("Done (")
    if side == "vanilla":
        for command, answer in VANILLA_COMMANDS:
            server.type(command)
            at = server.wait_for(answer, at)
    print(f"  {side}: up in {time.monotonic() - began:.1f}s on port {port}", flush=True)
    try:
        for scenario in scenarios:
            out = folder / f"{scenario}.bin"
            got = subprocess.run([str(bot), str(port), str(VIEW), scenario, str(out)], cwd=CALCITE,
                                 capture_output=True, text=True, encoding="utf-8", timeout=120)
            if got.returncode != 0:
                sys.exit(f"sessions: the bot failed {scenario} against {side}:\n{got.stdout}{got.stderr}")
            print(f"  {side}: {scenario}: {got.stdout.strip()}", flush=True)
    finally:
        server.stop()


def dump(a, files):
    """Runs SessionDump on the recorded sessions, which writes a .jsonl beside each."""
    argv = a["argv"][:-1] + ["calcite.rig.vanilla.SessionDump"] + [str(f) for f in files]
    got = subprocess.run(argv, cwd=a["cwd"], capture_output=True, text=True, encoding="utf-8")
    if got.returncode != 0:
        sys.exit(f"sessions: SessionDump failed:\n{got.stdout}{got.stderr[-4000:]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", action="append", choices=sorted(CONFIGS), help="only this configuration")
    ap.add_argument("--scenario", action="append", choices=SCENARIOS, help="only this scenario")
    ap.add_argument("--compare-only", action="store_true", help="compare the last run's sessions")
    ap.add_argument("--show", type=int, default=3, help="differences shown for each packet, 0 for all")
    args = ap.parse_args()
    configs = args.config or list(CONFIGS)
    scenarios = args.scenario or SCENARIOS
    a = adapter()
    if not args.compare_only:
        server, bot = build_calcite(find_calx())
        for config in configs:
            print(f"{config}:", flush=True)
            record(config, "vanilla", vanilla_argv(a), bot, scenarios)
            record(config, "calcite", [str(server)], bot, scenarios)
    dump(a, [SESSIONS / c / side / f"{s}.bin" for c in configs for side in ("vanilla", "calcite") for s in scenarios])
    complete = args.config is None and args.scenario is None
    report = sessiondiff.run(SESSIONS, configs, scenarios, CALCITE / "rig" / "differences", show=args.show, complete=complete)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
