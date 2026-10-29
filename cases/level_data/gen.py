"""Writes cases/level_data/generated.json: the `Data` of level.dat files, as SNBT, read and written
back as a server reads its level.dat as it starts and writes it when it saves.

    py -I cases/level_data/gen.py

The cases cover each field 26.3 keeps there, written well and badly: the game type, the name, the
difficulty, commands, the spawn, the time, the server brands, the data versions, the player of a
single-player world, the data packs and the feature flags, and fields of older versions, which
are dropped.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

# The level.dat a 26.3 server wrote for a new flat world.
WORLD = ('{difficulty_settings:{difficulty:"peaceful",hardcore:0b,locked:0b},Time:313L,version_history:[5023],'
         'GameType:0,ServerBrands:["vanilla"],version:19133,LastPlayed:1793298865434L,'
         'spawn:{pos:[I;0,-60,0],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f},'
         'Version:{Snapshot:0b,Series:"main",Id:5023,Name:"26.3"},LevelName:"world",initialized:1b,'
         'WasModded:0b,DataVersion:5023,allowCommands:0b,'
         'DataPacks:{Enabled:["vanilla"],Disabled:["minecart_improvements","redstone_experiments","trade_rebalance"]}}')


def case(name, snbt):
    return {"id": name, "input": {"snbt": snbt}}


def with_field(field):
    return "{" + field + "}"


def fields():
    out = [case("world", WORLD), case("empty", "{}")]
    # The game type, by ID, and what isn't one.
    for name, v in [("survival", "0"), ("creative", "1"), ("adventure", "2"), ("spectator", "3"), ("minus-one", "-1"),
                    ("four", "4"), ("large", "2147483647"), ("byte", "1b"), ("long", "3L"), ("float", "2.9f"),
                    ("negative-double", "-0.5d"), ("string", '"1"'), ("list", "[1]")]:
        out.append(case(f"game-type-{name}", with_field(f"GameType:{v}")))
    # Commands are allowed by default only in creative.
    for name, f in [("creative-default", "GameType:1"), ("creative-off", "GameType:1,allowCommands:0b"),
                    ("survival-on", "allowCommands:1b"), ("int", "allowCommands:5"), ("half", "allowCommands:0.5f"),
                    ("minus-zero", "allowCommands:-0.0d"), ("nan", "allowCommands:NaNd"), ("string", 'allowCommands:"true"'),
                    ("spectator-string", 'GameType:3,allowCommands:"no"')]:
        out.append(case(f"commands-{name}", with_field(f)))
    for name, v in [("plain", '"My World"'), ("unicode", '"Wörld ☃ 🌍"'), ("empty", '""'), ("number", "5"),
                    ("spaces", '"  padded  "')]:
        out.append(case(f"name-{name}", with_field(f"LevelName:{v}")))
    # The difficulty: all three fields, or none.
    for name, v in [("easy", '{difficulty:"easy",hardcore:0b,locked:0b}'), ("hard-hardcore", '{difficulty:"hard",hardcore:1b,locked:1b}'),
                    ("normal-locked", '{difficulty:"normal",hardcore:0b,locked:1b}'),
                    ("unknown", '{difficulty:"extreme",hardcore:1b,locked:0b}'), ("upper", '{difficulty:"HARD",hardcore:1b,locked:0b}'),
                    ("by-id", "{difficulty:3,hardcore:1b,locked:0b}"), ("no-hardcore", '{difficulty:"hard",locked:1b}'),
                    ("no-locked", '{difficulty:"easy",hardcore:1b}'), ("hardcore-int", '{difficulty:"easy",hardcore:7,locked:0b}'),
                    ("hardcore-string", '{difficulty:"easy",hardcore:"true",locked:0b}'),
                    ("extra", '{difficulty:"easy",hardcore:0b,locked:0b,extra:1}'), ("not-compound", '"hard"'),
                    ("list", '[{difficulty:"hard",hardcore:1b,locked:1b}]')]:
        out.append(case(f"difficulty-{name}", with_field(f"difficulty_settings:{v}")))
    # The spawn: a dimension, a position and a facing within range, or the default.
    for name, v in [("nether", '{pos:[I;10,64,-20],pitch:12.5f,dimension:"minecraft:the_nether",yaw:-90.0f}'),
                    ("no-namespace", '{pos:[I;1,2,3],pitch:0.0f,dimension:"the_end",yaw:0.0f}'),
                    ("custom", '{pos:[I;1,2,3],pitch:0.0f,dimension:"mod:mining",yaw:0.0f}'),
                    ("bad-dimension", '{pos:[I;1,2,3],pitch:0.0f,dimension:"Bad Name",yaw:0.0f}'),
                    ("yaw-edge", '{pos:[I;1,2,3],pitch:90.0f,dimension:"minecraft:overworld",yaw:180.0f}'),
                    ("yaw-past", '{pos:[I;1,2,3],pitch:0.0f,dimension:"minecraft:overworld",yaw:180.5f}'),
                    ("pitch-past", '{pos:[I;1,2,3],pitch:-90.01f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("yaw-double", '{pos:[I;1,2,3],pitch:0.0f,dimension:"minecraft:overworld",yaw:45.123456789d}'),
                    ("yaw-int", '{pos:[I;1,2,3],pitch:3,dimension:"minecraft:overworld",yaw:7b}'),
                    ("yaw-nan", '{pos:[I;1,2,3],pitch:0.0f,dimension:"minecraft:overworld",yaw:NaNf}'),
                    ("pos-list", '{pos:[1,2,3],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-long-list", '{pos:[1L,2L,3L],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-bytes", '{pos:[B;1b,2b,3b],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-longs", '{pos:[L;1L,2L,3L],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-floats", '{pos:[1.9f,-2.9f,3.0f],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-two", '{pos:[I;1,2],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-four", '{pos:[I;1,2,3,4],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("pos-mixed", '{pos:[1,"2",3],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("no-pitch", '{pos:[I;1,2,3],dimension:"minecraft:overworld",yaw:0.0f}'),
                    ("no-dimension", '{pos:[I;1,2,3],pitch:0.0f,yaw:0.0f}'),
                    ("extra", '{pos:[I;1,2,3],pitch:0.0f,dimension:"minecraft:overworld",yaw:0.0f,angle:5.0f}'),
                    ("not-compound", "[I;1,2,3]")]:
        out.append(case(f"spawn-{name}", with_field(f"spawn:{v}")))
    for name, v in [("int", "5"), ("double", "12.75d"), ("negative", "-3L"), ("huge-double", "1.0e30d"), ("string", '"5"'),
                    ("max", "9223372036854775807L"), ("float", "7.9f"), ("negative-double", "-7.9d")]:
        out.append(case(f"time-{name}", with_field(f"Time:{v}")))
    for name, f in [("off", "initialized:0b"), ("int", "initialized:2"), ("string", 'initialized:"no"'),
                    ("modded", "WasModded:1b"), ("modded-int", "WasModded:-1")]:
        out.append(case(f"flags-{name}", with_field(f)))
    # Brands keep the order they came in, each once; other types are left out.
    for name, v in [("several", '["vanilla","Paper","fabric","vanilla","Paper"]'), ("mixed", '["vanilla",1,"forge",{a:1}]'),
                    ("empty", "[]"), ("not-list", '"vanilla"'), ("ints", "[I;1,2]"),
                    ("many", "[" + ",".join(f'"brand{i}"' for i in range(20)) + "]")]:
        out.append(case(f"brands-{name}", with_field(f"ServerBrands:{v}")))
    # Removed features are a set, written in Java's HashSet order.
    for name, v in [("one", '["minecraft:bundle"]'), ("several", '["minecraft:bundle","minecraft:winter_drop","update_1_21","x","minecraft:trade_rebalance"]'),
                    ("repeats", '["a","b","a"]'), ("empty", "[]"), ("mixed", '["a",2,"b"]'),
                    ("many", "[" + ",".join(f'"feature_{i}"' for i in range(30)) + "]")]:
        out.append(case(f"removed-{name}", with_field(f"removed_features:{v}")))
    # The data versions the world was saved in, the current one added at the end.
    for name, v in [("current-last", "[4000,5023]"), ("current-first", "[5023,4000]"), ("ints", "[I;3700,4000]"),
                    ("strings", '["x",4000,"y"]'), ("floats", "[4000.9f,-1.5d]"), ("empty", "[]"), ("not-list", "5023"),
                    ("current-twice", "[5023,5023]"), ("longs", "[L;4000L,9000000000L]"), ("bytes", "[B;1b,2b]"),
                    ("compounds", "[{a:1},{b:2}]")]:
        out.append(case(f"history-{name}", with_field(f"version_history:{v}")))
    for name, v in [("ints", "[I;1,2,3,4]"), ("negative", "[I;-1155928273,798308776,-1951547997,-315148217]"),
                    ("short", "[I;1,2,3]"), ("long", "[I;1,2,3,4,5]"), ("list", "[1,2,3,4]"), ("string", '"bb19ef2f-2f95-39a8-8bad-bda3ed373847"'),
                    ("longs", "[L;1L,2L,3L,-4L]"), ("bytes", "[B;1b,2b,3b,4b]"), ("floats", "[1.5f,2.5d,-3.9f,4]"),
                    ("zero", "[I;0,0,0,0]")]:
        out.append(case(f"player-{name}", with_field(f"singleplayer_uuid:{v}")))
    # The data packs and feature flags, each read leniently: any problem gives the default.
    for name, f in [("default", 'DataPacks:{Enabled:["vanilla"],Disabled:[]}'),
                    ("files", 'DataPacks:{Enabled:["vanilla","file/my_pack","bundle"],Disabled:["trade_rebalance"]}'),
                    ("no-disabled", 'DataPacks:{Enabled:["vanilla","file/x"]}'),
                    ("not-strings", 'DataPacks:{Enabled:["vanilla",5],Disabled:[]}'),
                    ("empty-enabled", "DataPacks:{Enabled:[],Disabled:[]}"),
                    ("not-compound", 'DataPacks:["vanilla"]'),
                    ("features-default", 'enabled_features:["minecraft:vanilla"]'),
                    ("features-all", 'enabled_features:["minecraft:vanilla","minecraft:trade_rebalance","minecraft:redstone_experiments","minecraft:minecart_improvements"]'),
                    ("features-short", 'enabled_features:["vanilla","redstone_experiments"]'),
                    ("features-none", "enabled_features:[]"),
                    ("features-unknown", 'enabled_features:["minecraft:vanilla","minecraft:winter_drop"]'),
                    ("features-bad-id", 'enabled_features:["minecraft:vanilla","Not An Id"]'),
                    ("features-not-list", 'enabled_features:"minecraft:vanilla"'),
                    ("features-repeats", 'enabled_features:["minecraft:vanilla","minecraft:vanilla","minecraft:trade_rebalance"]'),
                    ("both", 'DataPacks:{Enabled:["vanilla","trade_rebalance"],Disabled:[]},enabled_features:["minecraft:vanilla","minecraft:trade_rebalance"]')]:
        out.append(case(f"packs-{name}", with_field(f)))
    # What older versions kept here, and what 26.3 writes on its own terms, is replaced or dropped.
    for name, f in [("old-fields", 'raining:1b,thundering:1b,rainTime:100,DayTime:6000L,GameRules:{doDaylightCycle:"false"},'
                                   'WorldGenSettings:{seed:5L},Player:{Health:20.0f},SpawnX:1,SpawnY:2,SpawnZ:3,hardcore:1b,Difficulty:3b,'
                                   'BorderSize:100.0d,WanderingTraderId:[I;1,2,3,4],CustomBossEvents:{}'),
                    ("versions", 'version:19132,DataVersion:3700,Version:{Snapshot:1b,Series:"ccpreview",Id:3700,Name:"1.20"},LastPlayed:5L'),
                    ("unknown", 'calcite:{x:1},extra:"y"')]:
        out.append(case(f"dropped-{name}", with_field(f)))
    return out


def main():
    write_file(HERE / "generated.json", "level_data", "cases/level_data/gen.py", fields())


if __name__ == "__main__":
    main()
