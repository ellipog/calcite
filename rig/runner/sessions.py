"""The protocol suites (P4.8, CAL-42): the rig's protocol bot runs the same scenarios against
vanilla 26.3 and against Calcite, and the two sessions are compared packet by packet.

    py -I rig/runner/sessions.py [--config NAME] [--scenario NAME] [--compare-only] [--show N] [--tape]
                                 [--trace]

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
--trace has each write its living entities' states to entities.txt in its folder, as each of their
ticks is done, a line each: vanilla's by the rig's agent and Calcite's with --entity-trace, to line
a mob's moves up far finer than its packets show them (rig/runner/traces.py, CAL-159).
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
from dataclasses import dataclass, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "rig" / "calcite-adapter"))
sys.path.insert(0, str(HERE))
from launch import find_calx  # noqa: E402
import nbt  # noqa: E402
import sessiondiff  # noqa: E402
import savediff  # noqa: E402
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
# How long a scenario's bot may run, in seconds, by the wall clock: `select` runs near nine
# minutes of steps (D559, D565, D566, D574, D577).
BOT_SECONDS = 660
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
# Scenarios only the configurations that name them run: `watch`, where the bot joins and stays put a
# fixed number of game ticks, for a world that never goes quiet; `watch-late`, the same but never
# saying its client's loaded, so both servers take it as loaded 60 ticks on (D431); `creative`,
# where it sets slots of its inventory as the creative menu does; `clicks`, where it clicks in its
# inventory menu; `dig` and `dig-creative`, where it digs blocks; `place` and `place-creative`,
# where it places them; `use`, where it uses them; `use-items` and `use-books`, where it uses items
# on them; and `use-containers`, where it opens containers and clicks in them; `items`, where it
# drops, throws and picks up items; `items-saved`, where it picks up items saved in the world;
# `orbs`, where it breaks blocks that give experience; `feed`, where it feeds animals; `attack`,
# where it hits and kills them; `sweep`, where it sweeps them with a sword; `enchant`, where it hits
# them with enchanted swords; `protect`, where it hits zombies in enchanted armor; `stand-hits`,
# where it hits armor stands; `thorns`, where it hits a zombie in thorns; `fall`, where it falls;
# `mace`, where it falls onto a zombie with a mace; `swim`, where it sprints and swims; `checks`,
# where its moves are checked; `duel`, where it hits a second player, Mate, whom the same bot
# runs, recording Mate's packets as `duel-mate`; `zombie`, where a zombie hunts it; `arrows`,
# where arrows fly by it and onto it; `skeleton`, where a skeleton shoots it or runs from the sun;
# `spider`, where a spider climbs to it; `creeper`, where a creeper comes for it; and `enderman`,
# where an enderman it stares at teleports away and comes back for it; `armadillo`, where it
# sprints by armadillos and hits one; `brush`, where it brushes one; `villager`, where it uses
# and hits villagers without AI; `villagers`, where it stands by villagers with their brains;
# `compost`, where it stands by them too and takes a full composter's bone meal; `asleep`, where
# it leaves while they sleep; `breed`, where it stays by them till 1000; `hearsay`, where it
# stays till 1500; `bell`, where it rings a bell by them; `talk`, where it types the commands
# every player may use, with Mate there, recorded as `talk-mate`; and `select`, where it types
# selectors with options as an operator, with Mate there, recorded as `select-mate`
# (src/rig/session.calx).
OTHER_SCENARIOS = ["watch", "watch-late", "creative", "clicks", "dig", "dig-creative", "place", "place-creative", "use", "use-items",
                   "use-books", "use-containers", "items", "items-saved", "orbs", "feed", "attack", "sweep", "enchant", "protect", "fall",
                   "checks", "stand-hits", "thorns", "mace", "swim", "duel", "zombie", "arrows", "skeleton",
                   "spider", "creeper", "enderman", "ender", "armadillo", "brush", "villager", "villagers", "compost", "asleep",
                   "breed", "hearsay", "bell", "bane", "tipped", "dosed", "lifted", "undying", "eaten", "beacons", "beacon-menu",
                   "traders", "frost", "soul", "splash", "linger", "talk", "select", "mites", "end", "crystals",
                   "gateways", "eyes", "throws", "locate", "compass", "bossbars", "dragon", "dragon-flight",
                   "dragon-charge", "dragon-breath", "dragon-fireball", "dragon-strafe", "dragon-death"]
# The scenario a second player's packets are recorded as, by the scenario the bot runs it in
# (CAL-162, CAL-165).
MATE_SCENARIOS = {"duel": "duel-mate", "talk": "talk-mate", "select": "select-mate", "bossbars": "bossbars-mate"}
# What the bot's saved data is compared by, after a configuration that gives it some: what's in
# its inventory and on it, the slot it holds and its game mode (CAL-135), and its attributes,
# whose order is that of vanilla's map of them, by their identity hashes, so they're compared by
# their IDs (D375); and its ender chest's items (CAL-144).
PLAYER_KEYS = ("Inventory", "equipment", "SelectedItemSlot", "playerGameType", "attributes", "EnderItems")
# Its effects too, where a configuration compares them, which vanilla saves as its map of them by
# their holders' identity hashes gives them (D514).
SORTED_KEYS = {"attributes": "id", "active_effects": "id"}
# The world the round trip has vanilla make and save (rig/runner/roundtrip.py), from the seed
# `calcite` with real terrain, its chunks full from -6 to 5 around the origin.
SAVED_WORLD = CALCITE / "build" / "rig" / "roundtrip" / "vanilla" / "world"
# The same seed's world with the same chunks loaded and saved, and nothing put in it, which
# roundtrip.py's `make_plain` has vanilla make the first time a configuration loads it (D599).
PLAIN_WORLD = CALCITE / "build" / "rig" / "roundtrip" / "plain" / "world"
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
    # The bot's saved data, which both servers read as it joins, or none for a player new to the
    # world.
    player: dict | None = None
    # The names of the players in ops.json, at level 4, none of them the bot (D376).
    ops: tuple = ()
    # Whether it's taped whether or not --tape says so, its levels' randoms seeded again at RESEED,
    # as what it compares lines up only from there, natural spawning's mobs (CAL-156).
    tape: bool = False
    # What else of the bot's saved data is compared, past PLAYER_KEYS (D418).
    keys: tuple = ()
    # The second player's saved data, Mate's, whom the whitelist lets in with the bot, or none
    # where there's none (CAL-162).
    mate: dict | None = None
    # Data packs put in the world's datapacks folder, which both servers find and load as they
    # start: each pack's folder name and its files, by their paths in it, with what's in them
    # (CAL-164).
    datapacks: dict | None = None
    # Saved data put in the world's data/minecraft folder, which both servers read as they start:
    # each file's root by its name, such as `scoreboard` (CAL-164).
    saved: dict | None = None
    # Saved data put in a dimension's data/minecraft folder: each file's root by the dimension's
    # folder under `dimensions` and its name, such as `minecraft/the_end/ender_dragon_fight`
    # (D586).
    dim_saved: dict | None = None


def stack(item, count=1, components=None):
    """A stack as `ItemStack.CODEC` writes it."""
    out = {"id": f"minecraft:{item}", "count": nbt.Int(count)}
    if components:
        out["components"] = components
    return out


def slotted(slot, item, count=1, components=None):
    return dict({"Slot": nbt.Byte(slot)}, **stack(item, count, components))


# The bot's data in `inventory`: in creative mode, on the flat world's ground at the spawn, holding
# the hotbar's second slot, with stacks in the hotbar, the inventory's own slots and the offhand,
# armor, and components of the kinds the stream codecs send: a number, enchantments, a name, a
# potion, a color, and one taken away (CAL-135).
INVENTORY = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(1),
    "SelectedItemSlot": nbt.Int(1),
    "Inventory": nbt.List(nbt.COMPOUND, [
        slotted(0, "stone", 64),
        slotted(1, "diamond_sword", 1, {"minecraft:damage": nbt.Int(5),
                                         "minecraft:enchantments": {"minecraft:sharpness": nbt.Int(3)}}),
        slotted(2, "potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:swiftness"}}),
        slotted(8, "bread", 7, {"!minecraft:food": {}}),
        slotted(9, "oak_log", 10, {"minecraft:custom_name": "Logs"}),
        slotted(35, "shield"),
    ]),
    "equipment": {
        "head": stack("diamond_helmet"),
        "chest": stack("elytra", 1, {"minecraft:damage": nbt.Int(10)}),
        "feet": stack("leather_boots", 1, {"minecraft:dyed_color": nbt.Int(0x3366CC)}),
        "offhand": stack("torch", 32),
    },
}


# The bot's data in `clicks`: `inventory`'s, in survival mode, where clicks are the inventory's own,
# rather than the creative menu's (CAL-136).
CLICKS = dict(INVENTORY, playerGameType=nbt.Int(0))

# The bot's data in `crafts`: in survival mode, holding nothing, with three oak logs in the
# inventory's first slot, four honey bottles in its fourth, paper in its fifth, gunpowder in its
# sixth, iron ingots in its seventh, sticks in its eighth and cobblestone in its ninth, which it
# crafts with in its inventory's grid and at the fixture's crafting table (CAL-147).
CRAFTS = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(0),
    "SelectedItemSlot": nbt.Int(0),
    "Inventory": nbt.List(nbt.COMPOUND, [
        slotted(9, "oak_log", 3),
        slotted(12, "honey_bottle", 4),
        slotted(13, "paper"),
        slotted(14, "gunpowder"),
        slotted(15, "iron_ingot", 3),
        slotted(16, "stick", 2),
        slotted(17, "cobblestone", 8),
    ]),
}

# The bot's data in `rewards`: in survival mode, its inventory full of wooden swords but for 30
# cobblestone in its last slot, so what an advancement's loot gives mostly doesn't fit (CAL-164).
REWARDS = dict(CRAFTS, Inventory=nbt.List(nbt.COMPOUND, [slotted(n, "wooden_sword") for n in range(35)] + [
    slotted(35, "cobblestone", 30)]))


# A loot table of an advancement's rewards with a pool for each `item` and `count` in `pools`, an
# entry's `modifier` setting its count, its random sequence its own ID, `name`, so both servers
# draw the same.
def reward_table(name, *pools):
    return json.dumps({"type": "minecraft:advancement_reward", "random_sequence": name, "pools": [
        {"rolls": 1, "entries": [{"type": "minecraft:item", "name": item, "modifier": {
            "type": "minecraft:set_count", "count": count}}]} for item, count in pools]})


# The `rewards` data pack: an advancement done on the player's first tick, which gives 5
# experience and two loot tables, 4 cobblestone, which fit, then 40 cobblestone, of which 30 fit
# and 10 are dropped, 2 diamonds, 1 to 3 arrows and 70 ender pearls, all dropped, the pearls in
# stacks of 16 (CAL-164).
REWARDS_PACK = {
    "pack.mcmeta": json.dumps({"pack": {"description": "The rig's rewards", "min_format": 121, "max_format": 121}}),
    "data/rig/advancement/given.json": json.dumps({
        "criteria": {"ticked": {"trigger": "minecraft:tick"}},
        "rewards": {"experience": 5, "loot": ["rig:fits", "rig:given"]}}),
    "data/rig/loot_table/fits.json": reward_table("rig:fits", ("minecraft:cobblestone", 4)),
    "data/rig/loot_table/given.json": reward_table(
        "rig:given", ("minecraft:cobblestone", 40), ("minecraft:diamond", 2),
        ("minecraft:arrow", {"type": "minecraft:uniform", "min": 1, "max": 3}), ("minecraft:ender_pearl", 70)),
}

# The functions `select` types `function` with (D567): `rig:load`, which `#minecraft:load` runs
# once, making the objective `fn`; `rig:tick`, which `#minecraft:tick` runs each tick, counting
# them and moving a player's `fn` of 50 on to 51; `rig:hello`, which says so; `rig:ret`, which
# returns 7 before it says all it would; `rig:retfail`, which fails; `rig:retrun`, which returns
# what a command gives; `rig:add` and `rig:double`, `#rig:both`, which give 2 and 3; `rig:count`,
# which calls itself till it's counted to 10; `rig:deep`, which calls itself till the command
# quota stops it; `rig:macro`, which says its argument, which `#minecraft:tick` skips, as it has
# none; `rig:macro2`, a command then a macro line naming one variable twice; `rig:macrotp`, whose
# line may not read once made; `rig:macroret`, which returns its argument; `#rig:macros`, a macro
# function and a plain one; `rig:bad`, which can't be read for its `/`; and `#rig:broken`, which
# can't be built for a function there isn't (D567, D568).
FUNCS_PACK = {
    "pack.mcmeta": json.dumps({"pack": {"description": "The rig's functions", "min_format": 121, "max_format": 121}}),
    "data/minecraft/tags/function/load.json": json.dumps({"values": ["rig:load"]}),
    "data/minecraft/tags/function/tick.json": json.dumps({"values": ["rig:tick", "rig:macro"]}),
    "data/rig/tags/function/macros.json": json.dumps({"values": ["rig:macro", "rig:hello"]}),
    "data/rig/tags/function/both.json": json.dumps({"values": ["rig:add", "rig:double"]}),
    "data/rig/tags/function/broken.json": json.dumps({"values": ["rig:hello", "rig:nope"]}),
    "data/rig/function/load.mcfunction": "scoreboard objectives add fn dummy\nscoreboard players set #loaded fn 1\n",
    "data/rig/function/tick.mcfunction": "# Each tick.\nscoreboard players add #ticks fn 1\n"
                                         "execute as @a[scores={fn=50}] run scoreboard players set @s fn 51\n",
    "data/rig/function/hello.mcfunction": "say hello from a function\n",
    "data/rig/function/ret.mcfunction": "say before\nreturn 7\nsay after\n",
    "data/rig/function/retfail.mcfunction": "return fail\n",
    "data/rig/function/retrun.mcfunction": "return run scoreboard players get #loaded fn\n",
    "data/rig/function/add.mcfunction": "return 2\n",
    "data/rig/function/double.mcfunction": "return 3\n",
    "data/rig/function/count.mcfunction": "scoreboard players add #n fn 1\n"
                                          "execute if score #n fn matches ..9 run \\\n    function rig:count\n",
    "data/rig/function/deep.mcfunction": "scoreboard players add #deep fn 1\nfunction rig:deep\n",
    "data/rig/function/macro.mcfunction": "$say $(x)\n",
    "data/rig/function/macro2.mcfunction": "say plain\n$say $(a) and $(b) and $(a)\n",
    "data/rig/function/macrotp.mcfunction": "$tp @s $(x) ~ ~\n",
    "data/rig/function/macroret.mcfunction": "$return $(v)\n",
    "data/rig/function/bad.mcfunction": "/say hi\n",
    "data/rig/function/pred.mcfunction": "execute store result score #pred fn if predicate rig:player\n"
                                         "execute store result score #always fn if predicate rig:always\n",
    "data/rig/predicate/always.json": json.dumps({"type": "minecraft:random_chance", "chance": 1.0}),
    "data/rig/predicate/never.json": json.dumps({"type": "minecraft:inverted", "term": "rig:always"}),
    "data/rig/predicate/coin.json": json.dumps({"type": "minecraft:random_chance", "chance": 0.5}),
    "data/rig/predicate/player.json": json.dumps({"type": "minecraft:entity_properties", "entity": "this",
                                                  "predicate": {"minecraft:entity_type": "minecraft:player"}}),
    "data/rig/predicate/overworld.json": json.dumps({"type": "minecraft:location_check",
                                                     "predicate": {"dimension": "minecraft:overworld"}}),
    "data/rig/slot_source/hands.json": json.dumps({"type": "minecraft:slot_range", "slots": "weapon.*"}),
    "data/rig/slot_source/firsts.json": json.dumps({"type": "minecraft:group", "terms": [
        {"type": "minecraft:slot_range", "slots": "hotbar.0"}, {"type": "minecraft:slot_range", "slots": "inventory.0"}]}),
    "data/rig/item_modifier/five.json": json.dumps({"type": "minecraft:set_count", "count": 5}),
    "data/rig/item_modifier/some.json": json.dumps({"type": "minecraft:set_count",
                                                  "count": {"type": "minecraft:uniform", "min": 1, "max": 9}}),
}

C = nbt.COMPOUND


# The scoreboard in `scores` (CAL-164): objectives of the leave stat, health, shown as hearts in
# the list, food, which follows its holders' display names and has a styled number format, in the
# sidebar, air, with a fixed one, armor, experience, with a blank one, its level, deaths, below
# names, and a dummy, in the red team's sidebar; scores of the dummy, one with a display and a
# format of its own, of deaths for the bot, and one of an objective there isn't, which both servers
# leave out; and three teams: red, with a color, a prefix and a suffix, its own rules, the bot and
# alice, blue, with carol, and an empty one.
SCOREBOARD = {
    "data": {
        "Objectives": nbt.List(C, [
            {"Name": "left", "CriteriaName": "minecraft.custom:minecraft.leave_game", "DisplayName": "Left"},
            {"Name": "hp", "CriteriaName": "health", "DisplayName": {"text": "Health", "color": "red"},
             "RenderType": "hearts"},
            {"Name": "food", "CriteriaName": "food", "DisplayName": "Food", "display_auto_update": nbt.Byte(1),
             "format": {"type": "minecraft:styled", "color": "gold", "bold": nbt.Byte(1)}},
            {"Name": "air", "CriteriaName": "air", "DisplayName": "Air",
             "format": {"type": "minecraft:fixed", "value": "lots"}},
            {"Name": "armor", "CriteriaName": "armor", "DisplayName": "Armor"},
            {"Name": "xp", "CriteriaName": "xp", "DisplayName": "XP", "format": {"type": "minecraft:blank"}},
            {"Name": "level", "CriteriaName": "level", "DisplayName": "Level"},
            {"Name": "deaths", "CriteriaName": "deathCount", "DisplayName": "Deaths"},
            {"Name": "plain", "DisplayName": "Plain"},
        ]),
        "PlayerScores": nbt.List(C, [
            {"Name": "alice", "Objective": "plain", "Score": nbt.Int(5), "Locked": nbt.Byte(1)},
            {"Name": "#fake", "Objective": "plain", "Score": nbt.Int(-3), "display": "Fake",
             "format": {"type": "minecraft:fixed", "value": "?"}},
            {"Name": "Bot", "Objective": "deaths", "Score": nbt.Int(2)},
            {"Name": "carol", "Objective": "ghost", "Score": nbt.Int(1)},
        ]),
        "DisplaySlots": {"list": "hp", "sidebar": "food", "below_name": "deaths", "sidebar.team.red": "plain"},
        "Teams": nbt.List(C, [
            {"Name": "red", "DisplayName": "Red", "TeamColor": "red", "AllowFriendlyFire": nbt.Byte(0),
             "MemberNamePrefix": "[R] ", "MemberNameSuffix": {"text": " *", "color": "gray"},
             "NameTagVisibility": "hideForOtherTeams", "CollisionRule": "pushOwnTeam",
             "Players": nbt.List(nbt.STRING, ["Bot", "alice"])},
            {"Name": "blue", "DisplayName": "Blue", "SeeFriendlyInvisibles": nbt.Byte(0),
             "DeathMessageVisibility": "never", "Players": nbt.List(nbt.STRING, ["carol"])},
            {"Name": "empty", "DisplayName": "Empty"},
        ]),
    },
    "DataVersion": nbt.Int(5023),
}

# The scoreboard in `teammates` (CAL-164): the bot and Mate in one team, which allows no friendly
# fire and no collisions.
TEAMMATES = {
    "data": {"Teams": nbt.List(C, [
        {"Name": "pals", "DisplayName": "Pals", "AllowFriendlyFire": nbt.Byte(0), "CollisionRule": "never",
         "Players": nbt.List(nbt.STRING, ["Bot", "Mate"])},
    ])},
    "DataVersion": nbt.Int(5023),
}

# The scoreboard in `rivals` (CAL-164): the bot in red, whose players push only each other, and
# Mate in blue, whose death messages only its own players see; objectives of kills, player kills,
# deaths, kills of blue and deaths by red, each shown.
RIVALS = {
    "data": {
        "Objectives": nbt.List(C, [
            {"Name": "kills", "CriteriaName": "totalKillCount", "DisplayName": "Kills"},
            {"Name": "pk", "CriteriaName": "playerKillCount", "DisplayName": "Player kills"},
            {"Name": "deaths", "CriteriaName": "deathCount", "DisplayName": "Deaths"},
            {"Name": "tk", "CriteriaName": "teamkill.blue", "DisplayName": "Blues killed"},
            {"Name": "kbt", "CriteriaName": "killedByTeam.red", "DisplayName": "Killed by red"},
        ]),
        "DisplaySlots": {"sidebar": "kills", "list": "pk", "below_name": "deaths", "sidebar.team.red": "tk",
                         "sidebar.team.blue": "kbt"},
        "Teams": nbt.List(C, [
            {"Name": "red", "DisplayName": "Red", "TeamColor": "red", "CollisionRule": "pushOwnTeam",
             "Players": nbt.List(nbt.STRING, ["Bot"])},
            {"Name": "blue", "DisplayName": "Blue", "TeamColor": "blue", "DeathMessageVisibility": "hideForOtherTeams",
             "Players": nbt.List(nbt.STRING, ["Mate"])},
        ]),
    },
    "DataVersion": nbt.Int(5023),
}

# The scoreboard in `talk` (CAL-165): the bot and Mate in aqua's team; trigger objectives, `door`,
# shown in the sidebar, whose score the bot may use, and `bell`, whose it may not; and `kills`,
# which isn't one.
TALK = {
    "data": {
        "Objectives": nbt.List(C, [
            {"Name": "door", "CriteriaName": "trigger", "DisplayName": "Door"},
            {"Name": "bell", "CriteriaName": "trigger", "DisplayName": {"text": "Bell", "color": "gold"}},
            {"Name": "kills", "CriteriaName": "totalKillCount", "DisplayName": "Kills"},
        ]),
        "PlayerScores": nbt.List(C, [
            {"Name": "Bot", "Objective": "door", "Score": nbt.Int(3), "Locked": nbt.Byte(0)},
            {"Name": "Bot", "Objective": "bell", "Score": nbt.Int(0), "Locked": nbt.Byte(1)},
        ]),
        "DisplaySlots": {"sidebar": "door"},
        "Teams": nbt.List(C, [
            {"Name": "pals", "DisplayName": "Pals", "TeamColor": "aqua",
             "Players": nbt.List(nbt.STRING, ["Bot", "Mate"])},
        ]),
    },
    "DataVersion": nbt.Int(5023),
}

# The boss bars `bossbars` starts with (D606): `calcite:saved`, shown, red with 10 notches, its
# value 30 of 60, darkening the screen, whose players the bot is among, so it's shown it as it
# joins; `calcite:hidden`, unseen, playing boss music and making fog, with Mate among its players
# and someone who isn't there; and `calcite:plain`, with only its name, so unseen. The bot's and
# Mate's UUIDs, `offline_uuid`'s, as `UUIDUtil.CODEC` saves them.
BOT_INTS = [-1155928273, 798308776, -1951547997, -315148217]
MATE_INTS = [105469737, -1056885334, -1415735622, -1521856055]
SAVED_BARS = {
    "data": {
        "calcite:saved": {"Name": {"text": "Saved", "color": "gold"}, "Visible": nbt.Byte(1), "Value": nbt.Int(30),
                          "Max": nbt.Int(60), "Color": "red", "Overlay": "notched_10", "DarkenScreen": nbt.Byte(1),
                          "Players": nbt.List(nbt.INT_ARRAY, [nbt.IntArray(BOT_INTS)])},
        "calcite:hidden": {"Name": "Hidden", "PlayBossMusic": nbt.Byte(1), "CreateWorldFog": nbt.Byte(1),
                           "Players": nbt.List(nbt.INT_ARRAY, [nbt.IntArray(MATE_INTS), nbt.IntArray([1, 2, 3, 4])])},
        "calcite:plain": {"Name": "Plain"},
    },
    "DataVersion": nbt.Int(5023),
}

# The bot's data in `dig`: in survival mode, by the spawn, holding a wooden shovel, with shears, a
# golden pickaxe one use from breaking and a diamond sword in the hotbar, and torches in its
# offhand (D376).
DIG = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(0),
    "SelectedItemSlot": nbt.Int(0),
    "Inventory": nbt.List(nbt.COMPOUND, [
        slotted(0, "wooden_shovel"),
        slotted(1, "shears"),
        slotted(2, "golden_pickaxe", 1, {"minecraft:damage": nbt.Int(31)}),
        slotted(3, "diamond_sword"),
    ]),
    "equipment": {"offhand": stack("torch", 32)},
}
# The same, in creative mode, in `dig_creative`.
DIG_CREATIVE = dict(DIG, playerGameType=nbt.Int(1))
# What the dig and place configurations' worlds are, and the rules they're run with: no drops,
# which come with item entities, and no natural spawning, as `terrain` (D376); and no random ticks,
# since grass by a block placed or broken turns to dirt, or dirt to grass, on a tick that falls in
# a different step on each server (D378).
DIG_RULES = (("minecraft:block_drops", nbt.Byte(0)), ("minecraft:spawn_mobs", nbt.Byte(0)),
             ("minecraft:random_tick_speed", nbt.Int(0)))
# The same with drops on, in `dig_drops` (CAL-153).
DIG_DROP_RULES = DIG_RULES[1:]
# The bot's data in `place`: in survival mode at the spawn, facing south, holding the first of the
# hotbar's stone, oak stairs, slabs, logs, doors, a red bed, torches, oak fences and a furnace, with
# cobblestone in its offhand (D378).
PLACE = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(0),
    "SelectedItemSlot": nbt.Int(0),
    "Inventory": nbt.List(nbt.COMPOUND, [
        slotted(0, "stone", 64),
        slotted(1, "oak_stairs", 8),
        slotted(2, "oak_slab", 8),
        slotted(3, "oak_log", 8),
        slotted(4, "oak_door", 4),
        slotted(5, "red_bed"),
        slotted(6, "torch", 8),
        slotted(7, "oak_fence", 8),
        slotted(8, "furnace"),
    ]),
    "equipment": {"offhand": stack("cobblestone", 16)},
}
# In `place_creative`: in creative mode, with nothing, given each block's item as it goes.
PLACE_CREATIVE = dict(PLACE, playerGameType=nbt.Int(1), Inventory=nbt.List(nbt.COMPOUND, []), equipment={})
# In `zombie-head`: `place_creative`'s, wearing a zombie's head, which hides it from zombies to
# half as far, `MOB_VISIBILITY` (CAL-159).
ZOMBIE_HEAD = dict(PLACE_CREATIVE, equipment={"head": stack("zombie_head")})
# In `use`: in survival mode, with nothing in its hands (D379).
USE = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, []), equipment={})
# In `use_items`: in survival mode, hungry, at 10 food, holding seeds, a cake, saplings, candles, a
# water bucket, bottles, a dyed helmet, banners with two patterns and buckets (CAL-142).
USE_ITEMS = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "wheat_seeds", 4),
    slotted(1, "cake"),
    slotted(2, "oak_sapling", 2),
    slotted(3, "red_candle", 2),
    slotted(4, "water_bucket"),
    slotted(5, "glass_bottle", 3),
    slotted(6, "leather_helmet", 1, {"minecraft:dyed_color": nbt.Int(0x3366CC)}),
    slotted(7, "white_banner", 2, {"minecraft:banner_patterns": nbt.List(nbt.COMPOUND, [
        {"pattern": "minecraft:stripe_top", "color": "red"},
        {"pattern": "minecraft:cross", "color": "blue"},
    ])}),
    slotted(8, "bucket", 2),
]), equipment={}, foodLevel=nbt.Int(10))
# In `use_books`: in survival mode, holding a book and quill, two books, an enchanted book, stone and
# dirt, with its sixth slot empty (CAL-142), and cat's record in the seventh, the last two empty
# (CAL-143).
USE_BOOKS = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "writable_book"),
    slotted(1, "book", 2),
    slotted(2, "enchanted_book"),
    slotted(3, "stone", 3),
    slotted(4, "dirt"),
    slotted(6, "music_disc_cat"),
]), equipment={})
# In `use_containers`: in survival mode, holding stone, with dirt in its hotbar's second slot
# (CAL-144).
USE_CONTAINERS = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "stone", 10),
    slotted(1, "dirt", 2),
]), equipment={})
# In `items`: in survival mode, holding stone, with dirt and an iron sword in the hotbar and oak logs
# in the inventory's first slot, which it drops and throws, then picks up (CAL-148).
ITEMS = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "stone", 64),
    slotted(1, "dirt", 10),
    slotted(2, "iron_sword"),
    slotted(9, "oak_log", 5),
]), equipment={})
# The bot's data in `orbs`: in survival mode at the spawn, facing east, holding a diamond hoe with
# mending, one use off whole (CAL-154).
ORBS = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "diamond_hoe", 1, {"minecraft:damage": nbt.Int(1),
                                  "minecraft:enchantments": {"minecraft:mending": nbt.Int(1)}}),
]), equipment={})
# The bot's data in `feed`: in survival mode at the spawn, facing east, holding wheat (CAL-158).
FEED = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "wheat", 16),
]), equipment={})
# The bot's data in `attack`: in survival mode at the spawn, facing east, its hand empty, with a
# stone axe in its hotbar's second slot (CAL-162).
ATTACK = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(1, "stone_axe"),
]), equipment={})
# The bot's data in `sweep`: in survival mode at the spawn, facing east, holding an iron sword
# (D417).
SWEEP = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_sword"),
]), equipment={})
# The bot's data in `thorns`: in survival mode at the spawn, facing east, its hands empty, with
# bread in its second slot, which its death drops (D442).
THORNS = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(1, "bread", 3),
]), equipment={})
# The bot's data in `villager`: `thorns`', with 40 pumpkins in the hotbar's third slot, which it
# trades with Fen, five trades' worth, the first taking her up a level (CAL-160, D509).
TRADER = dict(THORNS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(1, "bread", 3),
    slotted(2, "pumpkin", 40),
]))
# The bot's data in `brush`: `thorns`', with a brush in its main hand, worn by its uses on an
# armadillo till it breaks (CAL-160).
BRUSHER = dict(THORNS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "brush", 1),
]))
# The bot's data in `enchanted`: `thorns`', at the enchanted fixture's spawn among its villagers
# (D522).
ENCHANTED = dict(THORNS, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(4.5), nbt.Double(-60.0), nbt.Double(4.5)]))
# The bot's data in `shows`: `thorns`', holding 8 emeralds, which pay for trades the villagers by
# it hold up (CAL-160).
SHOWS = dict(THORNS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "emerald", 8),
]))
# The bot's data in `arrows`: at the arrows fixture's spawn, the middle of chunk (0, 0), facing
# east, in survival with nothing, so the arrow it picks up goes into its first slot (CAL-159).
ARROWS = dict(PLACE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(8.5), nbt.Double(-60.0), nbt.Double(8.5)]),
              Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, []),
              equipment={})
# The bot's data in `dosed`: `arrows`', at half health, with effects saved on it (D514):
# regeneration I for 120 ticks, which heals it at 100 and 50; poison I for 49, which hurts it at
# 25, its 25th tick, after its client's loaded on both servers, which spare it till then; resistance
# I for 300, which takes a fifth of the arrow's hurt; hunger II for 200; glowing for 80; and night
# vision for ever, ambient, its particles hidden.
def effect(name, duration, amplifier=0, **flags):
    out = {"id": f"minecraft:{name}", "amplifier": nbt.Byte(amplifier), "duration": nbt.Int(duration)}
    for k, v in flags.items():
        out[k] = nbt.Byte(1 if v else 0)
    return out


DOSED = dict(ARROWS, Health=nbt.Float(10.0), active_effects=nbt.List(nbt.COMPOUND, [
    effect("regeneration", 120),
    effect("poison", 49),
    effect("resistance", 300),
    effect("hunger", 200, 1),
    effect("glowing", 80),
    effect("night_vision", -1, ambient=True, show_particles=False),
]))
# The bot's data in `lifted`: `arrows`', with jump boost II and slow falling saved on it for 400
# ticks (D515), so its jump's a fifth higher and it falls back slowly as the server moves it.
LIFTED = dict(ARROWS, active_effects=nbt.List(nbt.COMPOUND, [
    effect("jump_boost", 400, 1),
    effect("slow_falling", 400),
]))
# The bot's data in `beacons`: `place`'s, at the beacons fixture's spawn, in creative mode with
# nothing but stone in its first hotbar slot (D520).
BEACONS = dict(PLACE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(5.5), nbt.Double(-60.0), nbt.Double(5.5)]),
               playerGameType=nbt.Int(1), Inventory=nbt.List(nbt.COMPOUND, [slotted(0, "stone", 64)]), equipment={})
# The bot's data in `splash`: `arrows`', in survival mode facing east, with splash potions of
# poison, healing, regeneration, water and harming in its first five hotbar slots (D527).
SPLASH = dict(ARROWS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "splash_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:poison"}}),
    slotted(1, "splash_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:healing"}}),
    slotted(2, "splash_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:regeneration"}}),
    slotted(3, "splash_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:water"}}),
    slotted(4, "splash_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:harming"}}),
]))
# The bot's data in `linger`: `arrows`', in survival mode facing east, with lingering potions of
# poison, healing, regeneration, harming and slowness in its first five hotbar slots (D529).
LINGER = dict(ARROWS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "lingering_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:poison"}}),
    slotted(1, "lingering_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:healing"}}),
    slotted(2, "lingering_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:regeneration"}}),
    slotted(3, "lingering_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:harming"}}),
    slotted(4, "lingering_potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:slowness"}}),
]))
# The bot's data in `beacon_menu`: `beacons`', in survival mode with an iron ingot, a gold ingot
# and four emeralds in its first three hotbar slots (D521).
BEACON_MENU = dict(BEACONS, playerGameType=nbt.Int(0), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_ingot"), slotted(1, "gold_ingot"), slotted(2, "emerald", 4)]))
# The bot's data in `eaten`: `arrows`', at 12 health, 2 food and no saturation, poisoned for 300
# ticks, carrying apples, honey bottles, a potion of swiftness, milk, a golden apple, a suspicious
# stew of night vision and a potion of healing in its hotbar, and bread in its off hand (D519).
EATEN = dict(ARROWS, Health=nbt.Float(12.0), foodLevel=nbt.Int(2), foodSaturationLevel=nbt.Float(0.0),
             Inventory=nbt.List(nbt.COMPOUND, [
                 slotted(0, "apple", 3),
                 slotted(1, "honey_bottle", 2),
                 slotted(2, "potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:swiftness"}}),
                 slotted(3, "milk_bucket"),
                 slotted(4, "golden_apple"),
                 slotted(5, "suspicious_stew", 1, {"minecraft:suspicious_stew_effects": nbt.List(nbt.COMPOUND, [
                     {"id": "minecraft:night_vision", "duration": nbt.Int(100)}])}),
                 slotted(6, "potion", 1, {"minecraft:potion_contents": {"potion": "minecraft:healing"}}),
             ]),
             equipment={"offhand": stack("bread")},
             active_effects=nbt.List(nbt.COMPOUND, [effect("poison", 300)]))
# The bot's data in `undying`: `arrows`', at 1 health with a totem of undying in its off hand, and
# swiftness and night vision saved on it, which the totem clears as it saves it (D518); 17 food
# and no saturation, so it doesn't heal before the arrow falls on it.
UNDYING = dict(ARROWS, Health=nbt.Float(1.0), foodLevel=nbt.Int(17), foodSaturationLevel=nbt.Float(0.0),
               equipment={"offhand": stack("totem_of_undying")},
               active_effects=nbt.List(nbt.COMPOUND, [
                   effect("speed", 300),
                   effect("night_vision", -1, ambient=True, show_particles=False),
               ]))
# The bot's data in `spider`: `thorns`', on the spider fixture's pillar at the spawn (CAL-159).
SPIDER = dict(THORNS, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-57.0), nbt.Double(0.5)]))
# The bot's data in `slime`: `thorns`', in iron armor, so the slime's hits wear it and leave the bot
# alive till the session's end (CAL-159).
SLIME = dict(THORNS, equipment={"head": stack("iron_helmet"), "chest": stack("iron_chestplate"),
                                "legs": stack("iron_leggings"), "feet": stack("iron_boots")})
# The bot's data in `zombie-sword`: `thorns`', in diamond armor with protection IV on each piece, so
# Rot's sword, its sharpness and its fire leave it alive till it leaves (CAL-159).
PROTECTED = {"minecraft:enchantments": {"minecraft:protection": nbt.Int(4)}}
KNIGHT = dict(THORNS, equipment={"head": stack("diamond_helmet", 1, PROTECTED), "chest": stack("diamond_chestplate", 1, PROTECTED),
                                 "legs": stack("diamond_leggings", 1, PROTECTED), "feet": stack("diamond_boots", 1, PROTECTED)})
# The bot's data in `zombie-thorns`: `slime`'s, its chestplate with thorns III, which hurts a mob that
# hits it now and then and wears as it does (CAL-159).
THORNY = dict(THORNS, equipment={"head": stack("iron_helmet"),
                                 "chest": stack("iron_chestplate", 1, {"minecraft:enchantments": {"minecraft:thorns": nbt.Int(3)}}),
                                 "legs": stack("iron_leggings"), "feet": stack("iron_boots")})
# The bot's data in `bane`: `thorns`', holding an iron sword with bane of arthropods I (D512).
BANE = dict(THORNS, Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_sword", 1, {"minecraft:enchantments": {"minecraft:bane_of_arthropods": nbt.Int(1)}}),
]))
# The bot's data in `thorns-sword`: `thorns`', holding an iron sword with unbreaking III, which its
# death drops in the attack that wears it after (D450), on 10 health, so his thorns kill it while
# it hits him with the sword rather than as it leaves.
THORNS_SWORD = dict(THORNS, Health=nbt.Float(10.0), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_sword", 1, {"minecraft:enchantments": {"minecraft:unbreaking": nbt.Int(3)}}),
    slotted(1, "bread", 3),
]))
# The bot's data in `duel`: in survival mode at the spawn, facing east, an iron sword in its first
# slot and nothing in its second; and Mate's, two blocks east of it, facing west, with nothing, at
# 17 food, so it doesn't heal as it's hit (CAL-162).
DUEL = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_sword"),
]), equipment={})
DUEL_MATE = dict(PLACE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(2.5), nbt.Double(-60.0), nbt.Double(0.5)]),
                 Rotation=nbt.List(nbt.FLOAT, [nbt.Float(90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, []),
                 equipment={}, foodLevel=nbt.Int(17))
# The bot's data in `enchant`: in survival mode at the spawn, facing east, holding an iron sword
# with smite V, with a wooden sword with sharpness I and knockback II in the second slot and one
# with fire aspect II in the third (D438).
ENCHANT = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "iron_sword", 1, {"minecraft:enchantments": {"minecraft:smite": nbt.Int(5)}}),
    slotted(1, "wooden_sword", 1, {"minecraft:enchantments": {"minecraft:sharpness": nbt.Int(1), "minecraft:knockback": nbt.Int(2)}}),
    slotted(2, "wooden_sword", 1, {"minecraft:enchantments": {"minecraft:fire_aspect": nbt.Int(2)}}),
]), equipment={})
# The bot's data in `fall`: in survival mode on the fall fixture's pillar, facing east, holding an
# iron sword (D418).
FALL = dict(PLACE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-30.0), nbt.Double(0.5)]),
            Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
                slotted(0, "iron_sword"),
            ]), equipment={})
# The bot's data in `fall-armored`: `fall`'s, in diamond boots with feather falling IV and an iron
# chestplate with protection IV, which take their shares of its falls (D439).
FALL_ARMORED = dict(FALL, equipment={
    "feet": stack("diamond_boots", 1, {"minecraft:enchantments": {"minecraft:feather_falling": nbt.Int(4)}}),
    "chest": stack("iron_chestplate", 1, {"minecraft:enchantments": {"minecraft:protection": nbt.Int(4)}}),
})
# What `fall` compares of the bot's saved data besides: its health and absorption, its food, its
# motion and its fall (D418).
FALL_KEYS = ("Health", "AbsorptionAmount", "foodLevel", "foodSaturationLevel", "foodExhaustionLevel", "foodTickTimer",
             "Motion", "fall_distance")
# The bot's data in `mace`: in survival mode on the mace fixture's pillar, facing east, holding a
# mace with density III and breach IV (D443).
MACE = dict(PLACE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-48.0), nbt.Double(0.5)]),
            Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, [
                slotted(0, "mace", 1, {"minecraft:enchantments": {"minecraft:density": nbt.Int(3), "minecraft:breach": nbt.Int(4)}}),
            ]), equipment={})
# What `mace` compares of the bot's saved data besides `fall`'s: its impulse, its grace and where
# it was given, and whether its next landing throws up a smash's dust (D443).
MACE_KEYS = FALL_KEYS + ("current_impulse_context_reset_grace_time", "current_explosion_impact_pos",
                         "spawn_extra_particles_on_fall")
# The bot's data in `swim`: in survival mode at the spawn, facing east and a little down, holding
# eight loaves of bread (D444).
SWIM = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(20.0)]), Inventory=nbt.List(nbt.COMPOUND, [
    slotted(0, "bread", 8),
]), equipment={})
# The bot's data in `checks`: in survival mode at the spawn, facing east, its hands empty (D420).
CHECKS = dict(PLACE, Rotation=nbt.List(nbt.FLOAT, [nbt.Float(-90.0), nbt.Float(0.0)]), Inventory=nbt.List(nbt.COMPOUND, []),
              equipment={})
# The bot's data in `frost`: `checks`', in diamond boots with frost walker II (D524).
FROST = dict(CHECKS, equipment={"feet": stack("diamond_boots", 1, {"minecraft:enchantments": {"minecraft:frost_walker": nbt.Int(2)}})})
# The bot's data in `soul`: on the soul fixture's soul sand, facing east, in diamond boots with soul
# speed III (D525).
SOUL = dict(CHECKS, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(3.5), nbt.Double(-60.125), nbt.Double(0.5)]),
            equipment={"feet": stack("diamond_boots", 1, {"minecraft:enchantments": {"minecraft:soul_speed": nbt.Int(3)}})})
# The bot's data in `night`: in creative mode at the spawn, so the monsters that spawn don't make
# for it (CAL-156).
NIGHT = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-63.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(1),
}
# The bot's data in `end` (D586): in survival mode at the spawn, hurt and hungry, fast for a while,
# holding a stone, all of which the respawn after the End's credits keeps.
END_PLAYER = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(0),
    "Health": nbt.Float(15.0),
    "foodLevel": nbt.Int(15),
    "Inventory": nbt.List(nbt.COMPOUND, [{"Slot": nbt.Byte(0), "id": "minecraft:stone", "count": nbt.Int(5)}]),
    "active_effects": nbt.List(nbt.COMPOUND, [{"id": "minecraft:speed", "amplifier": nbt.Byte(0), "duration": nbt.Int(4000),
                                              "ambient": nbt.Byte(0), "show_particles": nbt.Byte(1), "show_icon": nbt.Byte(1)}]),
}
# The bot's data in `choke`: in survival mode at the bottom of the choke fixture's water, out of
# air, starving, its food's timer at 30, with 100 health, which it has room for (D426).
CHOKE = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(4.5), nbt.Double(-60.0), nbt.Double(4.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(0),
    "Air": nbt.Short(0),
    "foodLevel": nbt.Int(0),
    "foodSaturationLevel": nbt.Float(0.0),
    "foodTickTimer": nbt.Int(30),
    "Health": nbt.Float(100.0),
    "attributes": nbt.List(nbt.COMPOUND, [{"id": "minecraft:max_health", "base": nbt.Double(100.0)}]),
}
# The same at the spawn, its eyes in the buried fixture's stone, its air and food full (D426).
BURIED = dict(CHOKE, Pos=nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-60.0), nbt.Double(0.5)]),
              Air=nbt.Short(300), foodLevel=nbt.Int(20), foodTickTimer=nbt.Int(0))
# What `choke` compares of the bot's saved data besides: `fall`'s, and its air (D426).
HURT_KEYS = FALL_KEYS + ("Air",)
# What `buried` does: the same but its health. Its hurts start as its client says it's loaded, once
# the bot has its chunks, which Calcite sends sooner, so its last hurt can fall either side of the
# bot's leave, as its first's tick does (D426).
BURIED_KEYS = tuple(k for k in HURT_KEYS if k != "Health")
# The bot's data in `death`: `buried`'s with 2 health, so the wall's second hurt kills it, stacks in
# the hotbar, the inventory's own slots and the offhand, armor, a stack in the inventory and the
# helmet cursed with vanishing, and 3 levels (D427).
VANISHING = {"minecraft:enchantments": {"minecraft:vanishing_curse": nbt.Int(1)}}
DEATH = dict(BURIED, Health=nbt.Float(2.0), XpLevel=nbt.Int(3), SelectedItemSlot=nbt.Int(4),
             Inventory=nbt.List(nbt.COMPOUND, [
                 slotted(0, "stone", 64),
                 slotted(4, "diamond_sword", 1, {"minecraft:enchantments": {"minecraft:sharpness": nbt.Int(3)}}),
                 slotted(9, "bread", 7),
                 slotted(20, "golden_apple", 2, VANISHING),
                 slotted(35, "oak_log", 10),
             ]),
             equipment={
                 "head": stack("iron_helmet", 1, VANISHING),
                 "chest": stack("leather_chestplate"),
                 "feet": stack("leather_boots"),
                 "offhand": stack("torch", 32),
             })
# What `death` compares: `buried`'s, its health, full once it's respawned, its levels, which it
# loses as it respawns, where it died, and how long it's been dead, none once it's back (D427,
# D428).
DEATH_KEYS = BURIED_KEYS + ("Health", "XpLevel", "LastDeathLocation", "DeathTime")
# The bot's data in `magma`: in survival mode on the magma at the spawn, its hands empty, in iron
# boots three wears from breaking, leather leggings with unbreaking, a netherite chestplate, which
# fire doesn't wear, and a golden helmet (D431).
MAGMA = dict(PLACE, Inventory=nbt.List(nbt.COMPOUND, []), equipment={
    "feet": stack("iron_boots", 1, {"minecraft:damage": nbt.Int(192)}),
    "legs": stack("leather_leggings", 1, {"minecraft:enchantments": {"minecraft:unbreaking": nbt.Int(3)}}),
    "chest": stack("netherite_chestplate"),
    "head": stack("golden_helmet"),
})
# What `magma` compares: `buried`'s, its burns starting as its client says it's loaded (D431).
MAGMA_KEYS = BURIED_KEYS
# The bot's data in `magma-frost`: `magma`'s, its boots diamond with frost walker II, which make it
# immune to the magma's burn; and in `magma-fireproof`, leather with fire protection IV, which take
# their share of each burn (D439).
MAGMA_FROST = dict(MAGMA, equipment=dict(MAGMA["equipment"], feet=stack("diamond_boots", 1, {
    "minecraft:enchantments": {"minecraft:frost_walker": nbt.Int(2)}})))
MAGMA_FIREPROOF = dict(MAGMA, equipment=dict(MAGMA["equipment"], feet=stack("leather_boots", 1, {
    "minecraft:enchantments": {"minecraft:fire_protection": nbt.Int(4)}})))
# The use_items rules: the dig configurations', and no natural regeneration, so the bot's food stays
# where the cake it eats puts it (CAL-142).
USE_ITEMS_RULES = DIG_RULES + (("minecraft:natural_health_regeneration", nbt.Byte(0)),)


CONFIGS = {
    "compressed": Config({}),
    # The bot joins with a saved inventory, which each server sends with the inventory menu's
    # slots, then joins again and sets creative slots; what each saves of it is compared (CAL-135).
    "inventory": Config({}, scenarios=("join", "creative"), player=INVENTORY),
    # The bot, in survival with the same inventory, clicks in its inventory menu; what each server
    # sends back, and what each saves of it, is compared (CAL-136). Taped, as the mobs natural
    # spawning puts by it are drawn from the levels' randoms (CAL-222).
    "clicks": Config({}, scenarios=("clicks",), player=CLICKS, tape=True),
    # The bot joins with its inventory full but for a slot, and a data pack's advancement gives it
    # experience and loot on its first tick: what fits added with a sound, the rest dropped for it
    # alone to pick up at once (CAL-164).
    "rewards": Config({}, scenarios=("join",), player=REWARDS, datapacks={"rewards": REWARDS_PACK}),
    "scores": Config({}, scenarios=("join",), saved={"scoreboard": SCOREBOARD}),
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
    # The bot, in survival mode, digs the dig fixture's ground: under spawn protection, which an op
    # who isn't it has a block around the spawn under; through, let go too soon so it's dug the
    # rest of the way; stopped, switched, aborted elsewhere, out of reach; a tripwire cut with
    # shears; a pickaxe broken; and its hands swapped (D376).
    "dig": Config({"spawn-protection": "1"}, view=3, scenarios=("dig",), world=FIXTURES / "dig" / "world",
                  fixture="dig", rules=DIG_RULES, player=DIG, ops=("Op",)),
    # The same with drops on (CAL-153): what each block the bot breaks drops, from its loot table
    # and random sequence, popped as items, which it picks up as it comes by them.
    "dig_drops": Config({"spawn-protection": "1"}, view=3, scenarios=("dig",), world=FIXTURES / "dig" / "world",
                        fixture="dig", rules=DIG_DROP_RULES, player=DIG, ops=("Op",)),
    # The bot, in creative mode, breaks the dig fixture's blocks: the ground, a bed's foot, a
    # door's and tall grass's tops, a command block it may not, and the ground with a sword
    # (D376).
    "dig_creative": Config({}, view=3, scenarios=("dig-creative",), world=FIXTURES / "dig" / "world",
                           fixture="dig", rules=DIG_RULES, player=DIG_CREATIVE),
    # The bot, in survival mode, places blocks by the place fixture's: on the ground, where it
    # stands, in short grass, from its offhand, on a lectern that takes the use; stairs, slabs, a
    # log, a door, a bed, torches, fences and a furnace, each as it looks; out of reach and hit far
    # from the block (D378).
    "place": Config({}, view=3, scenarios=("place",), world=FIXTURES / "place" / "world",
                    fixture="place", rules=DIG_RULES, player=PLACE),
    # The bot, in creative mode, places blocks given it: turned as it looks, joined to their
    # neighbours, on a side or falling to the floor, powered, and with block entities (D378).
    "place_creative": Config({}, view=3, scenarios=("place-creative",), world=FIXTURES / "place" / "world",
                             fixture="place", rules=DIG_RULES, player=PLACE_CREATIVE),
    # The bot, in survival mode with empty hands, uses the use fixture's blocks: doors, a trapdoor,
    # a fence gate, a lever and a button lighting lamps, a repeater, a comparator, a note block, a
    # bell, a daylight detector and redstone dust (D379).
    "use": Config({}, view=3, scenarios=("use",), world=FIXTURES / "use" / "world",
                  fixture="use", rules=DIG_RULES, player=USE),
    # The bot, in survival mode and hungry, uses items on the use_items fixture's blocks: seeds and
    # a cake in a composter, a sapling in a flower pot and back, a candle put out, a candle on a
    # cake, which it eats, and cauldrons with buckets, bottles, a dyed helmet and banners (CAL-142).
    "use_items": Config({}, view=3, scenarios=("use-items",), world=FIXTURES / "use_items" / "world",
                        fixture="use_items", rules=USE_ITEMS_RULES, player=USE_ITEMS),
    # The bot, in survival mode, puts a book on the use_items fixture's lectern, books in its
    # chiseled bookshelf and takes one back, and stone in its decorated pot (CAL-142); then plays
    # a record in its jukebox and swaps stacks on its shelves (CAL-143).
    "use_books": Config({}, view=3, scenarios=("use-books",), world=FIXTURES / "use_items" / "world",
                        fixture="use_items", rules=USE_ITEMS_RULES, player=USE_BOOKS),
    # The bot, in survival mode, opens the containers fixture's chest, large chest, trapped chest,
    # barrel, ender chest, shulker box, dispenser and hopper, each in a step of its own, clicks
    # stacks in and out of them and closes them; opens a chest with the hopper open; and finds a
    # chest under stone won't open (CAL-144).
    "use_containers": Config({}, view=3, scenarios=("use-containers",), world=FIXTURES / "containers" / "world",
                             fixture="containers", rules=DIG_RULES, player=USE_CONTAINERS),
    # The bot, in survival mode, crafts in its inventory menu's grid: planks, a button, sticks
    # shift-clicked, a rocket swapped out with a hotbar key and a honey block, its bottles left;
    # then at the crafting fixture's table: a pickaxe shift-clicked out, cobblestone dragged across
    # for slabs shift-clicked out twice over, and logs shift-clicked into the grid, which closing
    # puts back. What each server sends back, and
    # what each saves of it, is compared (CAL-147). The crafting fixture's world, as the dig one's
    # rules have it, has no mobs to tell of.
    "crafts": Config({}, view=3, scenarios=("crafts",), world=FIXTURES / "crafting" / "world", fixture="crafting",
                     rules=DIG_RULES, player=CRAFTS),
    # The bot, in survival mode, drops stacks it holds and throws them out of its inventory menu
    # and with the throw key, onto the items fixture's grass, ice and water, where they fall,
    # slide, float and merge, then walks over them and picks them up (CAL-148). Each item's packets
    # are compared in the order it was sent them, apart from the steps, whose ends fall between an
    # item's moves as the clock has it.
    "items": Config({}, view=3, scenarios=("items",), world=FIXTURES / "items" / "world", fixture="items",
                     rules=DIG_RULES, player=ITEMS),
    # The bot, in survival mode, joins a world with items saved in it, which both servers load, and
    # walks over them, picking up those it may; each server saves the rest again (CAL-148).
    "items_saved": Config({}, view=3, scenarios=("items-saved",), world=FIXTURES / "items_saved" / "world",
                           fixture="items_saved", rules=DIG_RULES, player=ITEMS),
    # The bot, in survival mode with drops on, breaks the orbs fixture's sculk and sculk catalyst
    # with a diamond hoe with mending; their experience orbs, split as `award` splits it, follow it
    # and are picked up one a touch, mending the hoe first, the rest the bot's (CAL-154).
    "orbs": Config({}, view=3, scenarios=("orbs",), world=FIXTURES / "orbs" / "world", fixture="orbs",
                   rules=DIG_DROP_RULES, player=ORBS),
    # The bot, in survival mode, feeds the feed fixture's penned cows, calf and sheep wheat by the
    # server's clock (D415), and waits as the cows and the sheep breed, their orbs come to it and
    # their babies grow; no natural spawning, and no advancement messages (CAL-158).
    "feed": Config({}, view=3, scenarios=("feed",), world=FIXTURES / "feed" / "world", fixture="feed",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=FEED),
    # The bot, in survival mode, hits the attack fixture's cows and sheep, each penned in a cell of
    # its own, by the server's clock (D415): with its fist, then a stone axe, charged and not, its
    # second hit in a tick shrugged off, till each dies, dropping its loot and orbs, the calf none;
    # then hits an item, for which the server disconnects it (CAL-162, D416).
    "attack": Config({}, view=3, scenarios=("attack",), world=FIXTURES / "attack" / "world", fixture="attack",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                     player=ATTACK),
    # The bot, in survival mode with an iron sword, hits the sweep fixture's cows and sheep, penned
    # side by side, by the server's clock: its sweeps hurt and knock back the others, a hit as it
    # sprints doesn't sweep and stops its sprint, till all are dead (D417).
    "sweep": Config({}, view=3, scenarios=("sweep",), world=FIXTURES / "sweep" / "world", fixture="sweep",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=SWEEP),
    # The bot, in survival mode with enchanted swords, hits the enchant fixture's cow, zombie and
    # sheep by the server's clock, on normal, which keeps the zombie (D438): smite on the cow and
    # the sheep its sweep reaches, which adds nothing; sharpness and knockback on the zombie; fire
    # aspect on the sheep and the cow its sweep reaches, which burn to death, their meat cooked;
    # and smite on the zombie, which kills it.
    "enchant": Config({"difficulty": "normal"}, view=3, scenarios=("enchant",), world=FIXTURES / "enchant" / "world",
                      fixture="enchant",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                      player=ENCHANT),
    # The bot, in survival mode with an iron sword, falls onto the fall fixture's honey, into its
    # water, and from its basin to the ground, hitting the cow there as it falls, by the server's
    # clock: each fall's damage, its dust and the cow's critical hit (D418).
    "fall": Config({}, view=3, scenarios=("fall",), world=FIXTURES / "fall" / "world", fixture="fall",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=FALL, keys=FALL_KEYS),
    # `fall` in enchanted armor, feather falling and protection taking their shares of each fall
    # (D439).
    "fall-armored": Config({}, view=3, scenarios=("fall",), world=FIXTURES / "fall" / "world", fixture="fall",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                           player=FALL_ARMORED, keys=FALL_KEYS),
    # The bot, in survival mode with an iron sword, hits the protect fixture's zombies by the
    # server's clock, on normal, which keeps them (D439): one in a diamond chestplate with
    # protection IV, which takes its share of each hit; and one in diamond boots with frost walker
    # II and one in a leather helmet with fire protection IV, which give nothing against a hit.
    # Taped, as what its hits do draws from the level's random, which holds what loading drew till
    # it's seeded again (CAL-223).
    "protect": Config({"difficulty": "normal"}, view=3, scenarios=("protect",), world=FIXTURES / "protect" / "world",
                      fixture="protect",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                      player=SWEEP, tape=True),
    # The bot, in survival mode with `enchant`'s swords, hits the stand_hits fixture's armor stands
    # by the server's clock (D441): Bob, named, shaken by a hit, again 30 ticks on, then broken by
    # one 3 ticks after that, dropping his helmet and himself, named, the first sweep reaching the
    # stand beside him and knocking it back; the stand to the north lit by fire aspect, which burns
    # it to its breaking, its chestplate dropped; the invisible stand and the marker, which no hit
    # hurts; while a stand in soul fire and one on a campfire burn to their breaking.
    "stand-hits": Config({}, view=3, scenarios=("stand-hits",), world=FIXTURES / "stand_hits" / "world",
                         fixture="stand_hits",
                         rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                         player=ENCHANT),
    # The bot, in survival mode with its hands empty, hits the thorns fixture's zombie by the
    # server's clock, on normal, which keeps him (D442): his thorns hurt it back, knocking it back
    # and bringing it into combat, which ends 300 of its ticks after; then they kill it, the
    # message naming him and the sword with a custom name he holds (D448), and it leaves dead.
    # Taped, as thorns' chance and damage are drawn from the level's random, which drew what loading
    # drew till it's seeded again (CAL-223).
    "thorns": Config({"difficulty": "normal"}, view=3, scenarios=("thorns",), world=FIXTURES / "thorns" / "world",
                     fixture="thorns",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=THORNS, tape=True),
    # The bot, in survival with an iron sword, hits a second player, Mate, by the server's clock on
    # the duel fixture's world, on normal, a sheep by Mate (CAL-162): a punch, a sword's hit whose
    # sweep reaches the sheep, a hit on the sheep whose sweep reaches Mate, a sprint's knockback
    # attack, then hits till Mate dies and one once it's respawned, and Mate leaves before the bot.
    "duel": Config({"difficulty": "normal"}, view=3, scenarios=("duel",), world=FIXTURES / "duel" / "world", fixture="duel",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                          ("minecraft:respawn_radius", nbt.Int(0))),
                   player=DUEL, mate=DUEL_MATE),
    # The bot, in survival mode with its hands empty, stands at the spawn under the zombie
    # fixture's roof, on normal, while Rot, the zombie six blocks east with his AI, takes it up as
    # his target, comes for it and hits it (CAL-159); it hits him back once, then he hits it till
    # it dies, the message naming him, and it leaves dead.
    "zombie": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie" / "world",
                     fixture="zombie",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=THORNS),
    # `zombie`'s, with Rot on fire (CAL-159): his hits set the bot on fire now and then, by the
    # local difficulty, and it burns. The bot's in `slime`'s iron armor, so it lives till it
    # leaves: a death and respawn has vanilla reload the level's entities, which Calcite doesn't
    # yet (CAL-193).
    "zombie-fire": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie-fire" / "world",
                          fixture="zombie-fire",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=SLIME),
    # `zombie`'s steps on hard at midnight, with natural spawning on, as `isSpawningMonsters`
    # wants it (CAL-159): the bot, in `slime`'s iron armor, hits Rot, whose chance of calling
    # reinforcements is 1, so he calls one, which comes where it may and goes for the bot.
    "reinforcements": Config({"difficulty": "hard"}, view=3, scenarios=("zombie",),
                             world=FIXTURES / "reinforcements" / "world", fixture="reinforcements",
                             rules=(("minecraft:show_advancement_messages", nbt.Byte(0)), ("minecraft:respawn_radius", nbt.Int(0))),
                             player=SLIME),
    # `creeper`'s steps on the zombie-loot fixture's world, the bot on its pillar at midnight, while
    # Grab, the zombie who picks up loot, comes to the pillar's foot, taking up a sword, a better
    # one for it and a helmet on his way, and leaving what he doesn't want (CAL-159).
    "zombie-loot": Config({"difficulty": "normal"}, view=3, scenarios=("creeper",), world=FIXTURES / "zombie-loot" / "world",
                          fixture="zombie-loot",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=SPIDER),
    # `zombie`'s, the bot in `slime`'s iron armor with thorns III on its chestplate (CAL-159): Rot's
    # hits on it are now and then thorns' on him, which hurt him from where it is and wear the
    # chestplate, and it lives till it leaves. Taped, as `thorns` is (CAL-223).
    "zombie-thorns": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie" / "world",
                            fixture="zombie",
                            rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                   ("minecraft:respawn_radius", nbt.Int(0))),
                            player=THORNY, tape=True),
    # `zombie`'s, Rot with an iron sword with sharpness II, knockback I and fire aspect I, the bot in
    # diamond armor with protection IV (CAL-159): his hits deal more, knock it back and set it on
    # fire, and it lives till it leaves.
    "zombie-sword": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie-sword" / "world",
                           fixture="zombie-sword",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=KNIGHT),
    # `zombie`'s steps on the zombie-fall fixture (CAL-159): Rot, on a pillar beside the bot, which
    # hides it from him, is knocked off it by the bot's hit and hurt by his fall.
    "zombie-fall": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie-fall" / "world",
                          fixture="zombie-fall",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=KNIGHT),
    # `zombie`'s steps on the zombie-mace fixture (CAL-159): Rot, with a mace, drops off a pillar
    # beside the bot, in `zombie-sword`'s armor, and smashes it as he falls.
    "zombie-mace": Config({"difficulty": "normal"}, view=3, scenarios=("zombie",), world=FIXTURES / "zombie-mace" / "world",
                          fixture="zombie-mace",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=KNIGHT),
    # `skeleton`'s steps on the zombie-spear fixture (CAL-159): the bot, in `zombie-sword`'s armor,
    # stands while Rot, with an iron spear, comes to within 10 blocks, lowers it and charges, his
    # spear's hits hurting and knocking it back, then gets away and charges again.
    "zombie-spear": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "zombie-spear" / "world",
                           fixture="zombie-spear",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=KNIGHT),
    # The bot, in survival mode with nothing, stands at the arrows fixture's spawn, on normal at
    # midnight, while arrows fly as the world loads (CAL-159): into a wall, into a zombie without
    # AI and an armor stand, which breaks, onto its head, and onto the grass by it, where it picks
    # up the one anyone may. Taped, as the stand's drop is drawn from the level's random (CAL-222).
    "arrows": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arrows" / "world",
                     fixture="arrows",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=ARROWS, tape=True),
    # The bot, in survival mode with nothing, stands at the spawn, on normal at midnight, while an
    # arrow shot up falls back onto each of two endermen without AI (CAL-159): Ender dodges his,
    # unhurt, teleporting away, `repeatedlyTryToTeleport`, and it flies on; Flare's is on fire, which
    # sets him burning though he dodges it, so the fire's hurts teleport him.
    # The bot, in survival mode with nothing, stands at the arrow-border fixture's spawn, on normal
    # at midnight, as arrows fly into the world border, set to chunk (0, 0)'s edges, as the world
    # loads (CAL-159): east, north and to the north-west corner, each bounced back off it a tenth
    # as fast, turned half round and a draw more, and fallen to the grass inside it.
    "arrow-border": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arrow-border" / "world",
                           fixture="arrow-border",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=ARROWS),
    # The bot, in survival mode with nothing, stands at the arrow-blocks fixture's spawn, on normal
    # at midnight, while arrows shot up as the world loads fall back onto blocks that act as
    # they're hit (CAL-159): amethyst chimes, burning arrows light a campfire and a candle, and a
    # chorus flower and a decorated pot break, the pot cracked, its sherds dropped.
    "arrow-blocks": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arrow-blocks" / "world",
                           fixture="arrow-blocks",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=ARROWS),
    # The bot, in survival mode with nothing, stands at the arrow-targets fixture's spawn, on normal
    # at midnight, while arrows from as the world loads hit a target block, a big dripleaf and a
    # bell (CAL-159): the target gives its signal, the leaf tilts down and the bell rings.
    "arrow-targets": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arrow-targets" / "world",
                            fixture="arrow-targets",
                            rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                   ("minecraft:respawn_radius", nbt.Int(0))),
                            player=ARROWS),
    # The bot, in survival mode with nothing, stands at the arrow-buttons fixture's spawn, on normal
    # at midnight, while arrows shot up as the world loads fall into buttons (CAL-159): an oak one,
    # which they press and hold, lighting a lamp, and a stone one, which they don't.
    "arrow-buttons": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arrow-buttons" / "world",
                            fixture="arrow-buttons",
                            rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                   ("minecraft:respawn_radius", nbt.Int(0))),
                            player=ARROWS),
    # The bot, in survival mode with nothing, stands at the arbalistic fixture's spawn, on normal
    # at midnight, while its piercing arrow from a crossbow, shot as the world loads, kills a
    # zombie, a skeleton, a creeper, a cow and a pig without AI in a row (CAL-164), each kill its
    # `player_killed_entity` and each hit its `killed_by_arrow`, the fifth `adventure/arbalistic`,
    # and their orbs come to it.
    "arbalistic": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "arbalistic" / "world",
                         fixture="arbalistic",
                         rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                ("minecraft:respawn_radius", nbt.Int(0))),
                         player=ARROWS),
    # The bot, in survival mode with nothing, stands at the bullseye fixture's spawn, on normal at
    # midnight, while its arrow, shot from beside it as the world loads, strikes the middle of a
    # target block 31.5 blocks east (CAL-164), whose signal of 15 is its `target_hit`,
    # `adventure/bullseye`.
    "bullseye": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "bullseye" / "world",
                       fixture="bullseye",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                              ("minecraft:respawn_radius", nbt.Int(0))),
                       player=ARROWS),
    # The bot, in survival mode with nothing, stands at the tipped fixture's spawn, on normal at
    # midnight, while tipped arrows from as the world loads hit a cow, a zombie and a pig without
    # AI (D513), which take their potions' effects, and one sticks in a wall, where its potion
    # wears off 600 ticks later; it leaves at 700.
    "tipped": Config({"difficulty": "normal"}, view=3, scenarios=("tipped",), world=FIXTURES / "tipped" / "world",
                     fixture="tipped",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=ARROWS),
    # The bot, in survival mode with nothing and the effects its data's saved with, stands at the
    # dosed fixture's spawn, on normal at midnight, while a tipped arrow of swiftness shot up falls
    # back onto its head (D514): its effects tick, heal it, hurt it and end, told it as they do,
    # and the arrow's swiftness is added, its speed's modifier sent; it leaves at 400.
    "dosed": Config({"difficulty": "normal"}, view=3, scenarios=("dosed",), world=FIXTURES / "dosed" / "world",
                    fixture="dosed",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                           ("minecraft:respawn_radius", nbt.Int(0))),
                    player=DOSED, keys=("active_effects", "Health", "AbsorptionAmount", "foodLevel", "foodSaturationLevel", "foodExhaustionLevel")),
    # The bot, in survival mode with nothing but jump boost II and slow falling, stands at the
    # lifted fixture's spawn, on normal, by mobs shut in glass with their AI and effects (D515):
    # Lift levitating up its tube and falling as it ends, Feather falling slowly down hers, Glide
    # sliding through water with dolphin's grace and Hop hopping with jump boost; at 150 it jumps,
    # and falls back slowly as the server moves it, on the ground again at 210; it leaves at 400.
    "lifted": Config({"difficulty": "normal"}, view=3, scenarios=("lifted",), world=FIXTURES / "lifted" / "world",
                     fixture="lifted",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=LIFTED, keys=("active_effects", "Health", "Motion", "fall_distance", "foodExhaustionLevel")),
    # The bot, in survival mode at 1 health with a totem in its off hand and effects saved on it,
    # stands at the undying fixture's spawn, on normal at midnight, while a plain arrow shot up
    # falls back onto it and its totem saves it, its effects cleared and the totem's given; it hits
    # Undying, a zombie without AI at 1 health with a totem, at 120, at 200, which would kill it
    # but for its totem, and at 280, which its absorption takes (D518); it leaves at 400.
    "undying": Config({"difficulty": "normal"}, view=3, scenarios=("undying",), world=FIXTURES / "undying" / "world",
                      fixture="undying",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                             ("minecraft:respawn_radius", nbt.Int(0))),
                      player=UNDYING, keys=("active_effects", "Health", "AbsorptionAmount", "equipment", "foodLevel")),
    # The bot, in survival mode at 12 health, 2 food and poisoned, stands at the eaten fixture's
    # spawn, on normal at noon, and eats and drinks what it carries, each to its end: an apple,
    # a honey bottle, which takes its poison off and leaves a bottle in its inventory, a potion
    # of swiftness, and milk, which takes it off again; it starts on another apple and lets go of
    # it, eats the bread in its off hand, then a golden apple and a suspicious stew, full, drinks
    # a potion of healing, and can't eat another apple (D519); it leaves at 540.
    "eaten": Config({"difficulty": "normal"}, view=3, scenarios=("eaten",), world=FIXTURES / "eaten" / "world",
                    fixture="eaten",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                           ("minecraft:respawn_radius", nbt.Int(0))),
                    player=EATEN, keys=("active_effects", "Health", "AbsorptionAmount", "foodLevel",
                                        "foodSaturationLevel")),
    # Splash potions thrown (D527): the bot, in survival mode at the splash fixture's spawn, on
    # normal at midnight, throws splash potions at Moo, the cow, and Rot, the zombie, both without
    # AI: poison at the cow, which poisons it and the bot; healing at the zombie, which hurts it;
    # regeneration at its own feet; water at nothing; and harming at the cow, which hurts it and
    # the bot; and it leaves at 420. Taped, as the throws' pitches are drawn from the level's
    # random, which holds what loading drew till it's seeded again (CAL-223).
    "splash": Config({"difficulty": "normal"}, view=3, scenarios=("splash",), world=FIXTURES / "splash" / "world",
                     fixture="splash",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=SPLASH, keys=("active_effects", "Health", "AbsorptionAmount"), tape=True),
    # Lingering potions thrown (D529): the bot, as in `splash`, throws lingering potions, each of
    # which leaves a cloud where it lands that doses what's in it each second, shrinking as it
    # does: poison at Moo, the cow; healing at Rot, the zombie, which hurts him; regeneration and
    # then harming at its own feet; and slowness away to the north, whose cloud is still there as
    # it leaves at 480, saved with the chunks. Its levels' randoms are seeded again at 101, as
    # `splash`'s are, as each throw's sound draws its pitch from one (CAL-245).
    "linger": Config({"difficulty": "normal"}, view=3, scenarios=("linger",), world=FIXTURES / "splash" / "world",
                     fixture="splash",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=LINGER, keys=("active_effects", "Health", "AbsorptionAmount"), tape=True),
    # The bot, in creative mode with stone in its hand, stands at the beacons fixture's spawn, on
    # normal at noon, among beacons that pulse their effects onto it every 80 ticks (D520): speed,
    # jump boost but not its regeneration, two levels short, resistance through bedrock, strength
    # and regeneration, and haste II; at 300 it breaks a corner of the speed beacon's base, which
    # goes off, and at 400 puts stone on the glass over the jump boost beacon, which cuts its beam;
    # it leaves at 560.
    "beacons": Config({"difficulty": "normal"}, view=3, scenarios=("beacons",), world=FIXTURES / "beacons" / "world",
                      fixture="beacons",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                             ("minecraft:respawn_radius", nbt.Int(0))),
                      player=BEACONS, keys=("active_effects", "Health")),
    # The bot, in survival mode with an iron ingot, a gold ingot and four emeralds, stands at the
    # beacons fixture's spawn, on normal at noon, and uses the beacon of jump boost, which opens
    # its menu: it pays with the iron ingot and picks speed, which the beacon gives from then on,
    # puts the gold ingot in and closes the menu, which drops it, then opens it again and
    # shift-clicks the emeralds, which don't go in, more than one (D521); it leaves at 480.
    "beacon_menu": Config({"difficulty": "normal"}, view=3, scenarios=("beacon-menu",),
                          world=FIXTURES / "beacons" / "world", fixture="beacons",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=BEACON_MENU, keys=("active_effects", "Inventory")),
    "ender-arrows": Config({"difficulty": "normal"}, view=3, scenarios=("arrows",), world=FIXTURES / "ender-arrows" / "world",
                           fixture="ender-arrows",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=ARROWS),
    # The bot, in survival mode with its hands empty, stands at the spawn, on normal at midnight,
    # while Bones, the skeleton ten blocks east with his AI and a bow, takes it up as his target,
    # draws, shoots it and strafes about it (CAL-159).
    "skeleton": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "skeleton" / "world",
                       fixture="skeleton",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                              ("minecraft:respawn_radius", nbt.Int(0))),
                       player=THORNS),
    # `skeleton`'s, on the skeleton-bow fixture's world, the bot in `zombie-sword`'s armor, with
    # protection IV, so it lives: Bones's bow has power III, punch II and flame, so his arrows burn
    # as they're shot, hit harder, knock the bot back and set it on fire (CAL-159). Not thorns,
    # whose chance is drawn from the level's random, as Bones shoots before the levels are seeded
    # again.
    "skeleton-bow": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "skeleton-bow" / "world",
                           fixture="skeleton-bow",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=KNIGHT),
    # The bot, in survival mode with its hands empty, stands on the spider fixture's pillar at the
    # spawn, on normal at midnight, while Webs, the spider eight blocks east with its AI, takes it
    # up, goes for it, climbs the pillar's side, which its path can't, and bites it (CAL-159).
    "spider": Config({"difficulty": "normal"}, view=3, scenarios=("spider",), world=FIXTURES / "spider" / "world",
                     fixture="spider",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                            ("minecraft:respawn_radius", nbt.Int(0))),
                     player=SPIDER),
    # The bot, in survival mode with its hands empty, stands on the creeper fixture's pillar at the
    # spawn, on normal at midnight, while Boom, the creeper eight blocks east with its AI, takes it
    # up and comes to the pillar's foot, from where it's too far up for Boom to swell (CAL-159).
    "creeper": Config({"difficulty": "normal"}, view=3, scenarios=("creeper",), world=FIXTURES / "creeper" / "world",
                      fixture="creeper",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                             ("minecraft:respawn_radius", nbt.Int(0))),
                      player=SPIDER),
    # The bot, in survival mode with its hands empty, stands on the enderman fixture's pillar at
    # the spawn, on normal at midnight, and turns to stare at Ender, the enderman two blocks east
    # with its AI, who takes it up, teleports away as it's stared at so near, and comes back for
    # it, angry (CAL-159). With mob griefing on, Ender's take and leave goals draw, and it takes
    # what it may hold and reach.
    "enderman": Config({"difficulty": "normal"}, view=3, scenarios=("enderman",), world=FIXTURES / "enderman" / "world",
                       fixture="enderman",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                              ("minecraft:respawn_radius", nbt.Int(0))),
                       player=SPIDER),
    # The bot, in survival mode with nothing, at the spawn on normal at midnight, by Ender, the
    # enderman with his AI two blocks east (CAL-159): it hits him once, so he takes it up, angry at
    # it, and hits it till it dies, and it leaves dead; with `forgive_dead_players` on, as it is by
    # default, he forgives it as it dies, `tellNeutralMobsThatIDied`, so he's saved angry at no one;
    # in `ender-grudge`, with it off, he's saved angry at it still.
    "ender-forgive": Config({"difficulty": "normal"}, view=3, scenarios=("ender",), world=FIXTURES / "ender-ground" / "world",
                            fixture="ender-ground",
                            rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                   ("minecraft:respawn_radius", nbt.Int(0))),
                            player=THORNS),
    "ender-grudge": Config({"difficulty": "normal"}, view=3, scenarios=("ender",), world=FIXTURES / "ender-ground" / "world",
                           fixture="ender-ground",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0)), ("minecraft:forgive_dead_players", nbt.Byte(0))),
                           player=THORNS),
    # The bot, on the `enderman` fixture's pillar, hits Ender below it once, with `universal_anger`
    # on (CAL-159): he doesn't take it up for its hit, `HurtByTargetGoal`, but angry at all players,
    # `ResetUniversalAngerTargetGoal`, his look for players does a few ticks on, and he comes for it,
    # too far up to hit.
    "ender-hit": Config({"difficulty": "normal"}, view=3, scenarios=("ender",), world=FIXTURES / "enderman" / "world",
                        fixture="enderman",
                        rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                               ("minecraft:respawn_radius", nbt.Int(0)), ("minecraft:universal_anger", nbt.Byte(1))),
                        player=SPIDER),
    # The bot, in creative mode with nothing, which no monster takes up, stands at the spawn, on
    # normal at noon, while Sunny, the skeleton out in the sun with his AI, burns and runs for the
    # shade under the stone roof by him, his paths kept out of the sun once he's in it (CAL-159).
    "skeleton-sun": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",),
                           world=FIXTURES / "skeleton-sun" / "world", fixture="skeleton-sun",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=PLACE_CREATIVE),
    # The bot, in survival mode in iron armor with its hands empty, stands at the spawn, on normal
    # at midnight, while Gloop, the slime of size 2 five blocks east with its AI, takes it up, hops
    # to it and hurts it as it touches it, wearing its armor (CAL-159).
    "slime": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "slime" / "world",
                    fixture="slime",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                           ("minecraft:respawn_radius", nbt.Int(0))),
                    player=SLIME),
    # The bot, in creative mode with nothing, which no monster takes up, stands at the spawn, on
    # normal at midnight, while Rot, the zombie villager six blocks east with its AI, and Shamble,
    # the zombie six blocks south, stroll and look about and at it, Rot's random seeded before its
    # profession's drawn (CAL-194).
    "zombie-villager": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",),
                              world=FIXTURES / "zombie-villager" / "world", fixture="zombie-villager",
                              rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                     ("minecraft:respawn_radius", nbt.Int(0))),
                              player=PLACE_CREATIVE),
    # `zombie-villager`'s, the bot in a zombie's head, which hides it from zombies to half as far
    # (CAL-159): Shamble, six blocks off, looks at it only within 4, so never, and Rot as before.
    "zombie-head": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",),
                          world=FIXTURES / "zombie-villager" / "world", fixture="zombie-villager",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=ZOMBIE_HEAD),
    # The bot, in creative mode with nothing, which no monster takes up, stands at the spawn, on
    # normal at midnight, while Hex, the witch six blocks east with her AI, strolls and looks about
    # and at it, with no one to throw at and nothing to drink (CAL-159).
    "witch": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "witch" / "world",
                    fixture="witch",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                           ("minecraft:respawn_radius", nbt.Int(0))),
                    player=PLACE_CREATIVE),
    # `witch` with the bot in survival with nothing, which Hex takes up (D528): she comes within
    # ten blocks, stops where she sees it, and throws splash potions at it every three seconds,
    # poison first, then harming, each flying and splashing it; it leaves at 300.
    "witch-throw": Config({"difficulty": "normal"}, view=3, scenarios=("skeleton",), world=FIXTURES / "witch" / "world",
                          fixture="witch",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                 ("minecraft:respawn_radius", nbt.Int(0))),
                          player=USE, keys=("active_effects", "Health", "AbsorptionAmount")),
    # `thorns` with the bot holding an iron sword with unbreaking III: the hit whose thorns kill it
    # drops the sword, which the attack then wears, as vanilla's `postHurtEnemy` wears the stack
    # the drop holds, unbreaking drawing from the level's random (D450). Taped, as `thorns` is
    # (CAL-223).
    "thorns-sword": Config({"difficulty": "normal"}, view=3, scenarios=("thorns",), world=FIXTURES / "thorns" / "world",
                           fixture="thorns",
                           rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                                  ("minecraft:respawn_radius", nbt.Int(0))),
                           player=THORNS_SWORD, tape=True),
    # The bot, in survival mode with a mace, falls onto the mace fixture's column and from it to
    # the ground by the server's clock, on normal, which keeps the zombie, smashing as it falls
    # (D443): a heavy smash on him from seven blocks, which pushes the cow and the stand by him; a
    # light one on the cow from two and five eighths, in the air; and a hit on him from the ground,
    # which isn't a smash.
    "mace": Config({"difficulty": "normal"}, view=3, scenarios=("mace",), world=FIXTURES / "mace" / "world", fixture="mace",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=MACE, keys=MACE_KEYS),
    # The bot, in survival mode, sprints on the swim fixture's grass by the server's clock, its
    # sprint's particles drawing from its random, which a loaf it drops shows; into the pool, where
    # it swims, stops sprinting and swims again; and out onto the grass beyond (D444).
    "swim": Config({}, view=3, scenarios=("swim",), world=FIXTURES / "swim" / "world", fixture="swim",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=SWIM, keys=FALL_KEYS + ("Air",)),
    # The bot, in survival mode at the frost fixture's spawn in boots with frost walker II, by the
    # server's clock from game time 200, walks east across its pool on what it freezes, three
    # blocks a second, onto the grass beyond, and stays as the frosted ice melts; it leaves at 900
    # (D524).
    "frost": Config({}, view=3, scenarios=("frost",), world=FIXTURES / "frost" / "world", fixture="frost",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=FROST, keys=FALL_KEYS),
    # The bot, in survival mode on the soul fixture's soul sand in boots with soul speed III, by the
    # server's clock from game time 200, walks back and forth on it, three blocks a second, its
    # boots speeding it, wearing as it goes and giving off souls; it leaves at 760 (D525).
    "soul": Config({}, view=3, scenarios=("soul",), world=FIXTURES / "soul" / "world", fixture="soul",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=SOUL, keys=FALL_KEYS),
    # The bot, in survival mode by the checks fixture's wall, by the server's clock: a move too
    # quick, one through the wall and one into it, each of which the server sends it back from,
    # then a float it's kicked for (D420).
    "checks": Config({}, view=3, scenarios=("checks",), world=FIXTURES / "checks" / "world", fixture="checks",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                     player=CHECKS, keys=FALL_KEYS),
    # Armor stands by the spawn, which both servers load and tick (CAL-155): falling onto stone,
    # hay, honey and slime, sliding on ice, down a ladder and into water, and standing, small, a
    # marker, without gravity, posed and invisible; watched, as `redstone`.
    "stands": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "stands" / "world", fixture="stands",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Mooshrooms (CAL-156): with natural spawning on, creatures spawn every 400 ticks in the
    # mooshrooms fixture's mushroom fields, chunks -2 to 2, which a view of 2 has their entities
    # tick, as mooshrooms both servers make; and two without AI stand and moo; watched, and
    # taped, as their places are drawn from the levels' randoms, which line up once seeded again.
    "mooshrooms": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "mooshrooms" / "world",
                         fixture="mooshrooms", tape=True),
    # The farm animals (CAL-156): as `mooshrooms`, in the farm fixture's birch forest and badlands
    # on grass, sheep, pigs, chickens and cows of their biomes' variants; and five without AI, two
    # chickens laying their eggs.
    # Armadillos with their brains (CAL-160): the bot, in survival mode with its hand empty, stands
    # at the armadillo fixture's spawn, penned with Dilly, by the server's clock from once it's
    # loaded, while she and Rolly idle, strolling, looking about and at it; at 200 it sprints,
    # which scares Dilly, who rolls up and peeks while it does, Rolly too far to see it; at 260 it
    # stops, and as the danger she saw runs out she unrolls; at 420 it hits her, which rolls her up,
    # and at 440 hits her again rolled up, which hurts her less; it leaves at 600.
    "armadillo": Config({}, view=3, scenarios=("armadillo",), world=FIXTURES / "armadillo" / "world", fixture="armadillo",
                        rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                        player=THORNS),
    # Brushing armadillos (CAL-160): as `armadillo`, but with a brush in the bot's main hand, which
    # it uses on Dilly four times, each brushing a scute off her, the fourth breaking it, then
    # once with its hand empty, which does nothing.
    "brush": Config({}, view=3, scenarios=("brush",), world=FIXTURES / "armadillo" / "world", fixture="armadillo",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=BRUSHER),
    # Armadillos breeding (CAL-160): the bot standing as in `villagers` by Dilly and Rolly, in love
    # and penned together, who find each other and have a baby, `AnimalMakeLove`.
    "armadillo-love": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "armadillo-love" / "world",
                             fixture="armadillo-love",
                             rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                             player=THORNS),
    # A spider without AI (D512): the bot, in survival mode holding a sword with bane of arthropods
    # I, stands at the bane fixture's spawn by Webs and hits it at 200 and 300, each hit slowing it,
    # slowness IV for a second and a half, its particles shown and its speed sent, and leaves at
    # 400.
    "bane": Config({"difficulty": "normal"}, view=3, scenarios=("bane",), world=FIXTURES / "bane" / "world", fixture="bane",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                          ("minecraft:respawn_radius", nbt.Int(0))),
                   player=BANE),
    # Villagers without AI (CAL-160): the bot, in survival mode with its hand empty and pumpkins in
    # its hotbar, stands at the villager fixture's spawn by Ada, grown with no profession, Bo, a
    # baby, and Fen, a desert farmer; it uses Ada, who has no trades, and Bo, which makes each
    # unhappy, then hits Fen and Ada, each of whom then gossips of it; then it trades its pumpkins
    # with Fen for emeralds, and leaves at 600.
    "villager": Config({}, view=3, scenarios=("villager",), world=FIXTURES / "villager" / "world", fixture="villager",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                       player=TRADER),
    # Enchanted trades (D522): the bot, in survival mode with its hand empty, stands at the
    # enchanted fixture's spawn among eight villagers without AI and with no offers, librarians,
    # a weaponsmith, a fletcher, a fisherman and a toolsmith, and uses each in turn, its offers made
    # from its level's trade set as it does, enchanted books, weapons and tools among them with the
    # cost their enchanting adds, and closes each one's trades; it leaves at 460.
    "enchanted": Config({}, view=3, scenarios=("traders",), world=FIXTURES / "enchanted" / "world", fixture="enchanted",
                        rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                        player=ENCHANTED),
    # Dyed trades (D523): as `enchanted`, on the dyed fixture's world, among leatherworkers at the
    # first five levels, a farmer at the fourth and two fletchers at the fifth, whose offers are
    # made as the bot uses them, leather armor dyed at random, suspicious stew of a random effect
    # and tipped arrows of a random potion among them.
    "dyed": Config({}, view=3, scenarios=("traders",), world=FIXTURES / "dyed" / "world", fixture="dyed",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=ENCHANTED),
    # Villagers with their brains (CAL-160): the bot, in survival mode with its hand empty, stands
    # at the villagers fixture's spawn by the server's clock from once it's loaded, in the morning,
    # while Ada, grown with no profession, five blocks east by a bed, and Bo, a baby, farther by
    # another, idle: strolling, looking about and at it, claiming the beds, Bo jumping on his, and
    # Ada showing it her trades and trading with Bo; it leaves at 600.
    "villagers": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "villagers" / "world", fixture="villagers",
                        rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                        player=THORNS),
    # A zombie going through a village at night (D605): as `villagers`, on normal, on the
    # village-zombie fixture's world, where Rot, a zombie, finds the bed Vi claims in her box above
    # the grass, a village's point of interest that's taken, `MoveThroughVillageGoal`, and walks
    # toward it as near as he gets, under her box, then not again, as he's been; the bot, in
    # creative mode with nothing, isn't his target.
    "village-zombie": Config({"difficulty": "normal"}, view=3, scenarios=("villagers",),
                             world=FIXTURES / "village-zombie" / "world", fixture="village-zombie",
                             rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                             player=PLACE_CREATIVE),
    # Professions (CAL-160): as `villagers`, on the professions fixture's world, where Di, a
    # farmer with no job site, loses her profession and takes a fletching table; Fa, holding Ed's
    # composter with less experience, forgets it and loses her profession, takes it and loses it
    # again, then takes the composter by Cy as a farmer for good; and Cy is left with none.
    "professions": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "professions" / "world", fixture="professions",
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                          player=THORNS),
    # Doors (CAL-160): as `villagers`, on the doors fixture's world, where Cy and Di, shut in a
    # hut, walk out through its door to the job sites outside, opening it and shutting it behind
    # them.
    "doors": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "doors" / "world", fixture="doors",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=THORNS),
    # Work (CAL-160): as `villagers`, on the work fixture's world, where Gi, a librarian, works at
    # her lectern and restocks her used offer; Ha, a cleric, works at his brewing stand on a new
    # day, his offers made then, their demand caught up; Fa, a farmer, works at her composter,
    # too soon for another restock; and Ib, a mason, walks back to his stonecutter.
    "work": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "work" / "world", fixture="work",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=THORNS),
    # Pickup (CAL-160): as `villagers`, on the pickup fixture's world, where Jo, a farmer, sees
    # wheat seeds and bread near her, walks to them and picks them up, but not a diamond she
    # doesn't want, nor bone meal too far to walk to; and Ko, a nitwit with a full inventory,
    # leaves carrots he has no room for, which Jo picks up as she strolls by.
    "pickup": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "pickup" / "world", fixture="pickup",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                     player=THORNS),
    # Harvest (CAL-160): as `villagers`, on the harvest fixture's world, where Hal, a farmer,
    # breaks ripe crops, plants seeds on bare farmland and grows young wheat with bone meal, and
    # Cy, a cleric, grows beetroots with hers.
    "harvest": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "harvest" / "world", fixture="harvest",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                      player=THORNS),
    # Compost (CAL-160): as `villagers`, on the compost fixture's world, where the bot takes a full
    # composter's bone meal at 450, and Hal, a farmer, bakes bread of his wheat, which he has no
    # room for and drops, takes his full composter's bone meal and composts his seeds.
    "compost": Config({}, view=3, scenarios=("compost",), world=FIXTURES / "compost" / "world", fixture="compost",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                      player=THORNS),
    # Throws (CAL-160): as `villagers`, on the throws fixture's world, where Ada, a nitwit, and Bo,
    # a farmer, trade and throw each other what they have too much of.
    "throws": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "throws" / "world", fixture="throws",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                     player=THORNS),
    # Sleep (CAL-160): as `villagers`, on the sleep fixture's world, where Ada lies down in her bed,
    # Bo walks to his and lies down, Cy, saved asleep, is put on his as he's loaded, and all get up
    # as the day comes; and `asleep`, the same but left while they sleep, so they're saved asleep.
    "sleep": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "sleep" / "world", fixture="sleep",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=THORNS),
    "asleep": Config({}, view=3, scenarios=("asleep",), world=FIXTURES / "sleep" / "world", fixture="sleep",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                     player=THORNS),
    # Breed (CAL-160): as `villagers` but till 1000, on the breed fixture's world, where Ada and Bo,
    # grown, each with bread, claim beds and have a baby, who takes the third.
    "breed": Config({}, view=3, scenarios=("breed",), world=FIXTURES / "breed" / "world", fixture="breed",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=THORNS),
    # Hearsay (CAL-160): as `villagers` but till 1500, on the hearsay fixture's world, where Ada and
    # Bo, grown and penned together, talk, and once the game time's 1200 one passes on or hears
    # what Ada's heard of two others.
    "hearsay": Config({}, view=3, scenarios=("hearsay",), world=FIXTURES / "hearsay" / "world", fixture="hearsay",
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                      player=THORNS),
    # Bell (CAL-160): as `villagers` but till 700, on the bell fixture's world, where the bot rings
    # the bell by it at 200 and Ada and Bo, grown and penned with two beds, hear it and hide by a
    # bed for 300 ticks.
    "bell": Config({}, view=3, scenarios=("bell",), world=FIXTURES / "bell" / "world", fixture="bell",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=THORNS),
    # Shows (CAL-160): as `villagers`, on the shows fixture's world, where the bot holds emeralds
    # and Fen and Gil, farmers penned with it, hold up what the emeralds buy of their trades,
    # Gil's offers made as he first looks.
    "shows": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "shows" / "world", fixture="shows",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                    player=SHOWS),
    # Tag (CAL-160): as `villagers`, on the tag fixture's world, where Ada and Bo, babies, play tag
    # in the morning by the bell Cy claims.
    "tag": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "tag" / "world", fixture="tag",
                  rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                  player=THORNS),
    # Homeless (CAL-160): as `villagers`, on the homeless fixture's world, where Ada, Bo and Cy,
    # with no homes at night, walk to a bed, step about under a roof and head for a village.
    "homeless": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "homeless" / "world", fixture="homeless",
                       rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                       player=THORNS),
    # Meet (CAL-160): as `villagers`, on the meet fixture's world, where Ada, Bo and Cy meet at
    # their bell, strolling around it and walking to each other to talk.
    "meet": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "meet" / "world", fixture="meet",
                   rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0))),
                   player=THORNS),
    # Crops (CAL-160): as `villagers`, on the crops fixture's world, with random ticks at 16 a
    # section, where wheat, carrots, potatoes, beetroots and torchflower crops grow, farmland by
    # water wets and farmland away from it dries, back to dirt where nothing's on it; and items, an
    # orb, a chicken and a cow land on farmland, each drawing as it lands.
    "crops": Config({}, view=3, scenarios=("villagers",), world=FIXTURES / "crops" / "world", fixture="crops",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                           ("minecraft:random_tick_speed", nbt.Int(16))),
                    player=THORNS),
    "farm": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "farm" / "world", fixture="farm",
                   tape=True),
    # Plains (CAL-156): as `farm`, on the plains fixture's grass, where horses and donkeys spawn
    # with the farm animals; and three without AI that graze.
    "plains": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "plains" / "world", fixture="plains",
                     tape=True),
    # Monsters (CAL-156): as `farm`, from dusk on the night fixture's plains, on normal, where
    # monsters spawn every tick, zombie horses among them, finalized by the difficulty where each
    # stands; the bot in creative, which they don't make for; and four without AI, a zombie, a
    # skeleton with its bow, a creeper and a spider. With mob griefing, so an enderman takes
    # blocks of the grass and leaves them, and one carrying a block stays, off the monsters' cap
    # (CAL-159).
    "night": Config({"difficulty": "normal"}, view=2, scenarios=("watch",), world=FIXTURES / "night" / "world",
                    fixture="night", tape=True, player=NIGHT),
    # Monsters on hard (D522): as `night`, on the night-hard fixture's, sixty days on and on hard,
    # so the monsters that spawn wear armor more and are enchanted from `mob_spawn_equipment`.
    "night_hard": Config({"difficulty": "hard"}, view=2, scenarios=("watch",), world=FIXTURES / "night-hard" / "world",
                         fixture="night-hard", tape=True, player=NIGHT),
    # A cow without AI sealed in a stone tank of water, its air nearly gone, which drowns, hurt in
    # its own tick till it dies, and its loot (D424); watched, as `stands`.
    "drown": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "drown" / "world", fixture="drown",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Two such cows, one saved with a death loot seed of its own and one with a chicken's death loot
    # table and a seed, each rolling its loot from a random of its seed as it drowns (D429).
    "seeded": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "seeded" / "world", fixture="seeded",
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # A slime of size 2 without AI suffocating in stone, which splits as it's taken out dying into
    # 2 to 4 of size 1 with what it was made of, which suffocate in turn (D430).
    "split": Config({"difficulty": "easy"}, view=2, scenarios=("watch",), world=FIXTURES / "split" / "world", fixture="split",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # The bot burning on magma in armor, which each burn wears but for the netherite chestplate, its
    # boots breaking at the third, on hard (D431). It watches late, `watch-late`, so its burns start
    # at the same game time on both servers, after its levels' randoms are seeded again, taped,
    # and the draws for its armor's unbreaking fall among the chunks' shuffles each tick as they do.
    "magma": Config({"difficulty": "hard"}, view=2, scenarios=("watch-late",), world=FIXTURES / "magma" / "world", fixture="magma",
                    player=MAGMA, keys=MAGMA_KEYS, tape=True,
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # `magma` in frost walker boots, immune to the burn, and in fire protection boots, which take
    # their share of each (D439).
    "magma-frost": Config({"difficulty": "hard"}, view=2, scenarios=("watch-late",), world=FIXTURES / "magma" / "world",
                          fixture="magma", player=MAGMA_FROST, keys=MAGMA_KEYS, tape=True,
                          rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    "magma-fireproof": Config({"difficulty": "hard"}, view=2, scenarios=("watch-late",), world=FIXTURES / "magma" / "world",
                              fixture="magma", player=MAGMA_FIREPROOF, keys=MAGMA_KEYS, tape=True,
                              rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # Penned by the spawn, a cow burning on magma till it dies, a pig lighting redstone ore, the
    # ore's particles drawn from the level's random, and a sheep slowed by slime blocks (D431),
    # taped; without random ticks, which would put the ore out.
    "stepped": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "stepped" / "world", fixture="stepped",
                      player=USE, tape=True,
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # Penned by the spawn, a cow in soul fire, a pig in lava, a chicken on a lit campfire, and a
    # sheep already alight that panics to water, which puts it out (D434), their drops burnt away
    # (D435) and cooked (D436), taped; without random ticks, which would have the lava light what's
    # by it.
    "burning": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "burning" / "world", fixture="burning",
                      player=USE, tape=True,
                      rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # Zombies without AI at noon, on normal, which keeps them: one lit by the sun, one whose
    # leather helmet's worn instead, one whose helmet breaks, one in water and one under stone,
    # which don't burn (D437); taped, without natural spawning.
    "daylight": Config({"difficulty": "normal"}, view=2, scenarios=("watch",), world=FIXTURES / "daylight" / "world",
                       fixture="daylight", tape=True, rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # Four cows without AI with their eyes in stone, glass and farmland, inside its shape and above
    # it, the stone and the farmland's inside suffocating theirs till they die (D425); watched, as
    # `stands`, without random ticks, which would turn the farmland to dirt.
    "walls": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "walls" / "world", fixture="walls",
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # The bot at the bottom of water out of air, drowning, and starving, on hard, which starves to
    # the end (D426); watched, without natural spawning.
    "choke": Config({"difficulty": "hard"}, view=2, scenarios=("watch",), world=FIXTURES / "choke" / "world",
                    fixture="choke", player=CHOKE, keys=HURT_KEYS, rules=(("minecraft:spawn_mobs", nbt.Byte(0)),)),
    # The bot with its eyes in stone, hurt in a wall and healing from its food, on hard, whose healing
    # goes from its first hurt, not from when its client loaded, as peaceful's would (D426); watched,
    # without natural spawning or random ticks, whose places part as vanilla's chunks come in later
    # (D315) and would turn the grass under the stone to dirt on one server only.
    "buried": Config({"difficulty": "hard"}, view=2, scenarios=("watch",), world=FIXTURES / "buried" / "world", fixture="buried",
                     player=BURIED, keys=BURIED_KEYS,
                     rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)))),
    # The same bot dying in the wall, its death told, what it carries and its experience dropped
    # around it, but what's cursed with vanishing, and taken out of its level 20 ticks after
    # (D427); then respawning, as it asks once it's out, on top of the stone at the spawn, where a
    # respawn radius of 0 has both servers' search look, the chunks around forced, so what it
    # dropped is loaded all along (D428).
    "death": Config({"difficulty": "hard"}, view=2, scenarios=("watch",), world=FIXTURES / "death" / "world", fixture="death",
                    player=DEATH, keys=DEATH_KEYS,
                    rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)),
                           ("minecraft:respawn_radius", nbt.Int(0)))),
    # The same on peaceful, watching late, so its hurts start at the same game time on both
    # servers: peaceful heals it and fills its saturation every 20 of the player's own ticks,
    # which its respawn counts from 0 again, `Entity.tickCount`, apart from its connection's
    # (D433).
    "death_peaceful": Config({"difficulty": "peaceful"}, view=2, scenarios=("watch-late",), world=FIXTURES / "death" / "world",
                             fixture="death", player=DEATH, keys=DEATH_KEYS,
                             rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:random_tick_speed", nbt.Int(0)),
                                    ("minecraft:respawn_radius", nbt.Int(0)))),
}
# `duel` with the bot and Mate in one team, which allows no friendly fire and no collisions
# (CAL-164): no hit hurts Mate, the sheep's sweep passes it by, and the step into it pushes
# neither.
CONFIGS["teammates"] = replace(CONFIGS["duel"], saved={"scoreboard": TEAMMATES})
# `duel` with the bot in red and Mate in blue (CAL-164): Mate's death counts for each criteria of
# kills and deaths, its message seen by no one else, and the step into it pushes both, as red's
# players push only each other but the other team's may push them.
CONFIGS["rivals"] = replace(CONFIGS["duel"], saved={"scoreboard": RIVALS})
# The bot on the duel fixture's world with Mate, in one team, typing the commands every player
# may use (CAL-165): `list`, `help`, `me`, `msg`, `tell`, `teammsg`, `trigger` and `random`, with
# their failures, and two it may not.
CONFIGS["talk"] = replace(CONFIGS["duel"], scenarios=("talk",), saved={"scoreboard": TALK})
# `talk` with the bot an operator, which types selectors with options in `say`, `gamemode` and
# `msg` (CAL-165), and runs the functions of FUNCS_PACK (D567). Taped, as weather's lengths,
# blocks' drops and summoned mobs are drawn from the levels' randoms, which line up only once
# seeded again (D316). Where the bot respawns, which its bed sets, and its sleep's ticks are
# compared too (D574), and its portal's cooldown and where it went into the Nether (D577), and
# the ender pearl still flying as it leaves, saved with it (D580).
CONFIGS["select"] = replace(CONFIGS["talk"], scenarios=("select",), ops=("Bot",), tape=True, datapacks={"funcs": FUNCS_PACK},
                            keys=("respawn", "SleepTimer", "PortalCooldown", "entered_nether_pos", "ender_pearls"))
# `talk` with the bot an operator, making and changing boss bars with `bossbar`, with Mate there,
# on a world whose saved boss bars are SAVED_BARS (D606). Taped, as a bar's UUID is drawn from the
# level's random, as `bossbar add` makes it.
CONFIGS["bossbars"] = replace(CONFIGS["talk"], scenarios=("bossbars",), ops=("Bot",), tape=True,
                              saved={"scoreboard": TALK, "custom_boss_events": SAVED_BARS})
# `night`, where monsters spawn, with the bot an operator, in creative mode, throwing thirty ender
# pearls straight down, some of which make endermites where it stands (D583), which then go about.
CONFIGS["mites"] = replace(CONFIGS["night"], scenarios=("mites",), ops=("Bot",))
# The bot's name in `join`, which the whitelist lets in. The default `white-list=true` stays, so
# `stranger`, whom it doesn't list, is turned away.
BOT = "Bot"
# The second player's name, whom a configuration with `mate` lists with the bot (CAL-162).
MATE = "Mate"
# Typed into vanilla's console once it's up, with what it answers. A player joins at a random
# place within `respawn_radius` of the spawn, drawn from a thread-local random, which can't be
# the same on both servers, so it's 0: on the spawn, or the ground there. Calcite reads it from
# the world's game rules, which `prepare` writes (CAL-75).
VANILLA_COMMANDS = [("gamerule respawn_radius 0", "respawn_radius")]
# The data version both servers save, which a game rules file the rig writes is in.
DATA_VERSION = 5023
# The End's dragon fight over, as vanilla saves it once its dragon's killed: its state known, so
# its arena isn't scanned, its dragon killed, as it has been before (D586).
FIGHT_OVER = {"data": {"needs_state_scanning": nbt.Byte(0), "dragon_killed": nbt.Byte(1), "previously_killed": nbt.Byte(1)},
              "DataVersion": nbt.Int(DATA_VERSION)}
# The bot, an operator, through end portals on the end fixture's world, the End's dragon fight over,
# with no mobs spawning (D586): into the End, out of it to the credits the first time, after which
# it respawns keeping all it has, and to where its spawn's set the second. Four chunks about it, so
# the crystal on the spike at 42, 0 is in its sight, those on the two others in chunks at x = 2
# too far off (D589). Taped, as the platform's drops are drawn from the End's random; where it's
# seen the credits is compared, and where its spawn's set, its health, food and effects.
CONFIGS["end"] = Config({"difficulty": "normal"}, view=4, scenarios=("end",), world=FIXTURES / "end" / "world", fixture="end",
                        rules=(("minecraft:spawn_mobs", nbt.Byte(0)), ("minecraft:show_advancement_messages", nbt.Byte(0)),
                               ("minecraft:respawn_radius", nbt.Int(0))),
                        ops=("Bot",), tape=True, player=END_PLAYER,
                        keys=("seenCredits", "respawn", "Health", "foodLevel", "active_effects"),
                        dim_saved={"minecraft/the_end/ender_dragon_fight": FIGHT_OVER})
# `end`'s world with the bot hitting an end crystal it summons in water in the Overworld (D590):
# in survival mode, invulnerable, which the hit doesn't hurt; then in creative mode with an iron
# sword, which breaks it, sweeping. Vanilla's crystal explodes, which Calcite's doesn't yet
# (CAL-182); the water keeps the blocks about it, and creative mode the bot. Then an arrow and an
# ender pearl falling onto another each, which they break, and a splash potion onto another (D591).
CONFIGS["crystals"] = replace(CONFIGS["end"], scenarios=("crystals",))
# `end`'s world with an end gateway the bot sets by its spawn, 2380 ticks old, its age read as it
# ticks, and its cooldown begun at 2400, its block event sent (D592); then the bot through one,
# its exit exact, again, its exit found above the tallest block about it, and through one with
# another on it, whose block event is sent twice (D593); then an item, a pig and an arrow
# through one (D594); then, in the End, an item and the bot through gateways with no
# exit, which make one (D595).
CONFIGS["gateways"] = replace(CONFIGS["end"], scenarios=("gateways",))
# `end`'s world with the bot filling the last frame of an end portal's ring it sets, which opens
# the portal, and again once it's set that frame without its eye (D596); then using an eye in the
# air, looking at the frame and up, which starts its use, as the world has no structures (D597);
# then summoning eyes of ender, which fly on till their life runs out (D598).
CONFIGS["eyes"] = replace(CONFIGS["end"], scenarios=("eyes",))
# `end`'s world with the bot using compasses on a lodestone it sets, which track it, and lodestone
# compasses in its inventory losing their targets as they tick, where the lodestone's broken, out
# of the world and far off, or keeping them, in another dimension or not tracking (D603).
CONFIGS["compass"] = replace(CONFIGS["end"], scenarios=("compass",))
# `end`'s world with the bot hitting ender dragons it summons without AI (D608): one hovering, which
# takes off and then would die, left dying; one in its holding pattern, which an end crystal heals;
# and one with 1 health, which dies as it sits, rising for 200 ticks, its experience given.
CONFIGS["dragon"] = replace(CONFIGS["end"], scenarios=("dragon",))
# `end`'s world with mob griefing off, the bot in creative watching an ender dragon with AI fly
# its holding pattern, land and take off again (D613).
CONFIGS["dragon-flight"] = replace(CONFIGS["end"], scenarios=("dragon-flight",),
                                   rules=CONFIGS["end"].rules + (("minecraft:mob_griefing", nbt.Byte(0)),))
# `dragon-flight`'s scenario with mob griefing on: the dragon breaks the ground it lands on (D614).
CONFIGS["dragon-griefing"] = replace(CONFIGS["end"], scenarios=("dragon-flight",))
# `end`'s world with mob griefing off, the bot in survival with resistance IV for ever on a pillar
# an ender dragon with AI lands by and then charges, its wings and head striking it (D615).
CONFIGS["dragon-charge"] = replace(CONFIGS["end"], scenarios=("dragon-charge",),
                                   rules=CONFIGS["end"].rules + (("minecraft:mob_griefing", nbt.Byte(0)),),
                                   player=dict(END_PLAYER, active_effects=nbt.List(nbt.COMPOUND, [
                                       effect("resistance", -1, 3, ambient=False, show_particles=False, show_icon=False)])))
# `end`'s world with mob griefing off, the bot in survival with resistance IV for ever and full
# health on the ground by the egg's place, where an ender dragon with AI lands, sees it, roars and
# breathes at it twice, its breath's clouds hurting it (D617).
CONFIGS["dragon-breath"] = replace(CONFIGS["dragon-charge"], scenarios=("dragon-breath",),
                                   player=dict(CONFIGS["dragon-charge"].player, Health=nbt.Float(20.0)))
# `dragon-breath`'s world and bot, at the spawn, summoning dragon fireballs that fall onto the
# ground, fly at an armor stand and at it, each leaving its cloud of dragon's breath, and one that
# stays still (D618).
CONFIGS["dragon-fireball"] = replace(CONFIGS["dragon-breath"], scenarios=("dragon-fireball",))
# `dragon-breath`'s world and bot, but with 1000 health, as the clouds of the fireballs it's shot
# at last 600 ticks where it stands, at the spawn by the egg's place, where an ender dragon with AI
# in its holding pattern strafes it, shooting fireballs at it (D619).
CONFIGS["dragon-strafe"] = replace(CONFIGS["dragon-breath"], scenarios=("dragon-strafe",),
                                   player=dict(CONFIGS["dragon-breath"].player, Health=nbt.Float(1000.0),
                                               attributes=nbt.List(nbt.COMPOUND, [{"id": "minecraft:max_health",
                                                                                   "base": nbt.Double(1000.0)}])))
# `dragon-strafe`'s world and bot, but 20 east of the spawn, where it hits an ender dragon with 1
# health it summons landing over it, which then dies on its way to the egg's place (D620).
CONFIGS["dragon-death"] = replace(CONFIGS["dragon-strafe"], scenarios=("dragon-death",),
                                  player=dict(CONFIGS["dragon-strafe"].player,
                                              Pos=nbt.List(nbt.DOUBLE, [nbt.Double(20.5), nbt.Double(-60.0), nbt.Double(0.5)])))
# The plain world, which generates structures, as `terrain` has it, without its entities and with
# no mobs spawning, its spawn at the origin, with the bot, an operator, throwing eyes of ender
# there (D599): each finds the nearest stronghold, `findNearestMapStructure` over the rings, and
# flies toward it till its life runs out, dropped as an item where it survives; the last in
# survival leaves its hand empty, still in use till it lets go; then one in creative mode. The
# plain world, not the round trip's, as its sand falls as an entity, which Calcite's doesn't yet,
# and every entity after has another ID. Taped, as each launch's pitch is drawn from the level's
# random.
CONFIGS["eye-throws"] = replace(CONFIGS["terrain"], scenarios=("throws",), world=PLAIN_WORLD, ops=("Bot",), tape=True)
# The plain world, with the bot, an operator, at its spawn, having `locate structure` find
# structures of each kind of placement, far and near, one the Overworld doesn't place and two
# there are none of (D600): Calcite's search finds the nearest anywhere, vanilla's the nearest of
# the first square of sectors with any, out to 100.
CONFIGS["locate"] = replace(CONFIGS["eye-throws"], scenarios=("locate",), tape=False)
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


def vanilla_argv(a, tape=False, trace=False):
    """The adapter's java and class path, running vanilla's server with its own logging, and the
    rig's agent, which seeds its levels' randoms, with `tape` writes their draws (D311), and with
    `trace` its living entities' states (CAL-159)."""
    if "agent" not in a:
        sys.exit("sessions: the vanilla adapter was built without the agent; run py -I oracle/vanilla-adapter/build.py")
    argv = a["argv"]
    cp = argv[argv.index("-cp") + 1]
    agent = f"-javaagent:{a['agent']}=seed={LEVEL_RANDOM_SEED}" + (f",tape=tape.txt,reseed={RESEED}" if tape else "")
    agent += ",trace=entities.txt" if trace else ""
    # Math.sin and Math.cos as StrictMath's, which Calcite's are, where HotSpot's intrinsics can
    # differ in the last bit: a dropped item's motion turns through them (CAL-148).
    strict = ["-XX:+UnlockDiagnosticVMOptions", "-XX:-UseLibmIntrinsic"]
    return [argv[0], "-Xmx2G", "-Dfile.encoding=UTF-8", *strict, agent, "-cp", cp, "net.minecraft.server.Main", "--nogui"]


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
    if c.player is not None:
        nbt.write(folder / "world" / "players" / "data" / f"{offline_uuid(BOT)}.dat", c.player)
    if c.mate is not None:
        nbt.write(folder / "world" / "players" / "data" / f"{offline_uuid(MATE)}.dat", c.mate)
    for pack, files in (c.datapacks or {}).items():
        for path, text in files.items():
            at = folder / "world" / "datapacks" / pack / path
            at.parent.mkdir(parents=True, exist_ok=True)
            at.write_text(text, encoding="utf-8")
    for name, saved in (c.saved or {}).items():
        nbt.write(folder / "world" / "data" / "minecraft" / f"{name}.dat", saved)
    for path, saved in (c.dim_saved or {}).items():
        namespace, dimension, name = path.split("/")
        nbt.write(folder / "world" / "dimensions" / namespace / dimension / "data" / "minecraft" / f"{name}.dat", saved)
    rules =folder / "world" / "data" / "minecraft" / "game_rules.dat"
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
    if c.mate is not None:
        listed.append({"uuid": offline_uuid(MATE), "name": MATE})
    (folder / "whitelist.json").write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
    if c.ops:
        ops = [{"uuid": offline_uuid(n), "name": n, "level": 4, "bypassesPlayerLimit": False} for n in c.ops]
        (folder / "ops.json").write_text(json.dumps(ops, indent=2) + "\n", encoding="utf-8")
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

    def said(self, text, after=0):
        """Whether the server's said `text` since line `after`, without waiting."""
        with self.seen:
            return any(text in line for line in self.lines[after:])

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
            argv = [str(bot), str(port), str(CONFIGS[config].view), scenario, str(out)]
            if scenario in MATE_SCENARIOS:
                argv.append(str(folder / f"{MATE_SCENARIOS[scenario]}.bin"))
            got = subprocess.run(argv, cwd=CALCITE, capture_output=True, text=True, encoding="utf-8", timeout=BOT_SECONDS)
            if got.returncode != 0:
                sys.exit(f"sessions: the bot failed {scenario} against {side}:\n{got.stdout}{got.stderr}")
            print(f"  {side}: {scenario}: {got.stdout.strip()}", flush=True)
            # Where the bot left by the server's clock, at the same game time on both servers,
            # the server runs PAUSE seconds empty, by its own ticks, once the players who joined
            # have left, and pauses: what it does after the scenario and what it saves are then
            # the same on both, not however long the stop took to come by the wall clock (D506).
            # A bot that left by the wall clock left at other game times on each anyway.
            if " left at game time " in got.stdout and server.said("joined the game", at):
                at = server.wait_for(f"Server empty for {PAUSE} seconds, pausing", at)
    finally:
        server.stop()


