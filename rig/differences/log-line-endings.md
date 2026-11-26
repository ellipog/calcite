---
title: logs/latest.log ends its lines with \n on every system
kind: platform
cases:
  - log:line-endings
---

# logs/latest.log ends its lines with `\n` on every system

**Vanilla:** Mojang's pattern ends each line with log4j's `%n`, which is Java's `System.lineSeparator()`. That's `\r\n` on Windows and `\n` elsewhere, in latest.log and on the console alike.

**Calcite:** each line ends with `\n`, in latest.log and on the console, on Windows too, as Calx writes the same bytes on every system (`std.io`). So does each line of the traces `debug function` writes to `debug/`, which vanilla ends with `PrintWriter.println`'s separator, the same `\r\n` on Windows. Apart from that, the `select` session's traces are vanilla's, byte for byte ([D962](../../docs/decisions.md)).

**Why:** a log's lines then read the same wherever they were written, and every tool that reads them, Notepad included, takes `\n`. Hosting panels such as Pterodactyl run on Linux, where vanilla writes `\n` anyway.

No rig probe compares log files yet, so `log:line-endings` names the case one would have.
