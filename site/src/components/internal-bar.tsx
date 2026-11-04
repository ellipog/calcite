'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Bitmap } from './mark';
import { markBits, MARK } from '@/lib/dither/mark';
import { still } from '@/lib/dither/motion';
import { cn } from '@/lib/cn';

// The sticky bar on the internal pages. Its mark watches the pointer, in twelfths, and the nav
// follows the section in view.
export function InternalBar({ title, sections, here }: { title: string; sections?: [id: string, label: string][]; here: '/brand' | '/components' }) {
	const [pos, setPos] = useState<[number, number]>([MARK.cx, MARK.cy]);
	const [on, setOn] = useState<string | null>(null);
	const raf = useRef(0);
	useEffect(() => {
		if (still()) return;
		let ex = 0, ey = 0;
		const move = (e: PointerEvent) => {
			ex = e.clientX;
			ey = e.clientY;
			if (raf.current) return;
			raf.current = requestAnimationFrame(() => {
				raf.current = 0;
				const q = (v: number) => Math.round(v * 12) / 12;
				setPos([q(0.2 + (0.6 * ex) / innerWidth), q(0.2 + (0.6 * ey) / innerHeight)]);
			});
		};
		addEventListener('pointermove', move, { passive: true });
		return () => removeEventListener('pointermove', move);
	}, []);
	useEffect(() => {
		if (!sections) return;
		const io = new IntersectionObserver(
			(es) => {
				for (const e of es) if (e.isIntersecting) setOn(e.target.id);
			},
			{ rootMargin: '-45% 0px -50% 0px' },
		);
		for (const [id] of sections) {
			const s = document.getElementById(id);
			if (s) io.observe(s);
		}
		return () => io.disconnect();
	}, [sections]);
	const n = 24;
	return (
		<header className="sticky top-0 z-40 rule-b bg-paper">
			<div className="wrap flex h-14 items-center gap-[18px]">
				<Link href={here} className="flex items-center gap-2.5 font-display text-[22px] leading-none font-extrabold tracking-display whitespace-nowrap">
					<Bitmap bits={markBits(n, { cx: pos[0], cy: pos[1] })} n={n} size={24} />
					calcite
					<small className="ml-1 hidden font-mono text-xs font-normal tracking-normal md:inline">{title}</small>
				</Link>
				<nav aria-label="Sections" className="ml-auto flex min-w-0 gap-0.5 overflow-x-auto [scrollbar-width:none]">
					{(sections ?? []).map(([id, label]) => (
						<a key={id} href={`#${id}`} className="group px-2 py-2 font-mono text-[12.5px] leading-none whitespace-nowrap">
							<span className={cn('bg-size-[8px_2px] bg-bottom bg-repeat-x pb-1', on === id ? 'bg-(image:--solid)' : 'group-hover:bg-(image:--solid)')}>{label}</span>
						</a>
					))}
					<Link href={here === '/brand' ? '/components' : '/brand'} className="link mx-2 my-2 font-mono text-[12.5px] leading-none whitespace-nowrap">
						{here === '/brand' ? 'components →' : 'brand guide →'}
					</Link>
				</nav>
			</div>
		</header>
	);
}
