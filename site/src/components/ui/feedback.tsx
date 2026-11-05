import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

// Status is density, as the mark's leaves are: solid is done, half is under way and marches,
// empty is not started. Always with its word.
export function Tag({ status = 'planned', children }: { status?: 'done' | 'running' | 'planned'; children: ReactNode }) {
	return (
		<span className="inline-flex items-center gap-[7px] rule px-[9px] py-1.5 font-mono text-xs leading-none whitespace-nowrap">
			<i className={cn('size-2.5 flex-none border border-ink', status === 'done' && 'bg-ink', status === 'running' && 'tile-ring march-8')} aria-hidden />
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
// row you point at goes solid. A `stack` table becomes a list on a phone: each row a block, its
// first cell on top, its last below, and any between with their column's label.
export interface Column {
	label: string;
	num?: boolean;
}
export function Table({ columns, rows, strong, stack, className }: { columns: Column[]; rows: ReactNode[][]; strong?: number; stack?: boolean; className?: string }) {
	const last = columns.length - 1;
	// a number stays on one line; its column's label may wrap over it
	const cell = (c: Column, j: number, head = false) =>
		cn(
			'rule-b py-2.5 pr-2.5 text-left',
			c.num && 'text-right font-mono tabular-nums',
			c.num && !head && 'whitespace-nowrap',
			stack && 'max-sm:block max-sm:border-0 max-sm:py-0.5 max-sm:pr-0 max-sm:text-left',
			stack && j === 0 && 'max-sm:pt-3',
			stack && j === last && 'max-sm:pb-3',
		);
	return (
		<table className={cn('w-full border-collapse text-[15px] [&_tbody_tr:hover>*]:[border-bottom-style:solid]', stack && 'max-sm:block', className)}>
			<thead className={cn(stack && 'max-sm:sr-only')}>
				<tr>
					{columns.map((c, j) => (
						<th key={c.label || j} scope="col" className={cn(cell(c, j, true), 'label font-normal')}>
							{c.label}
						</th>
					))}
				</tr>
			</thead>
			<tbody className={cn(stack && 'max-sm:block')}>
				{rows.map((r, i) => (
					<tr key={i} className={cn(i === strong && 'font-bold', stack && 'max-sm:block max-sm:rule-b')}>
						{/* the first cell names the row, so a screen reader can say which row a number is in */}
						{r.map((v, j) => {
							const Cell = j === 0 ? 'th' : 'td';
							return (
								<Cell key={j} scope={j === 0 ? 'row' : undefined} className={cn(cell(columns[j], j), j === 0 && 'font-[inherit]')}>
									{stack && j > 0 && j < last && columns[j].label && <span className="label mr-2 sm:hidden">{columns[j].label}</span>}
									{v}
								</Cell>
							);
						})}
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
					{typeof it.a === 'string' ? <p>{it.a}</p> : it.a}
				</Disclosure>
			))}
		</div>
	);
}