def typed(value):
    """A tag with its type, for comparing saved data whose numbers' types matter."""
    if isinstance(value, dict):
        return {k: typed(v) for k, v in value.items()}
    if isinstance(value, list):
        return (type(value).__name__, getattr(value, "kind", None), [typed(v) for v in value])
    return (type(value).__name__, value)


def progress_kept(pairs):
    """A progress file's object as its members, in order, each criterion's time only that it was
    obtained: when is the server's clock as it was awarded."""
    return [(k, True if isinstance(v, str) else v) for k, v in pairs]


def compare_progress(config, name=None):
    """Whether both servers saved the bot's advancements the same (CAL-164),
    `players/advancements/<uuid>.json`: each advancement with progress, in the order they were
    started, each with its criteria obtained, in their `HashMap`'s order, and whether it's done,
    printing what differs. A server that saved none, as when the bot never left, says so."""
    name = name or BOT
    saved = {}
    times = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "players" / "advancements" / f"{offline_uuid(name)}.json"
        if not path.is_file():
            print(f"saved progress differs  [{config}] {side} saved no advancements for {name}")
            return False
        text = path.read_text(encoding="utf-8")
        saved[side] = json.loads(text, object_pairs_hook=progress_kept)
        times[side] = sessiondiff.first_obtained(json.loads(text))
    vanilla, calcite = saved["vanilla"], saved["calcite"]
    same = vanilla == calcite
    # After a `reload`, the order is by when each was first obtained, to the second, which the
    # wall clock decides for those obtained together (D572).
    clocked = (not same and len(vanilla) == len(calcite) and dict(vanilla) == dict(calcite)
               and sessiondiff.ordered_by_the_clock([k for k, _ in vanilla], [k for k, _ in calcite],
                                                    times["vanilla"], times["calcite"]))
    same = same or clocked
    count = sum(1 for k, _ in vanilla if k != "DataVersion")
    who = "" if name == BOT else f" ({name})"
    print(f"saved progress {'PASS' if same else 'differs'}    {count} advancements{who}")
    if clocked:
        print(f"  [{config}] the order differs only where the wall clock's seconds order them")
    if not same:
        kept = dict(calcite)
        for k, v in vanilla:
            if kept.get(k) != v:
                print(f"  [{config}] {k}:\n      vanilla: {v}\n      calcite: {kept.get(k)}")
        for k, _ in calcite:
            if k not in dict(vanilla):
                print(f"  [{config}] {k}: only Calcite saved it")
        if [k for k, _ in vanilla] != [k for k, _ in calcite]:
            print(f"  [{config}] the order differs")
    book = compare_book(config, name)
    stats = compare_stats(config, name)
    return book and stats and same


