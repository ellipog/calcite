// The public pages' building blocks: section heads, stat tiles, the phase strip and page heads.

import type { ReactNode } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';

export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
	return <p className={cn('label mb-4 flex items-center gap-3 leading-none after:h-px after:w-10 after:bg-(image:--u50) after:bg-size-[8px_1px]', className)}>{children}</p>;
}

// The split every wide head uses, the hero's included: the title on the left, what it says on the
// right, so the lead lines up down the page. Anything beside a table or a chart under such a head
// uses the same columns (SPLIT_XL), so its text starts on the lead's line.
const SPLIT = 'lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:items-end lg:gap-x-10';
export const SPLIT_XL = 'grid grid-cols-1 gap-y-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] xl:gap-x-10';

/**
 * A section's head: a heavy title, a lead, and a mono kicker over it where one helps. A split head
 * spans the frame, with the title on the left and the lead and `more` link on the right; otherwise
 * it stacks, for a head in a column of its own.
 */
export function SectionHead({ kicker, title, lead, more, split, className, id }: { kicker?: ReactNode; title: ReactNode; lead?: ReactNode; more?: ReactNode; split?: boolean; className?: string; id?: string }) {
	return (
		<header className={cn('mb-10', split ? cn('grid gap-y-5 lg:mb-14', SPLIT) : 'max-w-[760px]', className)}>
			<div>
				{kicker && <Kicker>{kicker}</Kicker>}
				<h2 id={id} className={cn('scroll-mt-24 font-display leading-[0.95] font-extrabold tracking-title text-balance', split ? 'text-[clamp(34px,4.4vw,76px)]' : 'text-[clamp(34px,5vw,56px)]')}>
					{title}
				</h2>
			</div>
			{(lead || more) && (
				<div className={cn('max-w-[62ch] text-lg leading-normal', !split && 'mt-5')}>
					{lead}
					{more && <p className="mt-4">{more}</p>}
				</div>
			)}
		</header>
	);
}

/** A section of a long page: a dotted rule from one edge of the window to the other, and the frame under it. */
export function Band({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
	return (
		<section id={id} className={cn('mt-24 scroll-mt-16 rule-t pt-10 md:mt-32 md:pt-14', className)}>
			<div className="wrap">{children}</div>
		</section>
	);
}

/**
 * A page's own head, under the bar: the title on the left and the lead on the right, on a wide
 * screen. A bare head is for a page that's already in the frame, in a column beside a list.
 */
export function PageHead({ kicker, title, lead, bare, children }: { kicker?: ReactNode; title: ReactNode; lead?: ReactNode; bare?: boolean; children?: ReactNode }) {
	return (
		<section className={cn('pt-16 pb-12 md:pt-24', !bare && 'wrap')}>
			<div className={cn('grid gap-y-7', SPLIT)}>
				<div>
					{kicker && <Kicker>{kicker}</Kicker>}
					<h1 className="max-w-[16ch] font-display text-[clamp(48px,7vw,136px)] leading-[0.88] font-extrabold tracking-display text-balance">{title}</h1>
				</div>
				{lead && <div className="max-w-[60ch] text-lg leading-normal md:text-xl">{lead}</div>}
			</div>
			{children}
		</section>
	);
}

export interface Stat {
	label: string;
	value: string;
	note: ReactNode;
}

/**
 * Big numbers, each with what it is under it, in a dotted frame. A bled row runs its rules from one
 * edge of the window to the other, with the numbers in the frame.
 */
export function Stats({ items, bleed, className }: { items: Stat[]; bleed?: boolean; className?: string }) {
	const last = items.length - 1;
	const cells = items.map((s, i) => (
		<div
			key={s.label}
			className={cn(
				bleed ? 'py-7 lg:py-9' : 'px-[22px] py-6',
				i > 0 && 'max-sm:rule-t',
				i % 2 === 1 && 'sm:max-lg:rule-l',
				i >= 2 && 'sm:max-lg:rule-t',
				i > 0 && 'lg:rule-l',
				bleed && (i % 2 === 1 ? 'sm:max-lg:pl-8' : 'sm:max-lg:pr-8'),
				bleed && i > 0 && 'lg:pl-8',
				bleed && i < last && 'lg:pr-8',
			)}
		>
			<span className="label leading-none">{s.label}</span>
			<b className={cn('mt-3 mb-2.5 block font-display leading-none font-extrabold tracking-[-0.035em] whitespace-nowrap tabular-nums', bleed ? 'text-[clamp(44px,4.6vw,96px)] lg:mt-5 lg:mb-4' : 'text-[clamp(40px,3.6vw,64px)]')}>{s.value}</b>
			<span className="block max-w-[34ch] font-mono text-xs leading-normal">{s.note}</span>
		</div>
	));
	const grid = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
	if (!bleed) return <div className={cn(grid, 'rule', className)}>{cells}</div>;
	return (
		<div className={cn('bleed rule-t rule-b', className)}>
			<div className={cn('wrap', grid)}>{cells}</div>
		</div>
	);
}

export type PhaseState = 'done' | 'now' | 'next';

/** The plan's phases as a row of cells: solid when passed, marching while in progress, dotted ahead.
 *  Each link's name is its visible words with what the cell shows, "Phase 06, Simulation: in
 *  progress", so it holds the number a reader sees and can say to voice control. */
export function PhaseStrip({ phases, className }: { phases: { n: number; builds: string; state: PhaseState }[]; className?: string }) {
	return (
		<ol className={cn('grid grid-cols-5 gap-px md:grid-cols-10', className)}>
			{phases.map((p) => (
				<li key={p.n} className="grid content-start gap-2.5">
					<Link href={`/roadmap#phase-${p.n}`} className="group grid gap-2.5">
						<i
							aria-hidden
							className={cn(
								'block h-10 border border-ink xl:h-16',
								p.state === 'done' && 'bg-ink',
								p.state === 'now' && 'tint-38 march-16',
								p.state === 'next' && 'border-dotted',
								'group-hover:[border-style:solid]',
							)}
						/>
						<span className="font-mono text-[11px] leading-[1.35] xl:text-xs">
							<span className="sr-only">Phase </span>
							<b className="font-medium">{String(p.n).padStart(2, '0')}</b>
							<span className="sr-only">, </span>
							<span className="block pr-2 group-hover:underline group-hover:decoration-2 group-hover:underline-offset-2 max-md:sr-only">{p.builds}</span>
							<span className="sr-only">: {p.state === 'done' ? 'passed' : p.state === 'now' ? 'in progress' : 'to come'}</span>
						</span>
					</Link>
				</li>
			))}
		</ol>
	);
}
