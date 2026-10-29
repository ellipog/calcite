---
title: logs/latest.log rolls once as the server starts
kind: bug
cases:
  - log:rollover-*
---

# logs/latest.log rolls once as the server starts

**Vanilla:** Mojang's log4j2.xml gives logs/latest.log two triggering policies. `TimeBasedTriggeringPolicy` comes first, and sets its next roll to the midnight after the file's own time, the day it was last written. Then `OnStartupTriggeringPolicy` archives the file left from before. That leaves the next roll at a midnight that's already past. So the first line the server logs rolls the file again. The new latest.log is still empty, so there's nothing to archive, and log4j deletes the empty file. `DefaultRolloverStrategy` still purges the old day's archives first, though:

- **With 7 that day**, it removes the lowest and moves the rest down again. The day ends with 6, and one archive more is lost. With `2026-10-28-1` to `-7` holding f1 to f7, and yesterday's latest.log, vanilla leaves f3 to f7 and that file as 1 to 6.
- **With a number of 7 or more**, it moves every archive down once more. {3, 7} becomes {1, 5, 6}, not {2, 6, 7}.

This was measured by running log4j 2.26.0 with Mojang's configuration in set-up folders (CAL-46).

**Calcite:** a roll with nothing to archive does nothing. So each start archives the old file once, with the same name and number as vanilla's first roll, and the day's archives are moved once. Everything else is as vanilla does it: the names, the numbers, the gaps, the 7 a day, and when the file rolls. [`src/test/log_file.calx`](../../src/test/log_file.calx) checks each case, and says what vanilla left where this changes it.

**Why:** the second roll is a side effect of the policies' order, not a choice. It deletes a log for no reason. Nothing reads the logs folder by number, and no player can see it.

No rig probe compares the logs folder yet, so `log:rollover-*` names the cases one would have.
