'use client';

// The brand's generated pictures, shared by the site and the brand guide: the world from above in
// relief with contours, the crystal turning, and stills of the world from the ground.

import { useEffect, useRef } from 'react';
import { ordered } from '@/lib/dither/bayer';
import { surface, type Surface } from '@/lib/dither/canvas';
import { crystal } from '@/lib/dither/crystal';
import { useFrames, useSized } from '@/lib/dither/motion';
import { at, CAMS, fade, getBlurred, getWorld, still, WATER, type Cam, type Fade, type ViewOptions } from '@/lib/brand/terrain';

// A canvas filling its box, drawn by fn(surface) whenever its width changes. The first drawing
// waits until the canvas is within a screen or so of the view, and then for the browser to be
// idle, so a picture far down the page doesn't build its world while the page is loading.
export function Drawn({ draw, className, label }: { draw: (s: Surface, c: HTMLCanvasElement) => void; className?: string; label?: string }) {
	const ref = useRef<HTMLCanvasElement>(null), near = useRef(false), pending = useRef(false);
	const run = () => {
		pending.current = false;
		if (ref.current) draw(surface(ref.current, 2), ref.current);
	};
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		let idle = 0;
		const io = new IntersectionObserver(
			([e]) => {
				if (!e.isIntersecting || near.current) return;
				near.current = true;
				io.disconnect();
				if (pending.current) idle = typeof requestIdleCallback === 'function' ? requestIdleCallback(run, { timeout: 400 }) : window.setTimeout(run, 0);
			},
			{ rootMargin: '100% 0px' },
		);
		io.observe(el);
		return () => {
			io.disconnect();
			if (typeof cancelIdleCallback === 'function') cancelIdleCallback(idle);
			clearTimeout(idle);
		};
		// run draws through refs, so the first one is the only one needed
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);
	useSized(ref, () => {
		if (near.current) run();
		else pending.current = true;
	});
	return <canvas ref={ref} className={className} aria-label={label} role={label ? 'img' : undefined} />;
}

export function drawMap(s: Surface, at0: [number, number] = [30, 260], scale = 1.4) {
	const { LIT } = getWorld(), HB = getBlurred(), { cols, rows } = s, tone = new Float32Array(cols * rows);
	const [ox, oy] = at0, lev = (h: number) => Math.floor(h / 0.075);
	for (let y = 0; y < rows; y++)
		for (let x = 0; x < cols; x++) {
			const wx = ox + x * scale, wy = oy + y * scale, h = at(HB, wx, wy), hr = at(HB, wx + scale, wy), hd = at(HB, wx, wy + scale);
			let t;
			if (h < WATER) t = hr >= WATER || hd >= WATER ? 1 : 0.08;
			else if (hr < WATER || hd < WATER) t = 1;
			else if (lev(h) !== lev(hr) || lev(h) !== lev(hd)) t = 0.9;
			else t = 0.03 + 0.5 * (1 - at(LIT, wx, wy)) ** 1.6;
			tone[y * cols + x] = t;
		}
	fade(tone, cols, rows, { l: 0.08, r: 0.08, t: 0.14, b: 0.14 });
	s.bits(ordered(tone, cols, rows, 8));
	s.flush();
}

/** The world from above, in relief with contours. */
export function Relief({ className, label = 'A generated world from above, in relief with contours', origin, scale }: { className?: string; label?: string; origin?: [number, number]; scale?: number }) {
	return <Drawn className={className} draw={(s) => drawMap(s, origin, scale)} label={label} />;
}

/** A still of the world from the ground. */
export function Still({ cam, o, className, label }: { cam: keyof typeof CAMS | Cam; o?: ViewOptions & { fade?: Fade; diffuse?: boolean }; className?: string; label?: string }) {
	return <Drawn className={className} label={label} draw={(_, c) => still(c, typeof cam === 'string' ? CAMS[cam] : cam, o)} />;
}

// The crystal, turning; drag to turn it yourself.
export function Crystal({ className = 'h-[300px] w-full' }: { className?: string }) {
	const cv = useRef<HTMLCanvasElement>(null), st = useRef({ S: null as Surface | null, drag: null as null | { x: number; o: number }, off: 0, spin: 0, last: 0 });
	const POSE = [5.64, -0.26, 0.44];
	const draw = (t: number) => {
		const s = st.current, S = s.S;
		if (!S) return;
		const dt = Math.min(0.05, Math.max(0, t - s.last));
		s.last = t;
		if (!s.drag) s.spin += dt * 0.32;
		const v = crystal(POSE[0], POSE[1], POSE[2] + s.spin + s.off), { cols, rows } = S;
		const sc = (Math.min(rows * 0.8, cols * 0.6) / (2 * v.R)) * 1.05, ox = cols / 2, oy = rows * 0.45;
		const sy = oy + v.R * sc * 0.98, srx = v.R * sc * 0.95, sry = v.R * sc * 0.16, tone = new Float32Array(cols * rows);
		for (let y = 0; y < rows; y++)
			for (let x = 0; x < cols; x++) {
				const h = v.at((x + 0.5 - ox) / sc, (y + 0.5 - oy) / sc);
				let tt;
				if (h) tt = h.edge * sc < 1.1 ? 1 : 0.1 + 0.8 * (1 - h.lit) ** 1.1;
				else {
					const d = ((x - ox) / srx) ** 2 + ((y - sy) / sry) ** 2;
					tt = d < 1 ? 0.34 * (1 - d) : 0;
				}
				tone[y * cols + x] = tt;
			}
		S.bits(ordered(tone, cols, rows, 8));
		S.flush();
	};
	useSized(cv, () => {
		st.current.S = surface(cv.current!, 2);
		draw(st.current.last);
	});
	useFrames(cv, draw);
	return (
		<canvas
			ref={cv}
			className={`${className} cursor-ew-resize touch-pan-y`}
			aria-label="Calcite's cleavage rhombohedron, turning"
			onPointerDown={(e) => {
				st.current.drag = { x: e.clientX, o: st.current.off };
				e.currentTarget.setPointerCapture(e.pointerId);
			}}
			onPointerMove={(e) => {
				const d = st.current.drag;
				if (d) st.current.off = d.o + (e.clientX - d.x) * 0.012;
			}}
			onPointerUp={() => (st.current.drag = null)}
		/>
	);
}
