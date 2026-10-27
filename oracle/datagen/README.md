---
title: Data generator and tables
description: How Calcite turns Mojang's server jar into the tables its codegen reads, in one repeatable command.
---

# Data generator and tables

Calcite's block states, registries, item defaults, packet IDs and command tree come from Mojang's own data generator, run on the official server jar (Phase 2). One command fetches the jar, runs the generator, and converts its reports into neutral tables that Calx codegen reads. None of it is committed: `generated/` is gitignored (D30).

```sh
py -I oracle/datagen/datagen.py            # fetch, generate and convert into generated/26.3/
py -I oracle/datagen/datagen.py --check    # regenerate into a scratch folder and compare, byte for byte
py -I oracle/datagen/convert.py            # convert again from the existing reports only
py -I oracle/fetch.py [--check]            # fetch and verify the jar on its own
py -I oracle/fetch.py --jar <path>         # or install a jar you already have, with no network
```

`datagen.py` takes `--version` (default `26.3`) and `--java-home`. It finds JDK 25 the same way the [vanilla adapter's build](../vanilla-adapter/README.md#building) does. On Linux, use `python3` for `py`. A full run takes about 12 seconds on Windows.

## What it does

1. **Fetch.** [`../fetch.py`](../fetch.py) checks `oracle/jars/server-<version>.jar` against the SHA-1 pinned in [`../versions.json`](../versions.json), and downloads it from Mojang if it's missing or wrong (`P2.4`, D62). A jar you already have can be installed with `fetch.py --jar <path>`, as long as it's the pinned one.
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

## What's compiled in and what's loaded (D61)

Calcite compiles in what vanilla defines in code: everything in `tables/`. Codegen turns it into constant arrays, so a state lookup is arithmetic and an array read, with nothing parsed at startup. What vanilla loads from its built-in data pack (data-driven registries such as biomes, dimension types and damage types, worldgen settings, tags, loot tables, recipes, advancements and structure templates) Calcite loads at startup from the jar, through the same loader user data packs go through, so a data pack can override it as it can in vanilla.

## Tests

```sh
py -I -m unittest discover -s oracle/datagen/tests -v
```

The tests use only the standard library and small made-up reports, so they never need the jar. They cover number text surviving conversion, the canonical layout, ID gap checks, the mixed-radix rule and what breaks it, property kinds, and the fetch step's checks offline. CI runs them with the rig's tests.

## A new game version

1. `py -I oracle/fetch.py --version <v> --pin` records the jar's URL, size and SHA-1 from Mojang's manifest in `versions.json`. Commit that.
2. `py -I oracle/datagen/datagen.py --version <v>`. If the converter stops on a check, the game changed something codegen relies on: update the converter and this page together.
3. `py -I oracle/datagen/datagen.py --version <v> --check`.
