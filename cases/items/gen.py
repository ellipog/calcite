"""Writes cases/items/generated.json: item stacks read as vanilla reads them with
`ItemStack.CODEC`, from a data pack's JSON, or from SNBT through `NbtOps`, as a save's are, or
with `ItemStack.OPTIONAL_STREAM_CODEC` from the network, and written to NBT or the network, with
the vanilla data pack's registries and the items' default components bound, as a server has them
(CAL-77, D362, D363, D364). The `from-wire` cases are vanilla's own bytes for the `to-wire` ones,
taken from the goldens once they're recorded, so a new one needs recording twice.

    py -I cases/items/gen.py
"""

import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
sys.path.insert(0, str(HERE.parent / "packs"))
from cases import write_file  # noqa: E402
import gen as packs  # noqa: E402


def cases():
    out = []

    def add(cid, value, to="nbt"):
        out.append({"id": cid, "input": {"from": "json", "value": json.dumps(value), "to": to}})

    # The stack itself: its item, how many, always written, and its components.
    add("plain", {"id": "minecraft:stone"})
    add("short-id", {"id": "stone", "count": 64})
    add("no-id", {"count": 2})
    add("not-object", "minecraft:stone")
    add("air", {"id": "minecraft:air"})
    add("unknown", {"id": "w:nope"})
    add("count-zero", {"id": "minecraft:stone", "count": 0})
    add("count-100", {"id": "minecraft:stone", "count": 100})
    add("count-float", {"id": "minecraft:stone", "count": 2.5})
    add("count-string", {"id": "minecraft:stone", "count": "2"})
    add("empty-components", {"id": "minecraft:stone", "components": {}})
    # A stack no bigger than its item's stack size, with its components.
    add("pearls-16", {"id": "minecraft:ender_pearl", "count": 16})
    add("pearls-17", {"id": "minecraft:ender_pearl", "count": 17})
    add("sword-2", {"id": "minecraft:diamond_sword", "count": 2})
    add("stack-size-patch", {"id": "minecraft:stone", "count": 11, "components": {"max_stack_size": 10}})
    add("stack-size-removed", {"id": "minecraft:stone", "count": 2, "components": {"!max_stack_size": {}}})
    add("stack-size-raised", {"id": "minecraft:ender_pearl", "count": 40, "components": {"max_stack_size": 50}})
    add("damageable-stacks", {"id": "minecraft:stone", "components": {"max_damage": 10}})
    add("damageable-one", {"id": "minecraft:stone", "components": {"max_damage": 10, "max_stack_size": 1}})
    add("sword-stacks", {"id": "minecraft:diamond_sword", "components": {"max_stack_size": 5}})
    add("sword-undamageable", {"id": "minecraft:diamond_sword", "count": 2, "components": {"!max_damage": {}, "max_stack_size": 2}})
    add("sword-damaged", {"id": "minecraft:diamond_sword", "components": {"damage": 30, "enchantments": {"sharpness": 2}}})
    # What a stack holds must fit too: a container's and charged projectiles' stacks, and a
    # bundle's, which weigh no more than one.
    add("container-fits", {"id": "minecraft:shulker_box", "components": {"container": [{"slot": 0, "item": {"id": "minecraft:stone", "count": 64}}]}})
    add("container-too-many", {"id": "minecraft:shulker_box", "components": {"container": [{"slot": 0, "item": {"id": "minecraft:diamond_sword", "count": 2}}]}})
    add("projectiles-too-many", {"id": "minecraft:crossbow", "components": {"charged_projectiles": [{"id": "minecraft:firework_rocket", "count": 99}]}})
    add("bundle-full", {"id": "minecraft:bundle", "components": {"bundle_contents": [{"id": "minecraft:stone", "count": 32}, {"id": "minecraft:ender_pearl", "count": 8}]}})
    add("bundle-over", {"id": "minecraft:bundle", "components": {"bundle_contents": [{"id": "minecraft:stone", "count": 64}, {"id": "minecraft:dirt"}]}})
    add("bundle-nested", {"id": "minecraft:bundle", "components": {"bundle_contents": [
        {"id": "minecraft:red_bundle", "components": {"bundle_contents": [{"id": "minecraft:stone", "count": 60}]}},
        {"id": "minecraft:stone", "count": 0x3}]}})
    add("bundle-nested-over", {"id": "minecraft:bundle", "components": {"bundle_contents": [
        {"id": "minecraft:red_bundle", "components": {"bundle_contents": [{"id": "minecraft:stone", "count": 60}]}},
        {"id": "minecraft:stone", "count": 1}]}})
    add("bundle-hive", {"id": "minecraft:bundle", "components": {"bundle_contents": [
        {"id": "minecraft:bee_nest", "components": {"bees": [{"entity_data": {"id": "minecraft:bee"}, "ticks_in_hive": 0, "min_ticks_in_hive": 0}]}}]}})
    add("bundle-hive-over", {"id": "minecraft:bundle", "components": {"bundle_contents": [
        {"id": "minecraft:bee_nest", "components": {"bees": [{"entity_data": {"id": "minecraft:bee"}, "ticks_in_hive": 0, "min_ticks_in_hive": 0}]}},
        {"id": "minecraft:feather"}]}})
    add("bundle-sword-pair", {"id": "minecraft:bundle", "components": {"bundle_contents": [{"id": "minecraft:diamond_sword", "count": 2}]}})
    # A patch as applying it to the item's default components leaves it: the same as the item's
    # own left out, taking away one the item hasn't left out, and the rest in the order given.
    add("defaults-same", {"id": "minecraft:paper", "components": {
        "max_stack_size": 64, "lore": [], "enchantments": {}, "rarity": "common", "item_model": "minecraft:paper",
        "item_name": {"translate": "item.minecraft.paper"}, "repair_cost": 0, "break_sound": "minecraft:entity.item.break"}})
    add("defaults-other", {"id": "minecraft:paper", "components": {
        "item_model": "minecraft:stone", "item_name": {"translate": "block.minecraft.paper"}, "rarity": "rare", "repair_cost": 1}})
    add("defaults-taken", {"id": "minecraft:apple", "components": {"!food": {}, "!lore": {}, "!damage": {}, "!max_damage": {}, "!consumable": {}}})
    add("defaults-food-same", {"id": "minecraft:apple", "components": {"food": {"nutrition": 4, "saturation": 2.4}}})
    add("defaults-food-other", {"id": "minecraft:apple", "components": {"food": {"nutrition": 5, "saturation": 2.4}}})
    add("defaults-tool-same", {"id": "minecraft:diamond_pickaxe", "count": 1, "components": {"max_damage": 1561, "damage": 0, "max_stack_size": 1}})
    add("defaults-block-name", {"id": "minecraft:stone", "components": {"item_name": {"translate": "block.minecraft.stone"}, "custom_name": "S"}})
    add("defaults-many", {"id": "minecraft:paper", "components": {
        "max_stack_size": 16, "max_damage": 9, "damage": 1, "unbreakable": {}, "repair_cost": 3, "custom_name": "A",
        "item_name": "B", "item_model": "w:m", "lore": ["c"], "rarity": "epic", "enchantment_glint_override": False,
        "glider": {}, "minimum_attack_charge": 0.5, "use_effects": {"can_sprint": True}, "tooltip_style": "w:t",
        "enchantments": {"unbreaking": 1}, "intangible_projectile": {}}})
    # Text that's none of a string, a list and an object, or a list none of whose parts read.
    add("name-number", {"id": "minecraft:paper", "components": {"custom_name": 5}})
    add("name-bool", {"id": "minecraft:paper", "components": {"custom_name": True}})
    add("name-empty-list", {"id": "minecraft:paper", "components": {"custom_name": []}})
    add("name-list-one-bad", {"id": "minecraft:paper", "components": {"custom_name": ["a", 5]}})
    add("name-list-all-bad", {"id": "minecraft:paper", "components": {"custom_name": [5, False]}})
    add("lore-number", {"id": "minecraft:paper", "components": {"lore": [1]}})
    # Every component type, as the packs cases have them, on an item it may be on.
    items = ["minecraft:paper", "minecraft:paper", "minecraft:apple", "minecraft:paper", "minecraft:paper", "minecraft:paper",
             "minecraft:diamond_sword", "minecraft:potion", "minecraft:diamond_pickaxe", "minecraft:paper", "minecraft:paper",
             "minecraft:potion", "minecraft:potion", "minecraft:potion"]
    for i, components in enumerate(packs.ITEM_COMPONENTS):
        item = items[i] if i < len(items) else "minecraft:paper"
        add(f"components-{i}", {"id": item, "components": components})
    for name, components in packs.BAD_COMPONENTS.items():
        add(f"bad-{name}", {"id": "minecraft:paper", "components": components})

    # The same stacks as NBT, as a save has them, read through `NbtOps` (D363).
    def nbt(cid, text, to="nbt"):
        out.append({"id": f"snbt-{cid}", "input": {"from": "snbt", "value": text, "to": to}})

    nbt("plain", '{id:"minecraft:stone"}')
    nbt("short", '{id:stone,count:64}')
    nbt("count-byte", '{id:stone,count:5b}')
    nbt("count-short", '{id:stone,count:7s}')
    nbt("count-long", '{id:stone,count:3L}')
    nbt("count-long-wraps", '{id:stone,count:4294967298L}')
    nbt("count-float", '{id:stone,count:2.9f}')
    nbt("count-double", '{id:stone,count:3.99d}')
    nbt("count-negative-float", '{id:stone,count:-0.5f}')
    nbt("count-huge-float", '{id:stone,count:1.0E10f}')
    nbt("count-string", '{id:stone,count:"2"}')
    nbt("count-array", '{id:stone,count:[I;2]}')
    nbt("count-zero", '{id:stone,count:0b}')
    nbt("id-number", '{id:5}')
    nbt("id-list", '{id:[stone]}')
    nbt("no-id", '{count:2}')
    nbt("not-compound", '"minecraft:stone"')
    nbt("list", '[{id:stone}]')
    nbt("number", '5b')
    nbt("air", '{id:air}')
    nbt("unknown", '{id:"w:nope"}')
    nbt("components-not-compound", '{id:stone,components:[]}')
    nbt("components-string", '{id:stone,components:"x"}')
    # Components with NBT's own types.
    nbt("stack-size-byte", '{id:paper,components:{max_stack_size:10b}}')
    nbt("stack-size-double", '{id:paper,components:{max_stack_size:10.7d}}')
    nbt("stack-size-same", '{id:paper,components:{max_stack_size:64b}}')
    nbt("glint-byte", '{id:paper,components:{enchantment_glint_override:1b}}')
    nbt("glint-zero", '{id:paper,components:{enchantment_glint_override:0b}}')
    nbt("glint-half", '{id:paper,components:{enchantment_glint_override:0.5f}}')
    nbt("glint-int", '{id:paper,components:{enchantment_glint_override:2}}')
    nbt("glint-string", '{id:paper,components:{enchantment_glint_override:"true"}}')
    nbt("glint-list", '{id:paper,components:{enchantment_glint_override:[1b]}}')
    nbt("damage-byte", '{id:diamond_sword,components:{damage:5b}}')
    nbt("damage-negative", '{id:diamond_sword,components:{damage:-1}}')
    nbt("removed", '{id:apple,components:{"!food":{},"!minecraft:consumable":{}, "!lore":{}}}')
    nbt("unknown-component", '{id:paper,components:{"w:x":1}}')
    nbt("transient", '{id:paper,components:{"minecraft:creative_slot_lock":{}}}')
    nbt("custom-data", '{id:paper,components:{custom_data:{a:1b,b:[I;1,2],c:[B;],d:[L;5L],e:[],f:{},g:1.5f,'
                       'h:2.5d,i:"s",j:[1,2],k:3s,l:4L,m:[B;1B,-2B],n:[I;],o:[L;],p:[[1b],[2s]],q:["a",1]}}}')
    nbt("custom-data-list", '{id:paper,components:{custom_data:[1]}}')
    nbt("custom-data-string", '{id:paper,components:{custom_data:"{a:1}"}}')
    nbt("custom-data-bad-string", '{id:paper,components:{custom_data:"{a:"}}')
    nbt("name-string", '{id:paper,components:{custom_name:"Hi"}}')
    nbt("name-compound", '{id:paper,components:{custom_name:{text:"Hi",bold:1b,italic:0b,color:"red"}}}')
    nbt("name-list", '{id:paper,components:{custom_name:["a",{text:"b",underlined:1b}]}}')
    nbt("name-bold-two", '{id:paper,components:{custom_name:{text:"Hi",bold:2b}}}')
    nbt("name-bold-string", '{id:paper,components:{custom_name:{text:"Hi",bold:"true"}}}')
    nbt("name-number", '{id:paper,components:{custom_name:5}}')
    nbt("name-empty-list", '{id:paper,components:{custom_name:[]}}')
    nbt("name-list-one-bad", '{id:paper,components:{custom_name:["a",5]}}')
    nbt("name-list-all-bad", '{id:paper,components:{custom_name:[5,0b]}}')
    nbt("name-bold-big", '{id:paper,components:{custom_name:{text:"Hi",bold:256}}}')
    nbt("name-italic-half", '{id:paper,components:{custom_name:{text:"Hi",italic:0.5f}}}')
    nbt("lore", '{id:paper,components:{lore:["a",{text:"b"},[c,d]]}}')
    nbt("lore-empty", '{id:paper,components:{lore:[]}}')
    nbt("lore-empty-array", '{id:paper,components:{lore:[I;]}}')
    nbt("lore-array", '{id:paper,components:{lore:[I;1]}}')
    nbt("lore-string", '{id:paper,components:{lore:"a"}}')
    nbt("profile-name", '{id:player_head,components:{profile:{name:"Steve"}}}')
    nbt("profile-string", '{id:player_head,components:{profile:"Steve"}}')
    nbt("profile-id", '{id:player_head,components:{profile:{id:[I;1,2,3,4],name:"Al"}}}')
    nbt("profile-id-list", '{id:player_head,components:{profile:{id:[1,2,3,4]}}}')
    nbt("profile-id-bytes", '{id:player_head,components:{profile:{id:[B;1B,2B,3B,4B]}}}')
    nbt("profile-id-longs", '{id:player_head,components:{profile:{id:[L;1L,2L,3L,4L]}}}')
    nbt("profile-id-three", '{id:player_head,components:{profile:{id:[I;1,2,3]}}}')
    nbt("profile-id-five", '{id:player_head,components:{profile:{id:[I;1,2,3,4,5]}}}')
    nbt("profile-id-empty", '{id:player_head,components:{profile:{id:[I;]}}}')
    nbt("profile-id-strings", '{id:player_head,components:{profile:{id:["a","b","c","d"]}}}')
    nbt("profile-id-number", '{id:player_head,components:{profile:{id:5}}}')
    nbt("profile-properties", '{id:player_head,components:{profile:{name:"Al",properties:[{name:"textures",value:"v",signature:"s"}]}}}')
    nbt("dyed-color", '{id:leather_helmet,components:{dyed_color:16711680}}')
    nbt("dyed-color-byte", '{id:leather_helmet,components:{dyed_color:5b}}')
    nbt("enchantments", '{id:diamond_sword,components:{enchantments:{"minecraft:sharpness":2b,unbreaking:3s}}}')
    nbt("enchantments-high", '{id:diamond_sword,components:{enchantments:{sharpness:300}}}')
    nbt("enchantments-list", '{id:diamond_sword,components:{enchantments:[sharpness]}}')
    nbt("container", '{id:shulker_box,components:{container:[{slot:0b,item:{id:stone,count:3b}},{slot:5,item:{id:dirt}}]}}')
    nbt("container-bad-item", '{id:shulker_box,components:{container:[{slot:0b,item:{id:5}}]}}')
    nbt("bundle", '{id:bundle,components:{bundle_contents:[{id:stone,count:32b},{id:ender_pearl,count:8s}]}}')
    nbt("projectiles", '{id:crossbow,components:{charged_projectiles:[{id:arrow,count:1b}]}}')
    nbt("attributes", '{id:diamond_sword,components:{attribute_modifiers:[{type:"attack_damage",id:"w:a",amount:1.5d,'
                      'operation:"add_value",slot:"mainhand"},{type:"armor",id:"w:b",amount:2,operation:"add_value"}]}}')
    nbt("food", '{id:apple,components:{food:{nutrition:4,saturation:2.4f}}}')
    nbt("food-same-double", '{id:apple,components:{food:{nutrition:4b,saturation:2.4d}}}')
    nbt("food-other", '{id:apple,components:{food:{nutrition:5b,saturation:2.4f,can_always_eat:1b}}}')
    nbt("custom-model-data", '{id:paper,components:{custom_model_data:{floats:[1.0f,2.5d,3],flags:[1b,0b,5],strings:["a"],colors:[I;1,2]}}}')
    nbt("firework", '{id:firework_star,components:{firework_explosion:{shape:"star",colors:[I;1,2],fade_colors:[3],has_trail:1b}}}')
    nbt("lodestone", '{id:compass,components:{lodestone_tracker:{target:{dimension:"minecraft:overworld",pos:[I;1,2,3]},tracked:0b}}}')
    nbt("lodestone-pos-list", '{id:compass,components:{lodestone_tracker:{target:{dimension:"minecraft:overworld",pos:[1,2,3]}}}}')
    nbt("lodestone-pos-short", '{id:compass,components:{lodestone_tracker:{target:{dimension:"minecraft:overworld",pos:[I;1,2]}}}}')
    nbt("debug-stick", '{id:debug_stick,components:{debug_stick_state:{"minecraft:oak_log":"axis"}}}')
    nbt("debug-stick-bad", '{id:debug_stick,components:{debug_stick_state:{"minecraft:oak_log":"nope"}}}')
    nbt("map-id", '{id:filled_map,components:{map_id:5b}}')
    nbt("map-color", '{id:filled_map,components:{map_color:16711680L}}')
    nbt("book", '{id:written_book,components:{written_book_content:{title:"T",author:"A",generation:1b,pages:["a",{raw:"b"},'
                '{raw:{text:"c",bold:1b}},{raw:"d",filtered:"e"}],resolved:1b}}}')
    nbt("book-title-filtered", '{id:written_book,components:{written_book_content:{title:{raw:"T",filtered:"U"},author:"A"}}}')
    nbt("writable-book", '{id:writable_book,components:{writable_book_content:{pages:["a",{raw:"b"}]}}}')
    nbt("entity-data", '{id:pig_spawn_egg,components:{entity_data:{id:"minecraft:pig",Health:5.0f}}}')
    nbt("entity-data-no-id", '{id:pig_spawn_egg,components:{entity_data:{Health:5.0f,Tags:[a]}}}')
    nbt("entity-data-id-number", '{id:pig_spawn_egg,components:{entity_data:{id:5}}}')
    nbt("block-entity-data", '{id:chest,components:{block_entity_data:{id:"minecraft:chest",Items:[],Lock:{}}}}')
    nbt("bees", '{id:bee_nest,components:{bees:[{entity_data:{id:"minecraft:bee"},ticks_in_hive:5s,min_ticks_in_hive:6b}]}}')
    nbt("block-state", '{id:oak_log,components:{block_state:{axis:"x"}}}')
    nbt("block-state-number", '{id:oak_log,components:{block_state:{axis:1}}}')
    nbt("unbreakable", '{id:diamond_sword,components:{unbreakable:{}}}')
    nbt("unbreakable-list", '{id:diamond_sword,components:{unbreakable:[]}}')
    nbt("tooltip-display", '{id:paper,components:{tooltip_display:{hide_tooltip:1b,hidden_components:[damage,"minecraft:lore",damage]}}}')
    nbt("can-break", '{id:diamond_pickaxe,components:{can_break:{blocks:"minecraft:stone"}}}')
    nbt("can-break-list", '{id:diamond_pickaxe,components:{can_break:[{blocks:["stone","#minecraft:logs"]}]}}')
    nbt("potion", '{id:potion,components:{potion_contents:{potion:"minecraft:swiftness",custom_color:5b,'
                  'custom_effects:[{id:"minecraft:speed",amplifier:1b,duration:200s,show_icon:0b}]}}}')
    nbt("suspicious-stew", '{id:suspicious_stew,components:{suspicious_stew_effects:[{id:"minecraft:speed",duration:5L}]}}')
    nbt("rarity-number", '{id:paper,components:{rarity:1}}')
    nbt("instrument", '{id:goat_horn,components:{instrument:"minecraft:ponder_goat_horn"}}')
    nbt("trim", '{id:diamond_chestplate,components:{trim:{material:"minecraft:gold",pattern:"minecraft:coast"}}}')
    nbt("banner", '{id:white_banner,components:{banner_patterns:[{pattern:"minecraft:stripe_top",color:"red"}],base_color:"blue"}}')
    nbt("pot", '{id:decorated_pot,components:{pot_decorations:[brick,"minecraft:angler_pottery_sherd"]}}')
    nbt("sign", '{id:oak_sign,components:{block_entity_data:{id:"minecraft:sign",front_text:{messages:["a","b","c","d"]}}}}')
    nbt("note-block-sound", '{id:player_head,components:{note_block_sound:"minecraft:block.note_block.harp"}}')
    nbt("consumable", '{id:paper,components:{consumable:{consume_seconds:2,animation:"eat",has_consume_particles:0b,'
                      'on_consume_effects:[{type:"minecraft:teleport_randomly",diameter:8.5d}]}}}')
    nbt("tool", '{id:paper,components:{tool:{rules:[{blocks:"#minecraft:logs",speed:4,correct_for_drops:1b}],default_mining_speed:2b,damage_per_block:3L}}}')
    nbt("equippable", '{id:paper,components:{equippable:{slot:"head",dispensable:0b,swappable:1b,damage_on_hurt:1b,equip_on_interact:0b}}}')
    nbt("weapon", '{id:paper,components:{weapon:{item_damage_per_attack:2b,disable_blocking_for_seconds:1.5d}}}')
    nbt("ominous", '{id:ominous_bottle,components:{ominous_bottle_amplifier:3b}}')
    nbt("ominous-high", '{id:ominous_bottle,components:{ominous_bottle_amplifier:5}}')
    nbt("item-name", '{id:paper,components:{item_name:{translate:"item.minecraft.paper"},item_model:"minecraft:paper"}}')
    nbt("repair-cost", '{id:paper,components:{repair_cost:0b,max_damage:5s,damage:0L}}')
    nbt("many", '{id:paper,count:3b,components:{max_stack_size:16b,lore:["c"],custom_name:"A",rarity:"epic",'
                'enchantment_glint_override:0b,repair_cost:3,enchantments:{unbreaking:1b},glider:{},tooltip_style:"w:t",'
                'custom_data:{x:1b}}}')
    # Every component type and broken patch the `packs` cases have, written as SNBT. Vanilla
    # caches what it encodes most components to, and writes a value equal to one it wrote before
    # as that one was, so a profile, whose properties are equal in any order, is given a name of
    # its own here, or it would come out in the order the JSON case's did (D363).
    for i, components in enumerate(packs.ITEM_COMPONENTS):
        item = items[i] if i < len(items) else "minecraft:paper"
        if "profile" in components and isinstance(components["profile"], dict):
            components = dict(components, profile=dict(components["profile"], name="Snbt"))
        nbt(f"components-{i}", snbt({"id": item, "components": components}))
    for name, components in packs.BAD_COMPONENTS.items():
        nbt(f"bad-{name}", snbt({"id": "minecraft:paper", "components": components}))

    # Every JSON stack sent over the network with `ItemStack.OPTIONAL_STREAM_CODEC` (D364).
    for c in list(out):
        if c["input"]["from"] == "json" and c["input"]["to"] == "nbt":
            out.append({"id": f"to-wire-{c['id']}", "input": dict(c["input"], to="wire")})

    # Stacks off the network, made by hand: empty ones, air, what doesn't read, and patches that
    # applying them to the item's defaults changes.
    def wire(cid, data):
        blob = base64.b64encode(bytes(data)).decode("ascii")
        for to in ("nbt", "wire"):
            out.append({"id": f"wire-{cid}-{to}", "input": {"from": "wire", "to": to}, "blobs": [blob]})

    stone, paper, apple, sword = varint(1), varint(1145), varint(1007), varint(1050)
    wire("empty", [0])
    wire("negative", varint(-1))
    wire("air", [1, 0, 0, 0])
    wire("air-patch", [1, 0, 1, 0, 1, 5])
    wire("truncated", [1])
    wire("truncated-patch", [1] + stone + [1])
    wire("unknown-item", [1] + varint(99999) + [0, 0])
    wire("unknown-component", [1] + stone + [1, 0] + varint(9999))
    wire("left", [1] + stone + [0, 0, 7])
    wire("plain", [1] + stone + [0, 0])
    wire("count-64", [64] + stone + [0, 0])
    wire("count-100", varint(100) + stone + [0, 0])
    wire("count-big", varint(1000000) + stone + [0, 0])
    wire("stack-size-zero", [1] + stone + [1, 0, 1, 0])
    wire("stack-size-same", [1] + paper + [1, 0, 1, 64])
    wire("stack-size-twice", [1] + stone + [2, 0, 1, 5, 1, 6])
    wire("removed-absent", [1] + stone + [0, 1, 23])
    wire("removed-present", [1] + apple + [0, 1, 23])
    wire("damage-negative", [1] + sword + [1, 0, 3] + varint(-5))
    wire("name", [1] + stone + [1, 0, 6, 8, 0, 2, 72, 105])
    wire("name-bad-nbt", [1] + stone + [1, 0, 6, 99])
    wire("rarity-out-of-range", [1] + paper + [1, 0, 12, 9])
    wire("rarity-epic", [1] + paper + [1, 0, 12, 3])
    wire("lore-too-many", [1] + paper + [1, 0, 11] + varint(257))

    # Vanilla's own bytes for each stack above, read back, from the goldens where they've been
    # recorded, else as the case file had them.
    out.extend(from_vanilla(out))
    return out


