'use client';

// The ground under every page, across the whole window: a cut through a world from
// src/lib/brand/slab.ts seen square on, from the treetops down to bedrock, with the caves and ores
// the cut finds, drawn as the strip of steps on the home page draws its blocks. Blocks a little way
// back show through where the front is open: fainter in the open, dark underground.
//
// Hold the pointer on a block to mine it: ten stages of cracks, for as long as a hand takes on
// that block, and then it's gone and what's behind it shows. Keep holding and the next one goes,
// as in the game. Bedrock and water can't be mined. A crisp outline marks the block the pointer
// is on. It's drawn once it's near the view, and again only when something changes.

import { useEffect, useRef, useState } from 'react';
import { surface, type Surface } from '@/lib/dither/canvas';
import { clear, cracks, drawSlab, H, mineTime, Slab, Step, type View } from '@/lib/brand/slab';
import { cn } from '@/lib/cn';

const CELL = 2, S = 8, DEEP = 4, STAGES = 10, SEED = 23;
const CRACK = cracks(S, STAGES);
// a moment between one block going and the next starting, as in the game
const PAUSE = 0.25;

interface Target {
	x: number;
	y: number;
	z: number;
}
const same = (a: Target | null, b: Target | null) => a === b || (!!a && !!b && a.x === b.x && a.y === b.y && a.z === b.z);

