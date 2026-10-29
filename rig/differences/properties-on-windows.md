---
title: server.properties ends its lines with \n on Windows, and names the zone by its offset
kind: platform
cases:
  - properties:store-line-endings
  - properties:store-date-zone
---

# server.properties on Windows

**Vanilla:** `Properties.store` ends each line with Java's `System.lineSeparator()`, `\r\n` on Windows. Its date line is `Date.toString()`, which names the zone by its abbreviation, such as `CET`, from the JDK's own copy of tzdata, wherever it runs.

**Calcite:** each line ends with `\n`, on Windows too, as in logs/latest.log ([log-line-endings](log-line-endings.md)). The zone's name is the system's tzdata abbreviation, which is Java's in each of the 37 zones measured with JDK 25, and where it's only a number, such as Istanbul's `+03`, the offset as Java writes it then, `GMT+03:00`. Windows names zones only in full, such as `W. Europe Standard Time`, so there the name is always the offset: `#Thu Oct 29 10:48:03 GMT+01:00 2026` for vanilla's `#Thu Oct 29 10:48:03 CET 2026`.

**Why:** the file then reads the same wherever it was written, and every editor takes `\n`. The date is a comment that nothing reads. Naming the zone on Windows as Java does would mean carrying a table from Windows' zones to tzdata's and each one's abbreviations, for that comment alone. Elsewhere, where servers are usually hosted, the file is vanilla's byte for byte.

No rig probe compares server.properties yet, so the cases name the ones it would have.
