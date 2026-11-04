'use client';

// The strip of a world from src/lib/brand/slab.ts, across the window: a chunk at each step of
// vanilla's generation, from structure starts on the frame's left edge to light, with the chunks
// not yet begun to the left of them and finished ones to the right, out to the window's edges.
// Each step's chunk replays its step, all of them at once, as a server makes many chunks at once.
// Pointing at one holds it finished. Under each is the rig's count of cases for that step.
//
// Where the window is too narrow for seven chunks at a readable size, the strip scrolls sideways.

import { useEffect, useRef, useState } from 'react';
import { surface, type Surface } from '@/lib/dither/canvas';
import { still } from '@/lib/dither/motion';
import { drawSlab, H, D, Slab, Step, type View } from '@/lib/brand/slab';
import { cn } from '@/lib/cn';

export interface GenStep {
	/** What the step is called, and the rig's cases that compare it with vanilla's. */
	name: string;
	cases: number;
}

const SHOWN = 7, CELL = 2, PERIOD = 6.4, STAGGER = 0.55;
const ease = (t: number) => t * t * (3 - 2 * t);

// How far through its step a chunk is, at t seconds: a moment before, two seconds through it, a
// while finished, and quickly back.
function progress(t: number, i: number) {
	const m = t - i * STAGGER;
	if (m < 0) return 0;
	const q = m % PERIOD;
	if (q < 0.4) return 0;
	if (q < 2.6) return ease((q - 0.4) / 2.2);
	if (q < 5.9) return 1;
	return 1 - (q - 5.9) / 0.5;
}

interface Layout {
	view: View;
	/** A cell's size in CSS pixels, a whole number of screen pixels; chunks before the steps, and in all; whether the strip scrolls. */
	cell: number;
	before: number;
	chunks: number;
	scroll: boolean;
	width: number;
}

function layout(box: HTMLElement, frame: HTMLElement): Layout {
	const b = box.getBoundingClientRect(), f = frame.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
	const cell = Math.max(1, Math.round(CELL * dpr)) / dpr;
	const frameL = Math.round((f.left - b.left) / cell), frameW = Math.floor(f.width / cell);
	// seven chunks and the depth behind the last, in the frame
	let s = Math.min(9, Math.floor(frameW / (SHOWN * 16 + 8)));
	const scroll = s < 4;
	if (scroll) s = 4;
	const d = s >> 1, chunk = 16 * s;
	let cols: number, ox: number, before: number, chunks: number;
	if (scroll) {
		before = 1;
		chunks = SHOWN + 2;
		ox = Math.max(4, frameL) - chunk;
		cols = ox + chunks * chunk + 16 * d + Math.max(4, frameL);
	} else {
		cols = Math.floor(b.width / cell);
		before = Math.ceil(frameL / chunk);
		ox = frameL - before * chunk;
		chunks = Math.max(before + SHOWN + 1, Math.ceil((cols - ox) / chunk));
	}
	const oy = H * s + D * d + 2;
	return { view: { cols, rows: oy + 3, s, ox, oy }, cell, before, chunks, scroll, width: cols * cell };
}

