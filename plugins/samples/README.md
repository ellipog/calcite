# Sample addons

Written first in imagined Calx syntax (Phase 0). They become the acceptance test for the plugin host in Phase 7. Each one is chosen to stress a different part of the host API.

| Addon | Stresses |
| --- | --- |
| `/home` command with saved data | Commands, persistent per-player data, teleporting |
| Chat filter | Events that can cancel or rewrite, string handling |
| Custom mob drop | Entity and loot events, item creation |
| Cross-region teleport | Messaging between region instances, handing a player from one region to another |
| Timed world event | Scheduler, global instance, broadcasting to every region |

Phase 0 is done when all five are written without hand-waving over a missing feature.
