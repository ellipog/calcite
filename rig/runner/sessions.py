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
# a fixed number of game ticks, for a world that never goes quiet; `creative`, where it sets slots
# of its inventory as the creative menu does; `clicks`, where it clicks in its inventory menu;
# `dig` and `dig-creative`, where it digs blocks; `place` and `place-creative`, where it places
# them; `use`, where it uses them; `use-items` and `use-books`, where it uses items on them; and
# `use-containers`, where it opens containers and clicks in them; `items`, where it drops,
# throws and picks up items; `items-saved`, where it picks up items saved in the world; and
# `orbs`, where it breaks blocks that give experience (src/rig/session.calx).
OTHER_SCENARIOS = ["watch", "creative", "clicks", "dig", "dig-creative", "place", "place-creative", "use", "use-items",
                   "use-books", "use-containers", "items", "items-saved", "orbs"]
# What the bot's saved data is compared by, after a configuration that gives it some: what's in
# its inventory and on it, the slot it holds and its game mode (CAL-135), and its attributes,
# whose order is that of vanilla's map of them, by their identity hashes, so they're compared by
# their IDs (D375); and its ender chest's items (CAL-144).
PLAYER_KEYS = ("Inventory", "equipment", "SelectedItemSlot", "playerGameType", "attributes", "EnderItems")
SORTED_KEYS = {"attributes": "id"}
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
    # The bot's saved data, which both servers read as it joins, or none for a player new to the
    # world.
    player: dict | None = None
    # The names of the players in ops.json, at level 4, none of them the bot (D376).
    ops: tuple = ()
    # Whether it's taped whether or not --tape says so, its levels' randoms seeded again at RESEED,
    # as what it compares lines up only from there, natural spawning's mobs (CAL-156).
    tape: bool = False


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
# The bot's data in `night`: in creative mode at the spawn, so the monsters that spawn don't make
# for it (CAL-156).
NIGHT = {
    "DataVersion": nbt.Int(5023),
    "Pos": nbt.List(nbt.DOUBLE, [nbt.Double(0.5), nbt.Double(-63.0), nbt.Double(0.5)]),
    "Rotation": nbt.List(nbt.FLOAT, [nbt.Float(0.0), nbt.Float(0.0)]),
    "Dimension": "minecraft:overworld",
    "playerGameType": nbt.Int(1),
}
# The use_items rules: the dig configurations', and no natural regeneration, so the bot's food stays
# where the cake it eats puts it (CAL-142).
USE_ITEMS_RULES = DIG_RULES + (("minecraft:natural_health_regeneration", nbt.Byte(0)),)


CONFIGS = {
    "compressed": Config({}),
    # The bot joins with a saved inventory, which each server sends with the inventory menu's
    # slots, then joins again and sets creative slots; what each saves of it is compared (CAL-135).
    "inventory": Config({}, scenarios=("join", "creative"), player=INVENTORY),
    # The bot, in survival with the same inventory, clicks in its inventory menu; what each server
    # sends back, and what each saves of it, is compared (CAL-136).
    "clicks": Config({}, scenarios=("clicks",), player=CLICKS),
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
    "farm": Config({}, view=2, scenarios=("watch",), world=FIXTURES / "farm" / "world", fixture="farm",
                   tape=True),
    # Plains (CAL-156): as `farm`, on the plains fixture's grass, where horses and donkeys spawn
    # with the farm animals; and three without AI that graze.
    "plains": Config({}, view=3, scenarios=("watch",), world=FIXTURES / "plains" / "world", fixture="plains",
                     tape=True),
    # Monsters (CAL-156): as `farm`, from dusk on the night fixture's plains, on normal, where
    # monsters spawn every tick, zombie horses among them, finalized by the difficulty where each
    # stands; the bot in creative, which they don't make for; and four without AI, a zombie, a
    # skeleton with its bow, a creeper and a spider. Without mob griefing, as an enderman takes a
    # block by its AI, which Calcite doesn't run yet, and one carrying a block stays, so it isn't
    # counted against the monsters' cap and vanilla's would spawn again where Calcite's are at it.
    "night": Config({"difficulty": "normal"}, view=2, scenarios=("watch",), world=FIXTURES / "night" / "world",
                    fixture="night", tape=True, player=NIGHT, rules=(("minecraft:mob_griefing", nbt.Byte(0)),)),
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


def typed(value):
    """A tag with its type, for comparing saved data whose numbers' types matter."""
    if isinstance(value, dict):
        return {k: typed(v) for k, v in value.items()}
    if isinstance(value, list):
        return (type(value).__name__, getattr(value, "kind", None), [typed(v) for v in value])
    return (type(value).__name__, value)


def compare_saved(config):
    """Whether both servers saved the bot's PLAYER_KEYS the same, printing what differs."""
    saved = {}
    for side in ("vanilla", "calcite"):
        path = SESSIONS / config / side / "world" / "players" / "data" / f"{offline_uuid(BOT)}.dat"
        if not path.is_file():
            print(f"saved player   differs  [{config}] {side} saved no data for the bot")
            return False
        saved[side] = nbt.read(path)
    def kept(side, k):
        value = saved[side].get(k)
        if k in SORTED_KEYS and isinstance(value, list):
            return sorted((typed(v) for v in value), key=repr)
        return typed(value)

    differ = [k for k in PLAYER_KEYS if kept("vanilla", k) != kept("calcite", k)]
    print(f"saved player   {'PASS' if not differ else 'differs'}    {len(PLAYER_KEYS) - len(differ)} match, {len(differ)} differ")
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
            taped = args.tape or CONFIGS[config].tape
            record(config, "vanilla", vanilla_argv(a, taped), bot, scenarios[config])
            record(config, "calcite", [str(server)] + (["--rng-tape", "tape.txt", "--rng-reseed", str(RESEED)] if taped else []), bot, scenarios[config])
            if taped:
                print(f"{config}: the levels' draws, vanilla's against Calcite's (D312):", flush=True)
                tapediff.compare(tapediff.read(SESSIONS / config / "vanilla" / "tape.txt"),
                                 tapediff.read(SESSIONS / config / "calcite" / "tape.txt"), args.show, RESEED + 1)
    files = [SESSIONS / c / side / f"{s}.bin" for c in configs for side in ("vanilla", "calcite") for s in scenarios[c]]
    if not files:
        sys.exit("sessions: no configuration has those scenarios")
    dump(a, files)
    report = sessiondiff.run(SESSIONS, configs, scenarios, CALCITE / "rig" / "differences", show=args.show, complete=complete)
    saved = all([compare_saved(c) for c in configs if CONFIGS[c].player is not None and scenarios[c]])
    for c in configs:
        if CONFIGS[c].fixture is not None and scenarios[c]:
            compare_chunks(c, args.show)
    return 0 if report.passed and saved else 1


if __name__ == "__main__":
    sys.exit(main())