# The custom stats that count the ticks a player's been in, as `doTick` awards them. A bot joins
# by the wall clock, saying its client's loaded once its chunks are in, which starts its hurts in
# a wall (D431), and some scenarios leave by it too, so these can be a few ticks apart on the two
# servers where all else is the same; they're told, but don't fail the comparison.
TIMED_STATS = {"minecraft:play_time", "minecraft:total_world_time", "minecraft:time_since_death",
               "minecraft:time_since_rest", "minecraft:sneak_time"}


def compare_stats(config, name):
    """Whether both servers saved the player `name`'s statistics the same (CAL-164),
    `players/stats/<uuid>.json`: each type's stats and their counts, and the order each type's
    are in, a `HashMap`'s of their names, printing what differs. The types themselves can go in
    any order, as vanilla groups them in a `HashMap` keyed by identity, in another order each run.
    The time stats, `TIMED_STATS`, need only be saved by both; where their counts differ it's
    told. A server that saved none says so."""
    saved = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "players" / "stats" / f"{offline_uuid(name)}.json"
        if not path.is_file():
            print(f"saved stats    differs  [{config}] {side} saved no statistics for {name}")
            return False
        saved[side] = json.loads(path.read_text(encoding="utf-8"))
    vanilla, calcite = saved["vanilla"], saved["calcite"]
    vs, cs = vanilla.get("stats", {}), calcite.get("stats", {})
    timed = lambda kind, k: kind == "minecraft:custom" and k in TIMED_STATS
    same = set(vs) == set(cs) and vanilla.get("DataVersion") == calcite.get("DataVersion")
    for kind in sorted(set(vs) | set(cs)):
        a, b = vs.get(kind, {}), cs.get(kind, {})
        if set(a) != set(b) or list(a) != list(b):
            same = False
        elif any(a[k] != b[k] for k in a if not timed(kind, k)):
            same = False
    count = sum(len(v) for v in vs.values())
    who = "" if name == BOT else f" ({name})"
    print(f"saved stats    {'PASS' if same else 'differs'}    {count} stats{who}")
    for kind in sorted(set(vs) | set(cs)):
        a, b = vs.get(kind, {}), cs.get(kind, {})
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                late = " (timing)" if timed(kind, k) and k in a and k in b else ""
                print(f"  [{config}] {kind} {k}: vanilla {a.get(k)}, calcite {b.get(k)}{late}")
        if set(a) == set(b) and list(a) != list(b):
            print(f"  [{config}] {kind}: the order differs")
    if vanilla.get("DataVersion") != calcite.get("DataVersion"):
        print(f"  [{config}] DataVersion: vanilla {vanilla.get('DataVersion')}, calcite {calcite.get('DataVersion')}")
    return same


