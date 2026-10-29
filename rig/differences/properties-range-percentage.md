---
title: An entity-broadcast-range-percentage that isn't a number is the default
kind: bug
cases:
  - properties:entity-broadcast-range-percentage-not-a-number
---

# `entity-broadcast-range-percentage` that isn't a number

**Vanilla:** `DedicatedServerProperties` reads `entity-broadcast-range-percentage` with `Integer.parseInt` and no default for a value that doesn't parse, as every other number it reads has. So `entity-broadcast-range-percentage=abc` throws a `NumberFormatException`, and the server logs `Failed to start the minecraft server` and stops, measured with the 26.3 jar.

**Calcite:** it's the default, 100, as `max-players=abc` is 20, and that's what it writes back to server.properties. A number is kept between 10 and 1000, as vanilla keeps it.

**Why:** the one setting that stops the server over a typo is an oversight, not a choice: every other number vanilla reads, `max-world-size` and its neighbors included, falls back to its default.

No rig probe compares server.properties yet, so the case names the one it would have.