export function GenSteps({ steps, className }: { steps: GenStep[]; className?: string }) {
	const box = useRef<HTMLDivElement>(null), frame = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	const [lay, setLay] = useState<Layout | null>(null);
	const [hover, setHover] = useState(-1);
	const hoverRef = useRef(-1);

	// the layout, at once and whenever the window's width changes
	useEffect(() => {
		const measure = () => box.current && frame.current && setLay(layout(box.current, frame.current));
		measure();
		let w = window.innerWidth, id = 0;
		const ro = new ResizeObserver(() => {
			if (window.innerWidth === w) return;
			w = window.innerWidth;
			clearTimeout(id);
			id = window.setTimeout(measure, 120);
		});
		ro.observe(document.documentElement);
		return () => {
			ro.disconnect();
			clearTimeout(id);
		};
	}, []);

	// the world, and the drawing, for that layout; the world is made once the strip is near the view
	useEffect(() => {
		const c = cv.current;
		if (!lay || !c) return;
		const { view, before, chunks } = lay;
		let S: Surface | null = null, world: Slab | null = null, raf = 0, on = false, last = -1;
		const bits = new Uint8Array(view.cols * view.rows);
		const st = new Int8Array(chunks), pr = new Float32Array(chunks);
		for (let k = 0; k < chunks; k++) st[k] = k < before ? Step.Empty : k < before + SHOWN ? k - before + 1 : Step.Light;
		const calm = still(), t0 = performance.now(), was = new Int16Array(chunks).fill(-1);
		const paint = (t: number, force = false) => {
			if (!world || !S) return;
			// blocks change a few at a time, so a frame where no chunk has moved a 64th isn't drawn
			let moved = force;
			for (let k = 0; k < chunks; k++) {
				const i = k - before;
				pr[k] = i < 0 || i >= SHOWN || calm || hoverRef.current === i ? 1 : progress(t, i);
				const q = Math.round(pr[k] * 64);
				if (q !== was[k]) moved = true;
				was[k] = q;
			}
			if (!moved) return;
			drawSlab(world, view, bits, st, pr);
			// the canvas can round a cell wider or narrower than the layout, so copy what both have
			const { cols, rows } = view, u = S.u32, w = Math.min(cols, S.cols), h = Math.min(rows, S.rows), ink = 0xffd03818;
			for (let y = 0; y < h; y++)
				for (let x = 0; x < w; x++) u[y * S.cols + x] = bits[y * cols + x] ? ink : 0;
			S.flush();
		};
		const frameFn = (now: number) => {
			raf = 0;
			const t = (now - t0) / 1000;
			// blocks change one at a time, so fifteen frames a second is plenty
			if (t - last >= 1 / 15) {
				last = t;
				paint(t);
			}
			if (on && !calm) raf = requestAnimationFrame(frameFn);
		};
		const io = new IntersectionObserver(
			([e]) => {
				if (e.isIntersecting && !world) {
					world = new Slab(chunks);
					S = surface(c, CELL);
					paint(0);
				}
				on = e.isIntersecting && e.intersectionRatio > 0;
				if (on && !raf && !calm) raf = requestAnimationFrame(frameFn);
			},
			{ rootMargin: '50% 0px' },
		);
		io.observe(c);
		return () => {
			io.disconnect();
			cancelAnimationFrame(raf);
		};
	}, [lay]);

	// which step's chunk the pointer is over
	const point = (e: React.PointerEvent) => {
		if (!lay) return;
		const r = cv.current!.getBoundingClientRect(), cx = (e.clientX - r.left) / lay.cell;
		const i = Math.floor((cx - lay.view.ox) / (16 * lay.view.s)) - lay.before;
		hoverRef.current = i >= 0 && i < SHOWN ? i : -1;
		setHover(hoverRef.current);
	};

	const v = lay?.view;
	return (
		<div ref={box} className={cn('relative', className)}>
			{/* the frame, measured so the steps start on its left edge */}
			<div className="wrap pointer-events-none absolute inset-x-0 top-0 h-0" aria-hidden>
				<div ref={frame} className="h-0" />
			</div>
			<div className={cn(lay?.scroll && 'overflow-x-auto overscroll-x-contain [scrollbar-width:thin]')}>
				<div className="relative" style={lay ? { width: lay.width } : undefined}>
					<canvas
						ref={cv}
						role="img"
						aria-label="A strip of a world, each chunk a step further through vanilla's generation than the one before: structure starts, biomes, noise, surface, carvers, features and light"
						className="block w-full"
						style={{ height: v && lay ? v.rows * lay.cell : 'clamp(240px, 21vw, 460px)' }}
						onPointerMove={point}
						onPointerLeave={() => setHover((hoverRef.current = -1))}
					/>
					<ol className="relative h-[68px]">
						{steps.map((st, i) => (
							<li
								key={st.name}
								className={cn('absolute top-0 grid gap-1.5 border-t pt-3 pr-3', hover === i ? 'border-solid border-ink' : 'border-dotted border-ink')}
								style={v && lay ? { left: (v.ox + (lay.before + i) * 16 * v.s) * lay.cell, width: 16 * v.s * lay.cell } : { left: `${(i / SHOWN) * 100}%`, width: `${100 / SHOWN}%` }}
							>
								<span className={cn('label leading-none', hover === i && 'font-medium')}>
									<span className="tabular-nums">{String(i + 1).padStart(2, '0')}</span> {st.name}
								</span>
								<span className="font-mono text-xs leading-none tabular-nums">{st.cases.toLocaleString('en-US')} cases</span>
							</li>
						))}
					</ol>
				</div>
			</div>
		</div>
	);
}
