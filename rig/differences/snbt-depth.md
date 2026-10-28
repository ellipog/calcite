---
title: SNBT nesting has a fixed depth limit
kind: bug
cases:
  - nbt:snbt-compound-depth-51?
  - nbt:snbt-list-depth-51?
---

# SNBT nesting has a fixed depth limit

**Vanilla:** the SNBT parser (`TagParser`, over `SnbtGrammar`) recurses once per nesting level and has no depth limit of its own. Nest compounds or lists deeply enough and it throws `StackOverflowError`. How deep is enough depends on the thread's stack size, the JIT tier each parser method has reached, and what ran before. In the self-check, compounds overflowed somewhere between depth 511 and 514 depending on case order and compiler, and lists did only under the interpreter. Depth 256 never overflowed.

Binary NBT doesn't have this problem: `NbtAccounter` stops reading at depth 512 with an `NbtAccounterException`.

**Calcite:** SNBT gets the same limit as binary NBT. Nesting past it is rejected with a normal parse error, the same on every machine. Shallower input, such as the depth 128 and 256 cases, must still match vanilla exactly.

The levels are compounds, lists and operations such as `bool(...)` together, since each is a rule that recurses, and vanilla overflows on any mix of them. The 513th level fails the parse at once, whatever else could have read it: the error is `Tried to read NBT tag with too high complexity, depth > 512`, the message binary NBT has, at the position of that level's `{`, `[` or `(`, so `[` 513 times fails at position 512. [`src/test/snbt.calx`](../../src/test/snbt.calx) checks both kinds.

**Why:** a `StackOverflowError` is an `Error`, not an `Exception`, so it gets past the `catch (Exception e)` in both `Commands.performCommand` and `PacketProcessor` instead of being handled as a failed parse. Calcite has no JVM stack to overflow, so copying the exact depth isn't even possible. A fixed limit is deterministic, matches the binary one, and is far deeper than real data needs. The depth 511 to 514 cases are also quarantined (`expected/26.3/quarantine.json`), since vanilla's own result isn't repeatable.
