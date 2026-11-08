"""Fixture worlds (CAL-116): small worlds vanilla 26.3 builds from console commands, which a
protocol session then has both servers load, so what's built runs the same on each and is
compared packet by packet and draw by draw (rig/README.md, "Fixture worlds").

    py -I rig/runner/fixtures.py [NAME ...] [--force]

A fixture is a file of commands in rig/fixtures/, NAME.txt, one to a line, with `#` comments.
Vanilla's server makes a flat world in build/rig/fixtures/NAME/, from the seed the sessions use,
force loads chunk (0, 0), freezes its ticks, so each tick a block set schedules waits in the save,
and types the commands, each answered as it should be or it stops. Then it lets the chunk go,
saves and stops, and build/rig/fixtures/NAME/world is the fixture's world, with only its full
chunks: those vanilla only began around the forced one, which it would go on with where it left
them and Calcite makes afresh, the same blocks with their palettes in another order, are taken
out of its region files, so each server makes them anew. A world already built
from the same commands is kept, unless --force; sessions.py builds the fixtures its configurations
load as it starts.
"""

import argparse
import hashlib
import shutil
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nbt  # noqa: E402
import sessions  # noqa: E402
from sessions import Server, adapter, free_port, vanilla_argv  # noqa: E402

CALCITE = sessions.CALCITE
SOURCES = CALCITE / "rig" / "fixtures"
FIXTURES = sessions.FIXTURES

# The flat world the sessions' own is, which doesn't pause, so the console's heard all along.
PROPERTIES = dict(sessions.BASE, **{"spawn-protection": "0", "pause-when-empty-seconds": "0"})

# What vanilla answers each command with, by its first word.
ANSWERS = {
    "setblock": "Changed the block",
    "fill": "Successfully filled",
    "fillbiome": "biome entr",
    "setworldspawn": "Set the world spawn point",
    "summon": "Summoned new",
    "time": "Set minecraft:overworld to",
    "difficulty": "The difficulty has been set to",
    "forceload": "to be force loaded",
}


def answer(line):
    """What the console answers `line` with: a `forceload remove`'s, which lets chunks a fixture
    forced to build in go once it's built, "for force loading" (CAL-159)."""
    words = line.split()
    if words[:2] == ["forceload", "remove"]:
        return "for force loading"
    return ANSWERS[words[0]]


def commands(name):
    """The fixture's commands, without its comments and blank lines."""
    lines = (SOURCES / f"{name}.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def digest(name):
    return hashlib.sha256("\n".join(commands(name)).encode("utf-8")).hexdigest()


def built(name):
    """Whether the fixture's world is there, built from the commands it has now."""
    folder = FIXTURES / name
    stamp = folder / "commands.sha256"
    return (folder / "world" / "level.dat").is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == digest(name)


def keep_full(world):
    """Takes each chunk that isn't full out of the world's region files, leaving its sectors
    unused; the chunks kept and taken."""
    kept = taken = 0
    for region in sorted(world.glob("dimensions/*/*/region/*.mca")):
        data = bytearray(region.read_bytes())
        if len(data) < 8192:
            continue
        for i in range(1024):
            sector = int.from_bytes(data[i * 4:i * 4 + 3], "big")
            if sector == 0:
                continue
            at = sector * 4096
            length, kind = struct.unpack_from(">iB", data, at)
            if kind != 2:
                sys.exit(f"fixtures: {region.name} keeps chunk {i} compressed as {kind}, not zlib")
            r = nbt._Reader(zlib.decompress(bytes(data[at + 5:at + 4 + length])))
            r.take(">b")
            r.string()
            if r.payload(nbt.COMPOUND).get("Status") == "minecraft:full":
                kept += 1
                continue
            data[i * 4:i * 4 + 4] = bytes(4)
            data[4096 + i * 4:4096 + i * 4 + 4] = bytes(4)
            taken += 1
        region.write_bytes(bytes(data))
    return kept, taken


def ask(server, text, answer, at):
    server.type(text)
    return server.wait_for(answer, at, timeout=30)


def make(name, force=False):
    """Builds the fixture's world, unless it's built from the same commands and not `force`."""
    if not force and built(name):
        return
    typed = commands(name)
    for line in typed:
        if line.split()[0] not in ANSWERS:
            sys.exit(f"fixtures: {name}: no answer known for {line!r}")
    folder = FIXTURES / name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    port = free_port()
    props = dict(PROPERTIES, **{"server-port": str(port)})
    (folder / "server.properties").write_text("".join(f"{k}={v}\n" for k, v in props.items()), encoding="utf-8")
    # Elliot accepted Mojang's EULA for the rig's own scratch servers (CAL-42).
    (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    began = time.monotonic()
    server = Server(vanilla_argv(adapter()), folder, f"vanilla building {name}")
    try:
        at = server.wait_for("Done (")
        at = ask(server, "forceload add 0 0", "to be force loaded", at)
        while True:
            server.type("execute if loaded 0 0 0")
            at = server.wait_for("Test ", at, timeout=60)
            if "Test passed" in server.lines[at - 1]:
                break
            if time.monotonic() - began > 120:
                sys.exit(f"fixtures: {name}: chunk (0, 0) never loaded")
            time.sleep(0.2)
        at = ask(server, "tick freeze", "The game is frozen", at)
        for line in typed:
            at = ask(server, line, answer(line), at)
        at = ask(server, "forceload remove all", "Unmarked all force loaded chunks", at)
        # The fixture's own forced chunks, which the builder's took out with its own, kept in the
        # world it saves (D428).
        for line in typed:
            if line.split()[0] == "forceload":
                at = ask(server, line, answer(line), at)
        at = ask(server, "save-all flush", "Saved the game", at)
    finally:
        server.stop()
    kept, taken = keep_full(folder / "world")
    (folder / "commands.sha256").write_text(digest(name) + "\n", encoding="utf-8")
    print(f"  {name}: vanilla built it from {len(typed)} commands in {time.monotonic() - began:.1f}s; "
          f"{kept} full chunks kept, {taken} begun taken out", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="the fixtures to build, all of rig/fixtures/ if none")
    ap.add_argument("--force", action="store_true", help="build them again even if they're built")
    args = ap.parse_args()
    names = args.names or sorted(p.stem for p in SOURCES.glob("*.txt"))
    for name in names:
        if not (SOURCES / f"{name}.txt").is_file():
            sys.exit(f"fixtures: there's no rig/fixtures/{name}.txt")
        make(name, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