export function Ground({ className }: { className?: string }) {
	const box = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	const [mined, setMined] = useState(0);

	useEffect(() => {
		const el = box.current, c = cv.current;
		if (!el || !c) return;
		let world: Slab | null = null, surf: Surface | null = null, view: View | null = null, bits = new Uint8Array(0);
		let cell = CELL, steps = new Int8Array(0), prog = new Float32Array(0), raf = 0, near = false, width = 0, rid = 0;
		// what the pointer's on and the last place it was, whether it's held, and how far the block's mined
		let hover: Target | null = null, last: PointerEvent | null = null, held = false, since = 0, waitUntil = 0, stage = -1;

		// a cut as wide as the window, centred, starting a block over its highest block
		const build = () => {
			const dpr = window.devicePixelRatio || 1;
			width = el.getBoundingClientRect().width;
			cell = Math.max(1, Math.round(CELL * dpr)) / dpr;
			const cols = Math.ceil(width / cell), chunks = Math.ceil(cols / (16 * S)) + 1;
			world = new Slab(chunks, SEED, false);
			let top = 0;
			for (let x = 0; x < world.L; x++)
				for (let z = 0; z < DEEP; z++)
					for (let y = H - 1; y > top; y--) if (!clear(world.at(x, y, z))) top = y;
			const rows = (top + 2) * S;
			view = { cols, rows, s: S, ox: -Math.floor((chunks * 16 * S - cols) / 2), oy: rows, cut: { deep: DEEP } };
			steps = new Int8Array(chunks).fill(Step.Light);
			prog = new Float32Array(chunks).fill(1);
			bits = new Uint8Array(cols * rows);
			hover = null;
			stage = -1;
			c.style.height = `${rows * cell}px`;
			surf = surface(c, CELL);
			paint();
		};

		// the block the pointer's on: the nearest one there, past water
		const pick = (e: PointerEvent): Target | null => {
			if (!world || !view) return null;
			const r = c.getBoundingClientRect(), cx = Math.floor((e.clientX - r.left) / cell), cy = Math.floor((e.clientY - r.top) / cell);
			const x = Math.floor((cx - view.ox) / S), y = Math.floor((view.oy - 1 - cy) / S);
			if (x < 0 || x >= world.L || y < 0 || y >= H) return null;
			for (let z = 0; z < DEEP; z++) if (!clear(world.at(x, y, z))) return { x, y, z };
			return null;
		};

		const paint = () => {
			if (!world || !view || !surf) return;
			drawSlab(world, view, bits, steps, prog);
			const { cols, rows, ox, oy } = view;
			const put = (cx: number, cy: number, on: number) => {
				if (cx >= 0 && cy >= 0 && cx < cols && cy < rows) bits[cy * cols + cx] = on;
			};
			if (hover) {
				const fx = ox + hover.x * S, fy = oy - (hover.y + 1) * S;
				// the cracks: ink where the block's light, paper where it's dark, so they show on either
				if (stage >= 0)
					for (const i of CRACK[stage]) {
						const cx = fx + (i % S), cy = fy + Math.floor(i / S), k = cy * cols + cx;
						if (cx < 1 || cy < 1 || cx >= cols - 1 || cy >= rows - 1) continue;
						put(cx, cy, bits[k - 1] + bits[k + 1] + bits[k - cols] + bits[k + cols] >= 2 ? 0 : 1);
					}
				// the outline: ink round the block and paper just inside, crisp on any block
				for (let i = -1; i <= S; i++) {
					put(fx + i, fy - 1, 1);
					put(fx + i, fy + S, 1);
					put(fx - 1, fy + i, 1);
					put(fx + S, fy + i, 1);
				}
				for (let i = 0; i < S; i++) {
					put(fx + i, fy, 0);
					put(fx + i, fy + S - 1, 0);
					put(fx, fy + i, 0);
					put(fx + S - 1, fy + i, 0);
				}
			}
			const u = surf.u32, w = Math.min(cols, surf.cols), h = Math.min(rows, surf.rows), ink = 0xffd03818;
			for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) u[y * surf.cols + x] = bits[y * cols + x] ? ink : 0;
			surf.flush();
		};

		// while held, the block under the pointer cracks a stage at a time, then goes
		const tick = (now: number) => {
			raf = 0;
			if (!held || !world) return;
			const t = now / 1000;
			if (t >= waitUntil && hover) {
				const need = mineTime(world.at(hover.x, hover.y, hover.z));
				if (!isFinite(need)) return;
				if (since === 0) since = t;
				const k = Math.floor(((t - since) / need) * STAGES);
				if (k >= STAGES) {
					world.mine(hover.x, hover.y, hover.z);
					setMined((m) => m + 1);
					since = 0;
					stage = -1;
					waitUntil = t + PAUSE;
					hover = last ? pick(last) : null;
					paint();
				} else if (k !== stage) {
					stage = k;
					paint();
				}
			}
			raf = requestAnimationFrame(tick);
		};

		const move = (e: PointerEvent) => {
			last = e;
			const t = pick(e);
			if (same(t, hover)) return;
			// another block starts afresh
			hover = t;
			since = 0;
			stage = -1;
			paint();
		};
		const down = (e: PointerEvent) => {
			if (e.button !== 0) return;
			last = e;
			hover = pick(e);
			held = true;
			since = 0;
			stage = -1;
			if (e.pointerType === 'mouse') e.preventDefault();
			if (!raf) raf = requestAnimationFrame(tick);
		};
		const up = () => {
			if (!held) return;
			held = false;
			since = 0;
			stage = -1;
			paint();
		};
		const leave = () => {
			held = false;
			hover = null;
			stage = -1;
			paint();
		};

		const io = new IntersectionObserver(
			([e]) => {
				if (!e.isIntersecting || near) return;
				near = true;
				io.disconnect();
				build();
			},
			{ rootMargin: '50% 0px' },
		);
		io.observe(el);
		// a new cut when the window's width changes
		const ro = new ResizeObserver(() => {
			if (!near || Math.abs(el.getBoundingClientRect().width - width) < 1) return;
			clearTimeout(rid);
			rid = window.setTimeout(build, 150);
		});
		ro.observe(el);
		c.addEventListener('pointermove', move);
		c.addEventListener('pointerdown', down);
		c.addEventListener('pointerleave', leave);
		c.addEventListener('pointercancel', leave);
		window.addEventListener('pointerup', up);
		return () => {
			io.disconnect();
			ro.disconnect();
			cancelAnimationFrame(raf);
			clearTimeout(rid);
			c.removeEventListener('pointermove', move);
			c.removeEventListener('pointerdown', down);
			c.removeEventListener('pointerleave', leave);
			c.removeEventListener('pointercancel', leave);
			window.removeEventListener('pointerup', up);
		};
	}, []);

	return (
		<div ref={box} className={cn('relative', className)}>
			<canvas
				ref={cv}
				role="img"
				aria-label="The ground under the page: grass and trees, dirt, stone, deepslate and bedrock, with caves and ores. Hold the pointer on a block to mine it."
				className="block h-[clamp(160px,14vw,240px)] w-full cursor-crosshair touch-pan-y select-none"
				onContextMenu={(e) => e.preventDefault()}
			/>
			<p className="wrap pointer-events-none absolute inset-x-0 top-0 flex justify-end font-mono text-xs leading-none tabular-nums" aria-live="polite">
				{mined === 0 ? 'hold on a block to mine it' : `${mined.toLocaleString('en-US')} block${mined === 1 ? '' : 's'} mined`}
			</p>
		</div>
	);
}
