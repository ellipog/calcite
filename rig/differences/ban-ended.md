---
title: A ban that has ended is no ban
kind: bug
cases:
  - login:ban-ended-*
---

# A ban that has ended is no ban

**Vanilla:** `PlayerList.canPlayerLogin` asks `UserBanList.isBanned`, which only looks the player up, so a ban whose `expires` has passed still answers yes. It then calls `get`, which first drops every ban that has ended and so returns null, and reads the ban's reason from that. The login fails with a `NullPointerException`, and the next one finds no ban. An IP ban that has ended does the same.

**Calcite:** a ban that ended before the login is no ban, so the player gets in on the first try. A ban ends after its `expires`, not at it, as vanilla's `hasExpired` has it ([D161](../../docs/decisions.md)). [`src/test/access.calx`](../../src/test/access.calx) checks a ban a millisecond either side of its end.

**Why:** the exception is an oversight between two methods, not a choice. The player it hits is one vanilla meant to let in.

No rig probe or session scenario bans a player yet, so `login:ban-ended-*` names the cases one would have.
