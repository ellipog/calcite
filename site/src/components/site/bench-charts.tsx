'use client';

// The benchmark page's charts, which take functions in their configs and so draw on the client.

import { useMemo } from 'react';
import { BarChart, LineChart, type LineCfg } from '@/components/charts';
import { DATA } from '@/lib/data';

const fmt = (v: number, d = 1) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const threads = (n: number) => `${n} thread${n > 1 ? 's' : ''}`;

/** How much of its view Mojang's client had, flying at one speed. */
export function FlightChart({ speed }: { speed: '25' | '100' }) {
	const f = DATA.flight.runs[speed];
	const cfg = useMemo<LineCfg>(
		() => ({
			x: [0, DATA.flight.seconds],
			y: [0, 100],
			xTicks: [0, 10, 20, 30],
			yTicks: [0, 25, 50, 75, 100],
			xFmt: (t) => (t === 30 ? '30 s' : `${t}`),
			yFmt: (p) => (p === 100 ? '100%' : `${p}`),
			series: [{ pts: f.samples, area: 0.62, end: `<b>${fmt(f.had[0])}%</b><br>on average` }],
			endW: 96,
			tip: (t, s) => `<b>${fmt(t, 1)} s</b> into the flight at ${speed}×<br>${fmt(s[0][1])}% of the view`,
		}),
		[f, speed],
	);
	return <LineChart cfg={cfg} label={`Line chart: the share of its view Mojang's client had, flying at ${speed} times vanilla's speed`} />;
}

const B = DATA.worldgen.before;
const BEFORE: Record<number, number> = Object.fromEntries(DATA.worldgen.runs.map((r, i) => [r.threads, B.cps[i]]));

/** Vanilla's own worldgen through the whole server, by threads, now and at the end of Phase 5. */
export function ThreadsChart() {
	const W = DATA.worldgen.runs;
	const cfg = useMemo<LineCfg>(
		() => ({
			x: [0, 32],
			y: [0, 2100],
			xTicks: [1, 8, 16, 32],
			yTicks: [0, 500, 1000, 1500, 2000],
			xFmt: (v) => (v === 32 ? '32 threads' : `${v}`),
			yFmt: (v) => v.toLocaleString('en-US'),
			series: [
				{ pts: W.map((r) => [r.threads, r.cps] as const), area: 0.62, markers: true, end: `<b>now</b> · ${fmt(W[W.length - 1].cps, 0)}` },
				{ pts: W.map((r) => [r.threads, BEFORE[r.threads]] as const), dotted: true, markers: true, end: `${B.commit} · ${fmt(BEFORE[32], 0)}` },
			],
			endW: 128,
			tip: (x, v) => `<b>${threads(x)}</b><br>now ${fmt(v[0][1])} chunks a second<br>at ${B.commit} ${fmt(v[1][1])}<br>${fmt(v[0][1] / v[1][1], 2)}× as fast`,
		}),
		[W],
	);
	return <LineChart cfg={cfg} className="h-[300px]" label="Line chart: chunks a second of vanilla's worldgen by threads, now and at 868e0a0" />;
}

/** Peak memory while generating, by threads. */
export function MemoryBars({ which }: { which: 'worldgen' | 'packs' }) {
	const runs = which === 'worldgen' ? DATA.worldgen.runs : DATA.packs.calcite;
	return (
		<BarChart
			nameW={86}
			max={Math.max(...runs.map((r) => r.mem)) * 1.12}
			rows={runs.map((r) => ({ name: threads(r.threads), v: r.mem, strong: true, label: `${r.mem.toLocaleString('en-US')} MiB`, aria: `${threads(r.threads)}: ${r.mem} MiB at most`, tip: `<b>${threads(r.threads)}</b><br>${r.mem.toLocaleString('en-US')} MiB at most` }))}
		/>
	);
}

/** CPU time over a whole launch, warm-up included, at one thread count. */
export function CpuBars({ t }: { t: number }) {
	const P = DATA.packs;
	const rows = (
		[
			['Calcite', P.calcite, true],
			['C2ME', P.c2me, false],
			['Paper', P.paper, false],
			['Vanilla', P.vanilla, false],
		] as const
	).map(([name, runs, strong]) => ({ name, v: runs.find((r) => r.threads === t)!.cpu, strong }));
	return (
		<BarChart
			nameW={72}
			max={Math.max(...rows.map((r) => r.v)) * 1.12}
			rows={rows.map((r) => ({ ...r, label: `${r.v} s`, aria: `${r.name}, ${threads(t)}: ${r.v} seconds of CPU`, tip: `<b>${r.name}</b> · ${threads(t)}<br>${r.v} s of CPU` }))}
		/>
	);
}

/** Light: vanilla's engine and Calcite's, workload by workload. */
export function LightBars() {
	const L = DATA.light.runs, max = Math.max(...L.map((l) => l.vanilla)) * 1.15;
	return (
		<div className="grid gap-6">
			{L.map((l) => (
				<div key={l.name}>
					<p className="mb-1 text-[15px] font-semibold">
						{l.name} <span className="font-mono text-xs font-normal">· Calcite {l.x}× as fast</span>
					</p>
					<BarChart
						nameW={72}
						max={max}
						rows={[
							{ name: 'Calcite', v: l.calcite, strong: true, label: `${fmt(l.calcite, 2)} ms`, aria: `${l.name}: Calcite ${l.calcite} ms`, tip: `<b>Calcite</b><br>${fmt(l.calcite, 2)} ms` },
							{ name: 'Vanilla', v: l.vanilla, label: `${fmt(l.vanilla, 2)} ms`, aria: `${l.name}: vanilla ${l.vanilla} ms`, tip: `<b>Vanilla</b><br>${fmt(l.vanilla, 2)} ms` },
						]}
					/>
				</div>
			))}
		</div>
	);
}
