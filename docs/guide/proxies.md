---
title: Behind a proxy
description: Run Calcite behind a Velocity proxy with modern forwarding, as Paper does.
---

# Behind a proxy

Calcite takes players from a [Velocity](https://papermc.io/software/velocity) proxy with its modern forwarding, as Paper does. The proxy checks each player's account and forwards who they are, signed with a secret both sides share.

## Set it up

In Velocity's `velocity.toml`:

```toml
player-info-forwarding-mode = "modern"
```

In Calcite's `calcite.properties`, with the text of Velocity's `forwarding.secret`:

```properties
velocity-forwarding=true
velocity-secret=the text of forwarding.secret
```

Then add the server to Velocity's `[servers]` as any other. Keep Calcite's port closed to everyone but the proxy: with forwarding on, it lets players in only through it.

## What it does

- After a player's hello, Calcite asks the proxy for the player's data on `velocity:player_info`, version 4, and checks its signature with the secret.
- The player gets the address, UUID, name and skin the proxy sends. The log shows that address.
- The proxy has checked the account, so `online-mode` is ignored, and its warning isn't logged.
- `login-throttle` is ignored, since every player comes from the proxy's address.

A client that comes straight to the server, past the proxy, is told `This server only lets players in through its Velocity proxy`. Data signed with another secret, or that can't be read, is turned away with a line in the log saying which.

`velocity-forwarding=true` with no `velocity-secret` stops the server as it starts, with a line saying so.