def scoreboard_kept(root):
    """A saved scoreboard as it's compared: its scores sorted, as vanilla keeps each holder's
    by its objectives' identity hashes, in another order each run."""
    data = dict(root.get("data", {}))
    if isinstance(data.get("PlayerScores"), list):
        data["PlayerScores"] = sorted((typed(s) for s in data["PlayerScores"]), key=repr)
    return {k: typed(v) if k != "PlayerScores" else v for k, v in data.items()}, root.get("DataVersion")


def compare_scoreboard(config):
    """Whether both servers saved the scoreboard the same (CAL-164), `data/minecraft/scoreboard.dat`,
    which a new world's is too, empty: its objectives, scores, display slots and teams, each in
    its map's order but the scores, printing what differs."""
    kept = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "data" / "minecraft" / "scoreboard.dat"
        kept[side] = scoreboard_kept(nbt.read(path)) if path.is_file() else None
    same = kept["vanilla"] == kept["calcite"]
    vanilla = kept["vanilla"] or ({}, None)
    print(f"saved scores   {'PASS' if same else 'differs'}    {len(vanilla[0].get('PlayerScores', []))} scores")
    if not same:
        if kept["vanilla"] is None or kept["calcite"] is None:
            print(f"  [{config}] only {'Calcite' if kept['vanilla'] is None else 'vanilla'} saved a scoreboard")
        else:
            (a, av), (b, bv) = kept["vanilla"], kept["calcite"]
            for k in sorted(set(a) | set(b)):
                if a.get(k) != b.get(k):
                    print(f"  [{config}] {k}:\n      vanilla: {a.get(k)}\n      calcite: {b.get(k)}")
            if av != bv:
                print(f"  [{config}] DataVersion: vanilla {av}, calcite {bv}")
    return same


