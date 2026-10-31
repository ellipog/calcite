"""The round trip through vanilla (G5.2, CAL-61): a world vanilla 26.3 made and saved, loaded and
saved again by Calcite, then read by vanilla, which must find the same world.

    py -I rig/runner/roundtrip.py [--reuse]

It runs in build/rig/roundtrip/, with Mojang's EULA accepted in its scratch folders only:

1. `vanilla/`: vanilla's server makes a world from a fixed seed, with chunks loaded in all three
   dimensions, and the rig's protocol bot joins it, so it has a player's data, advancements and
   statistics. With its ticks frozen, so they're saved as they're set, the console then puts in
   block entities, points of interest, entities, scheduled ticks, scoreboards, command storage,
   a random sequence, a boss bar, the world border, the weather and the time. Then it's saved
   and stopped.
2. `calcite/`: a copy, which src/rig/resave.calx loads and saves again, every file Calcite keeps,
   with Calcite's readers and writers. A line it logs is a difference.
3. The vanilla adapter's WorldCheck reads both with vanilla's own readers and compares them file
   by file and chunk by chunk: anything not the same, or that vanilla logs reading Calcite's
   save, is a difference.
4. `back/` and `again/`: vanilla's server opens a copy of Calcite's save, and one of its own,
   answers the same questions from its console about each, what's in the chests and the sign,
   the portal, the bed, the scores, the storage, the border, the forced chunks, the teams, the
   boss bar and the entities, then saves and stops. An answer that isn't the same for both, or
   a warning or error it logs opening Calcite's that it doesn't log opening its own, is a
   difference.

It exits with 1 if there's a difference. --reuse skips step 1 and uses the last run's world.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sessions  # noqa: E402
from sessions import Server, adapter, find_calx, free_port, offline_uuid, vanilla_argv  # noqa: E402

CALCITE = sessions.CALCITE
EXE = sessions.EXE
BUILD = sessions.BUILD
ROOT = CALCITE / "build" / "rig" / "roundtrip"
VIEW = 4
BOT = "Bot"

PROPERTIES = {
    "online-mode": "false",
    "server-ip": "127.0.0.1",
    "level-seed": "calcite",
    "view-distance": str(VIEW),
    "simulation-distance": str(VIEW),
    "spawn-protection": "0",
}

# The areas loaded in each dimension, from block to block, which vanilla generates and keeps.
FORCED = [
    ("minecraft:overworld", -64, -64, 63, 63),
    ("minecraft:the_nether", -32, -32, 31, 31),
    ("minecraft:the_end", -32, -32, 31, 31),
]

BOOK = ('{Slot:5b,id:"minecraft:written_book",count:1,components:{"minecraft:written_book_content":'
        '{title:"Calcite",author:"rig",pages:["one","two"]}}}')

# Typed once the ticks are frozen, each with what vanilla answers. Everything is in the air,
# above y 190, where no terrain is, in the loaded chunks.
CONTENT = [
    # Block entities.
    ('setblock 0 200 0 minecraft:chest{Items:[{Slot:0b,id:"minecraft:diamond",count:3},' + BOOK + ']}', "Changed the block"),
    ('setblock 2 200 0 minecraft:oak_sign{front_text:{messages:["a","b","",""]}}', "Changed the block"),
    ('setblock 4 200 0 minecraft:furnace{Items:[{Slot:0b,id:"minecraft:iron_ore",count:5}]}', "Changed the block"),
    ("setblock 6 199 3 minecraft:stone", "Changed the block"),
    # Points of interest: a bed, a bell, job sites, a beehive and a nether portal.
    ("setblock 6 200 0 minecraft:red_bed[part=foot,facing=south]", "Changed the block"),
    ("setblock 6 200 1 minecraft:red_bed[part=head,facing=south]", "Changed the block"),
    ("setblock 8 200 0 minecraft:bell", "Changed the block"),
    ("setblock 10 200 0 minecraft:composter", "Changed the block"),
    ("setblock 12 200 0 minecraft:lectern", "Changed the block"),
    ("setblock 14 200 0 minecraft:beehive", "Changed the block"),
    ("setblock 40 200 40 minecraft:grindstone", "Changed the block"),
    ("fill 20 200 0 23 204 0 minecraft:obsidian", "Successfully filled"),
    ("fill 21 201 0 22 203 0 minecraft:nether_portal[axis=x]", "Successfully filled"),
    # Ticks that wait: sand over air falls on its tick, and water spreads on its.
    ("setblock 30 200 0 minecraft:sand", "Changed the block"),
    ("setblock 32 200 0 minecraft:water", "Changed the block"),
    ("setblock 34 200 0 minecraft:lava", "Changed the block"),
    # Entities.
    ('summon minecraft:pig 0 201 5 {NoAI:1b,CustomName:"Wilbur"}', "Summoned new"),
    ('summon minecraft:villager 4 201 5 {NoAI:1b,VillagerData:{profession:"minecraft:librarian",level:2,type:"minecraft:plains"}}', "Summoned new"),
    ("summon minecraft:armor_stand 8 201 5 {ShowArms:1b,NoGravity:1b}", "Summoned new"),
    ('summon minecraft:item 10 201 5 {Item:{id:"minecraft:apple",count:2},PickupDelay:32767s,NoGravity:1b}', "Summoned new"),
    ('summon minecraft:chest_minecart 12 201 5 {Items:[{Slot:0b,id:"minecraft:torch",count:16}],NoGravity:1b}', "Summoned new"),
    ('summon minecraft:zombie 14 201 5 {NoAI:1b,PersistenceRequired:1b,Passengers:[{id:"minecraft:chicken",NoAI:1b}]}', "Summoned new"),
    ("summon minecraft:pig -40 201 -40 {NoAI:1b}", "Summoned new"),
    # The other dimensions.
    ('execute in minecraft:the_nether run setblock 0 120 0 minecraft:chest{Items:[{Slot:1b,id:"minecraft:gold_ingot",count:7}]}', "Changed the block"),
    ("execute in minecraft:the_nether run summon minecraft:strider 3 121 3 {NoAI:1b}", "Summoned new"),
    ("execute in minecraft:the_end run setblock 0 120 0 minecraft:ender_chest", "Changed the block"),
    ("execute in minecraft:the_end run summon minecraft:end_crystal 3 121 3 {ShowBottom:0b}", "Summoned new"),
    # Saved data and level.dat.
    ("scoreboard objectives add rig dummy", "Created new objective"),
    ("scoreboard players set alice rig 5", "for alice to 5"),
    ("team add red", "Created team"),
    ('data modify storage calcite:rig value set value {a:1,b:[I;1,2,3],c:"x"}', "Modified storage"),
    ("random value 1..6 calcite:dice", "Randomized value"),
    ('bossbar add calcite:bar "Rig"', "Created custom bossbar"),
    ("worldborder set 1000", "Set the world border"),
    ("weather rain 6000", "Set the weather"),
    ("time set 1234", "1234"),
]


def prepare(folder, port, world=None):
    """A server's folder, with a copy of `world` as its world if one's given."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    props = dict(PROPERTIES, **{"server-port": str(port)})
    (folder / "server.properties").write_text("".join(f"{k}={v}\n" for k, v in props.items()), encoding="utf-8")
    listed = [{"uuid": offline_uuid(BOT), "name": BOT}]
    (folder / "whitelist.json").write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
    # Elliot accepted Mojang's EULA for the rig's own scratch servers (CAL-42).
    (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    if world is not None:
        shutil.copytree(world, folder / "world")


def command(server, text, answer, at):
    server.type(text)
    return server.wait_for(answer, at, timeout=60)


def loaded(server, dim, x, z, at):
    """Waits until the block at `x`, `z` in `dim` is loaded, asking the console."""
    end = time.monotonic() + 300
    while True:
        server.type(f"execute in {dim} if loaded {x} 0 {z}")
        at = server.wait_for("Test ", at, timeout=60)
        if "Test passed" in server.lines[at - 1]:
            return at
        if time.monotonic() > end:
            sys.exit(f"roundtrip: {dim} never loaded {x}, {z}")
        time.sleep(0.5)


def make(bot):
    """Step 1: vanilla's world."""
    folder = ROOT / "vanilla"
    port = free_port()
    prepare(folder, port)
    began = time.monotonic()
    server = Server(vanilla_argv(adapter()), folder, "vanilla")
    try:
        at = server.wait_for("Done (")
        for dim, x0, z0, x1, z1 in FORCED:
            at = command(server, f"execute in {dim} run forceload add {x0} {z0} {x1} {z1}", "to be force loaded", at)
        for dim, x0, z0, x1, z1 in FORCED:
            for x, z in ((x0, z0), (x1, z1), (x0, z1), (x1, z0)):
                at = loaded(server, dim, x, z, at)
        got = subprocess.run([str(bot), str(port), str(VIEW), "join", str(folder / "join.bin")], cwd=CALCITE,
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        if got.returncode != 0:
            sys.exit(f"roundtrip: the bot couldn't join vanilla:\n{got.stdout}{got.stderr}")
        at = server.wait_for(f"{BOT} left the game", at)
        at = command(server, "tick freeze", "The game is frozen", at)
        for text, answer in CONTENT:
            at = command(server, text, answer, at)
        at = command(server, "save-all flush", "Saved the game", at)
    finally:
        server.stop()
    print(f"  vanilla made its world in {time.monotonic() - began:.1f}s", flush=True)


def resave(tool):
    """Step 2: Calcite loads and saves a copy."""
    folder = ROOT / "calcite"
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(ROOT / "vanilla" / "world", folder / "world")
    began = time.monotonic()
    got = subprocess.run([str(tool), str(folder / "world")], cwd=CALCITE, capture_output=True, text=True,
                         encoding="utf-8", timeout=600)
    differences = []
    for line in got.stdout.splitlines():
        if line.startswith("WARN ") or line.startswith("ERROR "):
            differences.append(f"Calcite logged {line}")
        elif line.startswith("INFO saved"):
            print(f"  calcite {line[5:]} in {time.monotonic() - began:.1f}s", flush=True)
    if got.returncode != 0:
        differences.append(f"resave exited with {got.returncode}:\n{got.stdout}{got.stderr}")
    return differences


def check(a):
    """Step 3: vanilla reads both and compares them."""
    argv = a["argv"][:-1] + ["calcite.rig.vanilla.WorldCheck", str(ROOT / "vanilla" / "world"), str(ROOT / "calcite" / "world")]
    got = subprocess.run(argv, cwd=a["cwd"], capture_output=True, text=True, encoding="utf-8", timeout=600)
    lines = got.stdout.splitlines()
    if got.returncode not in (0, 1) or not lines or not lines[-1].startswith("checked "):
        return [f"WorldCheck failed:\n{got.stdout}{got.stderr[-4000:]}"]
    print(f"  vanilla {lines[-1]}", flush=True)
    return lines[:-1]


# A console line's level and message.
LINE = re.compile(r"^\[[^\]]*\] \[[^\]]*/(INFO|WARN|ERROR)\]: (.*)$")

# Asked of vanilla once it has opened a world, whose answers must be the same for Calcite's
# save as for vanilla's own: what the world holds, read back from the files.
QUERIES = [
    "data get block 0 200 0 Items",
    "data get block 2 200 0 front_text",
    "data get block 4 200 0 Items",
    "execute in minecraft:the_nether run data get block 0 120 0 Items",
    "execute if block 21 201 0 minecraft:nether_portal",
    "execute if block 6 200 1 minecraft:red_bed[part=head]",
    "scoreboard players get alice rig",
    "data get storage calcite:rig value",
    "worldborder get",
    "forceload query",
    "execute in minecraft:the_nether run forceload query",
    "execute in minecraft:the_end run forceload query",
    "team list",
    "bossbar list",
]
# The same for entities, which load a little after their chunks, so each is asked until it's
# found, for a while.
ENTITIES = [
    "execute if entity @e[type=minecraft:pig,name=Wilbur]",
    "data get entity @e[type=minecraft:villager,x=4,y=201,z=5,distance=..1,limit=1] VillagerData",
    "data get entity @e[type=minecraft:chest_minecart,x=12,y=201,z=5,distance=..1,limit=1] Items",
    "data get entity @e[type=minecraft:item,x=10,y=201,z=5,distance=..1,limit=1] Item",
    "execute if entity @e[type=minecraft:zombie,x=14,y=201,z=5,distance=..2]",
    "execute if entity @e[type=minecraft:chicken,x=14,y=201,z=5,distance=..4]",
    "execute in minecraft:the_nether if entity @e[type=minecraft:strider]",
    "execute in minecraft:the_end if entity @e[type=minecraft:end_crystal,x=3,y=121,z=3,distance=..2]",
]
MARK = "rig-mark"


def ask(server, text, at):
    """What vanilla answers `text`: what it tells the console, up to a mark said after it.
    Other lines, such as the save vanilla makes once it's up, are left out."""
    server.type(text)
    server.type(f"say {MARK}")
    end = server.wait_for(MARK, at, timeout=60)
    said = []
    for line in server.lines[at:end - 1]:
        m = LINE.match(line)
        if m and m.group(2).startswith("System chat: "):
            said.append(m.group(2)[len("System chat: "):])
    return " | ".join(said), end


def reopen(name, world):
    """Step 4: what vanilla warns of opening `world`, with numbers taken out, and what it
    answers the queries."""
    folder = ROOT / name
    prepare(folder, free_port(), world)
    server = Server(vanilla_argv(adapter()), folder, name)
    answers = {}
    try:
        at = server.wait_for("Done (")
        for q in QUERIES:
            answers[q], at = ask(server, q, at)
        for q in ENTITIES:
            end = time.monotonic() + 30
            while True:
                answers[q], at = ask(server, q, at)
                if "Test passed" in answers[q] or "has the following" in answers[q] or time.monotonic() > end:
                    break
                time.sleep(0.5)
        command(server, "save-all flush", "Saved the game", at)
    finally:
        server.stop()
    found = set()
    for line in server.lines:
        m = LINE.match(line)
        if m and m.group(1) != "INFO":
            found.add(f"{m.group(1)} {re.sub(r'[0-9]+', '#', m.group(2))}")
    return found, answers


def build(calx):
    BUILD.mkdir(parents=True, exist_ok=True)
    bot, tool = BUILD / f"session{EXE}", BUILD / f"resave{EXE}"
    for source, exe in (("src/rig/session.calx", bot), ("src/rig/resave.calx", tool)):
        subprocess.run([calx, "build", "--release", source, "-o", str(exe)], cwd=CALCITE, check=True)
    return bot, tool


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--reuse", action="store_true", help="use the last run's vanilla world")
    args = ap.parse_args()
    a = adapter()
    bot, tool = build(find_calx())
    if not args.reuse or not (ROOT / "vanilla" / "world").is_dir():
        make(bot)
    differences = resave(tool)
    back = ROOT / "back-world"
    if back.exists():
        shutil.rmtree(back)
    shutil.copytree(ROOT / "calcite" / "world", back)
    differences += check(a)
    own, own_answers = reopen("again", ROOT / "vanilla" / "world")
    theirs, their_answers = reopen("back", back)
    for w in sorted(theirs - own):
        differences.append(f"vanilla opening Calcite's save logged {w}")
    answers = {q: {"vanilla": own_answers[q], "calcite": their_answers[q]} for q in QUERIES + ENTITIES}
    (ROOT / "answers.json").write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
    for q in QUERIES + ENTITIES:
        if own_answers[q] != their_answers[q]:
            differences.append(f"vanilla answers {q!r} with {their_answers[q]!r} in Calcite's save and {own_answers[q]!r} in its own")
        if "Test failed" in own_answers[q] or "No entity" in own_answers[q] or "Found no" in own_answers[q]:
            differences.append(f"vanilla's own world doesn't answer {q!r}: {own_answers[q]!r}")
    print(f"  vanilla opened Calcite's save with {len(theirs - own)} lines it doesn't log opening its own, "
          f"and answered {len(QUERIES) + len(ENTITIES)} questions about it as about its own", flush=True)
    for d in differences:
        print(d)
    print(f"G5.2: {'passed' if not differences else f'{len(differences)} differences'}")
    return 0 if not differences else 1


if __name__ == "__main__":
    sys.exit(main())
