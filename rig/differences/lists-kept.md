---
title: A player list that can't be read isn't written over
kind: bug
cases:
  - login:list-unreadable-*
---

# A player list that can't be read isn't written over

**Vanilla:** as it starts, `DedicatedPlayerList` loads banned-players.json, banned-ips.json, ops.json and whitelist.json, then saves the first three whatever happened. A list that can't be read is logged, as `Failed to load operators list: ...`, and keeps what it read before it broke: nothing if the file isn't JSON, or the entries before the first that isn't an object. Saving it then writes those over the file, so a typo in ops.json leaves `[]` and every op gone. The whitelist is only written when it's missing.

**Calcite:** a list that can't be read is logged the same way and keeps the same entries, but the file is left as it is, so it can be fixed and the server started again. A list that's missing is written as `[]`, as vanilla writes it ([D161](../../docs/decisions.md)).

**Why:** losing a server's ops and bans to one wrong character is a side effect of saving every list as it starts, not a choice, and no one is let in or kept out differently while the server runs.

No rig probe compares the server's folder yet, so `login:list-unreadable-*` names the cases one would have.