def ordered(value):
    """A tag with its type and each compound's keys in order, for saved data whose order is
    vanilla's to match: a compound as its (key, value) pairs as they were written."""
    if isinstance(value, dict):
        return [(k, ordered(v)) for k, v in value.items()]
    if isinstance(value, list):
        return (type(value).__name__, getattr(value, "kind", None), [ordered(v) for v in value])
    return (type(value).__name__, value)


def storage_kept(world):
    """A world's command storage as it's compared (CAL-165): each namespace's
    `data/<namespace>/command_storage.dat`, by namespace, its root in order."""
    return {path.parent.name: ordered(nbt.read(path))
            for path in sorted((world / "data").glob("*/command_storage.dat"))}


def compare_storage(config):
    """Whether both servers saved command storage the same (CAL-165), each namespace's compounds
    with their keys in the order written, which is that of the maps `CompoundTag.copy` makes,
    printing what differs. Nothing's printed where neither saved any."""
    kept = {side: storage_kept(SESSIONS / config / side / "world") for side in ("vanilla", "calcite")}
    if not kept["vanilla"] and not kept["calcite"]:
        return True
    same = kept["vanilla"] == kept["calcite"]
    print(f"saved storage  {'PASS' if same else 'differs'}    {len(kept['vanilla'])} namespaces")
    if not same:
        for ns in sorted(set(kept["vanilla"]) | set(kept["calcite"])):
            if kept["vanilla"].get(ns) != kept["calcite"].get(ns):
                print(f"  [{config}] {ns}:\n      vanilla: {kept['vanilla'].get(ns)}\n      calcite: {kept['calcite'].get(ns)}")
    return same


