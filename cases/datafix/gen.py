"""Writes cases/datafix/generated.json: structure templates as older games saved them, which vanilla's
data fixer upgrades to 26.3's as they load (CAL-102). Each is our own small template, written to
reach one fix or a few, at data versions on both sides of each.

    py -I cases/datafix/gen.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import write_file  # noqa: E402


def q(s):
    """A string as SNBT, in double quotes."""
    return json.dumps(s, ensure_ascii=False)


def template(version, palette="[{Name:\"minecraft:stone\"}]", blocks="[{pos:[0,0,0],state:0}]", entities="[]", extra=""):
    v = f"DataVersion:{version}," if version is not None else ""
    return f"{{{v}size:[1,1,1],palette:{palette},blocks:{blocks},entities:{entities}{extra}}}"


def block(nbt, state=0):
    return f"{{pos:[0,0,0],state:{state},nbt:{nbt}}}"


def entity(nbt):
    return f"[{{pos:[0.5d,0.0d,0.5d],blockPos:[0,0,0],nbt:{nbt}}}]"


def case(cases, cid, snbt, version=None):
    inp = {"type": "structure", "snbt": snbt}
    if version is not None:
        inp["version"] = str(version)
    cases.append({"id": cid, "input": inp})


def palettes(cases):
    states = "[" + ",".join([
        "{Name:\"minecraft:grass\"}",
        "{Name:\"grass\"}",
        "{Name:\"minecraft:chain\",Properties:{axis:\"y\",waterlogged:\"false\"}}",
        "{Name:\"minecraft:cave_vines_head\",Properties:{age:\"3\",berries:\"true\"}}",
        "{Name:\"minecraft:cave_vines_body\"}",
        "{Name:\"minecraft:azalea_leaves_flowers\"}",
        "{Name:\"minecraft:creaking_heart\",Properties:{active:\"true\",axis:\"y\"}}",
        "{Name:\"minecraft:creaking_heart\",Properties:{active:\"false\"}}",
        "{Name:\"minecraft:test_block\",Properties:{test_block_mode:\"start\"}}",
        "{Name:\"minecraft:stone\"}",
        "{Name:\"Stone\"}",
        "{Name:1}",
        "{Properties:{a:\"b\"}}",
    ]) + "]"
    blocks = "[" + ",".join(f"{{pos:[{i},0,0],state:{i}}}" for i in range(13)) + "]"
    for v in (2700, 2730, 2865, 3691, 3692, 4293, 4294, 4304, 4305, 4540, 4541, 5005, 5006, 5022):
        case(cases, f"palette-{v}", template(v, states, blocks))
    case(cases, "palettes-2730", template(2730, "[]", "[{pos:[0,0,0],state:0}]", extra=",palettes:[[{Name:\"minecraft:grass\"}],[{Name:\"minecraft:chain\"}]]"))
    case(cases, "palette-no-version", template(None), 2730)
    case(cases, "palette-version-given", template(2730, "[{Name:\"minecraft:grass\"}]"), 3692)
    case(cases, "palette-current", template(5023, "[{Name:\"minecraft:grass\"}]"))


def jigsaws(cases):
    for v in (2730, 3692, 4541):
        for i, state in enumerate(["minecraft:grass", "minecraft:chain[axis=x]", "grass", "minecraft:grass{a:1}", "[x]minecraft:grass", "minecraft:air"]):
            nbt = f"{{id:\"minecraft:jigsaw\",final_state:{q(state)},joint:\"rollable\",name:\"minecraft:a\",pool:\"minecraft:empty\",target:\"minecraft:empty\"}}"
            case(cases, f"jigsaw-{v}-{i}", template(v, "[{Name:\"minecraft:jigsaw\",Properties:{orientation:\"up_north\"}}]", f"[{block(nbt)}]"))


def beds(cases):
    for v in (2730, 4884, 4885):
        case(cases, f"bed-{v}", template(v, "[{Name:\"minecraft:red_bed\",Properties:{facing:\"north\",occupied:\"false\",part:\"head\"}}]", f"[{block('{id:\"minecraft:bed\"}')}]"))
    case(cases, "bed-short-id-2730", template(2730, "[{Name:\"minecraft:red_bed\"}]", f"[{block('{id:\"bed\"}')}]"))


def signs(cases):
    old = "{id:\"minecraft:sign\",Text1:'{\"text\":\"Hello\"}',Text2:'\"plain\"',Text3:'{\"extra\":[{\"text\":\"a\",\"bold\":true}],\"text\":\"\"}',Text4:'{\"text\":\"\"}',Color:\"red\",GlowingText:1b}"
    for v in (2730, 3096, 3097, 3438, 3439, 3563, 3564, 4289, 4290, 4291, 4292, 5001, 5002):
        case(cases, f"sign-old-{v}", template(v, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(old)}]"))
    filtered = "{id:\"minecraft:sign\",Text1:'{\"text\":\"a\"}',FilteredText1:'{\"text\":\"b\"}',FilteredText3:'{\"text\":\"\"}'}"
    case(cases, "sign-filtered-2730", template(2730, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(filtered)}]"))
    case(cases, "sign-filtered-3200", template(3200, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(filtered)}]"))
    two_sided = "{id:\"minecraft:sign\",is_waxed:0b,front_text:{messages:['{\"text\":\"x\"}','{\"text\":\"\"}','{\"text\":\"\"}','{\"text\":\"\"}'],filtered_messages:['{\"text\":\"\"}','{\"text\":\"\"}','{\"text\":\"y\"}','{\"text\":\"\"}'],color:\"black\",has_glowing_text:0b},back_text:{messages:['\"\"','\"\"','\"\"','\"\"'],color:\"blue\",has_glowing_text:1b}}"
    for v in (3465, 3578, 4189):
        case(cases, f"sign-two-sided-{v}", template(v, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(two_sided)}]"))
    hanging = "{id:\"minecraft:hanging_sign\",front_text:{messages:['{\"text\":\"h\"}','\"\"','\"\"','\"\"'],color:\"black\",has_glowing_text:0b},back_text:{messages:['\"\"','\"\"','\"\"','\"\"'],color:\"black\",has_glowing_text:0b}}"
    case(cases, "hanging-sign-3465", template(3465, "[{Name:\"minecraft:oak_hanging_sign\"}]", f"[{block(hanging)}]"))
    events = ("{id:\"minecraft:sign\",front_text:{messages:["
              "'{\"text\":\"a\",\"clickEvent\":{\"action\":\"run_command\",\"value\":\"/say hi\"},\"bold\":\"true\",\"italic\":\"no\"}',"
              "'{\"text\":\"b\",\"clickEvent\":{\"action\":\"open_url\",\"value\":\"https://example.com\"},\"hoverEvent\":{\"action\":\"show_text\",\"contents\":{\"text\":\"tip\",\"underlined\":\"TRUE\"}}}',"
              "'{\"text\":\"c\",\"clickEvent\":{\"action\":\"open_url\",\"value\":\"file:///x\"}}',"
              "'{\"text\":\"d\",\"clickEvent\":{\"action\":\"change_page\",\"value\":\"3\"},\"extra\":[{\"text\":\"e\",\"clickEvent\":{\"action\":\"suggest_command\",\"value\":\"x\\\\u00a7y\"}}]}'"
              "],color:\"black\",has_glowing_text:0b},back_text:{messages:["
              "'{\"translate\":\"t\",\"with\":[{\"text\":\"w\",\"bold\":\"true\"}]}',"
              "'[{\"text\":\"l\"},\"m\"]',"
              "'{\"text\":\"n\",\"x\":1.5,\"y\":100000,\"z\":1e3,\"w\":0.1,\"v\":3000000000,\"u\":1.0}',"
              "'not json'"
              "],color:\"black\",has_glowing_text:0b}}")
    for v in (4189, 4290, 4291, 4292):
        case(cases, f"sign-events-{v}", template(v, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(events)}]"))
    hover_entity = "{id:\"minecraft:sign\",front_text:{messages:['{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"id\":[I;1,2,3,4],\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}','\"\"','\"\"','\"\"'],color:\"black\",has_glowing_text:0b}}"
    case(cases, "sign-hover-entity-4189", template(4189, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(hover_entity)}]"))


LENIENT = [
    "{text:'single',bold:TRUE}",
    "{\"text\":\"a\"/*c*/}",
    "# comment\n\"x\"",
    "{\"text\"=\"eq\";\"color\"=>\"red\"}",
    "[\"a\",,\"b\"]",
    "[\"a\",]",
    ")]}'\n{\"text\":\"p\"}",
    "123",
    "null",
    "",
    "trUe",
    "{\"text\":\"x\"} // trailing",
    "{\"text\":\"x\"}   ",
    "'it\\'s'",
    "{text:\"multi\\\nline\"}",
    "[1;2]",
    "{\"text\":NaN}",
    "{\"text\":01}",
    "{\"text\":1e}",
    "{\"text\":-}",
    "{\"text\":\"tab\there\"}",
    "null and more",
    "plain",
    "two words",
    "{'translate':'k',with:[a,b]}",
    "{\"text\":\"x\",}",
    "{,}",
    "[,]",
    "{\"text\":\"a\"}#",
    "\"unterminated",
    "/",
    "{\"extra\":[{\"text\":\"e\",bold:\"true\"}],text:''}",
    # What DataFixerUpper reads of a text in part: a list loses what isn't a text, and a part
    # that doesn't read whole isn't typed, so the later fixes don't reach into it.
    "[\"a\",1,\"b\"]",
    "[1]",
    "5",
    "true",
    "{\"text\":\"\",\"extra\":[{\"text\":\"e\",\"bold\":\"true\"},5]}",
    "{\"text\":\"\",\"extra\":[[{\"text\":\"x\",\"bold\":\"true\"}]]}",
    "{\"text\":\"s\",\"separator\":5,\"bold\":\"true\"}",
    "{\"text\":\"s\",\"separator\":{\"text\":\",\",\"bold\":\"true\"}}",
    "[{\"text\":\"a\",\"bold\":\"true\"},[1,{\"text\":\"b\",\"bold\":\"true\"}]]",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_text\",\"contents\":[1,{\"text\":\"x\",\"bold\":\"true\"}]},\"bold\":\"true\"}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_text\",\"contents\":{\"text\":\"x\",\"bold\":\"true\"}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"id\":[1,2,3,4],\"name\":[1,\"n\"]}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"minecraft:stone\",\"count\":2}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":\"minecraft:stone\"}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"nope\",\"contents\":\"x\"},\"clickEvent\":{\"action\":\"copy_to_clipboard\",\"value\":\"c\"}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"id\":[1,2,3,4],\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"id\":\"00000001-0002-0003-0004-000000000005\",\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"id\":[\"I\",1,2,3,4],\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"minecraft:stone\"}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"minecraft:stone\",\"count\":5,\"x\":1}}}",
    "{\"text\":\"a\",\"x\":null}",
    "{\"text\":\"a\",\"extra\":[\"b\",null]}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"minecraft:pig\",\"name\":{\"text\":\"P\",\"clickEvent\":{\"action\":\"run_command\",\"value\":\"/x\"}}}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"minecraft:stone\",\"count\":1,\"components\":{\"minecraft:custom_name\":{\"text\":\"N\",\"bold\":\"true\"}}}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_text\",\"contents\":{\"text\":\"x\",\"extra\":[{\"text\":\"y\",\"bold\":\"true\"}]}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_text\",\"contents\":{\"text\":\"x\",\"hoverEvent\":{\"action\":\"show_text\",\"contents\":{\"text\":\"z\",\"bold\":\"true\"}}}}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"name\":{\"text\":\"P\",\"bold\":\"true\"}}}}",
    "{\"text\":\"s\",\"hoverEvent\":{\"action\":\"show_entity\",\"contents\":{\"type\":\"pig\",\"id\":[1,2,3,4]}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"stone\",\"count\":2}}}",
    "{\"text\":\"h\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":\"chain\"}}",
    "{\"text\":\"h\",\"extra\":[{\"text\":\"e\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"minecraft:chain\",\"components\":{\"minecraft:lore\":[{\"text\":\"l\",\"italic\":\"true\"}]}}}}]}",
]


def lenient(cases):
    # Old signs' lines, unflattened at 4290 by `LenientJsonParser`, each in a sign of its own,
    # since where vanilla throws on one the whole template doesn't load.
    for i, line in enumerate(LENIENT):
        messages = ",".join(q(s) for s in [line, "\"\"", "\"\"", "\"\""])
        sign = f"{{id:\"minecraft:sign\",front_text:{{messages:[{messages}],color:\"black\",has_glowing_text:0b}}}}"
        case(cases, f"sign-lenient-{i}-4289", template(4289, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(sign)}]"))
    # Hover events already NBT, before and after their fix.
    nbt_hovers = [
        "{text:\"h\",hoverEvent:{action:\"show_item\",contents:{id:\"minecraft:stone\",count:2}}}",
        "{text:\"h\",hoverEvent:{action:\"show_entity\",contents:{type:\"minecraft:pig\",id:[I;1,2,3,4],name:{text:\"P\",bold:\"true\"}}}}",
        "{text:\"h\",hoverEvent:{action:\"show_item\",contents:\"minecraft:stone\"}}",
        "{text:\"h\",hoverEvent:{action:\"show_item\",contents:\"stone\"}}",
        "{text:\"h\",hoverEvent:{action:\"show_item\",contents:5}}",
    ]
    after = [
        "{text:\"h\",hover_event:{action:\"show_item\",id:\"minecraft:chain\",count:1}}",
        "{text:\"h\",hover_event:{action:\"show_text\",value:{text:\"v\",hover_event:{action:\"show_item\",id:\"chain\"}}}}",
    ]
    for i, h in enumerate(after):
        sign = f"{{id:\"minecraft:sign\",front_text:{{messages:[{h},\"\",\"\",\"\"],color:\"black\",has_glowing_text:0b}}}}"
        case(cases, f"sign-hover-item-{i}-4292", template(4292, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(sign)}]"))
    for i, h in enumerate(nbt_hovers):
        for v in (4290, 4291):
            sign = f"{{id:\"minecraft:sign\",front_text:{{messages:[{h},\"\",\"\",\"\"],color:\"black\",has_glowing_text:0b}}}}"
            case(cases, f"sign-nbt-hover-{i}-{v}", template(v, "[{Name:\"minecraft:oak_sign\"}]", f"[{block(sign)}]"))
    # `translate` read leniently from an ominous banner's old name.
    banner = "{id:\"minecraft:banner\",CustomName:" + q("{translate:'block.minecraft.ominous_banner'}") + "}"
    case(cases, "banner-lenient-ominous-3824", template(3824, "[{Name:\"minecraft:white_banner\"}]", f"[{block(banner)}]"))


def banners(cases):
    patterns = "{id:\"minecraft:banner\",Patterns:[{Pattern:\"bs\",Color:14},{Pattern:\"mc\",Color:0},{Pattern:\"xyz\",Color:20},{Color:3}]}"
    for v in (2730, 3818, 3819):
        case(cases, f"banner-patterns-{v}", template(v, "[{Name:\"minecraft:white_banner\"}]", f"[{block(patterns)}]"))
    ominous = "{id:\"minecraft:banner\",CustomName:'{\"color\":\"gold\",\"translate\":\"block.minecraft.ominous_banner\"}',Patterns:[{Pattern:\"mr\",Color:9}]}"
    for v in (2730, 3824, 3825, 4053, 4054, 4300, 4306, 4307):
        case(cases, f"banner-ominous-{v}", template(v, "[{Name:\"minecraft:white_banner\"}]", f"[{block(ominous)}]"))
    named = "{id:\"minecraft:banner\",CustomName:'{\"text\":\"Flag\"}'}"
    case(cases, "banner-named-2730", template(2730, "[{Name:\"minecraft:white_banner\"}]", f"[{block(named)}]"))


def item(id_, count="1b", tag=None, slot=None):
    parts = [f"id:{q(id_)}", f"Count:{count}"]
    if slot is not None:
        parts.insert(0, f"Slot:{slot}b")
    if tag is not None:
        parts.append(f"tag:{tag}")
    return "{" + ",".join(parts) + "}"


def items(cases):
    stacks = [
        item("minecraft:charcoal", "2b", slot=0),
        item("minecraft:stone_shovel", tag="{Damage:0}", slot=1),
        item("minecraft:iron_sword", tag="{Damage:5,RepairCost:2,Enchantments:[{id:\"minecraft:sweeping\",lvl:2s},{id:\"minecraft:sharpness\",lvl:0s},{id:\"minecraft:unbreaking\",lvl:300}],HideFlags:7,Unbreakable:1b}", slot=2),
        item("minecraft:enchanted_book", tag="{StoredEnchantments:[{id:\"minecraft:frost_walker\",lvl:2}]}", slot=3),
        item("minecraft:potion", tag="{Potion:\"minecraft:swiftness\",CustomPotionColor:3}", slot=4),
        item("minecraft:potion", tag="{Potion:\"minecraft:empty\"}", slot=5),
        item("minecraft:leather_helmet", tag="{display:{Name:'{\"text\":\"Hat\"}',Lore:['{\"text\":\"one\"}','bad json',\"\\\"two\\\"\"],color:255},HideFlags:64}", slot=6),
        item("minecraft:diamond_helmet", tag="{Damage:0,Enchantments:[{id:\"minecraft:protection\",lvl:3},{id:\"minecraft:binding_curse\",lvl:1}],Trim:{material:\"minecraft:netherite\",pattern:\"minecraft:silence\"},AttributeModifiers:[{Amount:3.0d,Name:\"\",Operation:0,UUID:[I;110525277,279138076,-2106776415,-641135084],AttributeName:\"minecraft:generic.armor\",Slot:\"head\"},{Amount:0.1d,Name:\"x\",Operation:2,UUID:[I;1,2,3,4],AttributeName:\"minecraft:horse.jump_strength\",Slot:\"head\"}],HideFlags:130}", slot=7),
        item("minecraft:written_book", tag="{pages:['{\"text\":\"p1\"}','\"p2\"'],filtered_pages:{\"1\":'\"f2\"'},title:\"T\",author:\"A\",resolved:1b,generation:1}", slot=8),
        item("minecraft:writable_book", tag="{pages:[\"raw text\"],filtered_title:\"x\"}", slot=9),
        item("minecraft:grass", "64b", slot=10),
        item("minecraft:scute", slot=11),
        item("minecraft:chain", slot=12),
        item("minecraft:pottery_shard_archer", slot=13),
        item("minecraft:white_banner", tag="{display:{Name:'{\"translate\":\"block.minecraft.ominous_banner\",\"color\":\"gold\"}'},HideFlags:32,BlockEntityTag:{id:\"minecraft:banner\",Patterns:[{Pattern:\"mr\",Color:9}]}}", slot=14),
        item("minecraft:shulker_box", tag="{BlockEntityTag:{id:\"minecraft:shulker_box\",Items:[" + item("minecraft:grass", "3b", slot=4) + "],Lock:\"key\"}}", slot=15),
        item("minecraft:player_head", tag="{SkullOwner:{Name:\"Steve\",Id:[I;1,2,3,4],Properties:{textures:[{Value:\"abc\",Signature:\"sig\"}]}}}", slot=16),
        item("minecraft:compass", tag="{LodestonePos:{X:1,Y:2,Z:3},LodestoneDimension:\"minecraft:overworld\",LodestoneTracked:0b}", slot=17),
        item("minecraft:crossbow", tag="{Charged:1b,ChargedProjectiles:[" + item("minecraft:arrow") + "]}", slot=18),
        item("minecraft:stone", tag="{CustomModelData:3,CanDestroy:[\"minecraft:stone\",\"minecraft:grass_block[snowy=false]{x:1}\"],display:{LocName:\"item.x\"}}", slot=19),
        "{}",
        "{id:\"minecraft:stick\"}",
    ]
    chest = "{id:\"minecraft:chest\",Items:[" + ",".join(stacks) + "],CustomName:'{\"text\":\"Box\",\"bold\":\"true\"}',Lock:\"key \\\"q\\\" \\\\b\"}"
    for v in (2730, 3818, 3819, 3825, 4060, 4068, 4290, 4292, 4306, 4307):
        case(cases, f"chest-items-{v}", template(v, "[{Name:\"minecraft:chest\"}]", f"[{block(chest)}]"))
    loot = "{id:\"minecraft:chest\",LootTable:\"minecraft:chests/village/village_plains_house\",LootTableSeed:0L,Lock:\"\"}"
    case(cases, "chest-loot-2730", template(2730, "[{Name:\"minecraft:chest\"}]", f"[{block(loot)}]"))
    barrel = "{id:\"minecraft:barrel\",LootTable:\"minecraft:chests/simple_dungeon\",components:{\"minecraft:lock\":\"k\",\"minecraft:custom_name\":'\"Barrel\"'}}"
    for v in (3839, 4067, 4068, 4176, 4290):
        case(cases, f"barrel-components-{v}", template(v, "[{Name:\"minecraft:barrel\"}]", f"[{block(barrel)}]"))
    broken = "{id:\"minecraft:barrel\",lock:{components:{\"minecraft:custom_name\":'\"\"'}}}"
    case(cases, "barrel-broken-lock-4175", template(4175, "[{Name:\"minecraft:barrel\"}]", f"[{block(broken)}]"))
    furnace = "{id:\"minecraft:furnace\",BurnTime:10s,CookTime:5s,CookTimeTotal:200s,Items:[" + item("minecraft:charcoal", "2b", slot=1) + "],RecipesUsed:{}}"
    for v in (2865, 4180, 4181):
        case(cases, f"furnace-{v}", template(v, "[{Name:\"minecraft:furnace\"}]", f"[{block(furnace)}]"))
    case(cases, "smoker-2865", template(2865, "[{Name:\"minecraft:smoker\"}]", f"[{block(furnace.replace('minecraft:furnace', 'minecraft:smoker'))}]"))
    campfire = "{id:\"minecraft:campfire\",Items:[" + item("minecraft:porkchop", slot=0) + "],CookingTimes:[I;1,0,0,0],CookingTotalTimes:[I;600,0,0,0]}"
    case(cases, "campfire-2973", template(2973, "[{Name:\"minecraft:campfire\"}]", f"[{block(campfire)}]"))
    lectern = "{id:\"minecraft:lectern\",Book:" + item("minecraft:written_book", tag="{pages:['{\"text\":\"hi\"}'],title:\"B\",author:\"me\"}") + ",Page:0}"
    case(cases, "lectern-3700", template(3700, "[{Name:\"minecraft:lectern\"}]", f"[{block(lectern)}]"))
    lectern_new = "{id:\"minecraft:lectern\",Book:{id:\"minecraft:written_book\",count:1,components:{\"minecraft:written_book_content\":{title:{raw:\"B\"},author:\"me\",pages:[{raw:'{\"text\":\"hi\",\"bold\":\"true\"}'}]}}},Page:0}"
    case(cases, "lectern-3839", template(3839, "[{Name:\"minecraft:lectern\"}]", f"[{block(lectern_new)}]"))
    brewing = "{id:\"minecraft:brewing_stand\",BrewTime:0s,Fuel:0b,Items:[" + item("minecraft:potion", tag="{Potion:\"minecraft:swiftness\"}", slot=0) + "]}"
    case(cases, "brewing-3578", template(3578, "[{Name:\"minecraft:brewing_stand\"}]", f"[{block(brewing)}]"))
    jukebox = "{id:\"minecraft:jukebox\",RecordItem:" + item("minecraft:music_disc_cat") + ",IsPlaying:1b,TickCount:500L,RecordStartTick:100L}"
    case(cases, "jukebox-3700", template(3700, "[{Name:\"minecraft:jukebox\"}]", f"[{block(jukebox)}]"))
    dispenser = "{id:\"minecraft:dispenser\",Items:[" + item("minecraft:water_bucket", slot=0) + "]}"
    case(cases, "dispenser-2865", template(2865, "[{Name:\"minecraft:dispenser\"}]", f"[{block(dispenser)}]"))


def more_block_entities(cases):
    skulls = ["{id:\"minecraft:skull\",SkullOwner:\"Notch\"}",
              "{id:\"minecraft:skull\",SkullOwner:\"bad name with spaces\"}",
              "{id:\"minecraft:skull\",SkullOwner:{Name:\"Alex\",Id:[I;5,6,7,8],Properties:{textures:[{Value:\"v\"}]}}}",
              "{id:\"minecraft:skull\",ExtraType:\"Herobrine\"}",
              "{id:\"minecraft:skull\"}"]
    for i, s in enumerate(skulls):
        for v in (2865, 3820):
            case(cases, f"skull-{i}-{v}", template(v, "[{Name:\"minecraft:player_head\"}]", f"[{block(s)}]"))
    hive = ("{id:\"minecraft:beehive\",FlowerPos:{X:1,Y:2,Z:3},Bees:[{MinOccupationTicks:600,TicksInHive:20,EntityData:"
            "{id:\"minecraft:bee\",HivePos:{X:0,Y:64,Z:0},FlowerPos:{X:1,Y:2,Z:3},Attributes:[{Name:\"minecraft:generic.follow_range\",Base:48.0d},{Name:\"minecraft:generic.movement_speed\",Base:0.3d}],"
            "FallDistance:0.5f,ArmorItems:[{},{},{},{}],HandItems:[{},{}],ArmorDropChances:[0.085f,0.085f,0.085f,0.085f],HandDropChances:[0.085f,0.085f],Health:10.0f}}]}")
    for v in (2865, 3812, 3813, 3818, 3819):
        case(cases, f"beehive-{v}", template(v, "[{Name:\"minecraft:beehive\"}]", f"[{block(hive)}]"))
    spawner_old = "{id:\"minecraft:mob_spawner\",Delay:20s,SpawnData:{id:\"minecraft:zombie\"},SpawnPotentials:[{Weight:3,Entity:{id:\"minecraft:skeleton\"},extra:1b}],SpawnCount:4s}"
    case(cases, "spawner-2730", template(2730, "[{Name:\"minecraft:spawner\"}]", f"[{block(spawner_old)}]"))
    spawner_new = "{id:\"minecraft:mob_spawner\",Delay:20s,SpawnData:{entity:{id:\"minecraft:cave_spider\"}},SpawnPotentials:[],MaxNearbyEntities:6s}"
    case(cases, "spawner-3465", template(3465, "[{Name:\"minecraft:spawner\"}]", f"[{block(spawner_new)}]"))
    sand = "{id:\"minecraft:suspicious_sand\",loot_table:\"minecraft:archaeology/desert_pyramid\",loot_table_seed:5L}"
    case(cases, "suspicious-sand-3337", template(3337, "[{Name:\"minecraft:suspicious_sand\"}]", f"[{block(sand)}]"))
    brushable = "{id:\"minecraft:brushable_block\",LootTable:\"minecraft:archaeology/desert_well\",item:{id:\"minecraft:air\",count:1}}"
    case(cases, "brushable-3832", template(3832, "[{Name:\"minecraft:suspicious_sand\"}]", f"[{block(brushable)}]"))
    pots = ["{id:\"minecraft:decorated_pot\",shards:[\"minecraft:brick\",\"minecraft:pottery_shard_archer\"]}",
            "{id:\"minecraft:decorated_pot\",sherds:[\"minecraft:brick\",\"minecraft:archer_pottery_sherd\",\"minecraft:brick\",\"minecraft:brick\"],item:" + item("minecraft:cod") + "}",
            "{id:\"minecraft:decorated_pot\"}",
            "{id:\"minecraft:decorated_pot\",sherds:[\"minecraft:brick\",\"\"],LootTable:\"minecraft:pots/trial_chambers/corridor\"}"]
    for i, pot in enumerate(pots):
        for v in (3337, 3700, 4325):
            case(cases, f"pot-{i}-{v}", template(v, "[{Name:\"minecraft:decorated_pot\"}]", f"[{block(pot)}]"))
    gateway = "{id:\"minecraft:end_gateway\",ExitPortal:{X:10,Y:60,Z:-4},Age:5L}"
    case(cases, "end-gateway-2730", template(2730, "[{Name:\"minecraft:end_gateway\"}]", f"[{block(gateway)}]"))
    simple = ["bell", "comparator", "daylight_detector", "enchanting_table", "ender_chest", "conduit"]
    for s in simple:
        case(cases, f"simple-{s}-2730", template(2730, f"[{{Name:\"minecraft:{s}\"}}]", f"[{block('{id:' + q('minecraft:' + s) + '}')}]"))


def entities(cases):
    villager = ("{id:\"minecraft:villager\",Attributes:[{Name:\"minecraft:generic.movement_speed\",Base:0.5d},"
                "{Name:\"minecraft:generic.follow_range\",Base:48.0d,Modifiers:[{Amount:0.02d,Operation:1,UUID:[I;-1,-2,-3,-4],Name:\"Random spawn bonus\"},{Amount:0.03d,Operation:1,UUID:[I;5,6,7,8],Name:\"Random spawn bonus\"},{Amount:1.0d,Operation:0,UUID:[I;1835885058,-1095021588,-1586315027,-1131838612],Name:\"x\"}]}],"
                "Offers:{Recipes:[{rewardExp:1b,maxUses:16,buy:{id:\"minecraft:emerald\",Count:5b},buyB:{id:\"minecraft:air\",Count:1b},sell:{id:\"minecraft:enchanted_book\",Count:1b,tag:{StoredEnchantments:[{id:\"minecraft:frost_walker\",lvl:2}]}}},"
                "{buy:{id:\"minecraft:paper\",Count:24b},buyB:{id:\"minecraft:book\",Count:1b},sell:{id:\"minecraft:emerald\",Count:1b}}]},"
                "VillagerData:{type:\"minecraft:plains\",level:1,profession:\"minecraft:librarian\"},Inventory:[" + item("minecraft:bread", "3b") + "],"
                "ArmorItems:[{},{},{},{}],HandItems:[{},{}],ArmorDropChances:[0.085f,0.085f,0.085f,0.085f],HandDropChances:[0.085f,0.085f],"
                "FallDistance:0.0f,Brain:{memories:{\"minecraft:job_site\":{value:{pos:[I;1,2,3],dimension:\"minecraft:overworld\"}}}},Pos:[1.0d,2.0d,3.0d],Rotation:[90.0f,0.0f],"
                "CustomName:'{\"text\":\"Bob\"}',Leash:{X:1,Y:2,Z:3},UUID:[I;1,2,3,4]}")
    for v in (2865, 3813, 3818, 3828, 3945, 4055, 4187, 4290, 4293, 4301, 4303, 4763):
        case(cases, f"villager-{v}", template(v, entities=entity(villager)))
    pillager = ("{id:\"minecraft:pillager\",PatrolTarget:{X:5,Y:6,Z:7},HandItems:[" + item("minecraft:crossbow", tag="{Charged:0b}") + ",{}],ArmorItems:[{},{},{},{id:\"minecraft:white_banner\",Count:1b,tag:{display:{Name:'{\"translate\":\"block.minecraft.ominous_banner\"}'}}}],"
                "ArmorDropChances:[0.085f,0.085f,0.085f,2.0f],HandDropChances:[0.5f,0.085f],Attributes:[{Base:0.35d,Name:\"minecraft:generic.movement_speed\"}],SleepingX:1,SleepingY:2,SleepingZ:3}")
    for v in (3578, 4300, 4310):
        case(cases, f"pillager-{v}", template(v, entities=entity(pillager)))
    stand = ("{id:\"minecraft:armor_stand\",ArmorItems:[" + item("minecraft:iron_boots", tag="{Damage:0}") + ",{},{id:\"minecraft:air\",Count:0b},{}],HandItems:[{},{}],"
             "Attributes:[{Base:0.7d,Name:\"minecraft:generic.movement_speed\"}],Pose:{},Tags:[\"in.checked\"]}")
    for v in (3578, 4301):
        case(cases, f"armor-stand-{v}", template(v, entities=entity(stand)))
    dropped = "{id:\"minecraft:item\",Item:" + item("minecraft:moss_carpet") + ",Age:2229s,PickupDelay:0s}"
    case(cases, "item-entity-3465", template(3465, entities=entity(dropped)))
    frame = "{id:\"minecraft:item_frame\",TileX:1,TileY:2,TileZ:3,Item:" + item("minecraft:map") + ",Facing:1b}"
    case(cases, "item-frame-4000", template(4000, entities=entity(frame)))
    horse = "{id:\"minecraft:horse\",ArmorItem:" + item("minecraft:iron_horse_armor") + ",SaddleItem:" + item("minecraft:saddle") + ",ArmorItems:[{},{},{},{}],ArmorDropChances:[0.085f,0.085f,0.085f,0.085f]}"
    case(cases, "horse-3700", template(3700, entities=entity(horse)))
    pig = "{id:\"minecraft:pig\",Saddle:1b,HandDropChances:[0.085f,0.085f],ArmorDropChances:[0.085f,0.085f,0.085f,0.085f]}"
    case(cases, "pig-4200", template(4200, entities=entity(pig)))
    painting = "{id:\"minecraft:painting\",Motive:\"minecraft:kebab\",Facing:2b,TileX:1,TileY:2,TileZ:3}"
    case(cases, "painting-3000", template(3000, entities=entity(painting)))
    cat = "{id:\"minecraft:cat\",CatType:4}"
    case(cases, "cat-3000", template(3000, entities=entity(cat)))
    falling = "{id:\"minecraft:falling_block\",BlockState:{Name:\"minecraft:grass\"},TileEntityData:{id:\"minecraft:bed\"},Time:1}"
    case(cases, "falling-block-2730", template(2730, entities=entity(falling)))
    rider = "{id:\"minecraft:spider\",Passengers:[{id:\"minecraft:skeleton\",HandItems:[" + item("minecraft:bow") + ",{}],ArmorItems:[{},{},{},{}],FallDistance:1.5f}],ArmorItems:[{},{},{},{}],HandItems:[{},{}]}"
    case(cases, "jockey-3700", template(3700, entities=entity(rider)))
    bee = "{id:\"minecraft:bee\",HivePos:{X:0,Y:64,Z:0},Attributes:[{Name:\"minecraft:generic.follow_range\",Base:48.0d}]}"
    case(cases, "bee-2865", template(2865, entities=entity(bee)))
    zombie_villager = "{id:\"minecraft:zombie_villager\",VillagerData:{type:\"minecraft:plains\",level:1,profession:\"minecraft:none\"}}"
    case(cases, "zombie-villager-4700", template(4700, entities=entity(zombie_villager)))
    tnt = "{id:\"minecraft:tnt_minecart\",TNTFuse:-1}"
    case(cases, "tnt-minecart-4000", template(4000, entities=entity(tnt)))


def main():
    cases = []
    palettes(cases)
    jigsaws(cases)
    beds(cases)
    signs(cases)
    lenient(cases)
    banners(cases)
    items(cases)
    more_block_entities(cases)
    entities(cases)
    write_file(HERE / "generated.json", "datafix", "cases/datafix/gen.py", cases)


if __name__ == "__main__":
    main()
