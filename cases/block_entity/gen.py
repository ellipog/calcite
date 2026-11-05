"""Writes cases/block_entity/generated.json: block entities loaded from data and saved again, as a
structure template's are when it places them, for each type Calcite loads, with data as 26.3's
templates have it and data that's off in each way a codec meets.

    py -I cases/block_entity/gen.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402

BEE = ("{id:\"minecraft:bee\",Age:0,PersistenceRequired:0b,Health:10.0f,HasStung:0b,AbsorptionAmount:0.0f,"
       "HasNectar:0b,attributes:[{base:16.0d,id:\"minecraft:follow_range\",modifiers:[{amount:0.0895d,"
       "id:\"minecraft:random_spawn_bonus\",operation:\"add_multiplied_base\"}]}],AngerTime:0,Invulnerable:0b}")


def item(id_, count=1, components=None):
    parts = [f"id:\"{id_}\"", f"count:{count}"]
    if components:
        parts.append(f"components:{components}")
    return "{" + ",".join(parts) + "}"


def cases():
    out = []

    def add(cid, kind, snbt):
        out.append({"id": cid, "input": {"id": f"minecraft:{kind}", "snbt": snbt}})

    # Beehives: their bees through `Occupant.CODEC`, and the flower's position.
    add("beehive-empty", "beehive", "{}")
    add("beehive-one", "beehive", "{bees:[{entity_data:" + BEE + ",ticks_in_hive:2558,min_ticks_in_hive:600}]}")
    add("beehive-three", "beehive", "{bees:[" + ",".join(
        "{entity_data:" + BEE + f",ticks_in_hive:{t},min_ticks_in_hive:600}}" for t in (2558, 2598, 0)) + "],flower_pos:[I;1,64,-3]}")
    add("beehive-short-id", "beehive", "{bees:[{entity_data:{id:\"bee\",Health:10.0f},ticks_in_hive:5,min_ticks_in_hive:600}]}")
    add("beehive-other-mob", "beehive", "{bees:[{entity_data:{id:\"minecraft:pig\"},ticks_in_hive:5,min_ticks_in_hive:1}]}")
    add("beehive-unknown-mob", "beehive", "{bees:[{entity_data:{id:\"minecraft:dragonfly\"},ticks_in_hive:5,min_ticks_in_hive:1},"
        "{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:6,min_ticks_in_hive:1}]}")
    add("beehive-no-id", "beehive", "{bees:[{entity_data:{Health:10.0f},ticks_in_hive:5,min_ticks_in_hive:1}]}")
    add("beehive-bad-id", "beehive", "{bees:[{entity_data:{id:\"Minecraft:Bee\"},ticks_in_hive:5,min_ticks_in_hive:1}]}")
    add("beehive-number-id", "beehive", "{bees:[{entity_data:{id:5},ticks_in_hive:5,min_ticks_in_hive:1}]}")
    add("beehive-no-min", "beehive", "{bees:[{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:5},"
        "{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:7,min_ticks_in_hive:2}]}")
    add("beehive-number-types", "beehive", "{bees:[{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:5b,min_ticks_in_hive:600L},"
        "{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:3.9d,min_ticks_in_hive:1e12d}]}")
    add("beehive-string-count", "beehive", "{bees:[{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:\"5\",min_ticks_in_hive:1}]}")
    add("beehive-extra-fields", "beehive", "{bees:[{entity_data:{id:\"minecraft:bee\"},ticks_in_hive:5,min_ticks_in_hive:1,TicksInHive:9}],extra:1b}")
    add("beehive-entity-not-compound", "beehive", "{bees:[{entity_data:[1,2],ticks_in_hive:5,min_ticks_in_hive:1}]}")
    add("beehive-bees-not-list", "beehive", "{bees:{a:1}}")
    add("beehive-bees-int-array", "beehive", "{bees:[I;1,2]}")
    add("beehive-old-fields", "beehive", "{Bees:[{EntityData:{id:\"minecraft:bee\"},TicksInHive:5,MinOccupationTicks:600}],FlowerPos:{X:1,Y:2,Z:3}}")
    add("beehive-flower-list", "beehive", "{flower_pos:[1,2,3]}")
    add("beehive-flower-bytes", "beehive", "{flower_pos:[B;1b,2b,3b]}")
    add("beehive-flower-longs", "beehive", "{flower_pos:[L;1L,4294967298L,3L]}")
    add("beehive-flower-short", "beehive", "{flower_pos:[I;1,2]}")
    add("beehive-flower-long", "beehive", "{flower_pos:[I;1,2,3,4]}")
    add("beehive-flower-doubles", "beehive", "{flower_pos:[1.5d,-2.5d,3.0d]}")
    add("beehive-flower-strings", "beehive", "{flower_pos:[\"1\",\"2\",\"3\"]}")
    add("beehive-flower-compound", "beehive", "{flower_pos:{X:1,Y:2,Z:3}}")

    # Lecterns: the book through `ItemStack.CODEC`, the page clamped to its pages.
    sand = ("{\"minecraft:written_book_content\":{pages:[{raw:\"I don't like sand. It's coarse and rough.\"}],"
            "author:\"Pillager 28\",title:{raw:\"Sand\"},resolved:1b}}")
    add("lectern-empty", "lectern", "{}")
    add("lectern-written", "lectern", "{Page:0,Book:" + item("minecraft:written_book", 1, sand) + "}")
    add("lectern-page-past", "lectern", "{Page:5,Book:" + item("minecraft:written_book", 1, sand) + "}")
    add("lectern-page-negative", "lectern", "{Page:-2,Book:" + item("minecraft:written_book", 1, sand) + "}")
    add("lectern-no-page", "lectern", "{Book:" + item("minecraft:written_book", 1, sand) + "}")
    add("lectern-count", "lectern", "{Book:" + item("minecraft:written_book", 3, sand) + "}")
    add("lectern-no-count", "lectern", "{Book:{id:\"minecraft:written_book\",components:" + sand + "}}")
    add("lectern-short-id", "lectern", "{Book:{id:\"written_book\",count:1b,components:" + sand + "}}")
    pages = ("[{raw:\"one\"},{raw:{text:\"two\",bold:1b,color:\"red\"},filtered:\"2\"},\"three\",{text:\"four\",italic:0b},"
             "[\"five\",{text:\"!\"}],{raw:{translate:\"book.title\",with:[\"a\",3]}}]")
    full = ("{\"minecraft:written_book_content\":{title:{raw:\"T\",filtered:\"t\"},author:\"A\",generation:2,"
            f"pages:{pages},resolved:0b}}}}")
    add("lectern-pages", "lectern", "{Page:3,Book:" + item("minecraft:written_book", 1, full) + "}")
    add("lectern-title-string", "lectern", "{Book:" + item("minecraft:written_book", 1,
        "{\"minecraft:written_book_content\":{title:\"Plain\",author:\"A\"}}") + "}")
    add("lectern-generation-zero", "lectern", "{Book:" + item("minecraft:written_book", 1,
        "{\"minecraft:written_book_content\":{title:\"G\",author:\"A\",generation:0,pages:[]}}") + "}")
    add("lectern-writable-empty", "lectern", "{Page:4,Book:" + item("minecraft:writable_book") + "}")
    add("lectern-writable-pages", "lectern", "{Page:1,Book:" + item("minecraft:writable_book", 1,
        "{\"minecraft:writable_book_content\":{pages:[{raw:\"a\"},\"b\",{raw:\"c\",filtered:\"C\"}]}}") + "}")
    add("lectern-writable-empty-content", "lectern", "{Page:0,Book:" + item("minecraft:writable_book", 1,
        "{\"minecraft:writable_book_content\":{pages:[]}}") + "}")
    add("lectern-written-writable", "lectern", "{Page:2,Book:" + item("minecraft:written_book", 1,
        "{\"minecraft:writable_book_content\":{pages:[\"x\",\"y\",\"z\"]}}") + "}")
    add("lectern-written-no-content", "lectern", "{Page:1,Book:" + item("minecraft:written_book") + "}")

    # The other types a template's data reaches, with data as templates have it.
    apple = "{Slot:0b,id:\"minecraft:apple\",count:3}"
    sword = "{Slot:5b,id:\"minecraft:diamond_sword\",count:1,components:{\"minecraft:damage\":5}}"
    add("chest-empty", "chest", "{}")
    add("chest-loot", "chest", "{LootTable:\"minecraft:chests/simple_dungeon\"}")
    add("chest-loot-seed", "chest", "{LootTable:\"minecraft:chests/simple_dungeon\",LootTableSeed:12345L}")
    add("chest-loot-and-items", "chest", "{LootTable:\"minecraft:chests/simple_dungeon\",Items:[" + apple + "]}")
    add("chest-items", "chest", "{Items:[" + apple + "," + sword + "]}")
    add("chest-name", "chest", "{CustomName:\"Loot\",Items:[]}")
    add("trapped-chest-loot", "trapped_chest", "{LootTable:\"minecraft:chests/jungle_temple\"}")
    add("barrel-loot", "barrel", "{LootTable:\"minecraft:chests/village/village_fisher\"}")
    add("dispenser-items", "dispenser", "{Items:[{Slot:4b,id:\"minecraft:arrow\",count:9}]}")
    add("dropper-empty", "dropper", "{}")
    add("hopper-empty", "hopper", "{}")
    add("hopper-cooldown", "hopper", "{TransferCooldown:8,Items:[" + apple + "]}")
    add("shulker-items", "shulker_box", "{Items:[" + apple + "]}")
    add("pot-sherds", "decorated_pot", "{sherds:{back:\"minecraft:brick\",front:\"minecraft:angler_pottery_sherd\"}}")
    add("pot-item", "decorated_pot", "{item:{id:\"minecraft:emerald\",count:2}}")
    add("pot-loot", "decorated_pot", "{LootTable:\"minecraft:pots/trial_chambers/corridor\",LootTableSeed:7L}")
    add("brushable-loot", "brushable_block", "{LootTable:\"minecraft:archaeology/desert_pyramid\",LootTableSeed:3L}")
    add("furnace-empty", "furnace", "{}")
    add("furnace-cooking", "furnace", "{Items:[{Slot:0b,id:\"minecraft:iron_ore\",count:4}],cooking_time_spent:5s,"
        "cooking_total_time:200,lit_time_remaining:100,lit_total_time:1600}")
    add("blast-furnace-empty", "blast_furnace", "{}")
    add("smoker-name", "smoker", "{CustomName:\"Smoky\"}")
    add("campfire-cooking", "campfire", "{Items:[{Slot:0b,id:\"minecraft:beef\",count:1}],CookingTimes:[I;10,0,0,0],"
        "CookingTotalTimes:[I;600,0,0,0]}")
    add("campfire-empty", "campfire", "{}")
    add("brewing-empty", "brewing_stand", "{}")
    add("brewing-fields", "brewing_stand", "{BrewTime:5s,Fuel:3b,Items:[{Slot:3b,id:\"minecraft:nether_wart\",count:1}]}")
    add("comparator-signal", "comparator", "{OutputSignal:5}")
    add("sculk-sensor", "sculk_sensor", "{last_vibration_frequency:3}")
    add("sign-text", "sign", "{front_text:{messages:[\"\",\"Hi\",\"\",\"\"],color:\"black\",has_glowing_text:0b},"
        "back_text:{messages:[\"\",\"\",\"\",\"\"],color:\"black\",has_glowing_text:0b},is_waxed:0b}")
    add("sign-styled", "sign", "{front_text:{messages:[{text:\"A\",color:\"red\"},\"\",\"\",\"\"],color:\"blue\",has_glowing_text:1b},"
        "is_waxed:1b}")
    add("sign-empty", "sign", "{}")
    # A side through `SignText.DIRECT_CODEC`: lines written as the component codec writes them, the
    # first four of more, none of fewer, filtered lines only where they differ, a dye's color (D288).
    add("sign-compound-lines", "sign", "{front_text:{messages:[{text:\"\"},{text:\"Hi\"},\"\",[{text:\"a\"},\"b\"]],color:\"black\",has_glowing_text:0b}}")
    add("sign-filtered-same", "sign", "{front_text:{messages:[\"a\",\"\",\"\",\"\"],filtered_messages:[{text:\"a\"},\"\",\"\",\"\"],color:\"red\",has_glowing_text:2b}}")
    add("sign-filtered-other", "sign", "{front_text:{messages:[\"a\",\"\",\"\",\"\"],filtered_messages:[\"#\",\"\",\"\",\"\"],color:\"red\",has_glowing_text:1b}}")
    add("sign-filtered-bad", "sign", "{front_text:{messages:[\"a\",\"\",\"\",\"\"],filtered_messages:[\"#\"],color:\"red\",has_glowing_text:1b}}")
    add("sign-bad-color", "sign", "{front_text:{messages:[\"a\",\"\",\"\",\"\"],color:\"rainbow\",has_glowing_text:0b}}")
    add("sign-three-lines", "sign", "{front_text:{messages:[\"a\",\"b\",\"c\"],color:\"blue\",has_glowing_text:1b}}")
    add("sign-five-lines", "sign", "{front_text:{messages:[\"a\",\"b\",\"c\",\"d\",\"e\"],color:\"blue\",has_glowing_text:1b}}")
    add("sign-no-color", "hanging_sign", "{back_text:{messages:[\"\",\"\",\"\",\"x\"]}}")
    add("sign-bad-line", "sign", "{front_text:{messages:[\"a\",5,\"c\",\"d\"],color:\"blue\",has_glowing_text:1b}}")
    add("hanging-sign-text", "hanging_sign", "{front_text:{messages:[\"\",\"Inn\",\"\",\"\"],color:\"black\",has_glowing_text:0b}}")
    add("banner-patterns", "banner", "{patterns:[{pattern:\"minecraft:stripe_top\",color:\"red\"},{pattern:\"minecraft:border\",color:\"black\"}]}")
    add("banner-empty-patterns", "banner", "{patterns:[]}")
    add("banner-name", "banner", "{CustomName:{color:\"gold\",translate:\"block.minecraft.ominous_banner\"}}")
    add("skull-profile", "skull", "{profile:{name:\"Steve\"}}")
    add("skull-sound", "skull", "{note_block_sound:\"minecraft:entity.zombie.ambient\"}")
    add("skull-empty", "skull", "{}")
    add("vault-config", "vault", "{config:{loot_table:\"minecraft:chests/trial_chambers/reward\"}}")
    add("vault-ominous", "vault", "{config:{loot_table:\"minecraft:chests/trial_chambers/reward_ominous\",key_item:"
        "{id:\"minecraft:ominous_trial_key\",count:1}}}")
    add("vault-empty", "vault", "{}")
    add("trial-spawner-configs", "trial_spawner", "{normal_config:\"minecraft:trial_chamber/breeze/normal\","
        "ominous_config:\"minecraft:trial_chamber/breeze/ominous\",required_player_range:14,target_cooldown_length:36000}")
    add("trial-spawner-empty", "trial_spawner", "{}")
    add("spawner-template", "mob_spawner", "{MaxNearbyEntities:6s,RequiredPlayerRange:16s,SpawnCount:4s,MaxSpawnDelay:800s,"
        "Delay:20s,SpawnRange:4s,MinSpawnDelay:200s,SpawnData:{entity:{id:\"minecraft:spider\"}},SpawnPotentials:[]}")
    add("spawner-empty", "mob_spawner", "{}")
    add("creaking-heart-empty", "creaking_heart", "{}")
    add("enchanting-table-name", "enchanting_table", "{CustomName:\"Runes\"}")
    add("bell-empty", "bell", "{}")
    add("ender-chest-empty", "ender_chest", "{}")
    add("jukebox-record", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:1},ticks_since_song_started:0L}")
    add("chiseled-bookshelf-books", "chiseled_bookshelf", "{Items:[{Slot:1b,id:\"minecraft:book\",count:1}],last_interacted_slot:1}")
    add("command-block", "command_block", "{Command:\"say hi\",auto:0b,powered:0b,SuccessCount:0,TrackOutput:1b,UpdateLastExecution:1b}")

    # A pot's sherds, each an `ItemStackTemplate`.
    add("pot-sherds-objects", "decorated_pot", "{sherds:{back:{id:\"minecraft:brick\",count:1},left:{id:\"brick\",count:2},"
        "right:\"minecraft:not_an_item\",front:{id:\"minecraft:brick\",count:100}}}")
    add("pot-sherds-air", "decorated_pot", "{sherds:{back:\"minecraft:air\",front:{id:\"minecraft:air\"},left:\"minecraft:brick\"}}")
    add("pot-sherds-empty-components", "decorated_pot", "{sherds:{back:{id:\"minecraft:brick\",components:{}}}}")
    add("pot-sherds-not-compound", "decorated_pot", "{sherds:\"minecraft:brick\"}")
    add("pot-sherds-list", "decorated_pot", "{sherds:[\"minecraft:brick\",\"minecraft:brick\",\"minecraft:brick\",\"minecraft:brick\"]}")
    add("pot-sherds-number", "decorated_pot", "{sherds:{back:5,front:\"minecraft:brick\"}}")

    # Every other type, new and with data as a template might have it.
    for kind in ("jukebox", "piston", "end_portal", "beacon", "structure_block", "command_block", "conduit", "sculk_catalyst",
                 "sculk_shrieker", "chiseled_bookshelf", "shelf", "crafter", "test_block", "test_instance_block", "daylight_detector",
                 "copper_golem_statue", "jigsaw", "end_gateway", "potent_sulfur", "calibrated_sculk_sensor"):
        add(kind.replace("_", "-") + "-new", kind, "{}")
    add("jukebox-playing", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:1},ticks_since_song_started:100L}")
    add("jukebox-not-a-disc", "jukebox", "{RecordItem:{id:\"minecraft:stone\",count:1},ticks_since_song_started:5L}")
    add("jukebox-no-ticks", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_pigstep\",count:1}}")
    add("piston-moving", "piston", "{blockState:{Name:\"minecraft:stone\"},facing:1,progress:0.5f,extending:1b,source:0b}")
    add("beacon-effects", "beacon", "{primary_effect:\"minecraft:speed\",secondary_effect:\"minecraft:regeneration\",CustomName:\"B\",Levels:4}")
    add("structure-block-save", "structure_block", "{name:\"minecraft:test\",author:\"x\",metadata:\"\",posX:0,posY:1,posZ:0,sizeX:5,"
        "sizeY:5,sizeZ:5,rotation:\"NONE\",mirror:\"NONE\",mode:\"SAVE\",ignoreEntities:1b,strict:0b,powered:0b,showair:0b,"
        "showboundingbox:1b,integrity:1.0f,seed:0L}")
    add("structure-block-data", "structure_block", "{mode:\"DATA\",metadata:\"chest\"}")
    add("conduit-target", "conduit", "{Target:[I;1,2,3,4]}")
    add("sculk-catalyst-cursors", "sculk_catalyst", "{cursors:[{pos:[I;1,2,3],charge:5,decay_delay:1,update_delay:0}]}")
    add("sculk-shrieker-warning", "sculk_shrieker", "{warning_level:2}")
    add("chiseled-bookshelf-slot-only", "chiseled_bookshelf", "{last_interacted_slot:3}")
    add("shelf-items", "shelf", "{Items:[{Slot:0b,id:\"minecraft:book\",count:1}],align_items_to_bottom:1b}")
    add("crafter-slots", "crafter", "{disabled_slots:[I;0,4],triggered:1,crafting_ticks_remaining:3}")
    add("crafter-loot", "crafter", "{LootTable:\"minecraft:chests/simple_dungeon\"}")
    add("test-block-message", "test_block", "{mode:\"start\",message:\"hi\",powered:0b}")
    add("end-gateway-exit", "end_gateway", "{Age:100L,exit_portal:[I;1,2,3],ExactTeleport:1b}")
    add("potent-sulfur-countdown", "potent_sulfur", "{countdown:5}")
    add("daylight-detector-data", "daylight_detector", "{x:1}")
    add("enchanting-table-styled-name", "enchanting_table", "{CustomName:{text:\"Runes\",color:\"aqua\"}}")

    # Where each type's fields are read with a default, a range or a check.
    add("piston-state-string", "piston", "{blockState:\"minecraft:stone\",facing:2,progress:1.0f,extending:0b,source:1b}")
    add("piston-state-props", "piston", "{blockState:\"minecraft:piston_head[facing=up,short=true,type=sticky]\",facing:1}")
    add("piston-state-log", "piston", "{blockState:\"minecraft:oak_log[axis=x]\"}")
    add("piston-state-log-default", "piston", "{blockState:\"minecraft:oak_log[axis=y]\"}")
    add("piston-state-empty-props", "piston", "{blockState:\"minecraft:stone[]\"}")
    add("piston-state-log-bare", "piston", "{blockState:\"minecraft:oak_log\"}")
    add("piston-state-short", "piston", "{blockState:\"stone\"}")
    add("piston-state-compound-props", "piston", "{blockState:{Name:\"minecraft:oak_log\",Properties:{axis:\"x\"}}}")
    add("piston-odd", "piston", "{blockState:\"nope\",facing:9,progress:2.5f}")
    add("beacon-not-beacon-effect", "beacon", "{primary_effect:\"minecraft:poison\",secondary_effect:\"speed\"}")
    add("beacon-unknown-effect", "beacon", "{primary_effect:\"minecraft:flying\",Levels:2}")
    add("structure-block-odd", "structure_block", "{name:\"Bad Name!\",posX:100,posY:-60,posZ:3,sizeX:60,sizeY:-2,sizeZ:7,"
        "integrity:2.0f,rotation:\"BAD\",mirror:\"FRONT_BACK\",mode:\"bad\",showair:1b,seed:-4L}")
    add("structure-block-path", "structure_block", "{name:\"ok/path\",mode:\"LOAD\",rotation:\"CLOCKWISE_90\",integrity:-1.0f}")
    add("command-block-last", "command_block", "{Command:\"x\",LastExecution:5L,LastOutput:\"out\",CustomName:\"Cmd\",SuccessCount:2,auto:1b}")
    add("command-block-no-update", "command_block", "{UpdateLastExecution:0b,LastExecution:5L,TrackOutput:0b,LastOutput:\"out\",conditionMet:1b,powered:1b}")
    add("sculk-catalyst-delays", "sculk_catalyst", "{cursors:[{pos:[I;0,0,0],charge:3,decay_delay:3,update_delay:2,facings:[\"up\",\"north\"]}]}")
    add("sculk-catalyst-odd", "sculk_catalyst", "{cursors:[{pos:[I;0,0,0],charge:2000},{charge:1},{pos:[I;5,5,5],charge:-1}]}")
    add("sculk-shrieker-odd", "sculk_shrieker", "{warning_level:9,listener:{event_delay:3,selector:{tick:5L}}}")
    add("chiseled-bookshelf-slot-high", "chiseled_bookshelf", "{last_interacted_slot:10}")
    add("crafter-odd", "crafter", "{disabled_slots:[I;4,0,4,12,-1],triggered:5,crafting_ticks_remaining:-3}")
    add("test-block-odd", "test_block", "{mode:\"bad\",message:5}")
    add("test-block-log", "test_block", "{mode:\"log\"}")
    add("end-gateway-odd", "end_gateway", "{Age:-5L,ExactTeleport:0b,exit_portal:[I;1,2]}")
    add("potent-sulfur-string", "potent_sulfur", "{countdown:\"x\"}")
    add("jigsaw-template", "jigsaw", "{name:\"minecraft:bottom\",target:\"minecraft:top\",pool:\"minecraft:village/plains/houses\","
        "final_state:\"minecraft:air\",joint:\"rollable\",placement_priority:2,selection_priority:-1}")
    add("jigsaw-odd", "jigsaw", "{name:\"Bad!\",target:\"top\",joint:\"sideways\",final_state:\"minecraft:stone[\"}")
    add("conduit-long-target", "conduit", "{Target:[I;1,2,3,4,5]}")
    add("conduit-string-target", "conduit", "{Target:\"x\"}")
    add("sculk-sensor-listener-no-delay", "sculk_sensor", "{listener:{selector:{tick:5L}}}")
    add("sculk-sensor-listener-negative", "sculk_sensor", "{listener:{event_delay:-1,selector:{tick:0L}}}")
    add("sculk-sensor-listener-no-selector", "sculk_sensor", "{listener:{event_delay:2}}")
    add("sculk-sensor-listener-not-compound", "calibrated_sculk_sensor", "{listener:5,last_vibration_frequency:4}")
    # `getIntOr` rounds a float down, `getBooleanOr` takes a number's low byte, and a codec's
    # `Codec.INT` cuts toward zero.
    add("hopper-float-cooldown", "hopper", "{TransferCooldown:-2.5f}")
    add("comparator-double-signal", "comparator", "{OutputSignal:3.9d}")
    add("sign-waxed-256", "sign", "{is_waxed:256,allow_op_features:512}")
    add("sign-waxed-half", "sign", "{is_waxed:0.5f}")
    add("trial-spawner-float", "trial_spawner", "{total_mobs_spawned:-2.7f,required_player_range:3.9d,cooldown_ends_at:-1.5d}")
    add("lectern-float-page", "lectern", "{Page:-0.5f,Book:" + item("minecraft:written_book", 1, sand) + "}")
    # A count that doesn't read is the default, 1, the partial value of its optional field.
    add("lectern-bad-count", "lectern", "{Book:{id:\"minecraft:written_book\",count:200,components:" + sand + "}}")
    add("lectern-string-count", "lectern", "{Book:{id:\"minecraft:written_book\",count:\"x\",components:" + sand + "}}")
    add("pot-sherds-bad-counts", "decorated_pot", "{sherds:{back:{id:\"minecraft:brick\",count:\"x\"},left:{id:\"minecraft:brick\",count:0},"
        "front:{id:\"minecraft:brick\",components:5}}}")
    add("jukebox-bad-count", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:0},ticks_since_song_started:7L}")
    add("jukebox-components", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:1,components:{}},ticks_since_song_started:3}")

    # Items through vanilla's codecs (D367): a container's as `ContainerHelper` loads them into its
    # slots and saves them in their order, each `ItemStackWithSlot.CODEC`, and each other item
    # `ItemStack.CODEC` or `ItemStackTemplate.CODEC`, with its components.
    named = "{\"minecraft:custom_name\":\"Named\"}"
    add("chest-items-unsorted", "chest", "{Items:[{Slot:5b,id:\"minecraft:stone\",count:2},{Slot:0b,id:\"minecraft:dirt\",count:1},"
        "{Slot:3b,id:\"minecraft:apple\",count:7}]}")
    add("chest-items-same-slot", "chest", "{Items:[{Slot:2b,id:\"minecraft:stone\",count:2},{Slot:2b,id:\"minecraft:dirt\",count:5}]}")
    add("chest-items-out-of-range", "chest", "{Items:[{Slot:27b,id:\"minecraft:stone\",count:1},{Slot:-1b,id:\"minecraft:dirt\",count:1},"
        "{Slot:26b,id:\"minecraft:apple\",count:1},{Slot:283,id:\"minecraft:bread\",count:1},{Slot:1.9f,id:\"minecraft:egg\",count:1}]}")
    add("chest-items-no-slot", "chest", "{Items:[{id:\"minecraft:stone\",count:3},{Slot:4b,id:\"minecraft:dirt\",count:1}]}")
    add("chest-items-bad", "chest", "{Items:[{Slot:0b,id:\"minecraft:air\",count:1},{Slot:1b,id:\"minecraft:not_an_item\",count:1},5,"
        "{Slot:\"x\",id:\"minecraft:stone\",count:2},{Slot:3b,id:\"minecraft:dirt\",count:0},{Slot:4b,id:\"minecraft:apple\",count:200},"
        "{Slot:5b,id:\"stick\",count:1b},{Slot:6b,count:1},{Slot:7b,id:\"minecraft:egg\",count:3,components:5}]}")
    add("chest-items-components", "chest", "{Items:[{Slot:0b,id:\"minecraft:diamond_sword\",count:1,components:{\"minecraft:damage\":0}},"
        "{Slot:1b,id:\"minecraft:diamond_sword\",count:1,components:{\"minecraft:damage\":7,\"minecraft:custom_name\":{text:\"Edge\",color:\"red\"}}},"
        "{Slot:2b,id:\"minecraft:stone\",count:1,components:{\"!minecraft:max_stack_size\":{},\"!minecraft:food\":{}}},"
        "{Slot:3b,id:\"minecraft:apple\",count:1,components:{\"minecraft:max_stack_size\":64,\"minecraft:rarity\":\"epic\"}},"
        "{Slot:4b,id:\"minecraft:stone\",count:1,components:{\"minecraft:not_a_component\":1}}]}")
    add("chest-items-nested", "chest", "{Items:[{Slot:0b,id:\"minecraft:shulker_box\",count:1,components:{\"minecraft:container\":["
        "{slot:0,item:{id:\"minecraft:diamond_sword\",count:1,components:{\"minecraft:damage\":0,\"minecraft:custom_name\":\"In\"}}},"
        "{slot:3,item:{id:\"minecraft:apple\",count:2,components:{\"minecraft:max_stack_size\":64}}}]}},"
        "{Slot:1b,id:\"minecraft:bundle\",count:1,components:{\"minecraft:bundle_contents\":[{id:\"minecraft:stone\",count:3,"
        "components:{\"minecraft:rarity\":\"common\"}}]}}]}")
    add("chest-items-not-list", "chest", "{Items:{Slot:0b,id:\"minecraft:stone\",count:1}}")
    add("chest-items-list-of-lists", "chest", "{Items:[[{Slot:0b,id:\"minecraft:stone\",count:1}]]}")
    add("trapped-chest-items", "trapped_chest", "{Items:[{Slot:9b,id:\"minecraft:gold_ingot\",count:4}]}")
    add("barrel-items", "barrel", "{Items:[{Slot:26b,id:\"minecraft:cod\",count:16},{Slot:1b,id:\"minecraft:salmon\",count:2}]}")
    add("shulker-empty", "shulker_box", "{}")
    add("shulker-no-items", "shulker_box", "{Items:[]}")
    add("shulker-bad-items", "shulker_box", "{Items:[{Slot:30b,id:\"minecraft:stone\",count:1},{Slot:0b,id:\"minecraft:air\",count:1}]}")
    add("shulker-loot", "shulker_box", "{LootTable:\"minecraft:chests/end_city_treasure\"}")
    add("hopper-slot-past", "hopper", "{Items:[{Slot:4b,id:\"minecraft:stone\",count:1},{Slot:5b,id:\"minecraft:dirt\",count:1}]}")
    add("dispenser-slot-past", "dispenser", "{Items:[{Slot:8b,id:\"minecraft:arrow\",count:1},{Slot:9b,id:\"minecraft:arrow\",count:2}]}")
    add("dropper-items", "dropper", "{Items:[{Slot:3b,id:\"minecraft:stone\",count:5},{Slot:0b,id:\"minecraft:dirt\",count:1}]}")
    add("crafter-items", "crafter", "{Items:[{Slot:8b,id:\"minecraft:stick\",count:1},{Slot:9b,id:\"minecraft:stick\",count:1}]}")
    add("furnace-slot-past", "furnace", "{Items:[{Slot:2b,id:\"minecraft:iron_ingot\",count:3},{Slot:3b,id:\"minecraft:coal\",count:1}]}")
    add("smoker-items", "smoker", "{Items:[{Slot:1b,id:\"minecraft:coal\",count:2},{Slot:0b,id:\"minecraft:beef\",count:1}]}")
    add("campfire-slot-past", "campfire", "{Items:[{Slot:3b,id:\"minecraft:beef\",count:1},{Slot:4b,id:\"minecraft:cod\",count:1}]}")
    add("brewing-slot-past", "brewing_stand", "{Items:[{Slot:4b,id:\"minecraft:blaze_powder\",count:1},{Slot:5b,id:\"minecraft:potion\",count:1}]}")
    add("chiseled-bookshelf-slot-past", "chiseled_bookshelf", "{Items:[{Slot:5b,id:\"minecraft:book\",count:1},{Slot:6b,id:\"minecraft:book\",count:1}]}")
    add("shelf-slot-past", "shelf", "{Items:[{Slot:2b,id:\"minecraft:book\",count:1},{Slot:3b,id:\"minecraft:book\",count:1}]}")
    add("chiseled-bookshelf-named-book", "chiseled_bookshelf", "{Items:[{Slot:0b,id:\"minecraft:enchanted_book\",count:1,"
        "components:{\"minecraft:stored_enchantments\":{\"minecraft:mending\":1}}}]}")
    add("pot-item-components", "decorated_pot", "{item:{id:\"minecraft:emerald\",count:3,components:" + named + "}}")
    add("pot-item-air", "decorated_pot", "{item:{id:\"minecraft:air\",count:1}}")
    add("pot-item-bad-count", "decorated_pot", "{item:{id:\"minecraft:emerald\",count:500}}")
    add("pot-item-not-compound", "decorated_pot", "{item:\"minecraft:emerald\"}")
    add("pot-loot-and-item", "decorated_pot", "{LootTable:\"minecraft:pots/trial_chambers/corridor\",item:{id:\"minecraft:emerald\",count:1}}")
    add("pot-sherds-components", "decorated_pot", "{sherds:{back:{id:\"minecraft:brick\",components:" + named + "},"
        "front:{id:\"minecraft:angler_pottery_sherd\",count:1,components:{\"!minecraft:rarity\":{}}}}}")
    add("brushable-item", "brushable_block", "{item:{id:\"minecraft:emerald\",count:1}}")
    add("brushable-item-components", "brushable_block", "{item:{id:\"minecraft:diamond\",count:2,components:" + named + "},hit_direction:2}")
    add("brushable-loot-and-item", "brushable_block", "{LootTable:\"minecraft:archaeology/desert_pyramid\",item:{id:\"minecraft:emerald\",count:1}}")
    add("jukebox-stone-with-song", "jukebox", "{RecordItem:{id:\"minecraft:stone\",count:1,components:{\"minecraft:jukebox_playable\":"
        "\"minecraft:cat\"}},ticks_since_song_started:40L}")
    add("jukebox-disc-without-song", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:1,components:{\"!minecraft:jukebox_playable\":{}}},"
        "ticks_since_song_started:40L}")
    add("jukebox-disc-named", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_13\",count:1,components:" + named + "},ticks_since_song_started:9L}")
    add("jukebox-two-discs", "jukebox", "{RecordItem:{id:\"minecraft:music_disc_cat\",count:2},ticks_since_song_started:5L}")
    add("lectern-stone", "lectern", "{Page:3,Book:{id:\"minecraft:stone\",count:1}}")
    add("lectern-not-an-item", "lectern", "{Page:3,Book:{id:\"minecraft:not_an_item\",count:1}}")
    add("lectern-book-named", "lectern", "{Page:0,Book:" + item("minecraft:written_book", 1,
        "{\"minecraft:written_book_content\":{title:\"T\",author:\"A\",pages:[\"a\",\"b\"]},\"minecraft:custom_name\":\"Mine\"}") + "}")
    add("lectern-writable-default", "lectern", "{Page:2,Book:" + item("minecraft:writable_book", 1,
        "{\"minecraft:writable_book_content\":{}}") + "}")
    add("lectern-stone-with-pages", "lectern", "{Page:1,Book:" + item("minecraft:stone", 1,
        "{\"minecraft:writable_book_content\":{pages:[\"x\",\"y\",\"z\"]}}") + "}")
    add("vault-key-components", "vault", "{config:{key_item:{id:\"minecraft:trial_key\",count:1,components:" + named + "}}}")
    add("vault-key-air", "vault", "{config:{key_item:{id:\"minecraft:air\",count:1}}}")
    add("vault-key-bad-count", "vault", "{config:{key_item:{id:\"minecraft:trial_key\",count:500}}}")
    return out


def main():
    write_file(HERE / "generated.json", "block_entity", "cases/block_entity/gen.py", cases())


if __name__ == "__main__":
    main()