def compare_scheduled(config):
    """Whether both servers saved the functions `schedule` has waiting the same (D569),
    `data/minecraft/scheduled_events.dat`, its root with its keys in the order written, printing
    what differs. Nothing's printed where neither saved any."""
    kept = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "data" / "minecraft" / "scheduled_events.dat"
        kept[side] = ordered(nbt.read(path)) if path.is_file() else None
    if kept["vanilla"] is None and kept["calcite"] is None:
        return True
    same = kept["vanilla"] == kept["calcite"]
    events = len(nbt.read(SESSIONS / config / "vanilla" / "world" / "data" / "minecraft" / "scheduled_events.dat")
                 .get("data", {}).get("events", [])) if kept["vanilla"] is not None else 0
    print(f"saved schedule {'PASS' if same else 'differs'}    {events} events")
    if not same:
        print(f"  [{config}] scheduled_events:\n      vanilla: {kept['vanilla']}\n      calcite: {kept['calcite']}")
    return same


def boss_bars_kept(world):
    """A world's boss bars as they're compared (D606): `data/minecraft/custom_boss_events.dat`, its
    root with its keys in the order written, each bar's players sorted, as vanilla saves them
    through `Set.copyOf`, whose order it draws afresh each run; None where there's none."""
    path = world / "data" / "minecraft" / "custom_boss_events.dat"
    if not path.is_file():
        return None
    root = nbt.read(path)
    for bar in root.get("data", {}).values():
        if isinstance(bar, dict) and isinstance(bar.get("Players"), list):
            bar["Players"].sort(key=list)
    return ordered(root)


