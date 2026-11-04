'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

// A small mono heading with a dotted rule after it, which draws in from the left as it comes
// into view.
export function Sub({ children, className, first }: { children: ReactNode; className?: string; first?: boolean }) {
	const ref = useRef<HTMLParagraphElement>(null);
	useEffect(() => {
		const el = ref.current!;
		el.classList.add('d-rule-in');
		const io = new IntersectionObserver(
			([e]) => {
				if (!e.isIntersecting) return;
				el.classList.add('in');
				io.disconnect();
			},
			{ rootMargin: '0px 0px -10% 0px' },
		);
		io.observe(el);
		return () => io.disconnect();
	}, []);
	return (
		<p
			ref={ref}
			className={cn(
				"label mb-[18px] flex items-baseline gap-3 leading-[1.4] after:flex-1 after:-translate-y-1 after:rule-t after:content-['']",
				first ? 'mt-0' : 'mt-16',
				className,
			)}
		>
			{children}
		</p>
	);
}
