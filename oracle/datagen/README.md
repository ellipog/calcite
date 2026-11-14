---
title: Data generator and tables
description: How Calcite turns Mojang's server jar into the tables its codegen reads, in one repeatable command.
---

# Data generator and tables

Calcite's block states, registries, item defaults, packet IDs and command tree come from Mojang's own data generator, run on the official server jar (Phase 2). One command fetches the jar, runs the generator, and converts its reports into neutral tables that Calx codegen reads. None of that is committed: `generated/` is gitignored (D30). What Calcite compiles in from the tables is committed as Calx, so it builds without the jar ([below](#calx-modules)).

```sh
py -I oracle/datagen/datagen.py            # fetch, generate and convert into generated/26.3/
py -I oracle/datagen/datagen.py --check    # regenerate into a scratch folder and compare, byte for byte
py -I oracle/datagen/convert.py            # convert again from the existing reports only
calx oracle/fetch.calx [--check]           # fetch and verify the jar on its own
calx oracle/fetch.calx --jar <path>        # or install a jar you already have, with no network
```

`datagen.py` takes `--version` (default `26.3`) and `--java-home`. It finds JDK 25 the same way the [vanilla adapter's build](../vanilla-adapter/README.md#building) does. On Linux, use `python3` for `py`. A full run takes about 12 seconds on Windows.

## What it does

1. **Fetch.** [`../fetch.calx`](../fetch.calx) checks `oracle/jars/server-<version>.jar` against the SHA-1 pinned in [`../versions.json`](../versions.json), and downloads it from Mojang if it's missing or wrong (`P2.4`, D62). A jar you already have can be installed with `fetch.py --jar <path>`, as long as it's the pinned one.
2. **Generate.** Runs `java -DbundlerMainClass=net.minecraft.data.Main -jar server-<version>.jar --all --output generated/<version>/datagen` from `oracle/work/`, where the bundler unpacks its libraries. It uses the rig's reference JVM flags (D60). The log goes to `build/datagen/<version>.log`. The old output is deleted first, so nothing stale survives.
3. **Drop the cache.** The generator's `.cache/` folder records a timestamp per run. It's the only output that changes between runs, and nothing reads it, so it's deleted.
4. **Convert.** [`convert.py`](convert.py) checks the reports and writes the tables to `generated/<version>/tables/`, replacing the folder whole, so a failed conversion leaves the old tables in place.

## Repeatability (gate G2)

`--check` regenerates everything into `build/datagen/check/` and compares every file with `generated/<version>/`. On 26.3, two runs match byte for byte (10,047 files), and a Linux run (WSL, OpenJDK 25.0.4.1) matches a Windows run (Temurin 25.0.5).

## Layout

| Path | What's there |
| --- | --- |
| `generated/26.3/datagen/reports/` | The generator's reports: the input to `convert.py` |
| `generated/26.3/datagen/data/` | Vanilla's built-in data pack as the generator writes it. Calcite doesn't read this copy: at runtime it reads the data pack from the jar (D61) |
| `generated/26.3/tables/` | The converted tables, described below |
| `generated/26.3/block_flags.json` | What each block state is, from vanilla's state cache, by [`block_flags.calx`](block_flags.calx) ([below](#block_flagsjson)) |
| `generated/26.3/entity_facts.json` | What natural spawning asks of each entity type and block state, by [`entity_facts.calx`](entity_facts.calx) ([below](#entity_factsjson)) |
| `generated/26.3/command_tree.json` | The dedicated server's command tree, by [`command_tree.calx`](command_tree.calx) ([below](#command_treejson)) |

## Table format

Every table is canonical, so the same reports always give the same bytes:

- UTF-8 with LF line endings, a two-space indent, and arrays of plain values on one line.
- Object keys are sorted. Wherever order means something, the table uses an array.
- **Numbers are written exactly as the report wrote them.** The reports mix float text (`1.8000001`) and widened-float double text (`0.10000000149011612`), so the converter never parses them into Python floats, and codegen has to read each with the precision its field needs.
- IDs are array positions: entry *i* of a registry, a packet list or `blocks` has ID *i*. The converter checks every report's IDs run from 0 with no gaps.

## Tables

### `index.json`

The game version the tables came from: `game_version`, `world_version` (the data version saves carry), `protocol_version`, `pack_version` and `java_version`, read from the jar's `version.json`. Also `jar_sha1`, `format` (this layout's version, now 1), and `tables`, the SHA-256 of every table.

### `registries.json`

All 95 built-in registries: `{"minecraft:block": {"id": 4, "default": "minecraft:air", "entries": [...]}}`. `id` is the registry's own ID, `default` its default entry or null, and `entries` its entries in ID order. Data-driven registries such as biomes aren't here; they come from data packs.

### `blocks.json`

Blocks in registry order, with their states described by arithmetic instead of listed one by one:

```json
{"id": 8, "name": "minecraft:grass_block", "first_state": 8, "state_count": 2, "default_state": 9, "properties": [100]}
```

- A block owns the global state IDs `first_state` to `first_state + state_count - 1`. Blocks follow each other with no gaps, so `state_count` (35,723 on 26.3) is the total.
- `properties` indexes the `properties` table, in name order. The state at `first_state + i` is the mixed-radix number `i` over those properties, with the last changing fastest. For `oak_stairs` (`facing`, `half`, `shape`, `waterlogged`), `i = ((facing × 2 + half) × 5 + shape) × 2 + waterlogged`, each the index of the value in its list.
- The `properties` table holds each distinct property once (121 on 26.3), sorted by name and then values: `{"name": "facing", "values": ["north", "south", "west", "east"], "kind": "enum"}`. `kind` is `bool` (values `true`, `false`), `int` (with `min` and `max`; values consecutive) or `enum`. Properties can share a name with different values: `facing` exists with four values, five (hoppers add `down`) and six.

The converter checks every state in the report against this rule, and that each block has exactly one default state. The report itself lists properties in a different order (its JSON writer sorts keys with `type` first), which is why the converter sorts them. The `block_state` rig probe confirms the result against the live game for every block and state.

### `items.json`

Items in registry order: `{"id": 1, "name": "minecraft:stone", "components": {...}}`, where `components` is the item's default data components, as the report gives them.

### `packets.json`

Packet names in ID order, by protocol phase and direction: `{"play": {"clientbound": [...], "serverbound": [...]}}`. The phases are `handshake`, `status`, `login`, `configuration` and `play`.

### `commands.json`

The command tree as the report gives it: nodes with `type` (`root`, `literal`, `argument`), `children`, and where they apply `executable`, `parser`, `properties`, `redirect` and `permissions`. The report sorts each node's children by name, so this doesn't record the order commands register in, which decides how ambiguous input parses. That has to come from probes.

### `biome_parameters.json`

The multi-noise biome parameter lists vanilla defines in code rather than in its data pack: `minecraft:overworld` and `minecraft:nether`, each a list of biomes with their climate parameter ranges.

### `datapack_registries.json` and `management_api.json`

The report of what data packs can define (each registry's `elements`, `tags` and `stable` flags), and the JSON-RPC schema of the server management API.

### `block_flags.json`

What each block state is that the reports don't say: whether it's air, takes random ticks, holds a fluid and whether that ticks, lets skylight down undimmed, uses its shape to stop light, can occlude, renders as a solid cube or has a block entity, and the light it gives and takes away. Vanilla works these out once for each state, in its state cache, so [`block_flags.calx`](block_flags.calx) asks the game: it runs the vanilla adapter's `BlockFlags`, which reads each state in ID order and writes `{"game_version", "states", "flags"}`, with `flags` a number for each state, its bits as `world.block_flags` names them (D164). It's beside `tables/`, not in it, since `convert.py` replaces that folder whole, and it needs the [vanilla adapter](../vanilla-adapter/README.md) built first:

```sh
calx oracle/datagen/block_flags.calx
```

It also has the faces light sees, for `world.light` (CAL-66): `light_faces`, each state's shape on each of its six sides as `LightEngine.getOcclusionShape` gives it, a number for each different shape, 0 the empty one and 1 the whole face; `face_boxes`, each shape's boxes; and `face_occludes`, for each two shapes, whether `Shapes.faceShapeOccludes` says light can't pass between them.

And it has what features ask of states and blocks (CAL-84): `facts`, a number for each state with its bits as `world.block_facts` names them. These cover legacy solidity, replaceability, a full-block collision shape, liquid, ignited by lava, redstone conductor, each face's sturdiness for `FULL`, `CENTER` and `RIGID` support, each face of the collision shape whole, each face of the occlusion shape whole, whether the shape reaches the top, whether it's empty, and the state's fluid and amount. It has `classes`, every block class a block is or extends that some rule asks about, and `class_parents`, each one's superclass among them. `survive_classes`, `place_on_classes` and `shape_classes` give, for each block, the class whose `canSurvive`, `mayPlaceOn` and `updateShape` it runs, found by asking which class declares them; and `neighbour_classes`, `place_classes`, `removal_classes` and `tick_classes` the class whose `neighborChanged`, `onPlace`, `affectNeighborsAfterRemoval` and `tick` it runs, what it does as a block beside it changes, as it's placed, once it's gone and as its scheduled tick runs (D325), and `random_tick_classes` the class whose `randomTick` it runs, what it does as a random tick comes to it (D338), and `precipitation_classes` the class whose `handlePrecipitation` it runs, what it does as rain or snow falls on it (D340), and `signal_classes`, `direct_signal_classes`, `own_signal_classes` and `signal_source_classes` the class whose `getSignal`, `getDirectSignal`, `ownSignal` and `isSignalSource` it runs, the redstone signal it gives (D345), and `has_analog_classes` and `analog_classes` the class whose `hasAnalogOutputSignal` and `getAnalogOutputSignal` it runs, what a comparator reads of it (D351). With them, `item_stack_sizes`, each item whose default `max_stack_size` isn't 64, with it, read once the items' default components are bound, as a server binds them (D351). `flammable_blocks` lists the blocks `FireBlock` can burn, its ignite odds above 0, read from the fire block, and `fire_odds` each block either of its odds is above 0 for, with its ignite odds and its burn odds (D339). `poi` lists each state with a point of interest and its type's ID, from `PoiTypes.forState`. `block_entities` lists each block with a block entity and the type `BlockEntityType.isValid` holds for its default state. `outline_differs` lists the states whose shape, their outline, is a full block where their collision shape isn't, or the other way round, which `LavaSubmergedBlockProcessor` asks. `wall_cover` lists the states whose collision shape's bottom covers `WallBlock`'s test shapes, its post's and each side's, otherwise than all of them where that face is full and none where it isn't, each with a bit for each it covers, which a wall's shape asks of the block above it. `own_suffocation` lists the states whose `isSuffocating` is their block's own, not the default, `causes_suffocation` with a full collision shape, each with whether it suffocates at the origin of an empty world, where a shulker box has no block entity and so does (D425). `turns` lists each state that `BlockState.rotate` or `mirror` changes, with what turning it clockwise 90, 180 and counterclockwise 90 and mirroring it left to right and front to back make of it; `calx_tables.py` checks that the 180 and counterclockwise turns are the clockwise one made twice and three times, and writes the clockwise turn and the two mirrors as how far each state is from what it becomes. `waterloggable_blocks` and `liquid_containers` list the blocks that are `SimpleWaterloggedBlock`s and the other `LiquidBlockContainer`s, and `dynamic_shape_blocks` those whose `hasDynamicShape` holds, which structure templates ask. `instruments` gives each block's `instrument()`, the one a note block plays over it, as an index into `instrument_names`, `NoteBlockInstrument`'s names in its order, and `instruments_above` the ones that play from above a note block, `worksAboveNoteBlock`; `BlockFlags` checks each block's states all have the one (D332).

And it has the faces a fluid sees, for `FlowingFluid.canPassThroughWall` (D327): `fluid_faces`, each state's collision shape with an empty context toward each of its six sides as `Shapes.mergedFaceOccludes` slices it, empty unless the shape reaches that side of its block, else the boxes that reach it, laid flat on the side's other two axes and numbered as the light's faces are; `fluid_face_boxes`, each face's boxes; and `fluid_covers`, for each two faces, whether they cover a face of a block between them. A state vanilla offsets by its position whose collision shape isn't empty, as pointed dripstone, moves, so its faces depend on where it is: `fluid_moving` gives each its boxes before they're offset and where its shape's grid starts and ends on each axis, as `mergedFaceOccludes` slices the grid's end cell, which an offset can leave empty, and `offsets` each block with an offset, whether it's offset up and down too, and the bits of how far it goes at most each way. `BlockFlags` checks these against vanilla's own `canPassThroughWall`, by reflection, before it writes them: every two shapes the states have, each way round and toward each side, and each state that moves at 24 places against every shape, and fails if any differs; that takes about two and a half minutes, and `block_flags.calx` prints how many it checked. `fluid_cases` are some of those places, most where moving changes the answer, and `offset_cases` where those states are offset, for Calcite's test.

And it has what entities move against (CAL-148, D388): `movement`, each state's collision shape with an empty context, before vanilla offsets it by its position, so a liquid has none and scaffolding is whole, numbered as the collision shapes are; `movement_boxes`, each shape's boxes; `movement_factors`, each block whose friction, speed factor, jump factor, bounce or fall distance reduction isn't the default, 0.6, 1, 1, 0 and 0, with the bits of the five floats (D398); and `movement_cases`, up to 8 boxes near each shape, an item's, a player's or a block's size, that don't overlap it by more than 1.0E-7, half against a face of one of its boxes, each moved along an axis by up to a block and a half either way, with the distance vanilla's own `VoxelShape.collide` gives, drawn from `java.util.Random(148)` so each run writes the same; `block_flags.calx` prints how many there are and how many stopped short.

And each state's outline shape (CAL-159, D465): `outline`, `getShape` with an empty context, as `ClipContext.Block.OUTLINE` reads it, numbered as the collision shapes are, with each shape's boxes in `outline_boxes`. Of the states with an offset, only some move their shape by it, as a flower does, which a short grass doesn't: those, whose shape differs at the first place along x where the offset does, have their shape before it's offset and are listed in `outline_moved`. A shape that goes by its block entity, as a shulker box's, is the empty world's.

And it has what digging reads of each block (D376): `destroy_speeds`, each block's `getDestroySpeed`, in block ID order, and `needs_tool_blocks`, the blocks whose states require the right tool for their drops, each checked the same for every state of its block before it's written.

And it has what placing reads (D378): `placement_classes`, `replace_classes`, `placed_by_classes`, `use_item_classes` and `use_classes`, the class declaring each block's `getStateForPlacement`, `canBeReplaced(BlockPlaceContext)`, `setPlacedBy`, `useItemOn` and `useWithoutItem`, in block ID order; `block_items`, each block item as `[item, block, class, wall block, attachment]`, by ID and the class's simple name, the last two a `StandingAndWallBlockItem`'s wall block and the 3D data value of its `attachmentDirection`, else -1 and -1; `items_of_blocks`, each block's `asItem`, by ID, in block ID order; `place_sounds`, the states' different sound types, each its place sound with its volume and pitch, and its step and fall sounds (D398); and `state_place_sounds`, each state's, by its index there.

Which heightmaps count a state isn't here: in 26.3 that comes from the data pack's tags, which Calcite reads as it starts.

### `entity_facts.json`

What natural spawning asks of each entity type and block state (D317), which the reports don't say, so [`entity_facts.calx`](entity_facts.calx) asks the vanilla adapter's `EntityFacts`, which reads vanilla's own types and states:

```sh
calx oracle/datagen/entity_facts.calx
```

`categories` lists the `MobCategory` names in order. Each of `types`, in ID order, has its category; whether it can be summoned, is immune to fire, can spawn far from players and is allowed in peaceful; the block tag it's immune to; its spawn box's half width and height; and its `spawn_group`, which of the four kinds of type `isValidSpawn` treats differently it is: any other, immune to fire, ocelots and parrots, and polar bears. A type registered in `SpawnPlacements` also has its `placement`, `heightmap` and `rule`, the class and method of its spawn predicate. The predicates are lambdas and method references, so `EntityFacts` reads `SpawnPlacements`' class initializer with `java.lang.classfile` to find which method each type's is. `states` has a number for each block state, in ID order: bit 0 whether it's a signal source, and bit 1 + g whether `isValidSpawn` holds for spawn group g. `attributes` has each attribute, in ID order, with its `default`, the `min` and `max` `RangedAttribute.sanitizeValue` keeps it between, and whether it's `synced` to clients; `player_attributes` has those `DefaultAttributes` gives a player, in ID order, each with its `base` (D375); `type_attributes` has every type `DefaultAttributes` has a supplier for, by type ID, each with its attributes' IDs and bases (D398). And what pathfinding reads of each state (D409): `paths`, a number for each state, bits 2t and 2t + 1 what `isPathfindable` gives for the t-th of `LAND`, `WATER` and `AIR`, never, always, where its fluid is in `#water` or where it isn't in `#lava`, which `PathFacts` tells apart by asking with no fluid in either tag and with every fluid in both, and from bit 6 the class `getPathTypeFromState` asks about that it is, a door open, shut and opened by hand or not, a rail, leaves or a shut fence gate; `path_type_names` and `path_maluses`, `PathType`'s in its order; and, once `EntityFacts` has loaded vanilla's tags and checked every state's path type worked out from its facts and those tags against vanilla's own `getPathTypeFromState`, failing if any differ, `path_types`, what that gives each state, and `path_block_tags` and `path_fluid_tags`, the tags it reads with vanilla's blocks and fluids in them, for Calcite's test.

### `command_tree.json`

The dedicated server's command tree (D552, [CAL-165](https://acta.aaenz.no/aaen-studios/calcite#CAL-165)). The reports' `commands.json` sorts each node's children by name, but the commands packet numbers the nodes breadth first in the order vanilla registered them, and says which need a permission, so [`command_tree.calx`](command_tree.calx) asks the vanilla adapter's `CommandTree`, which walks vanilla's own `Commands` as a dedicated server builds it:

```sh
calx oracle/datagen/command_tree.calx
```

Each of `nodes`, the root first, then each node and its children's in turn, has its kind, its name, its children by their places, whether it's executable, the node it redirects to or -1, and the lowest permission level whose source may use it, `canUse`; an argument has its type's ID and name in `command_argument_type`, its properties as `serializeToNetwork` writes them, in hex, and its custom suggestions' name where it has them. 26.3's has 2471 nodes and 92 commands, ten of them for every player.

## What's compiled in and what's loaded (D61)

Calcite compiles in what vanilla defines in code: everything in `tables/`. Codegen turns it into constant arrays, so a state lookup is arithmetic and an array read, with nothing parsed at startup. What vanilla loads from its built-in data pack (data-driven registries such as biomes, dimension types and damage types, worldgen settings, tags, loot tables, recipes, advancements and structure templates) Calcite loads at startup from the jar, through the same loader user data packs go through, so a data pack can override it as it can in vanilla.

## Calx modules

[`calx_tables.calx`](calx_tables.calx) writes the Calx modules Calcite compiles in from `tables/` (D126), with [`block_tables.calx`](block_tables.calx), which writes those from `block_flags.json`, and [`tablekit.calx`](tablekit.calx), what they share:

```sh
calx oracle/datagen/calx_tables.calx            # write them from generated/26.3/tables
calx oracle/datagen/calx_tables.calx --check    # fail if a committed one is out of date
```

| Module | From | What it holds |
| --- | --- | --- |
| `src/protocol/ids.calx` | `index.json`, `packets.json` | `PROTOCOL_VERSION`, `DATA_VERSION`, the data version saves are written with, `game_version()`, and `packet_names(state, bound)`, each state's packets in ID order, which `@packet` reads its IDs from |
| `src/registry/builtin.calx` | `registries.json` | `builtin_names()`, the 95 built-in registries in the order of their IDs, and `builtin_entries(i)`, each one's entries in ID order |
| `src/pack/pin.calx` | `../versions.json` | `jar_version()`, `jar_url()`, `jar_sha1()` and `JAR_SIZE`: the pinned server jar, which the rig checks; `client_url()`, `CLIENT_SIZE`, `DATA_OFFSET`, `DATA_LENGTH` and `data_sha256()`: the pinned client jar and the stretch of it holding the vanilla data, which the server reads or downloads and checks (D140) |
| `src/world/blocks.calx` | `blocks.json` | `STATE_COUNT`, `first_states()`, each block's first state ID, and `default_offsets()`, where its default state is among its states, in block ID order; `property_names()` and `property_values()`, every property and its values in vanilla's order, and `property_starts()` and `block_properties()`, each block's properties by name, which `world.states` names states with |
| `src/world/block_flags.calx` | `../block_flags.json` | The flags' constants, and `state_flags()`, each state's flags in ID order. The 35,723 states are a printable character each, an index into the 102 different values, commonest first, in lines of 96; the 13 rarest take two, after `~`. It's decoded once, as the server starts |
| `src/world/block_facts.calx` | `../block_flags.json` | The facts' constants, `state_facts()` and `state_fluids()`, each state's facts and its fluid and amount, a character a state as in `block_flags.calx`; `class_names()`, `block_classes()` and `class_parents()`, the classes and which one each block is; `survive_classes()` and `place_on_classes()`; `neighbour_classes()`, `place_classes()`, `removal_classes()` and `tick_classes()` (D325), and `random_tick_classes()` (D338), and `precipitation_classes()` (D340), and `signal_classes()`, `direct_signal_classes()`, `own_signal_classes()` and `signal_source_classes()` (D345), and `has_analog_classes()` and `analog_classes()`, with `small_stack_items()` and `small_stack_sizes()`, the items whose default `max_stack_size` isn't 64 and theirs (D351); `push_reactions()`, each block's `getPistonPushReaction` by its ordinal, and `unbreakable_blocks()`, those whose destroy speed is -1, each checked the same for every state of its block (D352); `destroy_speeds()`, each block's destroy speed, and `needs_tool_blocks()`, those that drop nothing unless dug with the right tool, `requiresCorrectToolForDrops`, each checked the same for every state of its block (D376); `toggle_sound_blocks()`, `toggle_sounds_on()` and `toggle_sounds_off()`, the doors, trapdoors, fence gates, buttons and pressure plates and the sounds each plays on and off, by the sound event's name (D353); `button_tick_blocks()` and `button_ticks()`, each button and how long it stays pressed, and `plate_weight_blocks()` and `plate_weights()`, each weighted pressure plate and how many entities it weighs at most (D354); `fire_odds()`, each block fire's odds are above 0 for with its ignite and burn odds (D339); `poi_states()`, each state with a point of interest and its type; and `block_entity_names()` and `block_entity_blocks()`, the block entity types and each block's; `outline_differs()`; `wall_cover()`; `own_suffocation()` (D425); and `instrument_names()`, `block_instruments()` and `instruments_above()` (D332); `placement_classes()`, `replace_classes()`, `placed_by_classes()`, `use_item_classes()` and `use_classes()`, `block_item_kind_names()`, `block_items()`, `wall_block_items()`, `items_of_blocks()`, `place_sound_names()`, `place_sound_volumes()`, `place_sound_pitches()` and `state_place_sounds()`, what placing reads (D378), and `step_sound_names()` and `fall_sound_names()`, what an entity's steps and falls play (D398) |
| `src/world/fluid_faces.calx` | `../block_flags.json` | `state_fluid_faces()`, each state's six fluid faces, packed in `FLUID_FACE_BITS` each, as an index into the different sets, a character or two a state; `fluid_covers()`, for each of the `FLUID_FACES` faces, `COVER_WORDS` words of a bit for each face it and a fluid can't pass between; `face_starts()` and `face_rects()`, each face's rectangles in 32nds; `moving_states()`, `moving_grids()`, `moving_starts()` and `moving_boxes()`, the states that move with their grids' ends and boxes; `offset_blocks()`; and `wall_cases()` and `offset_cases()`, for `test/fluid_faces.calx` (D327) |
| `src/world/movement_shapes.calx` | `../block_flags.json` | `SHAPES`, `state_shapes()`, `shape_starts()` and `shape_boxes()`, each state's shape as an entity moves against it, laid out as `collision_shapes.calx`'s are; `factor_blocks()` and `factors()`, each block whose friction, speed factor, jump factor, bounce or fall distance reduction isn't the default and the bits of the five (D398); and `collide_cases()`, every case vanilla stopped short and one in eight of the others, ten numbers each, for `test/movement.calx` (D388) |
| `src/world/outline_shapes.calx` | `../block_flags.json` | `SHAPES`, `state_shapes()`, `shape_starts()` and `shape_boxes()`, each state's outline shape laid out as `collision_shapes.calx`'s are; `exact_shapes()`, `exact_starts()` and `exact_boxes()`, the shapes whose coordinates aren't 32nds of a block, a lectern's thirds, as `f64`s; and `moved_states()`, the 110 states whose shape moves by their offset (D465) |
| `src/world/light_faces.calx` | `../block_flags.json` | `state_faces()`, each state's six faces, packed in `FACE_BITS` each, as an index into the 53 different sets, a character a state; and `face_occludes()`, for each of the `FACE_SHAPES` shapes, a bit for each shape light can't pass between it and |
| `src/world/item_defaults.calx` | `items.json` | Each item's default components as vanilla's JSON: `shared_components()`, the ones more than half the items have with one value; `block_named_items()`, the items whose name is `block.minecraft.<name>` rather than `item.minecraft.<name>`; and `item_patches()`, each item's others as a patch of the shared ones, `!` before a shared one it hasn't. Its model is its name. `calx_tables.py` checks both, and that nothing else is shared (D362) |
| `src/world/entity_facts.calx` | `../entity_facts.json` | The categories in order and their serialized names; the type flags', placements' and state facts' constants; `rules()`, the spawn predicates' names; `immune_tags()`; `types()`, each type's `TypeFacts` in ID order; `state_spawn_facts()`, each state's spawn facts, a character a state as in `block_flags.calx`; and the attributes' `attribute_names()`, `attribute_defaults()`, `attribute_mins()`, `attribute_maxes()` and `synced_attributes()`, with a player's `player_attributes()` and `player_attribute_bases()` (D375), and every living type's, `living_types()`, `living_attribute_starts()`, `living_attributes()` and `living_attribute_bases()` (D398); `state_path_facts()`, each state's path facts, a character a state, with `PathType`'s `PATH_` constants, `path_type_names()` and `path_maluses()`; and for `test/paths.calx`, `vanilla_path_types()`, each state's path type with vanilla's tags, and those tags, `path_block_tag_names()`, `path_block_tag_blocks()`, `path_fluid_tag_names()` and `path_fluid_tag_fluids()` (D409) |
| `src/command/tree.calx` | `../command_tree.json` | `NODES`; `node_parents()`, each node's parent; `node_facts()`, its kind, whether it runs, its permission level, its custom suggestions in `suggestion_names()`, its properties' size and its argument type, packed; `node_names()`; `node_properties()`, one after another; and `node_redirects()`, each node that redirects and where |

They're committed, and hold only the names, IDs and facts about states the protocol and the world need, which every compatible server encodes. Don't edit one: change the script and run it again. A new game version that changes them changes Calcite's build, which is the point: `@packet` then fails to compile for a packet that was renamed or removed.

## Tests

```sh
py -I -m unittest discover -s oracle/datagen/tests -v    # the converter's
calx test oracle/datagen/tests/test_calx_tables.calx     # the Calx modules'
```

The tests use only small made-up reports, so they never need the jar. The converter's cover number text surviving conversion, the canonical layout, ID gap checks, the mixed-radix rule and what breaks it, property kinds, and the fetch step's checks offline. The others cover the Calx modules `calx_tables.calx` writes, and the tables it refuses, each in a process of its own, as the tool stops there. Where the tables have been generated, they also check that the committed modules are current. CI runs the converter's with the rig's tests, and the others with Calcite's score.

## A new game version

1. `calx oracle/fetch.calx --version <v> --pin` records the jar's URL, size and SHA-1 from Mojang's manifest in `versions.json`. Commit that.
2. `py -I oracle/datagen/datagen.py --version <v>`. If the converter stops on a check, the game changed something codegen relies on: update the converter and this page together.
3. `py -I oracle/datagen/datagen.py --version <v> --check`.
4. `calx oracle/datagen/calx_tables.calx --version <v>`, then build Calcite and run its tests: a renamed or removed packet fails to compile where it's declared.
