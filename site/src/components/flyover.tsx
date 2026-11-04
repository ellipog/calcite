'use client';

// The hero: the world flown over, seen through the quadtree of the chunks in view. The view loads
// in eight steps when the page opens and follows the pointer; left alone, it wanders.

import { useEffect, useRef } from 'react';
import { ordered } from '@/lib/dither/bayer';
import { surface, type Surface } from '@/lib/dither/canvas';
import { quadtree, type Leaf } from '@/lib/dither/mark';
import { still, useFrames, useSized } from '@/lib/dither/motion';
import { fade, view } from '@/lib/brand/terrain';
import { cn } from '@/lib/cn';

export function Flyover({ chips = ['150.6 chunks/s on 1 thread', '2,022 on 32', "vanilla's worldgen"], className }: { chips?: string[]; className?: string }) {
	const fly = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	const st = useRef({ S: null as Surface | null, T: new Float32Array(0), Z: new Uint8Array(0), grow: 0, last: 0, t: 0, aim: null as [number, number] | null, pos: { x: 0, y: 0 }, cam: { x: 256, y: 200 } });

	const draw = (t: number) => {
		const s = st.current, S = s.S;
		if (!S) return;
		const dt = Math.min(0.05, Math.max(0, t - s.last));
		s.last = t;
		const { cols, rows } = S, T = s.T, Z = s.Z;
		const tx = s.aim ? s.aim[0] : cols * (0.5 + 0.3 * Math.sin(t * 0.11)), ty = s.aim ? s.aim[1] : rows * (0.52 + 0.2 * Math.sin(t * 0.17));
		s.pos.x += (tx - s.pos.x) * 0.08;
		s.pos.y += (ty - s.pos.y) * 0.08;
		const heading = Math.sin(t * 0.05) * 0.35;
		s.cam.x += Math.sin(heading) * 22 * dt;
		s.cam.y -= Math.cos(heading) * 22 * dt;
		view(T, cols, rows, { x: s.cam.x, y: s.cam.y, yaw: heading }, { horizon: 0.16, sky: 0.34, haze: 0.16 });
		// the quadtree: root squares as tall as the hero, side by side
		Z.fill(0);
		const leaves: Leaf[] = [], side = rows, r = rows * 0.46 * s.grow, minS = Math.max(6, rows / 18);
		for (let i = 0; i * side < cols; i++) quadtree(i * side, 0, side, s.pos.x, s.pos.y, r, minS, leaves);
		for (const l of leaves) {
			const z = l.zone === 'in' ? 1 : l.zone === 'edge' ? 2 : 3;
			const x0 = Math.round(l.x + 1), y0 = Math.round(l.y + 1), x1 = Math.min(cols, Math.round(l.x + l.s)), y1 = Math.min(rows, Math.round(l.y + l.s));
			for (let y = y0; y < y1; y++) Z.fill(z, y * cols + x0, y * cols + x1);
		}
		for (let i = 0; i < T.length; i++) {
			const z = Z[i];
			T[i] = z === 1 ? T[i] : z === 2 ? 0.16 + 0.5 * T[i] : z === 3 ? 0.05 : 0;
		}
		fade(T, cols, rows, { b: 0.12 });
		S.bits(ordered(T, cols, rows, 8));
		S.flush();
	};

	useSized(fly, () => {
		const s = st.current, S = (s.S = surface(cv.current!, 2));
		s.T = new Float32Array(S.cols * S.rows);
		s.Z = new Uint8Array(S.cols * S.rows);
		s.pos = { x: S.cols * 0.36, y: S.rows * 0.5 };
		if (still()) draw(0);
	});
	useEffect(() => {
		if (still()) {
			st.current.grow = 1;
			return;
		}
		let k = 0, id = 0;
		const go = () => {
			st.current.grow = ++k / 8;
			if (k < 8) id = window.setTimeout(go, 60);
		};
		id = window.setTimeout(go, 200);
		return () => clearTimeout(id);
	}, []);
	useFrames(fly, draw);

	return (
		<div
			ref={fly}
			className={cn('relative h-[clamp(320px,52vh,520px)] rule-t', className ?? 'mt-14')}
			onPointerMove={(e) => {
				const S = st.current.S;
				if (!S) return;
				const r = cv.current!.getBoundingClientRect();
				st.current.aim = [((e.clientX - r.left) / r.width) * S.cols, ((e.clientY - r.top) / r.height) * S.rows];
			}}
			onPointerLeave={() => (st.current.aim = null)}
		>
			<canvas ref={cv} className="absolute inset-0 size-full cursor-crosshair touch-pan-y" aria-label="A generated world, flown over, seen through a quadtree of the chunks in the player's view" />
			<span className="pointer-events-none absolute top-4 right-(--gutter) rule bg-paper pointer-coarse:hidden px-2.5 py-2 font-mono text-xs leading-none">move to look around</span>
			<div className="pointer-events-none absolute bottom-5 left-(--gutter) flex flex-wrap gap-2">
				{chips.map((t) => (
					<span key={t} className="rule bg-paper px-2.5 py-2 font-mono text-xs leading-none">
						{t}
					</span>
				))}
			</div>
		</div>
	);
}
