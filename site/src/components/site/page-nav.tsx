'use client';

// A long page's sections, in a sticky column beside it on a wide screen, as the docs' pages are
// listed beside them. The section you're reading is marked solid: the last one whose heading has
// passed the top third of the window.

import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';

export function PageNav({ items, className }: { items: readonly (readonly [id: string, title: string])[]; className?: string }) {
	const [on, setOn] = useState(items[0]?.[0]);
	useEffect(() => {
		let frame = 0;
		const look = () => {
			frame = 0;
			const line = innerHeight / 3;
			let here = items[0]?.[0];
			for (const [id] of items) {
				const el = document.getElementById(id);
				if (el && el.getBoundingClientRect().top <= line) here = id;
			}
			setOn(here);
		};
		const scroll = () => {
			if (!frame) frame = requestAnimationFrame(look);
		};
		look();
		addEventListener('scroll', scroll, { passive: true });
		addEventListener('resize', scroll, { passive: true });
		return () => {
			cancelAnimationFrame(frame);
			removeEventListener('scroll', scroll);
			removeEventListener('resize', scroll);
		};
	}, [items]);
	return (
		<nav aria-label="On this page" className={cn('sticky top-24', className)}>
			<p className="label mb-3">On this page</p>
			<ul className="grid gap-0.5">
				{items.map(([id, title]) => (
					<li key={id}>
						<a href={`#${id}`} aria-current={on === id ? 'location' : undefined} className={cn('relative block py-1.5 pl-4 text-[15px] leading-snug', on === id ? 'font-semibold' : 'hover:underline hover:decoration-2 hover:underline-offset-4')}>
							<span aria-hidden className={cn('absolute top-[0.9em] left-0 size-[6px]', on === id ? 'bg-ink' : 'border border-dotted border-ink')} />
							{title}
						</a>
					</li>
				))}
			</ul>
		</nav>
	);
}
