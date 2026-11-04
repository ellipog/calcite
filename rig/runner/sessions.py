"""The protocol suites (P4.8, CAL-42): the rig's protocol bot runs the same scenarios against
vanilla 26.3 and against Calcite, and the two sessions are compared packet by packet.

    py -I rig/runner/sessions.py [--config NAME] [--scenario NAME] [--compare-only] [--show N] [--tape]

For each configuration, a set of server.properties, this starts vanilla in a fresh folder under
build/rig/sessions/, sets what vanilla draws at random to fixed values from its console, waits for
it to pause, empty, so the bot joins at the same game time on both (D315), runs
src/rig/session.calx once for each scenario, and stops it; then the same for Calcite's release
build. Vanilla runs from the jar's own classes, which oracle/vanilla-adapter/build.py unpacks,
with Mojang's EULA accepted in its scratch folder only. The vanilla adapter's SessionDump reads
both servers' packets with vanilla's codecs, and the comparison lines them up a step at a time
(rig/README.md, "Protocol suites"). It exits with 1 if the login, configuration or status suite
has a difference no file in rig/differences/ explains.

--compare-only reads and compares what the last run recorded, without starting either server.
--tape has the rig's agent write each draw of vanilla's levels' randoms to tape.txt in its folder,
and Calcite write its own there with --rng-tape, and lines the two up level by level
(rig/runner/tapediff.py, D312). Both seed their levels' randoms again at RESEED, once the player's
chunks are in, so the tapes line up from there whatever each drew while they loaded (D316).
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
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
sys.path.insert(0, str(HERE))
from launch import find_calx  # noqa: E402
import nbt  # noqa: E402
import sessiondiff  # noqa: E402
import tapediff  # noqa: E402

PLATFORM = "windows" if os.name == "nt" else "linux"
EXE = ".exe" if os.name == "nt" else ""
BUILD = CALCITE / "build" / "rig" / PLATFORM
SESSIONS = CALCITE / "build" / "rig" / "sessions"
ADAPTER = CALCITE / "oracle" / "vanilla-adapter" / "build" / PLATFORM / "adapter.json"
VIEW = 4

# What both servers are given. Everything else is the default. The flat world has no structures,
# so vanilla places no village; peaceful spawns no monsters, which vanilla places at random. Each
# pauses once it's been empty PAUSE seconds, and the bot runs only once it has, so the bot joins
# both at the same game time and their ticks line up from there (D315).
PAUSE = 2
BASE = {
    "online-mode": "false",
    "server-ip": "127.0.0.1",
    "level-type": "minecraft\\:flat",
    "generate-structures": "false",
    "level-seed": "calcite",
    "difficulty": "peaceful",
    "view-distance": str(VIEW),
    "simulation-distance": str(VIEW),
    "pause-when-empty-seconds": str(PAUSE),
}
SCENARIOS = ["status", "outdated", "bad-name", "stranger", "join"]
# Scenarios only the configurations that name them run: `watch`, where the bot joins and stays put
# a fixed number of game ticks, for a world that never goes quiet (src/rig/session.calx).
OTHER_SCENARIOS = ["watch"]
# The world the round trip has vanilla make and save (rig/runner/roundtrip.py), from the seed
# `calcite` with real terrain, its chunks full from -6 to 5 around the origin.
SAVED_WORLD = CALCITE / "build" / "rig" / "roundtrip" / "vanilla" / "world"
# The fixture worlds vanilla builds from rig/fixtures/'s commands (rig/runner/fixtures.py), each in
# a folder of its name with its world in it.
FIXTURES = CALCITE / "build" / "rig" / "fixtures"


@dataclass
class Config:
    """A configuration: what it adds to the properties, the view, its scenarios, and the world
    both servers are given a copy of, or none for the flat world each makes."""
    props: dict
    view: int = VIEW
    scenarios: tuple = tuple(SCENARIOS)
    world: Path | None = None
    # Typed into vanilla's console after VANILLA_COMMANDS, with what it answers.
    commands: tuple = ()
    # Where the copy of `world` has its spawn, both servers' level.dat's, if it's moved.
    spawn: tuple | None = None
    # Whether the copy keeps the world's entities, each dimension's `entities` folder.
    entities: bool = True
    # Game rules set in the copy's game_rules.dat, which both servers read, by their names.
    rules: tuple = ()
    # The fixture `world` is, which is built from its commands if it isn't, or none.
    fixture: str | None = None


CONFIGS = {
    "compressed": Config({}),
    "uncompressed": Config({"network-compression-threshold": "-1"}),
    # A saved world, whose chunks both servers read and light (CAL-76). A view of 3 sends the
    # chunks from -4 to 4, which vanilla lights with their neighbours, all of them full in the
    # save. Its spawn is moved to the origin, so the player is in chunk (0, 0), on the ground
    # there, as each server finds it (CAL-75).
    "saved": Config({}, view=3, scenarios=("join",), world=SAVED_WORLD, spawn=(0, 100, 0)),
    # The same world without its entities, so its blocks' random ticks show on the tape past the
    # mobs, whose brains draw first, and the End's crystals, which come with entities (CAL-106);
    # and without natural spawning, `spawn_mobs` off, whose first mob's `finalizeSpawn` drew
    # where Calcite has no mob to draw for, so the tape goes on past it (D338).
    "terrain": Config({}, view=3, scenarios=("join",), world=SAVED_WORLD, spawn=(0, 100, 0), entities=False,
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Redstone that runs by itself, built in vanilla with its ticks waiting in the save, by the
    # spawn, in the player's chunk (CAL-116), without natural spawning, as `terrain`; its clocks
    # never stop, so the bot watches it a fixed time.
    "redstone": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "redstone" / "world", fixture="redstone",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Block entities saved by the spawn, sent with their chunks, and two heads a clock powers,
    # each sent with its update packet as it changes (CAL-115); watched, as `redstone`.
    "block_entities": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "block_entities" / "world",
                             fixture="block_entities", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Comparators by the spawn reading containers and other blocks, whose ticks wait in the save,
    # and two whose sides a clock powers, subtracting and comparing (CAL-123); watched, as
    # `redstone`.
    "comparators": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "comparators" / "world",
                          fixture="comparators", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Pistons by the spawn, driven by observer clocks and by repeaters whose ticks wait in the
    # save: pushing, pulling, slime and blocks they can't move (CAL-125); watched, as `redstone`.
    "pistons": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "pistons" / "world",
                      fixture="pistons", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # The blocks a signal changes by the spawn, each pulsed by an observer clock: doors, trapdoors,
    # a fence gate, a copper bulb, a hopper, an empty dispenser, dropper and crafter, a note block,
    # a bell, a big dripleaf, a command block, rails and shelves (CAL-124); watched, as `redstone`.
    "receivers": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "receivers" / "world",
                        fixture="receivers", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # The blocks that make a signal of their own by the spawn, set as a command sets them, each
    # beside a lamp an observer clock pulses: buttons, a lever, pressure plates, a lectern, a
    # detector rail, a lightning rod let go as it ticks, a target, a trapped chest, a jukebox and a
    # tripped tripwire line detaching (CAL-128); watched, as `redstone`.
    "sources": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "sources" / "world",
                      fixture="sources", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Sponges and frosted ice by the spawn: a lake a sponge took up as the world was built flowing
    # into the hole, water flowing up a channel to a dry sponge, and frosted ice aging and melting
    # (CAL-127); watched, as `redstone`.
    "water_blocks": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "water_blocks" / "world",
                           fixture="water_blocks", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Block entities' tickers at dusk: daylight detectors putting out the sky's light as it
    # darkens and the sun goes down, plain, inverted, under leaves and stone, lighting lamps; a
    # crafter done crafting, a brewing stand showing its bottles, a hopper's cooldown, and
    # tickers with nothing to do (CAL-130); watched, as `redstone`.
    "tickers": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "tickers" / "world",
                      fixture="tickers", rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
}
# The bot's name in `join`, which the whitelist lets in. The default `white-list=true` stays, so
# `stranger`, whom it doesn't list, is turned away.
BOT = "Bot"
# Typed into vanilla's console once it's up, with what it answers. A player joins at a random
# place within `respawn_radius` of the spawn, drawn from a thread-local random, which can't be
# the same on both servers, so it's 0: on the spawn, or the ground there. Calcite reads it from
# the world's game rules, which `prepare` writes (CAL-75).
VANILLA_COMMANDS = [("gamerule respawn_radius 0", "respawn_radius")]
# The data version both servers save, which a game rules file the rig writes is in.
DATA_VERSION = 5023
# Both servers' levels' randoms are seeded from this (D311): vanilla's by the rig's agent and
# Calcite's by level-random-seed. With --tape, each writes their draws to tape.txt in its folder.
LEVEL_RANDOM_SEED = 1103
# With --tape, the game time at which both seed each level's random again (D316): 3 seconds after
# the bot joins, at PAUSE seconds, by when vanilla's workers have made the player's chunks. A level
# is seeded as its tick starts at RESEED or later; the Overworld's tick moves the time on before
# its chunks draw, so its draws from the new seed are taped from RESEED + 1, and the tapes are
# lined up from there.
RESEED = (PAUSE + 3) * 20


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


def vanilla_argv(a, tape=False):
    """The adapter's java and class path, running vanilla's server with its own logging, and the
    rig's agent, which seeds its levels' randoms, and with `tape` writes their draws (D311)."""
    if "agent" not in a:
        sys.exit("sessions: the vanilla adapter was built without the agent; run py -I oracle/vanilla-adapter/build.py")
    argv = a["argv"]
    cp = argv[argv.index("-cp") + 1]
    agent = f"-javaagent:{a['agent']}=seed={LEVEL_RANDOM_SEED}" + (f",tape=tape.txt,reseed={RESEED}" if tape else "")
    return [argv[0], "-Xmx2G", "-Dfile.encoding=UTF-8", agent, "-cp", cp, "net.minecraft.server.Main", "--nogui"]


def prepare(folder, config, port, vanilla):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    c = CONFIGS[config]
    props = dict(BASE, **c.props)
    props["view-distance"] = props["simulation-distance"] = str(c.view)
    props["server-port"] = str(port)
    if c.world is not None:
        # Without the lock, which vanilla held, and the players' data, so neither server's
        # player starts where the round trip's bot was, and without the entities if the
        # configuration leaves them out.
        shutil.copytree(c.world, folder / "world", ignore=lambda at, names: [
            n for n in names if (n in ("session.lock", "players") and Path(at) == c.world) or (n == "entities" and not c.entities)])
        if c.spawn is not None:
            level = nbt.read(folder / "world" / "level.dat")
            level["Data"]["spawn"]["pos"] = nbt.IntArray(c.spawn)
            nbt.write(folder / "world" / "level.dat", level)
    rules = folder / "world" / "data" / "minecraft" / "game_rules.dat"
    if rules.is_file():
        saved = nbt.read(rules)
        saved["data"]["minecraft:respawn_radius"] = nbt.Int(0)
        for name, value in c.rules:
            saved["data"][name] = value
        nbt.write(rules, saved)
    elif not vanilla:
        nbt.write(rules, {"data": {"minecraft:respawn_radius": nbt.Int(0)}, "DataVersion": nbt.Int(DATA_VERSION)})
    (folder / "server.properties").write_text("".join(f"{k}={v}\n" for k, v in props.items()), encoding="utf-8")
    listed = [{"uuid": offline_uuid(BOT), "name": BOT}]
    (folder / "whitelist.json").write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
    if vanilla:
        # Elliot accepted Mojang's EULA for the rig's own scratch servers (CAL-42).
        (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    else:
        (folder / "calcite.properties").write_text(
            f"console-dashboard=off\nrecord-inputs=false\nlevel-random-seed={LEVEL_RANDOM_SEED}\n", encoding="utf-8")


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
        for command, answer in VANILLA_COMMANDS + list(CONFIGS[config].commands):
            server.type(command)
            at = server.wait_for(answer, at)
    at = server.wait_for(f"Server empty for {PAUSE} seconds, pausing", at)
    print(f"  {side}: up in {time.monotonic() - began:.1f}s on port {port}, paused", flush=True)
    try:
        for scenario in scenarios:
            out = folder / f"{scenario}.bin"
            got = subprocess.run([str(bot), str(port), str(CONFIGS[config].view), scenario, str(out)], cwd=CALCITE,
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
    ap.add_argument("--scenario", action="append", choices=SCENARIOS + OTHER_SCENARIOS, help="only this scenario")
    ap.add_argument("--compare-only", action="store_true", help="compare the last run's sessions")
    ap.add_argument("--show", type=int, default=3, help="differences shown for each packet, 0 for all")
    ap.add_argument("--tape", action="store_true", help="write both servers' levels' draws to tape.txt, and line them up")
    args = ap.parse_args()
    configs = args.config or list(CONFIGS)
    complete = args.config is None and args.scenario is None
    for c in list(configs):
        if CONFIGS[c].fixture is not None and not args.compare_only:
            import fixtures
            fixtures.make(CONFIGS[c].fixture)
        world = CONFIGS[c].world
        if world is not None and not (world / "level.dat").is_file():
            print(f"{c}: skipped, since there's no {world.relative_to(CALCITE)}; run py -I rig/runner/roundtrip.py", flush=True)
            configs.remove(c)
            complete = False
    scenarios = {c: [s for s in (args.scenario or CONFIGS[c].scenarios) if s in CONFIGS[c].scenarios] for c in configs}
    a = adapter()
    if not args.compare_only:
        server, bot = build_calcite(find_calx())
        for config in configs:
            if not scenarios[config]:
                continue
            print(f"{config}:", flush=True)
            record(config, "vanilla", vanilla_argv(a, args.tape), bot, scenarios[config])
            record(config, "calcite", [str(server)] + (["--rng-tape", "tape.txt", "--rng-reseed", str(RESEED)] if args.tape else []), bot, scenarios[config])
            if args.tape:
                print(f"{config}: the levels' draws, vanilla's against Calcite's (D312):", flush=True)
                tapediff.compare(tapediff.read(SESSIONS / config / "vanilla" / "tape.txt"),
                                 tapediff.read(SESSIONS / config / "calcite" / "tape.txt"), args.show, RESEED + 1)
    files = [SESSIONS / c / side / f"{s}.bin" for c in configs for side in ("vanilla", "calcite") for s in scenarios[c]]
    if not files:
        sys.exit("sessions: no configuration has those scenarios")
    dump(a, files)
    report = sessiondiff.run(SESSIONS, configs, scenarios, CALCITE / "rig" / "differences", show=args.show, complete=complete)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
