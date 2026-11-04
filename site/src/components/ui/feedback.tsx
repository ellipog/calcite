import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

// Status is density, as the mark's leaves are: solid is done, half is under way and marches,
// empty is not started. Always with its word.
export function Tag({ status = 'planned', children }: { status?: 'done' | 'running' | 'planned'; children: ReactNode }) {
	return (
		<span className="inline-flex items-center gap-[7px] rule px-[9px] py-1.5 font-mono text-xs leading-none">
			<i className={cn('size-2.5 flex-none border border-ink', status === 'done' && 'bg-ink', status === 'running' && 'animate-march bg-(image:--ring) bg-size-[8px_8px]')} aria-hidden />
			{children}
		</span>
	);
}

export function Callout({ title = 'Note', strong, children }: { title?: string; strong?: boolean; children: ReactNode }) {
	return (
		<div
			className={cn(
				'relative rule py-3.5 pr-4 pl-[46px] text-[15px]',
				"before:absolute before:top-4 before:left-3.5 before:size-[18px] before:outline before:outline-ink before:content-['']",
				strong ? 'before:bg-ink' : 'before:tint-50',
			)}
		>
			<b className="mb-0.5 block font-mono text-xs font-medium tracking-label uppercase">{title}</b>
			{children}
		</div>
	);
}

// Placeholder lines while something loads: sparse dots with a dithered band sweeping over them.
export function Skeleton({ lines = [100, 82, 64] }: { lines?: number[] }) {
	return (
		<div className="grid gap-2.5" role="status" aria-label="Loading">
			{lines.map((w, i) => (
				<i key={i} className="d-skel block h-3" style={{ width: `${w}%`, animationDelay: `${i * 0.08}s` }} />
			))}
		</div>
	);
}

// A data table: dotted rules, labels in mono caps, numbers right and tabular; the rule under the
// row you point at goes solid.
export interface Column {
	label: string;
	num?: boolean;
}
export function Table({ columns, rows, strong, className }: { columns: Column[]; rows: ReactNode[][]; strong?: number; className?: string }) {
	const cell = (c: Column) => cn('rule-b py-2.5 pr-2.5 text-left', c.num && 'text-right font-mono tabular-nums');
	return (
		<table className={cn('w-full border-collapse text-[15px] [&_tbody_tr:hover>td]:[border-bottom-style:solid]', className)}>
			<thead>
				<tr>
					{columns.map((c) => (
						<th key={c.label} className={cn(cell(c), 'label font-normal')}>
							{c.label}
						</th>
					))}
				</tr>
			</thead>
			<tbody>
				{rows.map((r, i) => (
					<tr key={i} className={cn(i === strong && 'font-bold')}>
						{r.map((v, j) => (
							<td key={j} className={cell(columns[j])}>
								{v}
							</td>
						))}
					</tr>
				))}
			</tbody>
		</table>
	);
}

// Disclosure: a pixel plus that becomes a minus; what opens dissolves in.
export function Disclosure({ summary, children, className, big }: { summary: ReactNode; children: ReactNode; className?: string; big?: boolean }) {
	return (
		<details className={cn('d-details', big && 'rule-b', className)}>
			<summary className={big ? 'py-3.5 font-sans text-base leading-[1.3] font-semibold' : 'py-2.5 font-mono text-[13px] leading-none'}>{summary}</summary>
			<div className={big ? 'pb-4 pl-5' : undefined}>{children}</div>
		</details>
	);
}
export function Accordion({ items }: { items: { q: ReactNode; a: ReactNode }[] }) {
	return (
		<div className="rule-t">
			{items.map((it, i) => (
				<Disclosure key={i} summary={it.q} big>
					<p>{it.a}</p>
				</Disclosure>
			))}
		</div>
	);
}
