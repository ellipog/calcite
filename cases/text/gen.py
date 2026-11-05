"""Writes cases/text/contents.json: the text probe's cases for every kind of contents, typed
and fuzzy, and the errors of each, beside the hand-written basic.json (D368).

    py -I cases/text/gen.py
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("contents.json")

J = [
    # The `type` field and the legacy matcher.
    ("type-unknown", {"type": "nope", "text": "x"}),
    ("type-number", {"type": 5, "text": "x"}),
    ("type-null", {"type": None, "keybind": "key.jump"}),
    ("type-keybind-missing", {"type": "keybind"}),
    ("type-text-ignores-others", {"type": "text", "text": "t", "keybind": "key.jump"}),
    ("type-keybind-over-text", {"type": "keybind", "keybind": "key.jump", "text": "t"}),
    ("fuzzy-text-not-string", {"text": 5, "keybind": "key.jump"}),
    ("fuzzy-translate-bad-arg-falls-through", {"translate": "k", "with": [{"txt": 1}], "keybind": "key.sneak"}),
    # Keybinds and scores.
    ("keybind-extra", {"keybind": "key.inventory", "extra": [" more", {"keybind": "key.drop"}]}),
    ("keybind-not-string", {"type": "keybind", "keybind": 3}),
    ("score-selector-name", {"score": {"name": "@a[tag=x]", "objective": "o"}}),
    ("score-star", {"score": {"name": "*", "objective": "deaths"}, "color": "aqua"}),
    ("score-missing-objective", {"type": "score", "score": {"name": "a"}}),
    ("score-name-number", {"type": "score", "score": {"name": 5, "objective": "o"}}),
    ("score-not-object", {"type": "score", "score": "a"}),
    # Selectors.
    ("selector-name", {"selector": "Steve"}),
    ("selector-separator-styled", {"selector": "@e[type=pig]", "separator": {"text": "; ", "color": "gray"}}),
    ("selector-bad-separator", {"type": "selector", "selector": "@p", "separator": 5}),
    # NBT contents.
    ("nbt-entity", {"nbt": "Health", "entity": "@s", "separator": ", "}),
    ("nbt-plain", {"nbt": "Name", "storage": "a:b", "plain": True}),
    ("nbt-root-pattern", {"nbt": "{a:1b}.b[0]", "storage": "x"}),
    ("nbt-bad-path", {"type": "nbt", "nbt": "a..b", "storage": "x"}),
    ("nbt-path-trailing", {"type": "nbt", "nbt": "a b", "storage": "x"}),
    ("nbt-path-bad-index", {"type": "nbt", "nbt": "a[x]", "storage": "x"}),
    ("nbt-both-flags", {"type": "nbt", "nbt": "a", "storage": "x", "interpret": True, "plain": True}),
    ("nbt-both-flags-fuzzy", {"nbt": "a", "storage": "x", "interpret": True, "plain": True}),
    ("nbt-no-source", {"type": "nbt", "nbt": "a"}),
    ("nbt-source-unknown", {"type": "nbt", "nbt": "a", "source": "world", "storage": "x"}),
    ("nbt-source-typed", {"nbt": "a", "source": "storage", "storage": "x", "block": "1 2 3"}),
    ("nbt-storage-bad-id", {"type": "nbt", "nbt": "a", "storage": "Bad Id"}),
    ("nbt-lenient-flags", {"nbt": "a", "storage": "x", "interpret": "yes", "plain": 7}),
    ("nbt-lenient-separator", {"nbt": "a", "storage": "x", "separator": 5}),
    ("nbt-block-local", {"nbt": "Items", "block": "^ ^1 ^-2.5"}),
    ("nbt-block-relative", {"nbt": "Items", "block": "~-1 ~.5 ~3."}),
    ("nbt-block-mixed", {"type": "nbt", "nbt": "Items", "block": "~ ^ ~"}),
    ("nbt-block-local-mixed", {"type": "nbt", "nbt": "Items", "block": "^ ~ ^"}),
    ("nbt-block-incomplete", {"type": "nbt", "nbt": "Items", "block": "1 2"}),
    ("nbt-block-bad-int", {"type": "nbt", "nbt": "Items", "block": "1.5 2 3"}),
    ("nbt-block-bad-double", {"type": "nbt", "nbt": "Items", "block": "~1-2 2 3"}),
    ("nbt-block-empty", {"type": "nbt", "nbt": "Items", "block": ""}),
    ("nbt-block-trailing", {"type": "nbt", "nbt": "Items", "block": "1 2 3 4"}),
    ("nbt-block-long-context", {"type": "nbt", "nbt": "Items", "block": "100000 200000 x"}),
    # Objects.
    ("object-atlas-other", {"object": "atlas", "atlas": "minecraft:gui", "sprite": "hud/heart"}),
    ("object-atlas-default-written", {"object": "atlas", "atlas": "blocks", "sprite": "block/dirt"}),
    ("object-sprite-modded", {"sprite": "mod:thing", "atlas": "mod:sheet"}),
    ("object-fallback", {"object": "atlas", "sprite": "block/dirt", "fallback": {"text": "dirt", "color": "gold", "extra": ["!"]}}),
    ("object-player-unknown", {"player": {"id": [1, 2, 3, 4]}}),
    ("object-player-string", {"player": "Alex", "hat": True}),
    ("object-player-properties", {"player": {"name": "Steve", "properties": [{"name": "textures", "value": "abc"}]}}),
    ("object-player-bad-name", {"type": "object", "object": "player", "player": "bad name!"}),
    ("object-unknown", {"type": "object", "object": "cube"}),
    ("object-no-info", {"type": "object", "fallback": "x"}),
    ("object-sprite-bad-id", {"type": "object", "sprite": "Bad Sprite"}),
    # Translations.
    ("translate-bool-in-extra", {"text": "a", "extra": [{"translate": "%s/%s", "with": [False, True]}]}),
    ("translate-bool-in-hover", {"text": "a", "hover_event": {"action": "show_text", "value": {"translate": "%s", "with": [True]}}}),
    ("translate-arg-object-typed", {"type": "translatable", "translate": "%s", "with": [{"txt": 1}]}),
    ("translate-arg-null-typed", {"type": "translatable", "translate": "%s", "with": [[]]}),
    ("translate-fallback-lenient", {"translate": "x.y", "fallback": 5}),
    ("translate-with-not-list", {"type": "translatable", "translate": "x", "with": "a"}),
    # Events.
    ("click-open-file", {"text": "a", "click_event": {"action": "open_file", "path": "x"}}),
    ("click-show-dialog", {"text": "a", "click_event": {"action": "show_dialog", "dialog": "minecraft:server_links"}}),
    ("click-show-dialog-unknown", {"text": "a", "click_event": {"action": "show_dialog", "dialog": "minecraft:nope"}}),
    ("click-custom-payload", {"text": "a", "click_event": {"action": "custom", "id": "x:y", "payload": {"a": [1, 2]}}}),
    ("click-page-zero", {"text": "a", "click_event": {"action": "change_page", "page": 0}}),
    ("click-no-action", {"text": "a", "click_event": {"url": "https://example.com"}}),
    ("hover-entity-bad-uuid", {"text": "a", "hover_event": {"action": "show_entity", "id": "pig", "uuid": "nope"}}),
    ("hover-entity-unknown-type", {"text": "a", "hover_event": {"action": "show_entity", "id": "dragonfly", "uuid": [1, 2, 3, 4]}}),
    ("hover-item-count-bad", {"text": "a", "hover_event": {"action": "show_item", "id": "minecraft:stone", "count": 100}}),
    ("hover-item-air", {"text": "a", "hover_event": {"action": "show_item", "id": "minecraft:air"}}),
    ("hover-unknown-action", {"text": "a", "hover_event": {"action": "show_achievement", "value": "x"}}),
    # Styles and lists.
    ("style-two-errors", {"text": "a", "color": "nope", "bold": "x"}),
    ("style-shadow-bad", {"text": "a", "shadow_color": "red"}),
    ("style-font-bad", {"text": "a", "font": "Not:Valid"}),
    ("style-and-contents-errors", {"type": "keybind", "color": "nope"}),
    ("extra-item-bad", {"text": "a", "extra": ["b", 5]}),
    ("extra-not-list", {"text": "a", "extra": "b"}),
    ("list-bad-item", ["a", 5]),
    ("list-all-bad", [5, 6]),
    ("list-nested", [["a", "b"], {"keybind": "key.jump"}]),
]

S = [
    ("keybind", '{keybind:"key.jump"}'),
    ("nbt-storage", '{nbt:"a.b",storage:"x:y",interpret:1b}'),
    ("nbt-flags-numbers", '{nbt:"a",storage:"x",interpret:2s,plain:0.0d}'),
    ("object", '{object:"atlas",sprite:"item/apple"}'),
    ("player-ids", '{player:{id:[I;1,2,3,4],name:"Steve"},hat:0b}'),
    ("type-unknown", '{type:"x",text:"a"}'),
    ("score", '{score:{name:"*",objective:"deaths"}}'),
    ("translate-typed-array", '{type:"translatable",translate:"%s",with:[[I;1,2]]}'),
    ("translate-typed-compound", '{type:"translatable",translate:"%s",with:[{a:1}]}'),
    ("style-errors", '{text:"a",color:5,italic:"no"}'),
    ("hover-item-components", '{text:"a",hover_event:{action:"show_item",id:"minecraft:stone",components:{"minecraft:custom_name":"Rock"}}}'),
    ("click-custom-payload", '{text:"a",click_event:{action:"custom",id:"x:y",payload:[B;1,2]}}'),
]

cases = [{"id": f"json-{name}", "input": {"json": json.dumps(value, ensure_ascii=False, separators=(",", ":"))}} for name, value in J]
cases += [{"id": f"snbt-{name}", "input": {"snbt": text}} for name, text in S]
lines = ['{', '  "probe": "text",', '  "probe_version": 1,', '  "cases": [']
for i, c in enumerate(cases):
    lines.append("    " + json.dumps(c, ensure_ascii=False) + ("," if i + 1 < len(cases) else ""))
lines += ["  ]", "}", ""]
OUT.write_bytes("\n".join(lines).encode("utf-8"))
print(len(cases))