def compare_boss_bars(config):
    """Whether both servers saved the boss bars the same (D606), printing what differs. Nothing's
    printed where neither saved any."""
    kept = {side: boss_bars_kept(SESSIONS / config / side / "world") for side in ("vanilla", "calcite")}
    if kept["vanilla"] is None and kept["calcite"] is None:
        return True
    same = kept["vanilla"] == kept["calcite"]
    path = SESSIONS / config / "vanilla" / "world" / "data" / "minecraft" / "custom_boss_events.dat"
    bars = len(nbt.read(path).get("data", {})) if path.is_file() else 0
    print(f"saved bars     {'PASS' if same else 'differs'}    {bars} bars")
    if not same:
        print(f"  [{config}] custom_boss_events:\n      vanilla: {kept['vanilla']}\n      calcite: {kept['calcite']}")
    return same


def compare_made_packs(config):
    """Whether both servers wrote the packs `datapack create` made the same (D573): each folder
    in the world's `datapacks` that no configuration put there, by its name, with its
    `pack.mcmeta`, byte for byte, printing what differs. Nothing's printed where neither made
    any."""
    given = set(CONFIGS[config].datapacks or {})
    made = {}
    for side in ("vanilla", "calcite"):
        folder = SESSIONS / config / side / "world" / "datapacks"
        made[side] = {p.name: (p / "pack.mcmeta").read_bytes() if (p / "pack.mcmeta").is_file() else None
                      for p in sorted(folder.iterdir()) if p.is_dir() and p.name not in given} if folder.is_dir() else {}
    if not made["vanilla"] and not made["calcite"]:
        return True
    same = made["vanilla"] == made["calcite"]
    print(f"saved packs    {'PASS' if same else 'differs'}    {len(made['vanilla'])} made")
    if not same:
        for name in sorted(set(made["vanilla"]) | set(made["calcite"])):
            if made["vanilla"].get(name) != made["calcite"].get(name):
                print(f"  [{config}] {name}/pack.mcmeta:\n      vanilla: {made['vanilla'].get(name)!r}\n"
                      f"      calcite: {made['calcite'].get(name)!r}")
    return same


