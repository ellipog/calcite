// Writes src/lib/data.ts, the numbers the site and the brand guide show, from bench/results and the
// light table in bench/README.md, so a new benchmark run reaches the site with `bun run data`. The
// build runs it first, so a deploy always shows what the repo has recorded.

import { readFileSync, writeFileSync } from 'node:fs';

const read = (f: string) => JSON.parse(readFileSync(`../bench/results/${f}`, 'utf8'));
const r1 = (v: number) => Math.round(v * 10) / 10;
const short = (c: string) => String(c).slice(0, 7);

const client = read('client-windows.json'), gen = read('worldgen-windows.json'), packs = read('terralith-windows.json');
const others = read('others-windows.json'), botsW = read('bots-windows.json'), botsL = read('bots-linux.json');

const machine = {
	cpu: String(gen.machine.cpu).replace(/^13th Gen Intel\(R\) Core\(TM\) /, ''),
	cores: gen.machine.cores,
	threads: gen.machine.threads,
	memory: Math.round(gen.machine.memory_gib),
	os: String(gen.machine.os).startsWith('Windows-11') ? 'Windows 11' : String(gen.machine.os),
};

const flights: Record<string, unknown> = {};
for (const r of client.runs) {
	const f = r.flight;
	flights[String(Math.round(r.speed))] = {
		had: f.had_of_view,
		samples: f.view_samples.map(([t, p]: number[]) => [Math.round(t * 100) / 100, r1(p)]),
		blocks: r1(f.blocks_a_second),
		sent: r1(f.chunks_a_second),
		nearest: f.nearest_missing,
		forgotten: f.forgotten,
		join: { chunks: r.join.chunks, p95: r.join.client_had_95_s, all: r.join.client_had_all_s },
		mspt: { mean: r.ticks.mspt_mean, p99: r.ticks.mspt_p99, max: r.ticks.mspt_max },
		memory: { idle: r.memory_mib.idle, still: r.memory_mib.joined, peak: r.memory_mib.peak },
	};
}

const calciteRuns = (runs: Record<string, number>[]) =>
	runs.map((r) => ({
		threads: r.threads,
		cps: r1(r.chunks_per_second),
		steady: r.steady_chunks_per_second ? r1(r.steady_chunks_per_second) : null,
		cpu: Math.round(r.cpu_seconds),
		mem: Math.round(r.peak_memory_mib),
	}));
const javaRuns = (runs: Record<string, number>[]) => runs.map((r) => ({ threads: r.threads, cps: r1(r.chunks_per_second), cpu: Math.round(r.cpu_seconds) }));

// The light table: | Workload | Vanilla | Calcite | Calcite is |
const readme = readFileSync('../bench/README.md', 'utf8');
const lightAt = readme.indexOf('## Light');
const light = [...readme.slice(lightAt).matchAll(/^\| ([^|]+?) \| ([\d.]+) ms \| ([\d.]+) ms \| ([\d.]+)× as fast \|$/gm)].map((m) => ({
	name: m[1],
	vanilla: +m[2],
	calcite: +m[3],
	x: +m[4],
}));
const lightCommit = /at commit (\w{7})/.exec(readme.slice(lightAt))?.[1] ?? '';
if (light.length < 2) throw new Error('bench/README.md: the light table moved; fix the pattern in scripts/data.ts');

// Vanilla's own worldgen at the end of Phase 5, which the README gives beside the runs now.
const was = /At (\w{7}) these were ([\d.,]+), ([\d.,]+), ([\d.,]+) and ([\d.,]+)\./.exec(readme);
if (!was) throw new Error("bench/README.md: the worldgen 'At ... these were' line moved; fix the pattern in scripts/data.ts");
const before = { commit: was[1], cps: was.slice(2, 6).map((v) => +v.replace(/,/g, '')) };

const bots = (b: Record<string, Record<string, number>>) => {
	const m = b.medians;
	return {
		mean: m.mspt_mean,
		p99: m.mspt_p99,
		max: m.mspt_max,
		tps: m.tps,
		joinMean: m.joining_mspt_mean,
		joinMax: m.joining_mspt_max,
		joinMs: m.join_ms_median,
		joinMsMax: m.join_ms_max,
		cpu: m.cpu_seconds,
		mem: m.peak_memory_mib,
		chunks: m.chunks_sent,
		mib: m.mib_received,
	};
};

const data = {
	machine,
	flight: { commit: short(client.commit), view: client.view, seconds: client.flight_seconds, runs: flights },
	worldgen: { commit: short(gen.commit), runs: calciteRuns(gen.runs), before },
	packs: {
		commit: short(packs.commit),
		othersCommit: short(others.commit),
		packs: packs.packs.map((p: { name: string; version: string }) => `${p.name} ${p.version}`),
		seed: packs.seed,
		radius: packs.measured.radius,
		warmup: packs.warmup.radius,
		chunks: packs.runs[0].chunks,
		calcite: calciteRuns(packs.runs),
		c2me: javaRuns(others.servers.c2me.runs),
		paper: javaRuns(others.servers.paper.runs),
		vanilla: javaRuns(others.servers.vanilla.runs),
		versions: {
			c2me: others.files.c2me.version.replace(/\+.*/, ''),
			paper: others.files.paper.version,
			fabric: others.files.fabric.version.replace(/,.*/, '').replace('loader ', ''),
			chunky: others.files['chunky-fabric'].version,
		},
	},
	light: { commit: lightCommit, runs: light },
	bots: { commit: short(botsW.commit), runs: botsW.runs, scenario: botsW.scenario, windows: bots(botsW), linux: bots(botsL) },
	calciteProperties: calciteProperties(),
};

// The calcite.properties Calcite writes on its first start, from default_text() in
// src/server/config.calx. The download page's setup ships it with the values picked, and that page
// is regenerated where only site/ is deployed, so it can't read src/ itself.
function calciteProperties() {
	const src = readFileSync('../src/server/config.calx', 'utf8').replace(/\r\n/g, '\n');
	const body = src.slice(src.indexOf('pub fn default_text()'));
	const end = body.indexOf('\n}');
	const lines = [...body.slice(0, end).matchAll(/push_str\("((?:[^"\\]|\\.)*)"\)|String\("((?:[^"\\]|\\.)*)"\)/g)].map((m) => (m[1] ?? m[2]).replace(/\\n$/, '').replace(/\\"/g, '"').replace(/\\\\/g, '\\'));
	if (lines.length < 10 || !lines.some((l) => l.startsWith('login-throttle='))) throw new Error('src/server/config.calx: default_text moved; fix calciteProperties in site/scripts/data.ts');
	return lines.join('\n') + '\n';
}

writeFileSync(
	'src/lib/data.ts',
	'// The numbers the site and the brand guide show, from bench/results and bench/README.md\'s light\n' +
		'// table. Made by scripts/data.ts, which the build runs; run `bun run data` after a benchmark.\n\n' +
		`export const DATA = ${JSON.stringify(data)} as const;\n`,
);
console.log('data.ts:', Object.keys(flights).join(', '), 'flights;', gen.runs.length, 'worldgen runs;', light.length, 'light workloads');
