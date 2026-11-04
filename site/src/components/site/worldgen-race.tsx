'use client';

// Calcite beside vanilla, Paper and C2ME generating the same world with Terralith and Terratonic,
// at the thread count you pick. The fastest at that count fills the width, and the bars step to
// their new lengths.

import { useState } from 'react';
import { BarChart } from '@/components/charts';
import { Segmented } from '@/components/ui/form';
import { DATA } from '@/lib/data';
import { cn } from '@/lib/cn';

const P = DATA.packs;
const THREADS = P.calcite.map((r) => r.threads);
const fmt = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const at = (runs: readonly { threads: number; cps: number }[], t: number) => runs.find((r) => r.threads === t)!.cps;

export function WorldgenRace({ className, defaultThreads = 32 }: { className?: string; defaultThreads?: number }) {
	const [t, setT] = useState(defaultThreads);
	const rows = [
		{ name: 'Calcite', v: at(P.calcite, t), strong: true },
		{ name: 'C2ME', v: at(P.c2me, t) },
		{ name: 'Paper', v: at(P.paper, t) },
		{ name: 'Vanilla', v: at(P.vanilla, t) },
	];
	const lead = rows[0].v / Math.max(...rows.slice(1).map((r) => r.v));
	return (
		<div className={cn('grid gap-5', className)}>
			<div className="flex flex-wrap items-end justify-between gap-4">
				<Segmented label="Threads" name="race-threads" options={THREADS.map(String)} defaultValue={String(defaultThreads)} onChange={(v) => setT(+v)} />
				<p className="font-mono text-xs leading-normal" aria-live="polite">
					{t} thread{t > 1 ? 's' : ''} · Calcite {lead.toFixed(2)}× the next fastest
				</p>
			</div>
			<BarChart
				nameW={72}
				rows={rows.map((r) => ({
					name: r.name,
					v: r.v,
					strong: r.strong,
					label: fmt(r.v),
					aria: `${r.name}, ${t} threads: ${fmt(r.v)} chunks a second`,
					tip: `<b>${r.name}</b> · ${t} thread${t > 1 ? 's' : ''}<br>${fmt(r.v)} chunks a second`,
				}))}
			/>
			<p className="font-mono text-[11px] leading-normal">chunks a second · higher is better</p>
		</div>
	);
}
