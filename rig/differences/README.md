---
title: Deliberate differences
description: Every place Calcite means to differ from vanilla, the rig cases it affects, and why.
---

# Deliberate differences

Calcite matches vanilla bit for bit, except where vanilla has a bug or an exploit worth fixing (`P1.8`). Each such difference gets one file here. The scoreboard reports cases a difference covers separately, as **Difference**, instead of counting them as failures. So a fix never looks like a regression, and a failure nobody explained never hides as a fix.

## A difference file

One Markdown file per difference, named for it, such as `snbt-depth.md`:

```markdown
---
title: SNBT nesting has a fixed depth limit
kind: bug
cases:
  - nbt:snbt-compound-depth-51?
  - nbt:snbt-list-depth-51?
---

What vanilla does, what Calcite does instead, and why.
```

| Field | Meaning |
| --- | --- |
| `title` | One line saying what Calcite does differently |
| `kind` | `bug` (a vanilla bug Calcite fixes), `exploit` (one it closes), `performance` (an unobservable shortcut that the rig can still see), or `platform` (where vanilla depends on its JVM or OS) |
| `cases` | The cases it covers, as `probe:case-id` globs. At least one |

The body says what vanilla does, what Calcite does, and why the difference is worth it. Link the decision if there is one.

## Rules

- **Only listed cases are excused.** A case fails unless a difference here covers it, and a difference covers only the cases it names.
- **A difference that passes is flagged.** If a covered case matches vanilla after all, the scoreboard notes it, since the entry may be out of date.
- **Quarantine is different.** A quarantined case is one where vanilla itself isn't repeatable, found by the self-check and listed in `expected/26.3/quarantine.json`. It isn't scored at all. A difference is a choice Calcite makes. A case can be both, as the SNBT depth cases are.
- **Players should rarely notice.** Fixing a bug that players or farms rely on breaks vanilla parity in a way that matters. Those stay unfixed, or become a config option that's off by default.

## Differences

| File | Kind | What changes |
| --- | --- | --- |
| [`log-line-endings.md`](log-line-endings.md) | platform | logs/latest.log ends its lines with `\n` on Windows too |
| [`log-second-roll.md`](log-second-roll.md) | bug | logs/latest.log rolls once at start, so an archive isn't lost |
| [`snbt-depth.md`](snbt-depth.md) | bug | Deeply nested SNBT is rejected at depth 512, instead of overflowing the stack |
