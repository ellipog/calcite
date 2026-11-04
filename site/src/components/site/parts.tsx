// The public pages' building blocks: section heads, stat tiles, the phase strip and page heads.

import type { ReactNode } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';

export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
	return <p className={cn('label mb-4 flex items-center gap-3 leading-none after:h-px after:w-10 after:bg-(image:--u50) after:bg-size-[8px_1px]', className)}>{children}</p>;
}

/** A section's head: a heavy title, a lead under it, and a mono kicker over it where one helps. */
export function SectionHead({ kicker, title, lead, className, id }: { kicker?: ReactNode; title: ReactNode; lead?: ReactNode; className?: string; id?: string }) {
	return (
		<header className={cn('mb-10 max-w-[760px]', className)}>
			{kicker && <Kicker>{kicker}</Kicker>}
			<h2 id={id} className="scroll-mt-24 font-display text-[clamp(34px,5vw,56px)] leading-[0.95] font-extrabold tracking-title text-balance">
				{title}
			</h2>
			{lead && <div className="mt-5 max-w-[62ch] text-lg leading-normal">{lead}</div>}
		</header>
	);
}

/** A page's own head, under the bar. */
export function PageHead({ kicker, title, lead, children }: { kicker?: ReactNode; title: ReactNode; lead?: ReactNode; children?: ReactNode }) {
	return (
		<section className="wrap pt-16 pb-12 md:pt-24">
			{kicker && <Kicker>{kicker}</Kicker>}
			<h1 className="max-w-[16ch] font-display text-[clamp(48px,8vw,108px)] leading-[0.88] font-extrabold tracking-display text-balance">{title}</h1>
			{lead && <div className="mt-7 max-w-[60ch] text-lg leading-normal md:text-xl">{lead}</div>}
			{children}
		</section>
	);
}

export interface Stat {
	label: string;
	value: string;
	note: ReactNode;
}

/** Big numbers in a dotted frame, each with what it is under it. */
export function Stats({ items, className }: { items: Stat[]; className?: string }) {
	return (
		<div className={cn('grid grid-cols-1 rule sm:grid-cols-2 lg:grid-cols-4', className)}>
			{items.map((s, i) => (
				<div key={s.label} className={cn('px-[22px] py-6', i > 0 && 'max-sm:rule-t', i % 2 === 1 && 'sm:max-lg:rule-l', i >= 2 && 'sm:max-lg:rule-t', i > 0 && 'lg:rule-l')}>
					<span className="label leading-none">{s.label}</span>
					<b className="mt-3 mb-2.5 block font-display text-[clamp(40px,4.4vw,56px)] leading-none font-extrabold tracking-[-0.035em] tabular-nums">{s.value}</b>
					<span className="block max-w-[30ch] font-mono text-xs leading-normal">{s.note}</span>
				</div>
			))}
		</div>
	);
}

export type PhaseState = 'done' | 'now' | 'next';

/** The plan's phases as a row of cells: solid when passed, marching while in progress, dotted ahead. */
export function PhaseStrip({ phases, className }: { phases: { n: number; builds: string; state: PhaseState }[]; className?: string }) {
	return (
		<ol className={cn('grid grid-cols-5 gap-px md:grid-cols-10', className)}>
			{phases.map((p) => (
				<li key={p.n} className="grid content-start gap-2.5">
					<Link href={`/roadmap#phase-${p.n}`} className="group grid gap-2.5" aria-label={`Phase ${p.n}, ${p.builds}: ${p.state === 'done' ? 'passed' : p.state === 'now' ? 'in progress' : 'to come'}`}>
						<i
							aria-hidden
							className={cn(
								'block h-10 border border-ink',
								p.state === 'done' && 'bg-ink',
								p.state === 'now' && 'animate-march16 tint-38 motion-reduce:animate-none',
								p.state === 'next' && 'border-dotted',
								'group-hover:[border-style:solid]',
							)}
						/>
						<span className="font-mono text-[11px] leading-[1.35]">
							<b className="font-medium">{String(p.n).padStart(2, '0')}</b>
							<span className="block group-hover:underline group-hover:decoration-2 group-hover:underline-offset-2 max-md:hidden">{p.builds}</span>
						</span>
					</Link>
				</li>
			))}
		</ol>
	);
}
