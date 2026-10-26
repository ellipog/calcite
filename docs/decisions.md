# Decision log

The source of truth for settled questions, alongside `CALX_SPEC.md`. Add new decisions at the bottom with the next number. Never edit an old entry; supersede it with a new one that names it.

| # | Date | Decision | Choice | Applies from |
| --- | --- | --- | --- | --- |
| D1 | 2026-10-26 | Target version | 26.3. Support one version at a time, and stay on 26.3 until Phase 5 is done | Phase 0 |
| D2 | 2026-10-26 | Scope | Server only, no client | Phase 0 |
| D3 | 2026-10-26 | Concurrency | Region actors only | Phase 0 |
| D4 | 2026-10-26 | Calcite | Written from scratch, with no code from other servers | Phase 0 |
| D5 | 2026-10-26 | Calx | Written from zero, with no Goose code. Goose's design notes may be read for ideas | Phase 0 |
| D6 | 2026-10-26 | Calx compiler | Written in C++, emitting C, built with clang | Phase 3 |
| D7 | 2026-10-26 | Platforms | Windows and Linux from the first commit; macOS later | Phase 3 |
| D8 | 2026-10-26 | License | MIT. Don't read GPL servers (Pumpkin, Paper, Folia) | Phase 0 |
| D9 | 2026-10-26 | Parity | Exact in single-region tests. Multi-region runs are deterministic and match single-region runs on everything not driven by randomness. Global state lives in one central world actor | Phase 5 |
| D10 | 2026-10-26 | Vanilla bugs | Functional parity: bugs and exploits are fixed, not copied, and each fix is listed in `rig/differences/` as a deliberate difference | Phase 1 |
| D11 | 2026-10-26 | Rig runner | Python | Phase 1 |
| D12 | 2026-10-26 | Proxy support | Velocity modern forwarding built in | Phase 4 |
| D13 | 2026-10-26 | Bedrock | Not built in. Left to a proxy (Geyser standalone) or a plugin (Floodgate-style auth) | — |
| D14 | 2026-10-26 | Plugins | Native Calx plugins first, WASM also supported, both built against one host API | Phase 0 |
| D15 | 2026-10-26 | Native plugin limits | Host API only by default. `extern` C calls only for plugins marked trusted in the server config | Phase 0 |
| D16 | 2026-10-26 | Plugin instances | One instance per region plus one global instance per plugin, talking by messages | Phase 0 |
| D17 | 2026-10-26 | WASM runtime | Embed Wasmtime (Apache 2.0). A custom WASM-to-C compiler is an option after Phase 8 | Phase 7 |
