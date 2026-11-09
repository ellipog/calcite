"""Writes cases/stats/generated.json: players' statistics as vanilla's `ServerStatsCounter` keeps
them (CAL-164). Each case is a player's file read as they join, through `STATS_CODEC`, with the
errors it logs for what doesn't read, then stats awarded, sent and saved, so the order each
`HashMap` and `Object2IntOpenHashMap` puts them in shows. The files say 26.3's `DataVersion`,
5023, since vanilla upgrades an older one, which Calcite doesn't.

    py -I cases/stats/gen.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

VERSION = 5023

# The custom stats, `Stats`' in its order.
CUSTOM = [
    "leave_game", "play_time", "total_world_time", "time_since_death", "time_since_rest",
    "sneak_time", "walk_one_cm", "crouch_one_cm", "sprint_one_cm", "walk_on_water_one_cm",
    "fall_one_cm", "climb_one_cm", "fly_one_cm", "walk_under_water_one_cm", "minecart_one_cm",
    "boat_one_cm", "pig_one_cm", "happy_ghast_one_cm", "horse_one_cm", "aviate_one_cm",
    "swim_one_cm", "strider_one_cm", "nautilus_one_cm", "jump", "drop", "damage_dealt",
    "damage_dealt_absorbed", "damage_dealt_resisted", "damage_taken", "damage_blocked_by_shield",
    "damage_absorbed", "damage_resisted", "deaths", "mob_kills", "animals_bred", "player_kills",
    "fish_caught", "talked_to_villager", "traded_with_villager", "eat_cake_slice", "fill_cauldron",
    "use_cauldron", "clean_armor", "clean_banner", "clean_shulker_box", "interact_with_brewingstand",
    "interact_with_beacon", "inspect_dropper", "inspect_hopper", "inspect_dispenser", "play_noteblock",
    "tune_noteblock", "pot_flower", "trigger_trapped_chest", "open_enderchest", "enchant_item",
    "play_record", "interact_with_furnace", "interact_with_crafting_table", "open_chest",
    "sleep_in_bed", "sleep_in_straw_bed", "open_shulker_box", "open_barrel",
    "interact_with_blast_furnace",
    "interact_with_smoker", "interact_with_lectern", "interact_with_campfire",
    "interact_with_cartography_table", "interact_with_loom", "interact_with_stonecutter",
    "bell_ring", "raid_trigger", "raid_win", "interact_with_anvil", "interact_with_grindstone",
    "target_hit", "interact_with_smithing_table",
]


def stats_file(stats, version=VERSION):
    """A stats file's text: `stats` as given, a dict or the raw JSON of its value, then the
    version."""
    body = stats if isinstance(stats, str) else json.dumps(stats)
    v = "" if version is None else f',"DataVersion":{version}'
    return '{"stats":' + body + v + "}"


def case(cases, cid, json_text=None, ops=None):
    inp = {}
    if json_text is not None:
        inp["json"] = json_text
    inp["ops"] = ops if ops is not None else [["mark_all_dirty"], ["send"], ["save"]]
    cases.append({"id": cid, "input": inp})


def reads(cases):
    case(cases, "no-file", None, [["save"], ["send"]])
    case(cases, "empty", stats_file({}))
    case(cases, "no-stats", '{"DataVersion":5023}')
    case(cases, "one", stats_file({"minecraft:custom": {"minecraft:jump": 3}}))
    case(cases, "every-type", stats_file({
        "minecraft:mined": {"minecraft:stone": 12, "minecraft:dirt": 3, "minecraft:oak_log": 7},
        "minecraft:crafted": {"minecraft:oak_planks": 16, "minecraft:stick": 8},
        "minecraft:used": {"minecraft:stone_axe": 5, "minecraft:bread": 2, "minecraft:dirt": 30},
        "minecraft:broken": {"minecraft:golden_pickaxe": 1},
        "minecraft:picked_up": {"minecraft:dirt": 10, "minecraft:oak_log": 5, "minecraft:mutton": 1},
        "minecraft:dropped": {"minecraft:stone": 64, "minecraft:iron_sword": 1},
        "minecraft:killed": {"minecraft:zombie": 1, "minecraft:skeleton": 2, "minecraft:cow": 3},
        "minecraft:killed_by": {"minecraft:creeper": 1, "minecraft:player": 2},
        "minecraft:custom": {"minecraft:play_time": 400, "minecraft:jump": 9, "minecraft:leave_game": 2},
    }))
    # Every custom stat, so the tables grow past their first size.
    case(cases, "every-custom", stats_file({"minecraft:custom": {f"minecraft:{n}": i + 1 for i, n in enumerate(CUSTOM)}}))
    case(cases, "every-custom-reversed", stats_file({"minecraft:custom": {f"minecraft:{n}": i + 1 for i, n in reversed(list(enumerate(CUSTOM)))}}))
    case(cases, "short-ids", stats_file({"custom": {"jump": 4, "minecraft:drop": 2}, "mined": {"stone": 1}}))
    # Counts as Gson's numbers give them as ints, `Number.intValue`, and a boolean as 1 or 0.
    case(cases, "counts", stats_file('{"minecraft:custom":{"minecraft:jump":-7,"minecraft:drop":0,'
                                     '"minecraft:deaths":1.9,"minecraft:mob_kills":1e3,'
                                     '"minecraft:player_kills":2147483648,"minecraft:fish_caught":-2147483649,'
                                     '"minecraft:play_time":99999999999999999999,"minecraft:bell_ring":true,'
                                     '"minecraft:raid_win":false}}'))
    case(cases, "repeated-key", stats_file('{"minecraft:custom":{"minecraft:jump":1,"minecraft:drop":2,"minecraft:jump":5}}'))
    case(cases, "repeated-type", stats_file('{"minecraft:custom":{"minecraft:jump":1},"minecraft:mined":{"minecraft:stone":1},'
                                            '"minecraft:custom":{"minecraft:drop":2}}'))


def errors(cases):
    case(cases, "stats-not-object", stats_file("3"))
    case(cases, "stats-array", stats_file("[1,2]"))
    case(cases, "type-not-object", stats_file('{"minecraft:custom":5,"minecraft:mined":{"minecraft:stone":1}}'))
    case(cases, "unknown-type", stats_file({"minecraft:nope": {"minecraft:stone": 1}, "minecraft:custom": {"minecraft:jump": 2}}))
    case(cases, "bad-type-id", stats_file({"Bad Type": {"minecraft:stone": 1}, "minecraft:custom": {"minecraft:jump": 2}}))
    case(cases, "unknown-value", stats_file({"minecraft:mined": {"minecraft:nope": 3, "minecraft:stone": 2}}))
    case(cases, "bad-value-id", stats_file({"minecraft:mined": {"A:b": 3, "minecraft:stone": 2}}))
    case(cases, "value-of-another-registry", stats_file({"minecraft:mined": {"minecraft:iron_sword": 3},
                                                         "minecraft:killed": {"minecraft:stone": 1}}))
    case(cases, "not-a-number", stats_file('{"minecraft:custom":{"minecraft:jump":"5","minecraft:drop":2}}'))
    case(cases, "null-count", stats_file('{"minecraft:custom":{"minecraft:jump":null,"minecraft:drop":2}}'))
    case(cases, "object-count", stats_file('{"minecraft:custom":{"minecraft:jump":{"a":1},"minecraft:drop":[2]}}'))
    case(cases, "bad-key-and-count", stats_file('{"minecraft:custom":{"minecraft:nope":"x","minecraft:drop":2}}'))
    case(cases, "many-errors", stats_file('{"minecraft:custom":{"minecraft:nope":1,"minecraft:jump":2,"minecraft:drop":"x",'
                                          '"Bad":3},"minecraft:what":{},"minecraft:mined":{"minecraft:stone":1,"minecraft:air":"y",'
                                          '"minecraft:missing":4},"minecraft:killed":7}'))
    case(cases, "all-bad", stats_file('{"minecraft:what":{"minecraft:jump":1},"minecraft:custom":[]}'))


def awards(cases):
    case(cases, "award-new", None, [
        ["award", "minecraft:custom", "minecraft:play_time", 1],
        ["award", "minecraft:custom", "minecraft:total_world_time", 1],
        ["award", "minecraft:custom", "minecraft:time_since_death", 1],
        ["award", "minecraft:custom", "minecraft:time_since_rest", 1],
        ["award", "minecraft:custom", "minecraft:leave_game", 1],
        ["send"], ["send"], ["save"],
    ])
    case(cases, "award-saturates", stats_file({"minecraft:custom": {"minecraft:jump": 2147483600}}), [
        ["award", "minecraft:custom", "minecraft:jump", 100],
        ["award", "minecraft:custom", "minecraft:drop", 2147483647],
        ["award", "minecraft:custom", "minecraft:drop", 1],
        ["send"], ["save"],
    ])
    case(cases, "award-negative", stats_file({"minecraft:custom": {"minecraft:jump": 3}}), [
        ["award", "minecraft:custom", "minecraft:jump", -5],
        ["award", "minecraft:custom", "minecraft:deaths", -2147483648],
        ["award", "minecraft:custom", "minecraft:deaths", -1],
        ["send"], ["save"],
    ])
    every = []
    for i, n in enumerate(CUSTOM):
        every.append(["award", "minecraft:custom", f"minecraft:{n}", i + 1])
    case(cases, "award-every-custom", None, every + [["send"], ["save"]])
    case(cases, "award-mixed", stats_file({"minecraft:custom": {"minecraft:jump": 3, "minecraft:play_time": 10}}), [
        ["award", "minecraft:killed", "minecraft:cow", 1],
        ["award", "minecraft:killed", "minecraft:sheep", 1],
        ["award", "minecraft:killed", "minecraft:cow", 1],
        ["award", "minecraft:custom", "minecraft:mob_kills", 3],
        ["award", "minecraft:used", "minecraft:stone_axe", 5],
        ["award", "minecraft:mined", "minecraft:grass_block", 1],
        ["award", "minecraft:mined", "minecraft:tripwire", 1],
        ["award", "minecraft:picked_up", "minecraft:mutton", 1],
        ["award", "minecraft:dropped", "minecraft:stone", 64],
        ["award", "minecraft:broken", "minecraft:golden_pickaxe", 1],
        ["award", "minecraft:crafted", "minecraft:stick", 4],
        ["award", "minecraft:killed_by", "minecraft:zombie", 1],
        ["send"], ["mark_all_dirty"], ["send"], ["save"],
    ])
    case(cases, "join-then-award", stats_file({"minecraft:custom": {f"minecraft:{n}": 2 for n in CUSTOM[:20]}}), [
        ["mark_all_dirty"],
        ["award", "minecraft:custom", "minecraft:jump", 1],
        ["send"],
        ["award", "minecraft:custom", "minecraft:jump", 1],
        ["award", "minecraft:custom", "minecraft:drop", 1],
        ["send"], ["save"],
    ])


def main():
    cases = []
    reads(cases)
    errors(cases)
    awards(cases)
    write_file(HERE / "generated.json", "stats", "cases/stats/gen.py", cases)


if __name__ == "__main__":
    main()
