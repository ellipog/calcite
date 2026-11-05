'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

// Holds each march (march-8, march-16 in globals.css) still while it's off screen. Where the
// screen's pixels don't line up with CSS pixels a march moves its background, which has the page
// painted again at every step, so one far down the page would cost that the whole time for
// nothing. Mount it once, in the root layout. It looks for marches again on each new page; one that
// appears otherwise, such as a button going busy, simply marches.
export function MarchWatch() {
	const path = usePathname();
	useEffect(() => {
		const io = new IntersectionObserver((entries) => {
			for (const e of entries) e.target.toggleAttribute('data-off', !e.isIntersecting);
		});
		document.querySelectorAll('.march-8, .march-16').forEach((el) => io.observe(el));
		return () => io.disconnect();
	}, [path]);
	return null;
}
