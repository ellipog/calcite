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
 "probes": {"ping": 1, "rng": 1, "nbt": 1, "text": 1, "math": 1, "strictmath": 1, "mth": 1}}
```

A probe the adapter doesn't list is reported as unimplemented, without being run.

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

An input that the game itself rejects, such as SNBT with a syntax error, is still `ok`. The rejection is the result, and it's compared like any other.

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

- `id` is unique within the probe.
- A case with blobs lists them as base64 strings in `"blobs"`.
- Generated case files say what generated them in a top-level `"generated_by"` field, and the generator is committed beside them with its seed.

## Probes

Each probe is a pure function of its input. Version numbers change when a probe's input or output format changes, and old expected hashes are re-recorded.

### `ping` (v1)

Input `{"echo": <any JSON>}`. Output `{"echo": <the same>}`. For testing the rig itself.

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

If the game throws, as `nextInt(0)` does, the run stops there and the output is `{"error": <the exception's class name>, "at": <the operation's index>}`, with the blob holding the results before it. An operation that doesn't apply to the current source, such as `setDecorationSeed` after `fork`, is an `error` status: the case is wrong, not the game.

### `nbt` (v1)

Input, one of:

- `{"from": "snbt", "snbt": "..."}`: parsed with `TagParser.parseCompoundFully`
- `{"from": "binary"}` with one blob: an unnamed binary tag, read with `NbtIo.readAnyTag` and no size limit

Output: `{"snbt": <the tag's toString()>, "type": <the tag type ID>}` and one blob, the tag written with `NbtIo.writeAnyTag`. If parsing fails: `{"error": <the exception's message>}` and no blobs.

### `text` (v1)

Input `{"json": "..."}`: a text component as JSON, decoded with `ComponentSerialization.CODEC` and `JsonOps`.

Output: `{"json": <re-encoded with the same codec, as compact JSON>, "plain": <getString()>}` and one blob, the component encoded with `NbtOps` and written with `NbtIo.writeAnyTag`. That's the protocol's form since 1.20.3. If decoding fails: `{"error": <the codec's error message>}`.

v1 decodes without registries, so components that need them (hover events showing items or entities) return `unimplemented`.

### `math` and `strictmath` (v1)

Input `{"fn": <name>}` and one blob of `f64` arguments, big-endian. `atan2` and `pow` take them in pairs.

Output: `{}` and one blob, `java.lang.Math.<fn>` (for `math`) or `java.lang.StrictMath.<fn>` (for `strictmath`) of each argument, as `f64` bits.

Functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `exp`, `log`, `log10`, `log1p`, `pow`, `sqrt`, `cbrt`, `sinh`, `cosh`, `tanh`, `expm1`, `hypot`.

The `math` hashes are what Calcite must match, since vanilla calls `Math`. Comparing the two probes' goldens shows where `Math` and `StrictMath` differ (`P1.5`, D58).

### `mth` (v1)

Vanilla's `Mth` helpers that use lookup tables or bit tricks, where a natural reimplementation would round differently.

| Input | Output blob |
| --- | --- |
| `{"fn": "sin_table"}` | All 65,536 entries of `Mth`'s sine table, in order, as `f32` bits. Entry *i* is `Mth.sin(i / 10430.378350470453)`, which reads entry *i* exactly |
| `{"fn": "sin"}`, `{"fn": "cos"}` with a blob of `f64` arguments | `Mth.sin` or `Mth.cos` of each, as `f32` bits |
| `{"fn": "atan2"}` with a blob of `(y, x)` `f64` pairs | `Mth.atan2(y, x)` of each, as `f64` bits. It uses `Mth`'s own arcsine tables, not `Math.atan2` |
| `{"fn": "fast_inv_sqrt"}` with a blob of `f64` arguments | `Mth.fastInvSqrt` of each, as `f64` bits |
| `{"fn": "wrap_degrees"}` with a blob of `f32` arguments | `Mth.wrapDegrees(float)` of each, as `f32` bits |
| `{"fn": "floor"}` with a blob of `f64` arguments | `Mth.floor(double)` of each, as int |
| `{"fn": "get_seed"}` with a blob of `(x, y, z)` int triples | `Mth.getSeed(x, y, z)` of each, as long |

## Adding a probe

1. Add its section here, with version 1.
2. Implement it in the vanilla adapter and add it to its `hello`.
3. Add case files under `cases/<probe>/`.
4. Record vanilla's results with the runner and commit the hashes.
5. The Calcite adapter answers `unimplemented` until Calcite can run it.
