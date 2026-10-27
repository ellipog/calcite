<img src="assets/logo/calcite-banner.png" alt="Calcite" width="100%">

A Minecraft Java Edition server written from scratch in [Calx](https://github.com/ellipog/calx). It targets 26.3.

Goals:

- **Plugin development.** Native Calx plugins at full speed and sandboxed WASM addons, both built against one documented host API.
- **Performance.** Folia-style regions on every core, ticking in lockstep so results never depend on the thread count.
- **Vanilla parity.** Worldgen matches block for block and behavior matches vanilla, checked bit for bit by an oracle rig. Bugs and exploits are fixed and listed.

Status: Phases 0 to 3 have passed their gates and are in review. That covers the design, the oracle rig, the data tables generated from the vanilla jar, and the Calx compiler core. Calcite's first Calx code, vanilla's random sources, passes the rig's `rng` probe bit for bit on Windows and Linux. Calx runs the Phase 3 tick-loop benchmark in about 0.7× the time of its Rust reference ([results](https://github.com/ellipog/calx#performance)). Next is Phase 4: the protocol, and a flat world a real client can join.

Acta board: aaen-studios/calcite ([open](https://acta.aaenz.no/aaen-studios/calcite)). Calx has its own board, aaen-studios/clx ([open](https://acta.aaenz.no/aaen-studios/clx)). The phase gates live here.

## Docs

- [Build plan](docs/PLAN.md): phases, tasks and gates
- [Decision log](docs/decisions.md): everything that's settled, and why
- [Host API sketch](plugins/api/HOST_API.md): the plugin contract
- [Source](src/README.md): Calcite's Calx modules and their tests
- [Oracle rig](rig/README.md): how Calcite is checked against vanilla, bit for bit
- [Data generator and tables](oracle/datagen/README.md): the tables Calcite's codegen reads, generated from the jar

## License

MIT. Calcite contains no Mojang code or assets. It downloads the official server jar from Mojang and reads vanilla's data from it.
