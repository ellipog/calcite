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

### `math` and `strictmath` (v1)

Input `{"fn": <name>}` and one blob of `f64` arguments, big-endian. `atan2`, `pow` and `hypot` take them in pairs.

Output: `{}` and one blob, `java.lang.Math.<fn>` (for `math`) or `java.lang.StrictMath.<fn>` (for `strictmath`) of each argument, as `f64` bits.

Functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `exp`, `log`, `log10`, `log1p`, `pow`, `sqrt`, `cbrt`, `sinh`, `cosh`, `tanh`, `expm1`, `hypot`.

Vanilla calls `Math`. In the rig's reference configuration (HotSpot's LIBM intrinsics off, D60), `Math` gives exactly `StrictMath`'s results, so both probes' hashes are the same there. With HotSpot's default intrinsics they differ, and `rig/runner/mathcmp.py` measures by how much (`P1.5`).

### `mth` (v1)

Vanilla's `Mth` helpers that use lookup tables or bit tricks, where a natural reimplementation would round differently.

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

On open maps and sets, `["trim"]` gives nothing. It shrinks the table to fit, which changes the iteration order.

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

### `registries` (v1)

What a server with only the vanilla data pack sends a client in configuration: its known packs, the synchronized registries in `registry_data`, and the tags in `update_tags`. The registries load once, as `WorldLoader.load` loads them, and are kept. Identifiers are written whole, `minecraft:stone`.

| Input | Output |
| --- | --- |
| `{"op": "known_packs"}` | `packs`: the server's known packs in order, each `[namespace, id, version]` |
| `{"op": "synced"}` | `registries`: each synchronized registry in the order the server sends them, `{name, entries}`, with `entries` in ID order, each `[id, sent_with_data]`. An entry from a pack the client knows goes without its data |
| `{"op": "tags", "registry": name}` | `tags`: the registry's tags as `update_tags` sends them, by name in string order, each `[name, ids]` with the entries' IDs in the order sent. An empty list for a registry it sends no tags for |

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

## Adding a probe

1. Add its section here, with version 1.
2. Implement it in the vanilla adapter and add it to its `hello`.
3. Add case files under `cases/<probe>/`.
4. Record vanilla's results with the runner and commit the hashes.
5. The Calcite adapter answers `unimplemented` until Calcite can run it.
