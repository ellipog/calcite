"""Writes cases/items/generated.json: item stacks read as vanilla reads them, from a data pack's
JSON with `ItemStack.CODEC`, and written to NBT, with the vanilla data pack's registries and the
items' default components bound, as a server has them (CAL-77).

    py -I cases/items/gen.py
"""

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
    # Every component type, as the packs cases have them, on an item it may be on.
    items = ["minecraft:paper", "minecraft:paper", "minecraft:apple", "minecraft:paper", "minecraft:paper", "minecraft:paper",
             "minecraft:diamond_sword", "minecraft:potion", "minecraft:diamond_pickaxe", "minecraft:paper", "minecraft:paper",
             "minecraft:potion", "minecraft:potion", "minecraft:potion"]
    for i, components in enumerate(packs.ITEM_COMPONENTS):
        item = items[i] if i < len(items) else "minecraft:paper"
        add(f"components-{i}", {"id": item, "components": components})
    for name, components in packs.BAD_COMPONENTS.items():
        add(f"bad-{name}", {"id": "minecraft:paper", "components": components})
    return out


def main():
    write_file(HERE / "generated.json", "items", "cases/items/gen.py", cases())


if __name__ == "__main__":
    main()
