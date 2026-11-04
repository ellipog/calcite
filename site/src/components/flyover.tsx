'use client';

// The hero: a world of blocks flown over (src/lib/brand/hero.ts). It draws in a worker, on a
// canvas the page hands over, so the flight never holds up scrolling or input; where a worker
// can't draw, it draws on the page. Under it, for visitors who don't scroll, a block is mined.

import { useEffect, useRef, useState } from 'react';
import { ordered } from '@/lib/dither/bayer';
import { surface } from '@/lib/dither/canvas';
import { PAPER, rgb } from '@/lib/dither/math';
import { still } from '@/lib/dither/motion';
import { hash } from '@/lib/brand/blocks';
import { cracks } from '@/lib/brand/slab';
import { Hero } from '@/lib/brand/hero';
import { cn } from '@/lib/cn';

const LABEL = 'A world of blocks flown over, its chunks generated as fast as Calcite generates them';

type Message = { type: 'size'; w: number; h: number; dpr: number } | { type: 'point'; p: [number, number] | null } | { type: 'wake' } | { type: 'show'; on: boolean };

export function Flyover({ className, cue = false, cps = 2000 }: { className?: string; cue?: boolean; cps?: number }) {
	const fly = useRef<HTMLDivElement>(null), count = useRef<HTMLSpanElement>(null);

	useEffect(() => {
		const box = fly.current;
		if (!box) return;
		// reduced motion, or a reader saving data, gets one still frame; a touch screen, fewer frames
		const o = {
			cps,
			still: still() || !!(navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData,
			touch: matchMedia('(pointer: coarse)').matches,
			seed: Math.floor(Math.random() * 1e9),
		};
		const shown = (n: number) => {
			if (count.current) count.current.textContent = `${n.toLocaleString('en-US')} chunks`;
		};
		// a canvas of its own each time, since one can be handed to a worker only once
		const make = () => {
			const c = document.createElement('canvas');
			c.className = 'absolute inset-0 size-full cursor-crosshair touch-pan-y';
			c.setAttribute('role', 'img');
			c.setAttribute('aria-label', LABEL);
			box.prepend(c);
			return c;
		};
		let canvas = make(), send: (m: Message) => void = () => {}, end = () => {}, size: Message | null = null, show: Message | null = null;

		// on the page, where a worker can't draw
		const local = () => {
			const hero = new Hero(canvas, { ...o, raf: (f) => requestAnimationFrame(f), caf: (id) => cancelAnimationFrame(id), count: shown });
			send = (m) => {
				if (m.type === 'size') hero.resize(m.w, m.h, m.dpr);
				else if (m.type === 'point') hero.point(m.p);
				else if (m.type === 'wake') hero.wake();
				else hero.show(m.on);
			};
			end = () => hero.stop();
		};
		let worker: Worker | null = null;
		if (typeof Worker !== 'undefined' && typeof OffscreenCanvas !== 'undefined' && 'transferControlToOffscreen' in canvas) {
			try {
				worker = new Worker(new URL('../lib/brand/hero.worker.ts', import.meta.url), { type: 'module' });
				const off = canvas.transferControlToOffscreen();
				worker.postMessage({ type: 'init', canvas: off, o }, [off]);
			} catch {
				worker?.terminate();
				worker = null;
			}
		}
		if (worker) {
			const w = worker;
			w.onmessage = (e: MessageEvent<{ type: string; n: number }>) => e.data.type === 'count' && shown(e.data.n);
			// if the worker can't start, draw on the page instead, on a fresh canvas
			w.onerror = () => {
				w.terminate();
				canvas.remove();
				canvas = make();
				local();
				if (size) send(size);
				if (show) send(show);
			};
			send = (m) => w.postMessage(m);
			end = () => w.terminate();
		} else local();
		const post = (m: Message) => {
			if (m.type === 'size') size = m;
			if (m.type === 'show') show = m;
			send(m);
		};

		// the canvas's size, at once and then as it changes
		let id = 0, first = true;
		const measure = () => {
			const r = box.getBoundingClientRect();
			post({ type: 'size', w: r.width, h: r.height, dpr: window.devicePixelRatio || 1 });
		};
		const ro = new ResizeObserver(() => {
			clearTimeout(id);
			if (first) {
				first = false;
				measure();
			} else id = window.setTimeout(measure, 120);
		});
		ro.observe(box);
		// on screen and the page shown, or the flight stops
		let seen = false;
		const tell = () => post({ type: 'show', on: seen && !document.hidden });
		const io = new IntersectionObserver(([e]) => {
			seen = e.isIntersecting;
			tell();
		});
		io.observe(box);
		document.addEventListener('visibilitychange', tell);
		// the pointer turns the camera; a touch wakes a resting flight
		const move = (e: PointerEvent) => {
			const r = box.getBoundingClientRect();
			post({ type: 'point', p: [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height] });
		};
		const leave = () => post({ type: 'point', p: null });
		const down = () => post({ type: 'wake' });
		box.addEventListener('pointermove', move, { passive: true });
		box.addEventListener('pointerleave', leave);
		box.addEventListener('pointerdown', down, { passive: true });
		return () => {
			ro.disconnect();
			io.disconnect();
			clearTimeout(id);
			document.removeEventListener('visibilitychange', tell);
			box.removeEventListener('pointermove', move);
			box.removeEventListener('pointerleave', leave);
			box.removeEventListener('pointerdown', down);
			end();
			canvas.remove();
		};
	}, [cps]);

	return (
		<div ref={fly} className={cn('relative min-h-[260px]', className)}>
			<span className="pointer-events-none absolute top-4 right-(--side) z-10 rule bg-paper pointer-coarse:hidden motion-reduce:hidden px-2.5 py-2 font-mono text-xs leading-none">move to look around</span>
			<div className="pointer-events-none absolute bottom-5 left-(--side) z-10 flex flex-wrap gap-2 font-mono text-xs leading-none max-sm:hidden">
				<span ref={count} className="rule bg-paper px-2.5 py-2 tabular-nums">
					0 chunks
				</span>
				<span className="rule bg-paper px-2.5 py-2">generated at {Math.round(cps).toLocaleString('en-US')} a second, Calcite&apos;s rate</span>
			</div>
			{cue && <MineCue />}
		</div>
	);
}

// A chip at the bottom of the hero with a block in it, mined in ten stages of cracks as a player
// mines one, that crumbles away and leaves an arrow down. It appears when the page has sat still
// at the top for a few seconds, goes as soon as the reader scrolls, and takes them down if they
// press it.
const BLOCK = 16, STAGES = 10, MINE = 1.6, CRUMBLE = 0.45;
const PAPER_RGB = rgb(PAPER);

function MineCue() {
	const [on, setOn] = useState(false);
	const cv = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const off = () => window.scrollY > 8;
		if (off()) return;
		const id = window.setTimeout(() => !off() && setOn(true), 3500);
		const gone = () => {
			if (!off()) return;
			setOn(false);
			clearTimeout(id);
			removeEventListener('scroll', gone);
		};
		addEventListener('scroll', gone, { passive: true });
		return () => {
			clearTimeout(id);
			removeEventListener('scroll', gone);
		};
	}, []);

	useEffect(() => {
		if (!on) return;
		const S = surface(cv.current!, 2), n = S.cols, bits = new Uint8Array(n * S.rows), crack = cracks(BLOCK, STAGES);
		// the block's face: stone, its cells a little lighter or darker, framed in ink
		const face = new Float32Array(BLOCK * BLOCK);
		for (let y = 0; y < BLOCK; y++) for (let x = 0; x < BLOCK; x++) face[y * BLOCK + x] = x === 0 || y === 0 || x === BLOCK - 1 || y === BLOCK - 1 ? 1 : 0.28 + hash(x, y + 40) * 0.22;
		const faceBits = ordered(face, BLOCK, BLOCK, 4);
		const t0 = performance.now();
		let raf = 0;
		const put = (x: number, y: number) => {
			if (x >= 0 && y >= 0 && x < n && y < S.rows) bits[y * n + x] = 1;
		};
		const frame = (now: number) => {
			const t = still() ? MINE + CRUMBLE : (now - t0) / 1000;
			bits.fill(0);
			if (t < MINE + CRUMBLE) {
				// the block, cracking, then crumbling away cell by cell
				const stage = Math.min(STAGES - 1, Math.floor((t / MINE) * STAGES)), cs = new Set(crack[stage]), gone = Math.max(0, (t - MINE) / CRUMBLE);
				for (let y = 0; y < BLOCK; y++)
					for (let x = 0; x < BLOCK; x++) {
						const i = y * BLOCK + x;
						if ((cs.has(i) || faceBits[i]) && hash(x + 7, y) >= gone) put(x, y);
					}
			} else {
				// the arrow left where the block was, bobbing a cell
				const bob = Math.floor((t * 2) % 2);
				for (let y = 2; y < 12; y++) for (const x of [7, 8]) put(x, y + bob);
				for (let i = 0; i < 6; i++) for (const x of [2 + i, 3 + i, 13 - i, 12 - i]) put(x, 6 + i + bob);
			}
			S.bits(bits, undefined, PAPER_RGB);
			S.flush();
			if (still() || t > 40) return;
			// every frame while the block breaks; once the arrow is up, only when it bobs
			if (t < MINE + CRUMBLE) raf = requestAnimationFrame(frame);
			else id = window.setTimeout(() => (raf = requestAnimationFrame(frame)), 500);
		};
		let id = 0;
		raf = requestAnimationFrame(frame);
		return () => {
			cancelAnimationFrame(raf);
			clearTimeout(id);
		};
	}, [on]);

	if (!on) return null;
	return (
		<button
			type="button"
			className="group absolute bottom-5 left-1/2 flex -translate-x-1/2 animate-dis-in items-center gap-2.5 rule bg-paper py-1.5 pr-3 pl-1.5 font-mono text-xs leading-none hover:[border-style:solid]"
			onClick={() => document.getElementById('more')?.scrollIntoView({ behavior: still() ? 'auto' : 'smooth' })}
		>
			<canvas ref={cv} className="size-8" aria-hidden />
			<span className="group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">more below</span>
		</button>
	);
}