def varint(n):
    n &= 0xFFFFFFFF
    data = []
    while True:
        if n < 0x80:
            data.append(n)
            return data
        data.append((n & 0x7F) | 0x80)
        n >>= 7


def from_vanilla(cases):
    """The stacks vanilla sends for the `to-wire` cases, read from the network as `from-wire`
    cases: from the goldens, else kept from the case file as it was."""
    golden = HERE.parents[1] / "golden" / "26.3" / "items.jsonl"
    blobs = {}
    if golden.is_file():
        for line in golden.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["id"].startswith("to-wire-") and record.get("blobs"):
                blobs[record["id"]] = record["blobs"][0]
    old = {}
    previous = HERE / "generated.json"
    if previous.is_file():
        for c in json.loads(previous.read_text(encoding="utf-8"))["cases"]:
            if c["id"].startswith("from-wire-"):
                old[c["id"]] = c
    derived = []
    for c in cases:
        if not c["id"].startswith("to-wire-"):
            continue
        name = c["id"][len("to-wire-"):]
        for to in ("nbt", "wire"):
            cid = f"from-wire-{name}-{to}"
            if c["id"] in blobs:
                derived.append({"id": cid, "input": {"from": "wire", "to": to}, "blobs": [blobs[c["id"]]]})
            elif cid in old:
                derived.append(old[cid])
    return derived


def snbt(value):
    """`value`, JSON, as SNBT: a boolean as a byte, a whole number as an int, or a long past an
    int, another number as a double, and every key quoted."""
    if value is True:
        return "1b"
    if value is False:
        return "0b"
    if isinstance(value, int):
        return str(value) if -2**31 <= value < 2**31 else f"{value}L"
    if isinstance(value, float):
        return f"{value!r}d"
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, list):
        return "[" + ",".join(snbt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{quote(k)}:{snbt(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"no SNBT for {value!r}")


def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    write_file(HERE / "generated.json", "items", "cases/items/gen.py", cases())


if __name__ == "__main__":
    main()
