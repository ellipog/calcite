'use client';

// A progress bar with the slider's edge: solid ink, then 75, 50 and 25% two cells each, then the
// empty track's dots. While it works, its pattern marches a cell every 100 ms. With no value it
// can't know how far it is, so a block, dithered at both ends, crosses it instead.

import { useRef } from 'react';
import { surface, type Surface } from '@/lib/dither/canvas';
import { useSized, useSteps } from '@/lib/dither/motion';
import { q4 } from '@/lib/dither/tiles';

const STEP = [12, 8, 4], B = 6;

function paint(s: Surface, value: number | undefined, k: number) {
	const { cols, rows } = s, bits = new Uint8Array(cols * rows);
	// a fill from a to b in cells, its edges stepping down on the side(s) it has
	const run = (a: number, b: number, lead: boolean, trail: boolean) => {
		for (let y = 0; y < rows; y++)
			for (let x = 0; x < cols; x++) {
				const px = x - k, i = y * cols + x;
				let on = q4(px, y) < 1;
				if (x >= a && x < b) on = true;
				else if (lead && x >= b && x < b + B) on ||= q4(px, y) < STEP[(x - b) >> 1];
				else if (trail && x < a && x >= a - B) on ||= q4(px, y) < STEP[(a - 1 - x) >> 1];
				if (on) bits[i] = 1;
			}
	};
	if (value === undefined) {
		const len = Math.max(12, Math.round(cols * 0.18)), span = cols + len + 2 * B, a = ((k * 4) % span) - len - B;
		run(a, a + len, true, true);
	} else {
		const f = Math.round(-B + Math.min(1, Math.max(0, value)) * (cols + B));
		run(0, f, value < 1, false);
	}
	s.bits(bits);
	s.flush();
}

export function Progress({ label, value, done, className }: { label: string; value?: number; done?: string; className?: string }) {
	const ref = useRef<HTMLCanvasElement>(null), S = useRef<Surface | null>(null), K = useRef(0);
	const working = value === undefined || value < 1;
	useSized(ref, () => {
		S.current = surface(ref.current!, 2);
		paint(S.current, value, K.current);
	}, [value]);
	useSteps(ref, 100, (k) => {
		if (!S.current || !working) return;
		K.current = k;
		paint(S.current, value, k);
	}, 0, [value]);
	const pct = value === undefined ? (done ?? 'working') : `${Math.round(value * 100)}%`;
	return (
		<div className={className}>
			<div className="mb-2 flex justify-between font-mono text-xs leading-none">
				<span>{label}</span>
				<span>{pct}</span>
			</div>
			<canvas
				ref={ref}
				className="block h-[18px] w-full"
				role="progressbar"
				aria-label={label}
				aria-valuemin={value === undefined ? undefined : 0}
				aria-valuemax={value === undefined ? undefined : 100}
				aria-valuenow={value === undefined ? undefined : Math.round(value * 100)}
			/>
		</div>
	);
}
