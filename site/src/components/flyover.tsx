'use client';

// The hero: a world of blocks flown over. Its chunks are generated around the camera, nearest
// first, at the rate Calcite generates them (the fastest recorded worldgen run), so the view fills
// in a fraction of a second and new chunks keep loading at its edge as the flight goes on. The
// pointer turns the camera; left alone, it drifts. Under it, for visitors who don't scroll, a block
// is mined.

import { useEffect, useRef, useState } from 'react';
import { ordered } from '@/lib/dither/bayer';
import { surface, type Surface } from '@/lib/dither/canvas';
import { PAPER, rgb } from '@/lib/dither/math';
import { still, useFrames } from '@/lib/dither/motion';
import { B, CHUNK, forget, frame, generate, groundAt, hash, isLoaded, reseed, SEA } from '@/lib/brand/blocks';
import { cn } from '@/lib/cn';

/** The view distance, in chunks, and the seconds a touch screen's flight goes on after the last touch. */
const VIEW = 14, REST = 30;
// The chunks in view around the camera's, nearest first, a little shuffled within each ring as a
// server's generation threads finish them.
const ORDER = (() => {
	const o: [number, number, number][] = [];
	for (let z = -VIEW; z <= VIEW; z++) for (let x = -VIEW; x <= VIEW; x++) if (x * x + z * z <= VIEW * VIEW) o.push([x, z, Math.hypot(x, z) + hash(x + 500, z) * 1.2]);
	return o.sort((a, b) => a[2] - b[2]);
})();

// Somewhere to start: land, a little above the sea, with the ground rising somewhere ahead.
function start() {
	for (let i = 0; i < 400; i++) {
		const x = 1000 + i * 97, y = 3000 - i * 61, g = groundAt(x, y);
		if (g > SEA + 4 && g < SEA + 16 && groundAt(x, y - 260) < SEA + 24) return { x, y };
	}
	return { x: 1000, y: 3000 };
}