def compare_book(config, name):
    """Whether both servers saved the player `name`'s recipe book the same, their data's
    `recipeBook` (CAL-164): its tabs' settings, and the recipes known and highlighted, each list
    sorted, as vanilla's come from sets hashed by identity, in another order each run."""
    books = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "players" / "data" / f"{offline_uuid(name)}.dat"
        if not path.is_file():
            print(f"saved book     differs  [{config}] {side} saved no data for {name}")
            return False
        book = nbt.read(path).get("recipeBook")
        if isinstance(book, dict):
            book = {k: sorted(v) if isinstance(v, list) else v for k, v in book.items()}
        books[side] = book
    same = books["vanilla"] == books["calcite"]
    known = len((books["vanilla"] or {}).get("recipes", []))
    print(f"saved book     {'PASS' if same else 'differs'}    {known} recipes known")
    if not same:
        print(f"  [{config}] recipeBook:\n      vanilla: {books['vanilla']}\n      calcite: {books['calcite']}")
    return same


def compare_saved(config, name=None):
    """Whether both servers saved the bot's PLAYER_KEYS and the configuration's own keys the same,
    or the player `name`'s, printing what differs."""
    name = name or BOT
    saved = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "players" / "data" / f"{offline_uuid(name)}.dat"
        if not path.is_file():
            print(f"saved player   differs  [{config}] {side} saved no data for {name}")
            return False
        saved[side] = nbt.read(path)
    def kept(side, k):
        value = saved[side].get(k)
        if k in SORTED_KEYS and isinstance(value, list):
            return sorted((typed(v) for v in value), key=repr)
        return typed(value)

    keys = PLAYER_KEYS + CONFIGS[config].keys
    differ = [k for k in keys if kept("vanilla", k) != kept("calcite", k)]
    who = "" if name == BOT else f" ({name})"
    print(f"saved player   {'PASS' if not differ else 'differs'}    {len(keys) - len(differ)} match, {len(differ)} differ{who}")
    for k in differ:
        print(f"  [{config}] {k}:\n      vanilla: {saved['vanilla'].get(k)}\n      calcite: {saved['calcite'].get(k)}")
    return not differ


# The chunks of a fixture's world whose saves are compared, as savediff.py compares them: those
# the fixtures are built in, around the spawn, from -1, -1 to 0, 0 (CAL-145).
FIXTURE_CHUNKS = (-1, -1, 0, 0)


def compare_chunks(config, show):
    """Prints what differs in what both servers saved of a fixture configuration's chunks, each
    block's state, block entity, tick, heightmap and light (CAL-145). Reported, not gated. A
    `show` of 0 shows them all, as it does the packets' (D407)."""
    limit = show if show > 0 else 10 ** 9
    lines = savediff.compare(SESSIONS / config / "vanilla" / "world", SESSIONS / config / "calcite" / "world",
                             FIXTURE_CHUNKS, limit)
    print(f"saved chunks   {'PASS' if not lines else 'differs'}    {len(lines)} differ")
    for line in lines[:limit]:
        print(f"  [{config}] {line[:400]}")


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
    ap.add_argument("--trace", action="store_true", help="write both servers' living entities' states to entities.txt")
    args = ap.parse_args()
    configs = args.config or list(CONFIGS)
    complete = args.config is None and args.scenario is None
    for c in list(configs):
        if CONFIGS[c].fixture is not None and not args.compare_only:
            import fixtures
            fixtures.make(CONFIGS[c].fixture)
        world = CONFIGS[c].world
        if world == PLAIN_WORLD and not (world / "level.dat").is_file() and not args.compare_only:
            import roundtrip
            roundtrip.make_plain()
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
            taped = args.tape or CONFIGS[config].tape
            record(config, "vanilla", vanilla_argv(a, taped, args.trace), bot, scenarios[config])
            record(config, "calcite", [str(server)] + (["--rng-tape", "tape.txt", "--rng-reseed", str(RESEED)] if taped else [])
                   + (["--entity-trace", "entities.txt"] if args.trace else []), bot, scenarios[config])
            if taped:
                print(f"{config}: the levels' draws, vanilla's against Calcite's (D312):", flush=True)
                tapediff.compare(tapediff.read(SESSIONS / config / "vanilla" / "tape.txt"),
                                 tapediff.read(SESSIONS / config / "calcite" / "tape.txt"), args.show, RESEED + 1)
    # What a second player recorded is compared as a scenario of its own (CAL-162).
    for c in configs:
        scenarios[c] = scenarios[c] + [MATE_SCENARIOS[s] for s in scenarios[c] if s in MATE_SCENARIOS]
    files = [SESSIONS / c / side / f"{s}.bin" for c in configs for side in ("vanilla", "calcite") for s in scenarios[c]]
    if not files:
        sys.exit("sessions: no configuration has those scenarios")
    dump(a, files)
    report = sessiondiff.run(SESSIONS, configs, scenarios, CALCITE / "rig" / "differences", show=args.show, complete=complete)
    saved = all([compare_saved(c) for c in configs if CONFIGS[c].player is not None and scenarios[c]]
                + [compare_saved(c, MATE) for c in configs if CONFIGS[c].mate is not None and scenarios[c]]
                + [compare_progress(c) for c in configs if scenarios[c]]
                + [compare_scoreboard(c) for c in configs if scenarios[c]]
                + [compare_storage(c) for c in configs if scenarios[c]]
                + [compare_scheduled(c) for c in configs if scenarios[c]]
                + [compare_boss_bars(c) for c in configs if scenarios[c]]
                + [compare_made_packs(c) for c in configs if scenarios[c]])
    for c in configs:
        if CONFIGS[c].fixture is not None and scenarios[c]:
            compare_chunks(c, args.show)
    return 0 if report.passed and saved else 1


if __name__ == "__main__":
    sys.exit(main())
