// Writes src/lib/brand/data.ts from the bench results the guide's charts show: the real-client
// flights (client-windows.json) and vanilla's worldgen through the whole server
// (worldgen-windows.json). Run from site/: bun run data

import { readFileSync, writeFileSync } from 'node:fs';

const read = (f: string) => JSON.parse(readFileSync(`../bench/results/${f}`, 'utf8'));
const c = read('client-windows.json'), w = read('worldgen-windows.json');
const r1 = (v: number) => Math.round(v * 10) / 10;

const flights: Record<string, { had: number[]; samples: [number, number][] }> = {};
for (const r of c.runs) {
	const f = r.flight;
	flights[String(Math.round(r.speed))] = {
		had: f.had_of_view,
		samples: f.view_samples.map(([t, p]: number[]) => [Math.round(t * 100) / 100, r1(p)]),
	};
}
const gen = w.runs.map((r: Record<string, number>) => ({
	threads: r.threads,
	cps: r1(r.chunks_per_second),
	steady: r.steady_chunks_per_second ? r1(r.steady_chunks_per_second) : null,
	mem: r.peak_memory_mib,
}));
const data = {
	flight: { commit: String(c.commit).slice(0, 7), view: c.view, seconds: c.flight_seconds, runs: flights },
	worldgen: { commit: String(w.commit).slice(0, 7), runs: gen },
};
writeFileSync(
	'src/lib/brand/data.ts',
	"// The numbers the brand guide's charts show, from bench/results (client-windows.json and\n" +
		'// worldgen-windows.json). Made by scripts/data.ts; run `bun run data` after a benchmark.\n\n' +
		`export const DATA = ${JSON.stringify(data)} as const;\n`,
);
console.log(Object.keys(flights), gen.length, 'worldgen runs');