export function Flyover({ className, cue = false, cps = 2000 }: { className?: string; cue?: boolean; cps?: number }) {
	const fly = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null), count = useRef<HTMLSpanElement>(null);
	const st = useRef({
		S: null as Surface | null, last: -1, full: NaN, budget: 0, shown: -1, aim: null as [number, number] | null, look: { yaw: 0, hor: 0 }, cam: null as { x: number; y: number } | null, h: 0, heading: 0,
		// pacing: still draws one frame; touch screens rest a while after the last touch; frames are spaced by what they cost
		still: false, touch: false, drawn: false, next: 0, rest: Infinity, wake: true, cost: 0,
	});

	const draw = (t: number) => {
		const s = st.current, S = s.S;
		if (!S) return;
		if (s.still) {
			if (s.drawn) return;
		} else if (s.last >= 0) {
			if (s.wake) {
				s.wake = false;
				s.rest = t + REST;
			}
			if (t < s.next || (s.touch && t > s.rest)) return;
		}
		const w0 = performance.now();
		if (!s.cam) {
			// a new world on every visit, and a spawn found in it
			reseed(Math.floor(Math.random() * 1e9));
			forget();
			s.cam = start();
			s.h = (groundAt(s.cam.x, s.cam.y) + 24) * B;
		}
		const dt = s.last < 0 ? 0 : Math.min(0.05, Math.max(0, t - s.last));
		s.last = t;
		const { cols, rows } = S, cam = s.cam;
		// the pointer turns the camera and tips it a little; without one it looks ahead
		const ay = s.aim ? (s.aim[0] - 0.5) * 0.9 : 0, ah = s.aim ? (s.aim[1] - 0.5) * 0.12 : 0;
		s.look.yaw += (ay - s.look.yaw) * 0.06;
		s.look.hor += (ah - s.look.hor) * 0.06;
		s.heading = Math.sin(t * 0.045) * 0.5;
		const fx = Math.sin(s.heading), fy = -Math.cos(s.heading);
		cam.x += fx * 16 * dt;
		cam.y += fy * 16 * dt;
		// fly over whatever is coming up, not into it
		let ahead = 0;
		for (const d of [0, 40, 80, 120]) ahead = Math.max(ahead, groundAt(cam.x + fx * d, cam.y + fy * d));
		s.h += ((ahead + 24) * B - s.h) * Math.min(1, dt * 0.8);
		// generate the nearest chunks missing, as many as Calcite would in the time since the last frame
		// (none to look for while the camera stays in a chunk whose view is already whole)
		const ccx = Math.floor(cam.x / CHUNK), ccz = Math.floor(cam.y / CHUNK), here = ccx * 65536 + ccz;
		let n = ORDER.length;
		if (s.full !== here) {
			const t0 = performance.now();
			// (a still frame generates the whole view, however long it takes)
			s.budget = s.still ? ORDER.length : Math.min(s.budget + cps * (dt || 1 / 60), ORDER.length);
			n = 0;
			for (const [x, z] of ORDER) {
				if (isLoaded(ccx + x, ccz + z)) {
					n++;
					continue;
				}
				if (s.budget < 1 || (!s.still && performance.now() - t0 > 10)) continue;
				generate(ccx + x, ccz + z);
				s.budget--;
				n++;
			}
			if (n === ORDER.length) s.full = here;
		}
		// the sky dissolves into the page above, and the land into it below
		frame(S.u32, cols, rows, { x: cam.x, y: cam.y, yaw: s.heading + s.look.yaw }, { height: s.h, horizon: 0.22 + s.look.hor, far: VIEW * CHUNK, sky: 0.22, haze: 0.08, drift: t * 3, fadeTop: 0.32, fadeBottom: 0.2 });
		S.flush();
		s.drawn = true;
		if (n !== s.shown && count.current) {
			s.shown = n;
			count.current.textContent = `${n.toLocaleString('en-US')} chunks`;
		}
		// 60 frames a second while a frame is cheap, fewer as it costs more, and never more than 30 on a touch screen
		const ms = performance.now() - w0;
		s.cost = s.cost ? s.cost * 0.9 + ms * 0.1 : ms;
		const fps = s.cost > 16 ? 20 : s.cost > 8 || s.touch ? 30 : 60;
		s.next = t + 1 / fps - 0.004;
	};

	// a new surface whenever the box changes size, either way
	useEffect(() => {
		const el = fly.current;
		if (!el) return;
		const s = st.current;
		// reduced motion, or a reader saving data, gets one still frame
		s.still = still() || !!(navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
		s.touch = matchMedia('(pointer: coarse)').matches;
		let w = -1, h = -1, id = 0;
		const make = () => {
			const r = el.getBoundingClientRect();
			if (Math.round(r.width) === w && Math.round(r.height) === h) return;
			w = Math.round(r.width);
			h = Math.round(r.height);
			s.S = surface(cv.current!, 2);
			s.drawn = false;
			if (s.still) draw(0);
		};
		// a touch wakes a resting flight
		const wake = () => (s.wake = true);
		el.addEventListener('pointerdown', wake, { passive: true });
		const ro = new ResizeObserver(() => {
			clearTimeout(id);
			id = window.setTimeout(make, w < 0 ? 0 : 120);
		});
		ro.observe(el);
		return () => {
			ro.disconnect();
			clearTimeout(id);
			el.removeEventListener('pointerdown', wake);
		};
		// draw reads everything through st, so the first one is the only one needed
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);
	useFrames(fly, draw);

	return (
		<div
			ref={fly}
			className={cn('relative min-h-[260px]', className)}
			onPointerMove={(e) => {
				const r = cv.current!.getBoundingClientRect();
				st.current.aim = [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height];
			}}
			onPointerLeave={() => (st.current.aim = null)}
		>
			<canvas ref={cv} className="absolute inset-0 size-full cursor-crosshair touch-pan-y" aria-label="A world of blocks flown over, its chunks generated as fast as Calcite generates them" />
			<span className="pointer-events-none absolute top-4 right-(--gutter) rule bg-paper pointer-coarse:hidden motion-reduce:hidden px-2.5 py-2 font-mono text-xs leading-none">move to look around</span>
			<div className="pointer-events-none absolute bottom-5 left-(--gutter) flex flex-wrap gap-2 font-mono text-xs leading-none max-sm:hidden">
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

function cracks() {
	// cracks walked out from the middle, each stage adding to the last
	const stages: number[][] = [];
	const seen = new Set<number>(), tips: [number, number][] = [[7, 8], [8, 7]];
	let k = 1;
	const r = () => ((k = Math.imul(k ^ (k >>> 15), 2246822507) + 0x9e3779b9), (k >>> 0) / 4294967296);
	for (let s = 0; s < STAGES; s++) {
		for (let step = 0; step < 3 + s; step++) {
			for (const tip of tips) {
				const a = Math.floor(r() * 8), dx = [1, 1, 0, -1, -1, -1, 0, 1][a], dy = [0, 1, 1, 1, 0, -1, -1, -1][a];
				tip[0] = Math.min(BLOCK - 2, Math.max(1, tip[0] + dx));
				tip[1] = Math.min(BLOCK - 2, Math.max(1, tip[1] + dy));
				seen.add(tip[1] * BLOCK + tip[0]);
			}
			if (r() < 0.25 && tips.length < 6) tips.push([...tips[Math.floor(r() * tips.length)]] as [number, number]);
		}
		stages.push([...seen]);
	}
	return stages;
}

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
		const S = surface(cv.current!, 2), n = S.cols, bits = new Uint8Array(n * S.rows), crack = cracks();
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
