---
title: Rig protocol
description: The wire format between the rig's runner and an adapter, and the signature of every probe.
---

# Rig protocol

The runner talks to an adapter (the vanilla one in Java, or Calcite's) over the adapter's standard input and output. This page is the whole contract, so an adapter can be written from it alone, in any language, sharing no code with Calcite (`P1.7`).

Protocol version: **1**.

## Frames

Every message in either direction is one frame:

| Bytes | Content |
| --- | --- |
| 4 | Header length *n*, unsigned, big-endian |
| *n* | The header: one JSON object, UTF-8 |
| ... | The blobs the header lists, back to back |

The header's `blobs` field lists each blob's length in bytes, in order. It's `[]` or missing when there are none. Blobs carry anything binary or anything that must keep exact bits: NBT, floats, packed results.

The adapter writes only frames to standard output. Logs go to standard error, which the runner saves but never parses.

## Messages

The runner sends one request and waits for its response before sending the next.

### `hello`

The first request.

```json
{"type": "hello", "protocol": 1}
```

The adapter answers with what it is and which probes it knows, each with its version:

```json
{"type": "hello", "protocol": 1, "adapter": "vanilla", "game_version": "26.3",
 "probes": {"ping": 1, "rng": 1, "nbt": 1, "text": 1, "math": 1, "strictmath": 1, "mth": 1},
 "about": {"java.vm.version": "25.0.5+8-LTS", "os.arch": "amd64"}}
```

A probe the adapter doesn't list is reported as unimplemented, without being run. `about` is optional and free-form: whatever the adapter thinks a result depends on, such as the JVM build. The runner records it beside the goldens.

### `run`

Runs one case of one probe.

```json
{"type": "run", "id": 7, "probe": "rng", "case": "legacy-seed-0", "input": {...}, "blobs": [12]}
```

The adapter answers with the same `id`:

```json
{"type": "result", "id": 7, "status": "ok", "output": {...}, "blobs": [40]}
```

`status` is one of:

- **`ok`**: the probe ran. `output` and the blobs are the result.
- **`unimplemented`**: the adapter knows the probe but not this part of it.
- **`error`**: the adapter itself failed, such as an exception in its own code, with a `message`.

An input that the game itself rejects, such as SNBT with a syntax error, is still `ok`. The rejection is the result, and it's compared like any other. Unless a probe says otherwise, a rejection's output is:

```json
{"exception": "CommandSyntaxException", "error": "Expected a valid unquoted string at position 3: {a:<--[HERE]"}
```

`exception` is the simple name of the class vanilla threw, and `error` is its message, or `""` if it has none. Calcite's adapter maps its own errors to the same names. The messages matter, since players see many of them.

### `bye`

```json
{"type": "bye"}
```

The adapter answers `{"type": "bye"}` and exits with status 0.

## Results and hashes

The runner hashes each `ok` result with SHA-256 over:

1. The `output` object as canonical JSON: keys sorted, no whitespace, UTF-8, non-ASCII characters written as themselves.
2. For each blob in order: its length as 8 bytes, unsigned, big-endian, then its bytes.

The hash of vanilla's result is what gets committed, in `expected/26.3/<probe>.json`.

So that results hash the same from any language:

- **Never put a float in JSON.** Floats go in blobs as raw IEEE bits, big-endian.
- **Integers in JSON stay within ±2^53.** A 64-bit value (a seed, a `long` result) is a decimal string.
- **Strings are compared exactly.** No trimming, no normalization.
- **Nulls are written.** A field whose value is `null` stays in the output as `null`, never left out. Some JSON libraries drop null fields by default, as Gson does, and that changes the hash.

## Case files

Case inputs are committed in `cases/<probe>/<group>.json`:

```json
{
  "probe": "rng",
  "probe_version": 1,
  "cases": [
    {"id": "legacy-seed-0", "input": {"kind": "legacy", "seed": "0", "ops": [["nextInt"], ["nextLong"]]}}
  ]
}
```

- `id` is unique within the probe, and uses only `a-z`, `0-9`, `.`, `_` and `-`.
- A case with blobs lists them in `"blobs"`. Each is base64, or a readable form such as `{"f64": ["1.5", "nan"]}` or a seeded generator, which the runner expands to bytes before sending. Adapters only ever see bytes. The forms are listed in [`README.md`](README.md#blobs-in-case-files).
- Generated case files say what generated them in a top-level `"generated_by"` field, and the generator is committed beside them with its seed.
- A case that only one system can run, such as one that makes symbolic links, which Windows doesn't let most users make, or one whose paths only one system writes, says so with `"system": "windows"` or `"linux"`. On any other system it isn't recorded or run, and scores as elsewhere; its expected hash, recorded on its own system, is kept when the others are recorded again.
- A case whose blobs vanilla fills in an order that changes from run to run says `"unordered": true`. The runner sorts each NBT compound in its blobs by key, by the bytes of its name, before it hashes them, for every adapter, so only what's in them is compared. Only `registries` contents cases use it, where vanilla's `Map.copyOf` over keys hashed by identity puts entries that share a bucket in a different order each run (D192).

## Probes

Each probe is a pure function of its input. Version numbers change when a probe's input or output format changes, and old expected hashes are re-recorded.

### `ping` (v1)

Input `{"echo": <any JSON>}` and any blobs. Output `{"echo": <the same>}` and the same blobs. For testing the rig itself.

### `rng` (v1)

Runs a sequence of operations on one of vanilla's random sources.

Input:

- `kind`:
  - `legacy`: `LegacyRandomSource`, Java's 48-bit LCG, what `RandomSource.create(seed)` gives
  - `single_threaded`: `SingleThreadedRandomSource`, the same LCG without atomics, what `createThreadLocalInstance(seed)` gives
  - `xoroshiro`: `XoroshiroRandomSource` from a 64-bit seed
  - `xoroshiro128`: `XoroshiroRandomSource` from `seed_lo` and `seed_hi`
  - `worldgen_legacy` and `worldgen_xoroshiro`: `WorldgenRandom` over either
- `seed`: a decimal string. For `xoroshiro128`, `seed_lo` and `seed_hi` instead.
- `ops`: a list of operations, each a list whose first element is its name.

Output: `{}` and one blob, the concatenation of every operation's result in order. `int` is 4 bytes, `long` 8, `float` 4 (bits), `double` 8 (bits), `boolean` 1 (0 or 1), all big-endian.

| Operation | Result |
| --- | --- |
| `["nextInt"]` | int |
| `["nextInt", bound]` | int, `nextInt(bound)` |
| `["nextIntRange", origin, bound]` | int, `nextInt(origin, bound)` |
| `["nextIntBetween", min, max]` | int, `nextIntBetweenInclusive` |
| `["nextLong"]` | long |
| `["nextBoolean"]` | boolean |
| `["nextFloat"]` | float |
| `["nextDouble"]` | double |
| `["nextGaussian"]` | double |
| `["triangle", mean, spread]` | double, with `mean` and `spread` as decimal strings parsed by `Double.parseDouble` |
| `["setSeed", seed]` | nothing |
| `["consume", n]` | nothing; `consumeCount(n)` |
| `["fork"]` | nothing; the source becomes `fork()` |
| `["at", x, y, z]` | nothing; the source becomes `forkPositional().at(x, y, z)` |
| `["fromHashOf", name]` | nothing; the source becomes `forkPositional().fromHashOf(name)` |
| `["fromSeed", seed]` | nothing; the source becomes `forkPositional().fromSeed(seed)` |
| `["setDecorationSeed", seed, chunkX, chunkZ]` | long, on `worldgen_*` only |
| `["setFeatureSeed", seed, index, step]` | nothing, on `worldgen_*` only |
| `["setLargeFeatureSeed", seed, chunkX, chunkZ]` | nothing, on `worldgen_*` only |
| `["setLargeFeatureWithSalt", seed, x, z, salt]` | nothing, on `worldgen_*` only |

Seeds inside operations are decimal strings too.

If the game throws, as `nextInt(0)` does, the run stops there. The output is the rejection plus `"at"`, the operation's index, and the blob holds the results before it. An operation that doesn't apply to the current source, such as `setDecorationSeed` after `fork`, is an `error` status: the case is wrong, not the game.

### `nbt` (v1)

Input, one of:

- `{"from": "snbt", "snbt": "..."}`: parsed with `TagParser.parseCompoundFully`, as data files and most commands do
- `{"from": "snbt_any", "snbt": "..."}`: any tag, not just a compound, parsed with `TagParser.create(NbtOps.INSTANCE).parseFully`
- `{"from": "binary"}` with one blob: a tag in network form (a type byte, then the payload, no name), read with `NbtIo.readAnyTag` and no size limit

Output: `{"snbt": <the tag's toString()>, "type": <the tag type ID>, "network": "ok"}` and two blobs:

1. The **network form**, written with `NbtIo.writeAnyTag` as `FriendlyByteBuf.writeNbt` does. If that throws, as it does for a string over 65,535 bytes, `network` is the rejection and this blob is empty.
2. The **file form**, written with `NbtIo.writeUnnamedTagWithFallback` as `NbtIo.write` does for saves: a type byte, an empty name, then the payload, with any over-long string written as `""`.

If parsing fails, the output is the rejection and there are no blobs. The SNBT parser has no depth limit of its own, so deeply nested input overflows the stack. That's reported as a `StackOverflowError` rejection, and the self-check decides whether it's repeatable.

Strings in binary NBT are Java's modified UTF-8, so a character outside the Basic Multilingual Plane is two 3-byte surrogates, not one 4-byte sequence.

### `text` (v1)

Input, one of:

- `{"json": "..."}`: a text component as JSON, as data packs write them
- `{"snbt": "..."}`: as SNBT, as commands like `/tellraw` take them since 1.21.5

The component is decoded with `ComponentSerialization.CODEC`, using `RegistryOps` over vanilla's built-in registries (`VanillaRegistries.createWorldLookup()`), so hover events can show items and entities.

Output: `{"json": <re-encoded with the same codec, written by GsonHelper.toStableString>, "plain": <getString()>}` and one blob, the component encoded as NBT and written with `NbtIo.writeAnyTag`. That's the network form since 1.20.3. `toStableString` sorts object keys, so `json` doesn't depend on codec field order. `plain` is resolved with vanilla's `en_us` language file.

If the JSON or SNBT doesn't parse, the output is the rejection. If the codec rejects it: `{"error": <the codec's message>}`.

### `math` and `strictmath` (v2)

Input `{"fn": <name>}` and one blob of `f64` arguments, big-endian. `atan2`, `pow` and `hypot` take them in pairs.

Output: `{}` and one blob, `java.lang.Math.<fn>` (for `math`) or `java.lang.StrictMath.<fn>` (for `strictmath`) of each argument, as `f64` bits from `Double.doubleToLongBits`, so every NaN is `0x7ff8000000000000`. v1 wrote `doubleToRawLongBits`, where `Math.log` of a negative gave `0x7ff8…` and `StrictMath.log` x86's `0xfff8…`: no code sees a NaN's sign, so v2 compares NaNs as NaNs (D208).

Functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `exp`, `log`, `log10`, `log1p`, `pow`, `sqrt`, `cbrt`, `sinh`, `cosh`, `tanh`, `expm1`, `hypot`.

Vanilla calls `Math`. In the rig's reference configuration (HotSpot's LIBM intrinsics off, D60), `Math` gives exactly `StrictMath`'s results but for NaNs' signs, so both probes' hashes are the same there. With HotSpot's default intrinsics they differ, and `rig/runner/mathcmp.py` measures by how much (`P1.5`).

### `mth` (v2)

Vanilla's `Mth` helpers that use lookup tables or bit tricks, where a natural reimplementation would round differently. Floats and doubles are written with `Float.floatToIntBits` and `Double.doubleToLongBits`, every NaN as one, as in `math` (v2, D208).

| Input | Output blob |
| --- | --- |
| `{"fn": "sin_table"}` | All 65,536 entries of `Mth`'s private sine table, in order, as `f32` bits. Entry *i* is `(float) Math.sin(i / 10430.378350470453)`. The vanilla adapter reads the table directly, since going through `Mth.sin` with an angle could round to the neighboring entry |
| `{"fn": "sin"}`, `{"fn": "cos"}` with a blob of `f64` arguments | `Mth.sin` or `Mth.cos` of each, as `f32` bits |
| `{"fn": "atan2"}` with a blob of `(y, x)` `f64` pairs | `Mth.atan2(y, x)` of each, as `f64` bits. It uses `Mth`'s own arcsine tables, not `Math.atan2` |
| `{"fn": "fast_inv_sqrt"}` with a blob of `f64` arguments | `Mth.fastInvSqrt` of each, as `f64` bits |
| `{"fn": "wrap_degrees"}` with a blob of `f32` arguments | `Mth.wrapDegrees(float)` of each, as `f32` bits |
| `{"fn": "floor"}` with a blob of `f64` arguments | `Mth.floor(double)` of each, as int |
| `{"fn": "get_seed"}` with a blob of `(x, y, z)` int triples | `Mth.getSeed(x, y, z)` of each, as long |

### `block_state` (v1)

Global block state IDs, the block registry's state layout, the command syntax for block states, and the NBT form chunks and structure templates store them in. A state is printed the way `BlockStateParser.serialize` prints it: `minecraft:oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]`, with the properties in name order and no brackets for a block that has none.

| Input | Output |
| --- | --- |
| `{"op": "by_id", "from": n, "count": c}` | `states`: the state for each ID from `n`, or null where the ID map has none (the game reads those as air). `defaults`: the IDs in the range that are their block's default state. `round_trip_mismatches`: the IDs whose state doesn't come back to the same ID when printed and parsed, or written to NBT and read back. `count` is 0 to 4,096 |
| `{"op": "blocks", "from": n, "count": c}` | `blocks`: for each block registry ID from `n`, null if there's no block, or `{name, first_state, state_count, default_state, properties}`. `properties` is the block's properties in the order the game keeps them, each `{name, values}` |
| `{"op": "parse", "input": s, "nbt": b}` | `BlockStateParser.parseForBlock` on `s`, allowing a `{...}` NBT suffix if `b`: `{id, state, written, given, nbt, cursor}`. `written` is the state's NBT form as SNBT, `given` the properties the input set, `nbt` the suffix as SNBT or null, and `cursor` where parsing stopped. A rejection if the parser throws |
| `{"op": "from_nbt", "snbt": s}` | `NbtUtils.readBlockState` on the compound `s`: `{id, state, written}`. It never rejects: an unknown block reads as air and a bad property is left at its default |

### `collections` (v1)

Runs a sequence of operations on one of the collections whose order shows in vanilla's behaviour: the order entities tick in, the order a set's blocks are written, ties in a scheduled tick queue. Each result goes into one blob, and so does the iteration order whenever an operation asks for it.

Input:

- `collection`:
  - `hash_map`, `hash_set`: `java.util.HashMap` and `HashSet`
  - `linked_hash_map`, `linked_hash_set`: `LinkedHashMap` and `LinkedHashSet`
  - `tree_map`, `tree_set`: `TreeMap` and `TreeSet`
  - `open_hash_map`, `open_hash_set`: fastutil's open hash tables, `Int2IntOpenHashMap`, `Long2IntOpenHashMap` or `Object2IntOpenHashMap<String>`, and `IntOpenHashSet`, `LongOpenHashSet` or `ObjectOpenHashSet<String>`
  - `priority_queue`: `java.util.PriorityQueue`, in natural order
  - `array_deque`: `ArrayDeque`
- `key`: `int`, `long` or `string`. Keys in operations are JSON strings, decimal for `int` and `long`. A map's values are `int`, as JSON numbers.
- `capacity`: optional, for `hash_map`, `hash_set`, `open_hash_map` and `open_hash_set` only. The table is made with the constructor that takes an expected size. Not negative.
- `ops`: a list of operations, each a list whose first element is its name.

Output: `{}` and one blob, every operation's result in order, big-endian:

- An `int` is 4 bytes, a `long` 8, a `string` a 4-byte length and then its UTF-8 bytes, and a boolean 1 byte, 0 or 1.
- A *maybe* is a 0 byte for nothing, or a 1 byte and then the thing.
- A key is written as its key type, and an *entry* is a key and then its `int` value.
- An *iteration* is an `int` count, then each key, or each entry for a map, in the collection's iteration order.

On every map:

| Operation | Result |
| --- | --- |
| `["put", k, v]` | maybe the previous value |
| `["get", k]`, `["remove", k]` | maybe the value |
| `["contains", k]` | boolean, `containsKey` |
| `["size"]` | int |
| `["clear"]` | nothing |
| `["iter"]` | iteration |

On every set:

| Operation | Result |
| --- | --- |
| `["add", k]`, `["remove", k]` | boolean, whether the set changed |
| `["contains", k]` | boolean |
| `["size"]`, `["clear"]`, `["iter"]` | as on maps |

On linked and tree maps and sets, with `poll_*` giving a maybe-entry on maps and a maybe-key on sets:

| Operation | Result |
| --- | --- |
| `["first"]`, `["last"]` | maybe the key, `firstKey`/`lastKey` or `getFirst`/`getLast` without throwing |
| `["poll_first"]`, `["poll_last"]` | `pollFirstEntry`/`pollLastEntry` or `pollFirst`/`pollLast`, or `SequencedMap`'s and `SequencedSet`'s `removeFirst`/`removeLast` |

On linked maps, `["put_first", k, v]` and `["put_last", k, v]` give maybe the previous value. On linked sets, `["add_first", k]` and `["add_last", k]` give nothing. Both move an existing key to that end.

On tree maps and sets, `["floor", k]`, `["ceiling", k]`, `["lower", k]` and `["higher", k]` give maybe the key, and `["range", a, b]` gives an iteration of the keys from `a` up to but not including `b`, with no values. A range whose end is before its start is an `error` status.

On open maps and sets, `["trim"]` gives nothing. It shrinks the table to fit, which changes the iteration order. `["remove_iter", m, r]` gives an iteration of every key, without values, in the order a loop over fastutil's iterator goes over them while it removes each key whose number, or string length, is `r` modulo `m` (`Math.floorMod`), as `TicketStorage.removeTicketIf` and `ChunkMap.processUnloads` do. A map's loop goes over its `fastIterator`. That order isn't always the table's, since a removal can move a key the loop hasn't reached past the table's end. `m` is positive.

On `priority_queue`:

| Operation | Result |
| --- | --- |
| `["add", k]` | boolean, always 1 |
| `["poll"]`, `["peek"]` | maybe the key |
| `["remove", k]`, `["contains", k]` | boolean |
| `["remove_iter", m, r]` | nothing. Walks the queue's iterator and removes each key whose number, or string length, is `r` modulo `m` (`Math.floorMod`), as `LevelChunkTicks.removeIf` does. `m` is positive |
| `["size"]`, `["clear"]`, `["iter"]` | as on maps |

On `array_deque`: `["add_first", k]` and `["add_last", k]` give nothing. `["poll_first"]`, `["poll_last"]`, `["first"]` and `["last"]` give maybe the key, `peekFirst` and `peekLast` for the last two. `["contains", k]`, `["size"]`, `["clear"]` and `["iter"]` are as before.

An operation a collection doesn't have is an `error` status, as is a key that doesn't parse as the case's type.

### `registries` (v2)

What a server with only the vanilla data pack sends a client in configuration: its known packs, the synchronized registries in `registry_data`, and the tags in `update_tags`. The registries load once, as `WorldLoader.load` loads them, and are kept. Identifiers are written whole, `minecraft:stone`.

| Input | Output |
| --- | --- |
| `{"op": "known_packs"}` | `packs`: the server's known packs in order, each `[namespace, id, version]` |
| `{"op": "synced"}` | `registries`: each synchronized registry in the order the server sends them, `{name, entries}`, with `entries` in ID order, each `[id, sent_with_data]`. An entry from a pack the client knows goes without its data |
| `{"op": "tags", "registry": name}` | `tags`: the registry's tags as `update_tags` sends them, by name in string order, each `[name, ids]` with the entries' IDs in the order sent. An empty list for a registry it sends no tags for |
| `{"op": "contents", "registry": name}` | One blob: the synchronized registry's entries in ID order with their contents, as `registry_data` sends them to a client that knows none of the server's packs (`RegistrySynchronization.packRegistries` with no known packs). An `int` count, then each entry's ID as an `int` length and its UTF-8, then its contents, encoded with the registry's network codec and `NbtOps`, as `NbtIo.writeAnyTag` writes them. Big-endian. Added in v2. The cases for `timeline`, `dimension_type` and `worldgen/biome` are `unordered` |

### `palette` (v1)

A chunk section's paletted containers, as vanilla keeps, sends and saves them, and the packed longs under them. Each operation's result goes into one blob, big-endian: an `int` is 4 bytes, a `long` 8, a byte 1, and a *message* an `int` length and then its UTF-8 bytes.

Input `{"of": "container", "strategy": s, "registry": n, "value": v, "ops": [...]}` runs `new PalettedContainer(v, strategy)`, with `strategy` `block_states` or `biomes` for `Strategy.createForBlockStates` or `createForBiomes`. The registry holds `n` values, 1 to 1,048,576: objects compared by identity, as block states and biomes are, the value with ID `i` written as `i`. An index `i` is a position among the container's 4,096 or 64 values, which vanilla's `set` and `get` take as its `x`, `y` and `z`: `i` is `(y << b | z) << b | x`, with `b` 4 for block states and 2 for biomes.

| Operation | Result |
| --- | --- |
| `["set", i, v]` | nothing |
| `["get", i]` | `int`, the value |
| `["get_and_set", i, v]` | `int`, the value it had |
| `["random_sets", seed, count, low, high]` | nothing. `count` sets, each at an index and to a value from `low` up to but not including `high`, drawn from a 64-bit LCG whose state starts at `seed`, a decimal string: each draw steps the state to `x * 6364136223846793005 + 1442695040888963407`, wrapping, and takes `x >>> 33`. A set draws its index, modulo the container's size, and then its value, modulo `high - low`, plus `low` |
| `["bits"]` | `int`, `bitsPerEntry` |
| `["write"]` | `int` length and the bytes `write` sends |
| `["pack"]` | `pack`: an `int` count and the palette's values as `int`s, then a byte 0 if there's no data, or a 1, an `int` count and the `long`s |
| `["unpack", palette, data]` | `PalettedContainer.unpack` of the values `palette`, and `data`, the longs as decimal strings, or null for no data. A byte 0 if it unpacked, and the container is the one it gave, or a 1 and the message of vanilla's error |
| `["repack"]` | `pack`, then `unpack` of what it gave, as `unpack` |
| `["counts"]` | `count`: an `int` number of pairs, then each value and how many times it's there, as `int`s, by value and then by count |

Input `{"of": "storage", "bits": b, "size": n, "ops": [...]}` runs a `SimpleBitStorage` of `n` values, 0 to 4,096, of `b` bits each, 1 to 32, all 0. A value is a non-negative `int`, since vanilla checks it as one.

| Operation | Result |
| --- | --- |
| `["set", i, v]`, `["fill", v]` | nothing |
| `["get", i]`, `["get_and_set", i, v]` | `int` |
| `["random_sets", seed, count, low, high]` | nothing, with draws as on a container |
| `["longs"]` | an `int` count and the `long`s, `getRaw` |
| `["values"]` | an `int` count and each value as an `int`, `unpack` |
| `["load", data]` | `new SimpleBitStorage(b, n, data)`, with `data` decimal strings: a byte 0 if it loaded, and the storage is that one, or a 1 and the message of vanilla's exception |

An index or value out of range is an `error` status, as is an operation the input doesn't have.

### `chunk` (v1)

A chunk's sections and heightmaps, as a chunk in the world keeps them while blocks are set, with the vanilla data pack's block tags. Results go into one blob, as `palette`'s do.

Input `{"min_y": y, "sections": n, "ops": [...]}` runs a chunk whose `n` sections go up from `y`, a multiple of 16, all inside -2032 to 2032, as a dimension's are. It starts all air, in plains, with all six heightmaps at the bottom. A `LevelChunk` needs a whole level, so vanilla's side is a `ProtoChunk`, whose sections, heightmaps and `getBlockState` are the same, and `set` does to it what `LevelChunk.setBlockState` does. A block is at `x` and `z` in the chunk, 0 to 15, and `y` in the world; a state is its ID; a heightmap is its ID in `Heightmap.Types`, 0 for `WORLD_SURFACE_WG` to 5 for `MOTION_BLOCKING_NO_LEAVES`.

| Operation | Result |
| --- | --- |
| `["set", x, y, z, state]` | `int`, the state that was there, or -1 if nothing changed. The state goes into its section, and `MOTION_BLOCKING`, `MOTION_BLOCKING_NO_LEAVES`, `OCEAN_FLOOR` and `WORLD_SURFACE` are told of it, in that order |
| `["fill", x0, y0, z0, x1, y1, z1, state]` | nothing: `set` on every block from one corner to the other, both included, by `y`, then `x`, then `z` |
| `["random_sets", seed, count, states, low, high]` | `int`, how many `set`s changed something. `count` sets, each drawing `x` and `z` modulo 16, `y` from `low` to `high`, both included, and a state from the list `states`, in that order, from `palette`'s LCG |
| `["block", x, y, z]` | `int`, `getBlockState` |
| `["update", kind, x, y, z, state]` | a byte, 1 if `Heightmap.update` changed the heightmap. Nothing is set: it's how generation tells the `_WG` heightmaps of a state |
| `["prime", kinds]` | nothing: `Heightmap.primeHeightmaps` of the heightmaps listed |
| `["heightmap", kind]` | an `int` count and the heightmap's `long`s |
| `["highest"]` | `int`, `getHighestSectionPosition` |
| `["counts"]` | for each section from the bottom, four `int`s: the blocks that aren't air, those that take random ticks, those with a fluid, and those whose fluid takes random ticks |
| `["recount"]` | nothing: `recalcBlockCounts` on every section |
| `["write"]` | `int` length and the bytes every section's `write` sends, from the bottom |

A place outside the chunk, a state or heightmap that isn't one, and an operation it doesn't have are an `error` status.

### `region` (v1)

Region files, as vanilla's `RegionFile` reads and writes them: operations on one file, `r.0.0.mca`, in a new folder of its own. A chunk's bytes come from the case compressed already, so the files compare byte for byte. Results go into one blob, as `palette`'s do. Each operation's result comes after what it logged: an `int` count of lines, then for each its level as a byte, 1 for a warning and 2 for an error, and its message, with the folder taken out of the paths in it, so `r.0.0.mca` and `c.3.4.mcc` stand alone.

Input `{"ops": [...]}`, with blobs. A chunk is at `x` and `z` in the region, 0 to 31, and a blob is its index in the case's list.

| Operation | Result |
| --- | --- |
| `["put", blob]` | nothing: the region file's bytes become the blob |
| `["put_external", x, z, blob]` | nothing: `c.x.z.mcc` holds the blob |
| `["open"]` | nothing: closes the file if it's open, then opens it, as `new RegionFile(info, path, folder, VERSION_DEFLATE, false)`, which makes it if it isn't there |
| `["write", x, z, blob]` | nothing: writes the chunk whose bytes are the blob, its compression's byte and then its stream, as `ChunkBuffer.close` writes them, with their length before them |
| `["clear", x, z]` | nothing: `clear` |
| `["has", x, z]` | a byte, 1 if `hasChunk` |
| `["read", x, z]` | a byte: 0 if `getChunkDataInputStream` gives null; 1, then an `int` length and the bytes read from it; or 2, then the simple class name of what it throws, as a message. Only the class, since zlib words its messages its own way |
| `["close"]` | `close`, then every file in the folder, by name: an `int` count, then for each its name as a message, an `int` length and its bytes. In `r.0.0.mca`, each of the header's times becomes 1 if it isn't 0, since they're the clock's |

A chunk of 256 sectors or more goes in its own file, with a stub that names the region file's compression, deflate, so its bytes must be deflate's, as they always are in a world that saves with it. An operation on a file that isn't open, a chunk outside the region, a blob that isn't there and an operation it doesn't have are an `error` status.

### `chunk_nbt` (v1)

A chunk's NBT as a region file holds it, read by vanilla's `SerializableChunkData.parse` and written back by its `write`, as a chunk is loaded and saved again. The containers' block states come from the built-in registry and their biomes from the vanilla data pack's, as `registries` loads them.

Input `{"min_y": -64, "sections": 24, "snbt": "{...}"}`, with no blobs: the world's lowest block, a multiple of 16, how many sections high it is, the sections within -2032 to 2032, and the chunk's NBT as SNBT, which must be a compound.

The result is one blob. First what was logged while it was read and written: an `int` count of lines, then for each its level as a byte, 1 for a warning and 2 for an error, and its message as `region` writes one. Then a byte: 0 if `parse` gives null, for a chunk without a `Status` string; 1, then an `int` length and the NBT written, as `NbtIo.write` writes a file's root, its type, an empty name and its payload; or 2, then the simple class name of what was thrown and its message, each as a message, the message empty if it has none. A chunk can throw as it's read or as it's written: a section's biomes with a value past their palette's end throw only when it's written.

A `min_y` that isn't a multiple of 16, sections outside the range, blobs and SNBT that isn't a compound are an `error` status.

### `level_data` (v1)

The `Data` compound of a world's `level.dat`, read as a server reads it as it starts, by vanilla's `LevelStorageSource.readDataConfig`, `LevelSettings.parse` and `PrimaryLevelData.parse`, and written back by `PrimaryLevelData.createTag`, as it saves.

Input `{"snbt": "{...}"}`, with no blobs: the compound as SNBT.

The result is one blob: what was logged while it was read and written, as `chunk_nbt` writes it, then an `int` length and the NBT written, as `NbtIo.write` writes a file's root. `LastPlayed`, the clock's, is written as 0.

Blobs and SNBT that isn't a compound are an `error` status.

### `world_folder` (v5)

A world's folder, as vanilla's `LevelStorageSource` and its `LevelStorageAccess` keep it, its players' data, as `PlayerDataStorage` keeps it, its saved data, as `SavedDataStorage` keeps it, and its players' advancements and statistics, as `PlayerAdvancements` and `ServerStatsCounter` keep them: operations on `world`, in a new folder of its own, which is the server's folder, the universe. Results go into one blob, each after what its operation logged, as `region` writes them. In what was logged and in names, the folder's path is taken out, `/` goes between names, the time in a `level.dat_corrupted_` file's name becomes `<time>`, and the random number in a new `level<n>.dat` becomes `<n>`, since each is the run's own.

Input `{"ops": [...]}`, with blobs. A name is a path in `world` with `/` between names, which mustn't leave it, and a blob is its index in the case's list.

| Operation | Result |
| --- | --- |
| `["put", name, blob]` | nothing: makes the folders on the way, and the file holds the blob |
| `["dir", name]` | nothing: makes the folder, and the folders on the way |
| `["link", name, target]` | nothing: makes a symbolic link at the name, `""` for `world` itself, with the folders on the way, to the target as it's written, which is a path as this system's `Path` writes it, with `<folder>` for the universe's path and its separator |
| `["allow", blob]` | nothing: the universe's `allowed_symlinks.txt` holds the blob, with `<folder>` in it for the universe's path and its separator |
| `["open"]` | a byte: 1 if `createDefault(universe).validateAndCreateAccess("world")` read `allowed_symlinks.txt`, found no link in `world` it doesn't allow, and opened and locked it; or 0, then what it threw as its class's full name, `: ` and its message, as a message |
| `["has"]` | a byte, 1 if `hasWorldData` |
| `["load"]` | a byte: 0 if `getUnfixedDataTagWithFallback` threw, where `Main` stops; or 1, then an `int` length and the `Data` read, as `NbtIo.write` writes a file's root |
| `["check"]` | a byte, from `fixAndGetSummaryFromTag` on what was loaded, as `Main` checks it: 0, then what it threw, as `open` writes it; 1 if it `requiresManualConversion`; 2 if it isn't `isCompatible`; or 3, then the `int` data version, `NbtUtils.getDataVersion` |
| `["save"]` | nothing: `saveLevelData` with what was loaded |
| `["player_load", uuid, name]` | a byte: 0 if `load(new NameAndId(uuid, name))` gives nothing; or 1, then an `int` length and the compound, as `load` writes it. The first makes the `PlayerDataStorage`, as a server makes it as it starts, which makes `players/data` |
| `["saved_load", folder, id]` | a byte: 0 if a new `SavedDataStorage` for the folder gives nothing for the type `id`, with no file or one it can't read; 2 if the file has no `data`; or 1, then an `int` length and its `data`, as `NbtIo.writeAnyTag` writes it. The folder is `""` for the world's `data`, or a dimension's ID for `data` in its folder. The type's codec keeps `data` as it is |
| `["saved_save", folder, id, blob]` | a byte: 0 once a new `SavedDataStorage` for the folder has saved the blob, read as `NbtIo.readAnyTag` reads it, as the type `id`'s `data`, with `saveAndJoin`; or 1, then what the save threw, as `open` writes it |
| `["progress_load", kind, uuid]` | what was logged, then a byte: 0 if `players/advancements/<uuid>.json`, for `kind` `advancements`, or `players/stats/<uuid>.json`, for `stats`, isn't a regular file or can't be read, as `PlayerAdvancements.load` and `ServerStatsCounter`'s constructor read it before their codecs, through a buffered UTF-8 reader with `StrictJsonParser`; or 1, then the JSON as `JsonElement.toString` writes it, as a message, then a byte: 1, then the `int` data version the kind's codec would read it as, `DataFixTypes.wrapCodec`'s for advancements and `NbtUtils.getDataVersion` for statistics, or 0 if that throws. The UUID is any name in the folder |
| `["progress_save", kind, uuid, blob]` | what was logged: the blob, a JSON object, saved to that file as the kind's `save` saves what its codec gives, with the data version put in and its own `GSON` |
| `["stats_locate", uuid, name]` | what was logged, then the file `PlayerList.locateStatsFile` gives for the player, as a message, moving one under their name to their UUID's |
| `["close"]` | `close`, then every file and folder in `world`, sorted by name: an `int` count, then for each its name as a message and a byte, 0 for a file, 1 for a folder and 2 for a file that's gzip and inflates whole, then for a file an `int` length and its bytes, or for a gzipped one what it inflates to. No two deflaters write the same bytes, so a gzipped file is compared by what it holds |

Opening a folder that's open, an operation on one that isn't, `check` and `save` with nothing loaded, a name outside `world`, a UUID, ID or dimension that isn't one, a blob that isn't there or isn't a tag or a JSON object, a kind that isn't `advancements` or `stats`, and an operation it doesn't have are an `error` status. Version 2 added `player_load`, version 3 `saved_load` and `saved_save`, version 4 `progress_load`, `progress_save` and `stats_locate`, and version 5 `link` and `allow`. A target that isn't a path as Java writes it is an `error` status too.

### `allow_list` (v1)

`allowed_symlinks.txt`, read as a server reads it as it starts, by `LevelStorageSource.parseValidator`, then asked about each of a list of link targets, as `DirectoryValidator` asks about each link it finds, with the `PathMatcher` it keeps.

Input `{"paths": [...]}`, with the file as the one blob, or no blob for no file. Each path is a link's target as this system's `Path` writes it, so a case says which system it's for.

The result is one blob: what was logged reading the file, as `world_folder` writes it, then for each path what was logged matching it, then a byte, 1 if it's allowed.

More than one blob, and a path that's empty or isn't as Java writes it, are an `error` status.

### `entities_poi` (v1)

A chunk of a world's `entities` or `poi` folder, its NBT as a region file holds it, read and written as vanilla reads and writes it, without the region file.

Input `{"op": ..., "x": 0, "z": 0, "snbt": "{...}"}`, with no blobs: the operation, the chunk read from or saved to, and its NBT as SNBT, a compound, which `entities_load` and `poi` take as no file when it isn't there. `poi` also takes `min_y` and `sections`, as `chunk_nbt` does.

The result is one blob: what was logged, as `chunk_nbt` writes it, then what the operation gives. A root is an `int` length and the compound as `NbtIo.write` writes a file's root.

| Operation | Result |
| --- | --- |
| `entities_load` | `EntityStorage.loadEntities` up to making the entities, on its own logger: the `Position` checked with `ChunkPos.CODEC`, the tag upgraded, and `Entities` read with `TagValueInput.childrenListOrEmpty` in a `ScopedCollector` for the chunk, whose report is logged as it closes. A byte, 0 for no file; or 1, then a byte for what's reported to the server, 0 for nothing, 1 for a misplaced chunk, then where it says it is, `x` and `z` as `int`s, or 2 for a position that can't be read, then an `int` count and each entity's compound as a root, an empty one for an empty element |
| `entities_save` | `storeEntities`, with the case's `Entities`, a list, as the tags the entities saved: a byte, 0 if there's no `Entities`, for a chunk with no entities, which stores nothing; or 1, then the chunk's tag as a root |
| `poi` | `SectionStorage`'s `PackedChunk.parse` and `unpackChunk` with `PoiSection`'s codec, as `PoiManager` reads a chunk, then `writeChunk`: the chunk written, as a root |

Blobs, an `x` or `z` that isn't an `int`, SNBT that isn't a compound, `entities_save` without it, a `min_y` or `sections` as `chunk_nbt` refuses them, and an operation it doesn't have are an `error` status.

### `tickets` (v1)

A dimension's chunk tickets, in vanilla's own `TicketStorage`, through a list of operations, with what its two listeners, the loading and the simulation trackers, are told as they're told it.

Input `{"ops": [...]}`, with no blobs. A chunk is `ChunkPos.pack`'s `long`, as a decimal string. A type is a ticket type's name in `minecraft`, without the namespace, such as `"portal"`.

The result is one blob. As a listener is told of a chunk, the blob gets a byte 1, then a byte, 0 for the loading tracker or 1 for the simulation tracker, then the chunk as a `long`, the level as an `int`, and a byte, 1 if the change can only have lowered it. After each operation, the blob gets a byte 0, then its result. A ticket is its type's full name as a message (an `int` length and its UTF-8), its level as an `int` and the ticks it has left as a `long`, read from the ticket's field.

| Operation | Result |
| --- | --- |
| `["add", chunk, type, level]` | a byte, 1 if `addTicket` added it, with a new `Ticket` of the type and level |
| `["remove", chunk, type, level]` | a byte, 1 if `removeTicket` took one out |
| `["add_radius", type, x, z, radius]` | nothing: `addTicketWithRadius` |
| `["remove_radius", type, x, z, radius]` | nothing: `removeTicketWithRadius` |
| `["forced", x, z, forced]` | a byte, 1 if `updateChunkForced` changed it |
| `["replace_level", level, type]` | nothing: `replaceTicketLevelOfType` |
| `["purge", [chunk, ...]]` | nothing: `purgeStaleTickets`, with a `ChunkMap` made without its constructor whose `updatingChunkMap` holds a holder, made the same way with a `saveSync` that hasn't finished, for each chunk given, the busy ones, and none for any other |
| `["deactivate"]` | nothing: `deactivateTicketsOnClosing` |
| `["activate"]` | nothing: `activateAllDeactivatedTickets` |
| `["level", chunk, simulation]` | `getTicketLevelAt`, an `int` |
| `["debug", chunk, simulation]` | `getTicketDebugString`, as a message |
| `["dump"]` | 3 bytes, for `hasTickets`, `shouldKeepDimensionActive` and `isDirty`; then the tickets in use and those deactivated, each table in its order: an `int` count, then each chunk as a `long`, an `int` count and each ticket; then the forced chunks, `getForceLoadedChunks` in its order, an `int` count and each chunk as a `long` |
| `["save"]` | a byte for `isDirty`, then an `int` length and what `TicketStorage.CODEC` encodes, as `NbtIo.write` writes a file's root; then `setDirty(false)` |
| `["load", snbt]` | the root of a `chunk_tickets` file, a compound as SNBT, read as `SavedDataStorage.readSavedData` reads one: its `data` parsed with the type's codec, keeping what can be read. An `int` count and each line logged as a message, then a byte, 1 if it read the tickets. The storage is then what was read, or a new one if nothing was, with the same listeners |

`ChunkLevel.MAX_LEVEL` must be 44, for which the cases are written; the vanilla adapter checks it. Blobs, an operation that isn't a non-empty array named by a string, one it doesn't have or with the wrong count of arguments, a chunk that isn't a decimal `long`, a coordinate, level or radius that isn't an `int`, a type that isn't one, and SNBT that isn't a compound are an `error` status.

### `levels` (v1)

The graph every chunk tracker is, vanilla's own `ChunkTracker`, through a list of operations, with each level it sets written as it's set.

Input `{"level_count": n, "unset": u, "keep_below": k, "no_source": s, "ops": [...]}`, with no blobs. The vanilla adapter's tracker is a subclass with its levels and sources in two `Long2IntOpenHashMap`s, made with fastutil's defaults: `getLevel` gives a chunk's level, or `u` if it has none; `setLevel` takes the chunk out at `k` or above, and puts it in below; `getLevelFromSource` gives the chunk's source, or `s` if it has none. The loading tracker is `46, 45, 45, 45`, the simulation tracker `34, 33, 33, 45`, the natural spawn counter `10, 10, 9, 2147483647` and the player ticket tracker `34, 34, 33, 2147483647`. A chunk is its `x` and `z`, each an `int`, packed with `ChunkPos.pack`.

The result is one blob. As the tracker sets a level, the blob gets a byte 1, then the chunk as a `long` and the level as an `int`. After each operation, the blob gets a byte 0, then its result.

| Operation | Result |
| --- | --- |
| `["source", x, z, level]` | nothing: the chunk's source is `level`, and the tracker isn't told |
| `["unsource", x, z]` | nothing: the chunk has no source, and the tracker isn't told |
| `["update", x, z, level, only_decreased]` | nothing: `update` |
| `["set", x, z, level]` | nothing: the chunk's level is `level`, kept or taken out as `setLevel` does, without the tracker, as a chunk holder's removal changes the loading tracker's levels |
| `["run", count]` | `runUpdates(count)`, an `int`, how many of `count` are left |
| `["dump"]` | a byte for `hasWork`, an `int` for `getQueueSize`, then the levels in the map's order: an `int` count, then each chunk as a `long` and its level as an `int` |

Blobs, a `level_count` that isn't from 2 to 253, an operation that isn't a non-empty array named by a string, one it doesn't have or with the wrong count of arguments, a coordinate, level or count that isn't an `int`, and an `only_decreased` that isn't a boolean are an `error` status.

### `distance` (v1)

A dimension's distance manager, vanilla's own `DistanceManager`, with its trackers, its player ticket dispatcher and its `TicketStorage`, and the chunk holders `ChunkMap` keeps for it, through a list of operations.

Input `{"ops": [...]}`, with no blobs. A chunk is its `x` and `z`, each an `int`, packed with `ChunkPos.pack`. A type is a ticket type's name in `minecraft`, without the namespace, such as `"portal"`. A player is an `int` the case names it by; the vanilla adapter makes a `ServerPlayer` without its constructor the first time a case names it, with an entity ID, since a player's hash is its ID.

The manager's two executors are queues the case runs: the dispatcher's worker and the main thread. The worker runs the dispatcher's jobs one at a time, lowest priority first, as its `PriorityConsecutiveExecutor` does, and the main thread runs its tasks in the order they came. The vanilla adapter replaces the manager's `chunksToUpdateFutures`, a set of identities whose order is different every run, with a `LinkedHashSet`, so the holders whose level changed are updated in the order it changed ([D177](../docs/decisions.md)).

The holders are the vanilla adapter's subclass of the manager, with `ChunkMap`'s part: `updatingChunkMap` and `pendingUnloads`, two `Long2ObjectLinkedOpenHashMap`s, `toDrop`, a `LongOpenHashSet`, and `modified`. Its `updateChunkScheduling` is `ChunkMap`'s, and the holders are vanilla's `ChunkHolder` with their futures cut down to the one for the chunk ticking its entities, made when the holder's level reaches 31 and done with no chunk when it leaves, and with no worldgen or light. Each holder dropped has its unload queued at once, as a holder whose saves are done has, and an unload takes its holder out only if it's still the one waiting, as `pendingUnloads.remove(pos, holder)` does. `runAllUpdates` is given a `ChunkMap` made without its constructor whose `updatingChunkMap` is the manager's.

The result is one blob, each operation's result after the last's.

| Operation | Result |
| --- | --- |
| `["player", player, x, z]` | nothing: `addPlayer` |
| `["unplayer", player, x, z]` | nothing: `removePlayer`. Vanilla throws if no player was added in the chunk |
| `["view", d]` | nothing: `updatePlayerTickets(d)` |
| `["simulation", d]` | nothing: `updateSimulationDistance(d)` |
| `["ticket", type, level, x, z]` | a byte, 1 if the storage's `addTicket` added a new `Ticket` of the type and level |
| `["unticket", type, level, x, z]` | a byte, 1 if `removeTicket` took one out |
| `["update"]` | a byte for `runAllUpdates` |
| `["promote"]` | a byte for `modified`, as `promoteChunkMap` reads it, which it then clears |
| `["dispatch", n]` | an `int`, how many of the worker's next `n` jobs ran |
| `["main", n]` | an `int`, how many of the main thread's next `n` tasks ran |
| `["ready", x, z]` | a byte, 1 if the holder at the chunk, in `updatingChunkMap` or else `pendingUnloads`, had its chunk waited for, which then ticks its entities: its future is done |
| `["ready_first", n]` | an `int`: the same for the holders in `updatingChunkMap`, in its order, until `n` were waited for |
| `["drop"]` | the start of `processUnloads`: each chunk in `toDrop`, in fastutil's iterator's order, taken out, its holder moved from `updatingChunkMap` to `pendingUnloads` and its unload queued. An `int` count, then each chunk moved as a `long` |
| `["unload", n]` | an `int`, how many of the next `n` unloads ran |
| `["nearby", x, z]` | a byte for `hasPlayersNearby`: 0 for `TRUE`, 1 for `DEFAULT`, 2 for `FALSE` |
| `["spawn_count"]` | `getNaturalSpawnChunkCount`, an `int` |
| `["brief"]` | the state below, without the trackers' levels |
| `["dump"]` | the state below |

The state, each table in its order: the holders in `updatingChunkMap`, then those in `pendingUnloads`, each an `int` count, then each holder's chunk as a `long`, its ticket level as an `int`, a byte for its future, 0 if it's the one done with no chunk, 1 if it isn't done and 2 if it is, and its future's dependents as an `int`; `toDrop`, an `int` count and each chunk as a `long`; the unloads queued, an `int`; a byte for `modified`; `ticketsToRelease`, as `toDrop` is; a byte for the dispatcher's `sleeping`; its `chunkPositionsInExecution`, as `toDrop` is; its queue's `topPriorityQueueIndex`, an `int`; each of its queue's 46 levels with tasks, lowest first, as its level as an `int`, an `int` count, then each chunk as a `long` and its tasks as an `int`, and then an `int` -1; the worker's jobs waiting at each of its four priorities, four `int`s; the tickets in use, an `int` count, then each chunk as a `long`, an `int` count and each ticket, its type's ID in its registry as a byte, its level as an `int` and the ticks it has left as a `long`; and `getDebugStatus`, an `int` length and its UTF-8. Then, for `dump`, the levels of the simulation tracker, the natural spawn counter and the player ticket tracker, from their `Long2ByteOpenHashMap`s, and the player ticket tracker's `queueLevels`, each an `int` count, then each chunk as a `long` and its level as an `int`; then the player ticket tracker's view distance and the manager's simulation distance, each an `int`.

`ChunkLevel.MAX_LEVEL` must be 44, for which the cases are written; the vanilla adapter checks it. Blobs, an operation that isn't a non-empty array named by a string, one it doesn't have or with the wrong count of arguments, a player, coordinate, level, distance or count that isn't an `int`, an `unplayer` of a player no earlier `player` named, and a type that isn't one are an `error` status.

### `light` (v1)

A dimension's light, vanilla's own `LevelLightEngine` with its block and sky engines, over chunks the case makes, through a list of operations.

Input `{"min_y": y, "sections": n, "sky": s, "ops": [...]}`, with no blobs: the dimension from `min_y`, a multiple of 16, `n` sections up, all inside −2032 to 2032, with a sky if `s` is 1 and none if it's 0. The chunks are `ProtoChunk`s of that height, each with its own `ChunkSkyLightSources`, which the engine gets from a `LightChunkGetter` over a map, as a level's chunk source gives the chunks it has: a chunk the case hasn't made is missing, and the level reads air there. A state is a block state's ID. A seed is a `long` as a decimal string, for the probe's LCG: `x = x * 6364136223846793005 + 1442695040888963407`, each draw `(int) (x >>> 33)`. A chunk's `x` and `z` are from −1000 to 1000, and a block's from −16000 to 16015.

A block is set *quietly* as generation sets one before light: straight into its section, except air in a section of only air, which `LevelChunk` doesn't set either, so the section's palette is what the world's would be. It's *told* as `LevelChunk.setBlockState` tells light once it's set one: nothing for air in a section of only air or for the state it had; otherwise, if the section stopped or started being only air, `updateSectionStatus`, and if `hasDifferentLightProperties` says the two states' light differs, the chunk's `getSkyLightSources().update` and then `checkBlock`.

The result is one blob, each operation's result after the last's.

| Operation | Result |
| --- | --- |
| `["chunk", x, z]` | nothing: an empty chunk there, which mustn't be there already |
| `["fill", x0, y0, z0, x1, y1, z1, state]` | nothing: every block from one corner to the other set quietly, `y`, then `x`, then `z`, at most 256 blocks across, in chunks that are there |
| `["random", tell, seed, count, [state, ...], x0, y0, z0, x1, y1, z1]` | nothing: `count` blocks, each at `x0 + draw % (x1 − x0 + 1)` and the same for `y` and `z`, then a state from the list at `draw % length`, set quietly or told by `tell`, 0 or 1 |
| `["set", x, y, z, state]` | the block told, and the state it had as an `int`, or −1 for nothing changed |
| `["sources", x, z]` | nothing: the chunk's `initializeLightSources`, as the `INITIALIZE_LIGHT` status starts |
| `["sections", x, z]` | nothing: `updateSectionStatus(…, false)` for each of the chunk's sections that isn't only air, as `ThreadedLevelLightEngine.initializeLight` starts |
| `["status", x, y, z, empty]` | nothing: `updateSectionStatus` of the section, `y` from one below the dimension's sections to one above |
| `["enable", x, z, on]` | nothing: `setLightEnabled` |
| `["retain", x, z, on]` | nothing: `retainData` |
| `["propagate", x, z]` | nothing: `propagateLightSources`, as the `LIGHT` status does for a chunk not lit yet |
| `["check", x, y, z]` | nothing: `checkBlock`, `y` up to 16 past the dimension each way |
| `["queue", sky, x, y, z, kind, v]` | nothing: `queueSectionData` for the sky's layer if `sky` is 1 or the block's, `kind` 0 for `null`, 1 for `new DataLayer(v)`, `v` from 0 to 15, or 2 for 2048 bytes, each a draw from seed `v` as a byte |
| `["run"]` | `runLightUpdates`, an `int` |
| `["work"]` | a byte for `hasLightWork` |
| `["on", x, z]` | a byte for `lightOnInColumn` |
| `["value", sky, x, y, z]` | the layer listener's `getLightValue`, a byte, `y` up to 64 past the dimension each way |
| `["layer", sky, x, y, z]` | the layer listener's `getDataLayerData`, as a packet reads it: a byte 0 for `null`, 1 for an empty layer, or 2 and its 2048 bytes |
| `["light", x, z]` | the chunk's light as `level_chunk_with_light` sends it, `new ClientboundLightUpdatePacketData(pos, engine, null, null)` encoded with its `STREAM_CODEC`: an `int` length and the bytes |

Blobs, a `min_y`, `sections` or `sky` it doesn't take, an operation that isn't a non-empty array named by a string, one it doesn't have or with the wrong count of arguments, an argument that isn't an `int` where one is wanted or is out of its range, a seed that isn't a decimal `long`, a state that isn't one, an empty list of states, and a block in a chunk that isn't there are an `error` status.

### `spawn` (v1)

Where a player new to the world joins it, as vanilla's own `PlayerSpawnFinder` finds the place, over chunks the case makes, through a list of operations.

Input `{"ops": [...]}`, with no blobs. The chunks are `LevelChunk`s of the overworld's height, from −64 to 319, in a stand-in for the overworld's `ServerLevel` made without its constructor: its chunk source has every chunk the case made full and notes each ticket a search adds, which must be a `spawn_search` ticket of radius 0 for a chunk the case made, and its server runs each task handed to it in turn, as its thread would once the ticket's chunk is full. No entity collides, and the world border is the default one. A block is set as `LevelChunk.setBlockState` sets it in its section and the chunk's heightmaps, with nothing else told: nothing for air in a section of only air or for the state it had. A state is a block state's ID. A seed is a `long` as a decimal string, for the probe's LCG: `x = x * 6364136223846793005 + 1442695040888963407`, each draw `(int) (x >>> 33)`. A chunk's `x` and `z` are from −1000 to 1000, and a block's from −16000 to 16015.

The result is one blob, each operation's result after the last's. A place is `Vec3.atBottomCenterOf` a block, three `double`s, `x`, `y` and `z`.

| Operation | Result |
| --- | --- |
| `["chunk", x, z]` | nothing: an empty chunk there, which mustn't be there already |
| `["fill", x0, y0, z0, x1, y1, z1, state]` | nothing: every block from one corner to the other set, `y`, then `x`, then `z`, at most 256 blocks across, in chunks that are there |
| `["random", seed, count, [state, ...], x0, y0, z0, x1, y1, z1]` | nothing: `count` blocks, each at `x0 + draw % (x1 − x0 + 1)` and the same for `y` and `z`, then a state from the list at `draw % length` |
| `["respawn", x, z]` | `getLevelRespawnPos` of the column, in a chunk that's there: a byte 0 for `null`, or 1 and the block's `x`, `y` and `z` as `int`s |
| `["fits", x, y, z]` | a byte for `noCollisionNoLiquid` at the block, `y` up to 64 past the world each way |
| `["fixup", x, y, z]` | the place `fixupSpawnHeight` moves the block to, as an adventure world's spawn, `y` up to 64 past the world each way |
| `["search", x, y, z, radius, offset]` | a whole search around the block, `PlayerSpawnFinder`'s private constructor with `radius`, from 0 to 64, its random `offset` replaced by the case's, from 0 to one less than its candidates, then `scheduleNext` and every task it hands the server: an `int` count of the tickets it added, each chunk's `x` and `z` as `int`s, then the place it found |

Blobs, an operation that isn't a non-empty array named by a string, one it doesn't have or with the wrong count of arguments, an argument that isn't an `int` where one is wanted or is out of its range, a seed that isn't a decimal `long`, a state that isn't one, an empty list of states, a block in a chunk that isn't there, and a search with a candidate in one are an `error` status.

### `packs` (v2)

A world's data packs: found as a server starting finds them, by `ServerPacksSource.createPackRepository` with the validator `LevelStorageSource.parseValidator` makes from `allowed_symlinks.txt`; picked as `MinecraftServer.configurePackRepository` picks them; their files listed by a `MultiPackResourceManager` over the picked packs, as the server's resources are made; and the world's registries loaded from them, as `WorldLoader.load` loads them. The operations work on `world`, in a new folder of its own, the universe, as `world_folder`'s do, and vanilla's own pack and its feature packs come from the pinned server jar.

Input `{"ops": [...]}`, with blobs, as `world_folder`'s. The result is one blob, each operation's result after what it logged. A line logged is its level as a byte, 1 for a warning, 2 for an error and 0 for anything else, then its words as a message, an `int` length and its UTF-8, with a line break and what was thrown after it, as `Throwable.toString` writes it. What an operation logged is an `int` count and each line. In the lines the folder's path is taken out, and each `\` is written `/`, on every system, so names have `/` between them and a line reads the same on each system, an escape in a message included. A list of names is an `int` count and each as a message, and feature flags are their IDs in the order `FeatureFlagRegistry.toNames` gives them.

| Operation | Result |
| --- | --- |
| `["put", name, blob]`, `["dir", name]`, `["link", name, target]`, `["allow", blob]` | nothing, as `world_folder`'s |
| `["pick", setup]` | the packs found and picked, once. `setup` is `{"enabled": [...], "disabled": [...], "features": [...], "init": b, "safe": b}`: the packs on and off, as a world's `DataPackConfig` has them; its feature flags by ID; whether the world is new, so that the packs are server.properties' `initial-enabled-packs` and `initial-disabled-packs`; and `--safeMode`. The result is an `int` count of the packs found, then each in ID order: its ID as a message; its source as a byte, 0 built in, 1 a feature pack, 2 the world's; its `PackCompatibility` as a byte, 0 too old, 1 too new, 2 unknown, 3 compatible; the feature flags it asks for; and its description, as `ComponentSerialization.CODEC` encodes it to JSON, as a message. Then come the packs picked and the packs off, as names, and the world's feature flags |
| `["list", folder, suffix]` | the picked packs' files in the folder whose paths end with the suffix, as `listResources` gives them. The first `list` opens the packs, with `openAllSelected`, and what that logs is logged with it. The result is an `int` count, then each file's identifier and its pack's ID, as messages, then an `int` length and the file's bytes |
| `["load"]` | the registries loaded from the picked packs, once, opening them first if no `list` has: the built-in registries' tags, as `TagLoader.loadTagsForExistingRegistries` loads them, then `RegistryDataLoader.WORLD_REGISTRIES` with `RegistryDataLoader.load`, on one thread. What that logged comes first, in order of the lines' words and then their levels, since a server loads the registries on many threads. In the `Registry loading errors` line each exception's stack frames are left out, `\n` goes between lines, and an exception of Gson's is named alone, without its message or what caused it. Then a byte, 1 if the registries loaded and 0 if what was logged stopped them. If they loaded, each synchronized registry follows as `RegistrySynchronization.packRegistries` packs it for a client with every known pack of the picked ones: its identifier as a message, an `int` count of its entries, then each one's identifier as a message and a byte, 1 if its contents go with it, then an `int` length and the contents as `NbtIo.writeAnyTag` writes them, or 0 |

A second `pick`, a `list` or `load` before one, a second `load`, a setup that isn't an object with those fields, a feature flag that isn't one, and anything `world_folder` refuses are an `error` status.

Vanilla finds a folder's entries in the order the file system lists them. NTFS lists a folder in the same order on every machine, by name; a Linux file system needn't, since ext4 lists by a hash of each name with a seed of each file system's own. So a case where more than one entry in a folder logs something is Windows'.

### `noise` (v1)

Vanilla's noises, made from a random source and sampled at points the case gives, or over a volume as a density function samples them.

Input `{"random": r, "seed": s, "noise": n, "fn": f, ...}`. The source is `new LegacyRandomSource(seed)` if `r` is `"legacy"` or `new XoroshiroRandomSource(seed)` if it's `"xoroshiro"`, `s` a `long` as a decimal string, and the noise is made from it by `n`:

| `noise` | Made by |
| --- | --- |
| `{"type": "perlin"}` | `new PerlinNoise(random)` |
| `{"type": "smeared", "fudge_y_scale": d}` | `new SmearedPerlinNoise(random, d)` |
| `{"type": "simplex", "discard_offset": b}` | `new SimplexNoise(random, b)` |
| `{"type": "normal", "parameters": p}` | `create(random)` of the `NormalNoise` that `NormalNoise.DIRECT_CODEC` reads from `p`, a noise as a data pack writes it |
| `{"type": "legacy_nether", "parameters": p}` | `createForLegacyNetherBiome(random)` of the same |
| `{"type": "fbm", "first_octave": n, "smear_scale_y": d, "value_factor": v}` | `BlendedNoise.createFbm(random, n, d, v)` |

A `double` in the input, `d` and `v` here, is a decimal string, read as `Double.parseDouble` reads it; so are the `float`s below, read as `Float.parseFloat` reads them. The result is one blob:

| `fn` | Blob |
| --- | --- |
| `"get3"`, with a blob of `(x, y, z)` `f64` triples | `get(x, y, z)` of each, as `f32` bits |
| `"get2"`, with a blob of `(x, y)` `f64` pairs | `get(x, y)` of each, as `f32` bits |
| `"volume"`, with `"volume": [sx, sy, sz, x, y, z, stepx, stepy, stepz]`, `"xz_scale"`, `"y_scale"` and `"amplitude"` | `addToVolume` of a `DensityBuffer` of zeros over `new DensityVolume(...)` of those `int`s, with the two `double` scales and the `float` amplitude, then each of its values in order, `y` fastest, then `x`, then `z`, as `f32` bits. The volume is at most 65,536 values |
| `"range"` | the noise's `range()`, its `min` and `max` as `f32` bits, then for `normal` and `legacy_nether` the `NormalNoise`'s own `range()` the same way |

Every NaN is written as `0x7fc00000`, `Float.floatToIntBits`'s NaN, whatever its sign and payload (D198): which NaN Java gives when two meet isn't defined, and differs with the order the JIT puts them in, so only where a NaN comes out is compared.

If making the noise throws, the result is the rejection, as `rng`'s is, and no blob. Parameters the codec doesn't read, a noise or `fn` it doesn't have, a field missing or of the wrong type, a blob it doesn't take or of the wrong length, and a volume too big or not positive are an `error` status.

### `density` (v1)

Density functions, read as a data pack writes them, compiled by a `RandomState` and sampled at points or over volumes, every op through one `SamplerContext`. The registries are vanilla's own, from the pinned server jar, so a function or noise named by ID is vanilla's.

Input `{"seed": s, "functions": [...], "cached": b, "ops": [...]}`, with `"settings": id` or `"legacy_random": b`, and one blob. `s` is a `long` as a decimal string. With `settings`, the `RandomState` is `RandomState.create(noises, seed, settings)` of those noise settings, and their `useLegacyRandomSource` picks the random; without, it's `RandomState.create(noises, seed, legacy_random, stone, 63, router)` with a router of zeros. Each function is `{"function": f}`, `f` read by `DensityFunction.CODEC` with the registries' ops, so an ID, a number or an object; or `{"router": field}`, the settings' router's `temperature`, `vegetation`, `continents`, `erosion`, `depth`, `ridges`, `chunk_surface_level` or `final_density`. The context is `SamplerContext.builder().enableCaches().build()` if `cached`, else `SamplerContext.EMPTY_UNCACHED`.

Each op is `{"fn": i, "points": n}`, `n` points from the blob, an `int` triple each, with `sampleValue` of function `i`'s sampler; or `{"fn": i, "volume": [sx, sy, sz, x, y, z, stepx, stepy, stepz]}`, `sampleVolume` into a `DensityBuffer` of zeros over `new DensityVolume(...)` of those `int`s, at most 65,536 values. The ops give at most 2^20 values in all, and the blob holds each `points` op's triples in order.

First each function's `range()` and `domainAxes()` are worked out, in order, then each one's sampler with `getSampler`, then the ops in order. The output is `{"functions": [{"range": r, "axes": a}, ...]}`: `r` the range's `min` and `max` as `%08x` of their `Float.floatToIntBits`, or `null` if it's `NaI`, and `a` the axes, X 1, Y 2 and Z 4. The blob is every value the ops give, in order, as `f32` bits, a volume's `y` fastest, then `x`, then `z`. Every NaN is `0x7fc00000` (D198).

If any of that throws, the result is the rejection, as `rng`'s is, and no blob. A function the codec doesn't read, an op that isn't one of those, a router field without `settings` or that the router doesn't have, `legacy_random` with `settings`, too many values and a blob of the wrong length are an `error` status.

### `biomes` (v1)

A biome source, read as a dimension's generator writes its `biome_source`, with the climate sampler of a noise settings' router, asked for biomes at quarts, at climate targets and over chunks. The registries are vanilla's own, as `density`'s are, so a biome, tag or preset named by ID is vanilla's.

Input `{"seed": s, "settings": id, "source": v, "cached": b, "ops": [...]}` and one blob. `s` is a `long` as a decimal string, and the `RandomState` is `RandomState.create(noises, seed, settings)` of the noise settings `id`. `v` is read by `BiomeSource.CODEC` with the registries' ops. The climate sampler is `createClimateSampler` of a `SamplerContext.builder().enableCaches().build()` if `cached`, else of `SamplerContext.EMPTY_UNCACHED`, and the resolver is the source's `createResolver` of it.

Each case runs on a thread of its own, so the parameter list's search starts from no last result, and every op after shares the one it leaves. The ops, in order:

| Op | Reads from the blob | Writes to the blob |
| --- | --- | --- |
| `["list"]` | nothing | the multi-noise source's parameter list: its size as an `int`, then each entry's temperature, humidity, continentalness, erosion, depth and weirdness `min` and `max`, and its offset, as `long`s, and its biome's number as an `int` |
| `["climate", n]` | `n` quart `int` triples | `sample(x, y, z)` of the climate sampler at each, its six values as `long`s |
| `["points", n]` | `n` quart `int` triples | `getNoiseBiome(x, y, z)` of the resolver at each, as the biome's number |
| `["search", n]` | `n` targets of six `int`s | the multi-noise source's `getNoiseBiome(new TargetPoint(...))` of each, as the biome's number |
| `["chunk", x, z, min_y, height]` | nothing | the chunk's biomes as `ChunkGenerator.createBiomes` fills them: `createResolverForChunk` of a new climate sampler with caches, over the chunk's quarts from `min_y` for `height` blocks, then each section from the bottom, its quarts with `z` fastest, then `y`, then `x`, as the biome's number |

`min_y` and `height` are whole sections, `height` positive, within -2032 and 2032. The ops give at most 2^20 values in all. A biome's number is the order the case first writes it in, from 0. The output is `{"possible": [...], "biomes": [...]}`: `possibleBiomes()` in order, then each number's biome, as IDs.

A source the codec doesn't read is `{"invalid": true}` and no blob: the codec's messages are its own, so only that it doesn't read is compared. If anything else throws, the result is the rejection, as `rng`'s is, and no blob. Settings that don't exist, an op that isn't one of those or isn't whole sections, `list` or `search` with another kind of source, too many values and a blob of the wrong length are an `error` status.

### `terrain` (v1)

A noise settings' terrain shape: chunks filled as `NoiseBasedChunkGenerator.buildTerrain` fills them before their surface and carvers, and base columns and heights. The registries are vanilla's own, as `density`'s are.

Input `{"seed": s, "settings": id, "level": [min_y, height], "ops": [...]}` and no blobs. `s` is a `long` as a decimal string, and the `RandomState` is `RandomState.create(noises, seed, settings)` of the noise settings `id`. The generator is a `NoiseBasedChunkGenerator` of those settings, with a fixed biome source, which the terrain doesn't use. The world is `LevelHeightAccessor.create(min_y, height)`, whole sections, `height` positive, within -2032 and 2032. The ops, in order:

| Op | Writes to the blob |
| --- | --- |
| `["fill", x, z]` | A new `ProtoChunk` at chunk `x`, `z` of the world, filled as `buildTerrain` does with no structures to beardify and nothing to blend: the settings' noise clamped to the world (`clampToHeightAccessor`), and if any is left, `doFill` with a new `NoiseChunk` over the chunk's volume. Then the chunk's blocks from the bottom up, each section in `y`, `z`, `x` order, as runs: their count, then each run's state ID and length, as `int`s; the `OCEAN_FLOOR_WG` and `WORLD_SURFACE_WG` heightmaps, each column's `getFirstAvailable` by `x` + 16`z`; and each section's blocks marked for post-processing, their count and then each one packed as `ProtoChunk.packOffsetCoordinates` packs it |
| `["column", x, z]` | `getBaseColumn(x, z, world, random_state)`: its length, or -1 if there's no column, then its bottom and each block's state ID from the bottom up; then `getBaseHeight` of each of the six heightmaps, in `Heightmap.Types` order |

The ops give at most 2^22 blocks in all, 256 times the world's height for each `fill` and the height for each `column`. The output is `{}`.

If anything throws, the result is the rejection, as `rng`'s is, and no blob. Settings that don't exist, a world that isn't whole sections within the limits, an op that isn't one of those, too many blocks and any blob are an `error` status.

### `surface` (v1)

Chunks filled with a noise settings' terrain shape and then given their materials, as `NoiseBasedChunkGenerator.buildTerrain` does before its carvers: `doFill`, then 26.3's `MaterialSystem.buildSurface` in the same `NoiseChunk`, with the biomes of a biome source. The registries are vanilla's own, as `density`'s are, so a rule, condition, noise, biome or tag named by ID is vanilla's.

Input `{"seed": s, "settings": id, "level": [min_y, height], "source": v, "ops": [...]}`, with `"rule": r` or without, and no blobs. `s` is a `long` as a decimal string, and the `RandomState` is `RandomState.create(noises, seed, settings)` of the noise settings `id`. `v` is read by `BiomeSource.CODEC` and `r` by `MaterialRule.CODEC`, both with the registries' ops; without `r`, the rule is the settings' own `material_rule`. The generator is a `NoiseBasedChunkGenerator` of `v` and the settings, and the world is `LevelHeightAccessor.create(min_y, height)`, whole sections, `height` positive, within -2032 and 2032.

Each case runs on a thread of its own, as `biomes`' do, so the parameter list's search starts from no last result. Each op is `["surface", x, z]`, in order:

1. The chunk at `x`, `z` and the eight around it, `z` outer and `x` inner from the lower corner, each a new `ProtoChunk` given its biomes as `createBiomes` gives them, through a climate sampler with caches of its own, and marked done with `biomes`.
2. A `BiomeManager` of the obfuscated seed that reads biomes from those nine chunks, as a `WorldGenRegion` does; the possible biomes are those in their palettes.
3. The settings' noise clamped to the world, and if any is left, a new `NoiseChunk` over the chunk's volume with no structures and nothing to blend, `doFill` with it, and `buildSurface` with the same `NoiseChunk`, a `WorldGenerationContext` of the generator and the chunk, the rule and the possible biomes.
4. The chunk written as `terrain`'s `fill` writes it: its blocks as runs, each read with `getBlockState`, so a section that holds only air, cave air and void air reads as air; the two `_WG` heightmaps; and the blocks marked for post-processing.

The ops give at most 2^22 blocks in all, 256 times the world's height for each. The output is `{}`.

A source the codec doesn't read is `{"invalid": "source"}`, and then a rule it doesn't read `{"invalid": "rule"}`, each with no blob: the codecs' messages are their own, so only that they don't read is compared. If anything else throws, the result is the rejection, as `rng`'s is, and no blob. Settings that don't exist, a world that isn't whole sections within the limits, an op that isn't `surface`, too many blocks and any blob are an `error` status.

### `carvers` (v1)

Chunks filled, given their materials and then carved: the whole of 26.3's `buildTerrain`, whose carvers run after the surface in the same `NoiseChunk`. Everything is as in `surface`, with these differences.

The input may also have `"carvers": c`, read by `WorldCarver.LIST_CODEC` with the registries' ops: one carver or a list, each by ID or written out. Each op is `["carve", x, z]`, and step 3 goes on, if any of the noise is left, to carve the chunk:

- Without `c`, `generateCarvers` itself, through reflection, with `Blender.empty()`, the biome manager of step 2, no `WorldGenRegion`, and the rule. So the carvers are those of the biome the generator's uncached resolver gives at each chunk's corner at height 0, for the chunks up to 8 away.
- With `c`, a copy of `generateCarvers`' loop with `c` in every chunk up to 8 away in place of its biome's: the same `WorldgenRandom`, seeded with `setLargeFeatureSeed(seed + index, x, z)` for each carver, the same `WorldGenerationContext` and `CarvingMask`, then vanilla's own `applyCarvingMask`, through reflection, with the biome manager over the uncached resolver and no filter.

The chunk is written as in `surface`. After a source and a rule, carvers that don't read are `{"invalid": "carvers"}`, with no blob; a weighted list whose weights add up past an `int` throws as it's read, and counts as not reading. An op that isn't `carve` is an `error` status.

### `features` (v4)

Chunks decorated as 26.3's `ChunkGenerator.applyBiomeDecoration` decorates them, or one placed feature placed, in a `WorldGenRegion` for the `features` step. The registries are vanilla's own, as `density`'s are, so a feature, placed feature, block state provider, biome or tag named by ID is vanilla's.

Input `{"seed": s, "settings": id, "level": [min_y, height], "source": v, "ops": [...]}`, with `"feature": f` or without, `"shared": b` or without, `"final": b` or without, and no blobs. `s`, `id`, `level` and `v` are as in `surface`. `f` is read by `PlacedFeature.CODEC` with the registries' ops: a placed feature by ID or written out. The generator is a `NoiseBasedChunkGenerator` of `v` and the settings. Each case runs on a thread of its own, as `surface`'s do. The ops, in order, at most 64:

| Op | Does |
| --- | --- |
| `["decorate", cx, cz]` | `applyBiomeDecoration` of the chunk at `cx`, `cz`, with a structure manager whose world options don't generate structures |
| `["structured", cx, cz]` | `applyBiomeDecoration` of the chunk at `cx`, `cz` with structures, as below |
| `["place", cx, cz, x, y, z, seed]` | `f.place` in the region around chunk `cx`, `cz`, at block `x`, `y`, `z`, with a `WorldgenRandom` over a `XoroshiroRandomSource` given `setSeed(seed)`, `seed` a `long` as a decimal string. It has no top feature, so a biome filter in it throws, as one in a feature placed by another does |

With `"shared": true`, the ops' chunks are one world's: a chunk an op made is kept, with whatever its decoration and later ones wrote in it, and an op whose 3×3 or 5×5 reaches it takes it as it is rather than making it again. So the ops decorate in the order given, each into what the ones before it left, as a server's decorations of neighbouring chunks do. Its starts, references and beardifiers are made again for each op, the same.

For each op, the region is made as the server makes it for the `features` step, without running its constructor, which wants the server's chunk holders:

1. The 5×5 chunks around `cx`, `cz` are new `ProtoChunk`s given their biomes as `createBiomes` gives them. The 3×3 are each filled, given their materials and carved as `carvers` does with no carvers written out, each with a biome manager over its own eight neighbours, and marked done with `terrain`.
2. The region's cache holds those 3×3 chunks and, out to 8 away, new empty chunks marked done with `structure_starts`. Its other fields are what the constructor would set: the level, a seed, level data whose game time is 0, the `worldgen_region_random` factory's random at the center, the dimension type, tick access through the chunks, the `features` step of the generation pyramid with its write radius of 1, the uncached biome resolver and a biome manager over the region.
3. The level is a stand-in for a `ServerLevel`, also made without its constructor. It gives the dimension type the settings' world has (the Nether's for `nether`, the End's for `end` and the Overworld's for any other), the generator's random state and sea level, the world's height, a server (a `DedicatedServer` made without its constructor) whose structure template manager loads each template from the vanilla data pack, `data/<namespace>/structure/<path>.nbt`, as vanilla's does, upgraded from its data version, and a light engine with no sections, as the server's is for chunks not yet lit: sky light 15 where the dimension has sky light, block light 0. It notes each point-of-interest change the region reports. It gives what a structure's mobs ask as they're made: the region's level data, whose difficulty is normal, the world's seed, which a capped processor seeds from, a clock at 0 under a full moon, as a new world's, the decoration's structure manager, over the region's chunks, where a cat asks whether it stands in a swamp hut, and the region's environment attributes, which a villager's schedule reads as it's made. Without them vanilla would make no mob there, since a template's entity that throws as it's made is skipped.

A `structured` op first makes the starts of every chunk within 9 of `cx`, `cz` as the `structures` probe's `bearded` op makes those within 8, and each of the 3×3 its references to them, in the structure registry's order, and the `Beardifier` `forStructuresInChunk` makes from them, which its terrain is filled with. The region's chunks out to 8 away are given those starts, and the 3×3 their references, and the structure manager's world options generate structures, so before each step's features `applyBiomeDecoration` places the starts the center references of each structure of the step, each piece whose box reaches the chunk post-processed and then the structure's `afterPlace`. Vanilla binds the items' default components first, as a server does as it starts, since some pieces make item stacks.

After each op, the blob gets each of the 3×3 chunks, `z` outer and `x` inner from the lower corner: written as `terrain`'s `fill` writes it; then its four final heightmaps, `WORLD_SURFACE`, `OCEAN_FLOOR`, `MOTION_BLOCKING` and `MOTION_BLOCKING_NO_LEAVES`, each column's `getHeight + 1` by `x` + 16`z`, primed if no feature primed them; its block entities by position, `y` then `z` then `x`, as a count and then each one's `x`, `y` and `z` and its NBT as `NbtIo.writeAnyTag` writes it (the `DUMMY` marker the region leaves, or the block entity's own data with full metadata once something asked for it); its block ticks and fluid ticks in the order they were scheduled, each a count and then each tick's registry ID, `x`, `y`, `z` and priority; and its entities, a count and each one's NBT with its `UUID` written as four zeros, in its place, since vanilla makes an entity's UUID from a random seeded by the clock. After a `structured` op, each entity is written only as its `id`, `Pos` and `Rotation`, since the rest of what a structure's mob saves is random or set as it spawns; a shulker's `Rotation` is written as zeros, since nothing that places one turns it and it keeps the yaw its own random, seeded from the clock, drew as it was made. Then the point-of-interest changes: a count, then each one's `x`, `y` and `z` and its old and new type's registry ID, -1 for none. The output is `{}`.

With `"final": true`, which needs `"shared": true`, nothing is written after each op. After the last, the blob gets the world's chunks instead: a count, then each chunk by `z` and then `x`, its `x` and `z` and then the chunk as above, its entities as a `structured` op's are if any op is `structured`; then every op's point-of-interest changes, a count and each as above, in order of their five numbers. So the same chunks decorated in two orders give the same blob exactly when the order made no difference to the world they left (CAL-33).

A source that doesn't read is `{"invalid": "source"}`, and then a feature that doesn't read `{"invalid": "feature"}`, each with no blob. If anything else throws, the result is the rejection, as `rng`'s is, and no blob. `applyBiomeDecoration` reports anything a feature throws as a `ReportedException` titled `Biome decoration`. Settings that don't exist, a world that isn't whole sections within the limits, more than 64 ops, an op that isn't one of those, a `place` op without `f` and any blob are an `error` status.

Calcite answers `unimplemented` for a case that reaches a feature type, a block's `canSurvive`, a placement or a structure piece it doesn't place yet.

Version 4 added `structured`.

### `structures` (v2)

Where 26.3's structure sets place structures, and the starts `ChunkGenerator.createStructures` makes. The registries are vanilla's own, as `features`' are, so the structure sets are every one in vanilla's data, in their registry's order.

Input `{"seed": s, "settings": id, "level": [min_y, height], "source": v, "ops": [...]}` and no blobs, `s`, `id`, `level` and `v` as in `surface`. The generator is a `NoiseBasedChunkGenerator` with the settings and the source, and its structure state is `createState` of the structure set registry, the settings' random state and the seed, as a server makes it: the sets with a structure whose biomes the source may give, in order.

| Op | Does |
| --- | --- |
| `["placement", cx, cz, size]` | For each of the state's structure sets: its ID with `writeUTF`, then how many chunks of the `size`×`size` square from chunk `cx`, `cz` its placement's `isStructureChunk` holds for, `size` 1 to 256, and each one's `x` and `z`, `z` outer |
| `["rings"]` | For each set placed in concentric rings: its ID, then how many positions `getRingPositionsFor` gives, -1 for none, and each one's `x` and `z` |
| `["starts", cx, cz]` | `createStructures` on a new `ProtoChunk` at chunk `cx`, `cz`, with a structure manager made without its constructor, which reads and writes only that chunk's starts, and a template manager that loads vanilla's templates as `features`' does; then the chunk's starts as a saved chunk's `structures.starts` compound has them, with `NbtIo.writeAnyTag` |
| `["ring_starts", n]` | For each set placed in concentric rings, how many of its first `n` positions, 0 to 16, there are, then the starts made at each as `starts` makes them |
| `["bearded", cx, cz]` | `createStructures`, as `starts` runs it, on a new `ProtoChunk` for every chunk within 8 of chunk `cx`, `cz`; then `createReferences` for the chunk at `cx`, `cz` over a level of those chunks alone, with a structure manager that reads them. Its references are put in the structure registry's order, since vanilla keeps them in a map by the structures' identity hashes, which no two runs need iterate alike. Then how many structures it references, and each one's ID with `writeUTF`, how many start chunks and each one's `ChunkPos.pack`ed position as a `long`, in its `LongOpenHashSet`'s order; then the chunk filled as `terrain`'s `fill` fills it, but with the `Beardifier` `forStructuresInChunk` makes from those references, and written as `fill` writes it |
| `["ring_bearded", k]` | For each set placed in concentric rings, whether it has a `k`th position, as a byte 1 or 0, then `bearded` at that position if it does |

The output is `{}`, with one blob of each op's bytes in order. A source that doesn't read is `{"invalid": "source"}` with no blob. If anything else throws, the result is the rejection, as `rng`'s.

Calcite answers `unimplemented` for a case that reaches a structure type, a placement or a piece it doesn't make yet.

Version 2 added `bearded` and `ring_bearded`.

### `datafix` (v1)

Data saved by an older game, upgraded to 26.3's by vanilla's data fixers, as a structure template is when it loads: `TemplateSource.readStructure` runs `DataFixTypes.STRUCTURE.updateToCurrentVersion` on it.

Input `{"type": "structure", "snbt": text, "version": v}`. The data is `text`, a compound in SNBT as `TagParser.parseCompoundFully` reads it, or, without `snbt`, the one blob, a gzipped NBT file as `NbtIo.readCompressed` reads it. `v`, optional, is the data version it's upgraded from, a decimal integer as a string, cast to an `int`; without it, it's the data's own `DataVersion`, 500 without one, as `NbtUtils.getDataVersion` reads it.

The output is `{"snbt": s}`, `s` the upgraded compound as `CompoundTag.toString` writes it, its keys sorted. Where the fixers throw, as they do for a text whose JSON is a number, the output is `{"loads": false}`: `TemplateSource.load` logs what reading a template throws and has no template.

Calcite answers `unimplemented` for data older than 2700, or with a part that only fixes it doesn't port yet reach (D285).

## Adding a probe

1. Add its section here, with version 1.
2. Implement it in the vanilla adapter and add it to its `hello`.
3. Add case files under `cases/<probe>/`.
4. Record vanilla's results with the runner and commit the hashes.
5. The Calcite adapter answers `unimplemented` until Calcite can run it.
