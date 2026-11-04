'use client';

// The mark on screen, live: its player follows the pointer across the window, in twelfths, so the
// quadtree splits about wherever the pointer is. With reduced motion, or no pointer, it's the master.

import { useEffect, useRef, useState } from 'react';
import { Bitmap } from './mark';
import { markBits, MARK } from '@/lib/dither/mark';
import { still } from '@/lib/dither/motion';

export function LiveMark({ cells = 24, size = 24, title }: { cells?: number; size?: number; title?: string }) {
	const [pos, setPos] = useState<[number, number]>([MARK.cx, MARK.cy]);
	const raf = useRef(0);
	useEffect(() => {
		if (still() || !matchMedia('(hover: hover)').matches) return;
		let ex = 0, ey = 0;
		const move = (e: PointerEvent) => {
			ex = e.clientX;
			ey = e.clientY;
			if (raf.current) return;
			raf.current = requestAnimationFrame(() => {
				raf.current = 0;
				const q = (v: number) => Math.round(v * 12) / 12;
				setPos((p) => {
					const n: [number, number] = [q(0.2 + (0.6 * ex) / innerWidth), q(0.2 + (0.6 * ey) / innerHeight)];
					return n[0] === p[0] && n[1] === p[1] ? p : n;
				});
			});
		};
		addEventListener('pointermove', move, { passive: true });
		return () => {
			removeEventListener('pointermove', move);
			cancelAnimationFrame(raf.current);
		};
	}, []);
	return <Bitmap bits={markBits(cells, { cx: pos[0], cy: pos[1] })} n={cells} size={size} title={title} />;
}
