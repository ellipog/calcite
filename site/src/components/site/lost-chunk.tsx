'use client';

// The 404 page's world: a strip of finished chunks across the window with one missing in the
// middle, the chunk this address would be, never generated. Through the hole shows the cut side
// of the chunk beside it, from the grass to bedrock. Then the server generates it anyway, a step
// at a time, as the home page's strip shows: structure starts reserves a box, biomes, noise,
// surface, carvers, features and light follow, and the structure it builds in its box, in the
// features step, is the page's number in bricks. A log under it says what the server did.
//
// The address picks the world: its hash is the seed and the chunk's coordinates, so every wrong
// address is somewhere else, and going to another starts over there. With reduced motion the chunk is drawn generated, with the whole log.

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { surface, type Surface } from '@/lib/dither/canvas';
import { still } from '@/lib/dither/motion';
import { drawSlab, H, D, Slab, Step, type View } from '@/lib/brand/slab';
import { cn } from '@/lib/cn';

const CELL = 2;
/** The steps, each a second and a bit, after a moment with the hole as it is. */
const WAIT = 1.2, STEP = 1.25, MOVE = 1.0;
const STEPS = ['structure starts', 'biomes', 'noise', 'surface', 'carvers', 'features', 'light'];
// "404" in blocks, four wide and six high, a block between, as wide as fits a chunk
const FOUR = ['#..#.####.#..#', '#..#.#..#.#..#', '#..#.#..#.#..#', '####.#..#.####', '...#.#..#....#', '...#.####....#'];
// the world border is 29,999,984 blocks out, 1,874,999 chunks
const EDGE = 1_874_999;

const ease = (t: number) => t * t * (3 - 2 * t);
function fnv(s: string, seed = 0x811c9dc5) {
	let h = seed >>> 0;
	for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619) >>> 0;
	return h;
}
const signed = (n: number) => (n < 0 ? `−${(-n).toLocaleString('en-US')}` : n.toLocaleString('en-US'));

interface Place {
	path: string;
	seed: number;
	x: number;
	z: number;
}
interface Layout {
	view: View;
	cell: number;
	chunks: number;
	mid: number;
}

export function LostChunk({ className }: { className?: string }) {
	const box = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	const [place, setPlace] = useState<Place | null>(null);
	const [lay, setLay] = useState<Layout | null>(null);
	// the step under way, how many are done, and a count of replays, which starts them again
	const [under, setUnder] = useState(0);
	const [done, setDone] = useState(0);
	const [run, setRun] = useState(0);
	const pathname = usePathname(), router = useRouter();

	// where this address is, and its world, sized to the window, with the hole in the middle
	const world = useRef<Slab | null>(null);
	useEffect(() => {
		const el = box.current;
		if (!el) return;
		let path = pathname;
		try {
			path = decodeURIComponent(path);
		} catch {}
		const h = fnv(path), hx = fnv(path, h), hz = fnv(path, hx);
		const place: Place = { path, seed: h % 1_000_000, x: (hx % (2 * EDGE + 1)) - EDGE, z: (hz % (2 * EDGE + 1)) - EDGE };
		const measure = () => {
			setPlace(place);
			const dpr = window.devicePixelRatio || 1, cell = Math.max(1, Math.round(CELL * dpr)) / dpr;
			const cols = Math.ceil(el.getBoundingClientRect().width / cell);
			// blocks as big as fit five and a half chunks across, and on a phone as big as leave some world each side
			const s = Math.max(6, Math.min(10, Math.floor(cols / 88))), d = s >> 1;
			const chunks = Math.ceil(cols / (16 * s)) + 3, mid = chunks >> 1;
			const w = new Slab(chunks, place.seed, true, mid);
			w.build(mid, FOUR);
			world.current = w;
			// the canvas starts a little over the highest block on screen anything will have
			const ox = Math.round(cols / 2 - (mid * 16 + 8) * s - (D * d) / 2);
			let top = 0;
			for (let z = 0; z < D; z++)
				for (let x = 0; x < w.L; x++) {
					const sx = ox + x * s + z * d;
					if (sx + s + d <= 0 || sx >= cols) continue;
					for (let y = H - 1; y >= 0; y--)
						if (w.at(x, y, z)) {
							top = Math.max(top, (y + 1) * s + z * d);
							break;
						}
				}
			const oy = top + 2 * s;
			setLay({ view: { cols, rows: oy + 3, s, ox, oy, focus: mid }, cell, chunks, mid });
		};
		measure();
		let w = window.innerWidth, id = 0;
		const ro = new ResizeObserver(() => {
			if (window.innerWidth === w) return;
			w = window.innerWidth;
			clearTimeout(id);
			id = window.setTimeout(measure, 150);
		});
		ro.observe(document.documentElement);
		return () => {
			ro.disconnect();
			clearTimeout(id);
		};
	}, [pathname]);

	// the steps, played in the hole
	useEffect(() => {
		const c = cv.current, w = world.current;
		if (!lay || !c || !w) return;
		const { view, chunks, mid } = lay;
		const S: Surface = surface(c, CELL), bits = new Uint8Array(view.cols * view.rows);
		const st = new Int8Array(chunks).fill(Step.Light), pr = new Float32Array(chunks).fill(1);
		const calm = still(), t0 = performance.now();
		let raf = 0, last = -1, shown = -1, was = -1;
		const paint = () => {
			drawSlab(w, view, bits, st, pr);
			const { cols, rows } = view, u = S.u32, ww = Math.min(cols, S.cols), hh = Math.min(rows, S.rows), ink = 0xffd03818;
			for (let y = 0; y < hh; y++) for (let x = 0; x < ww; x++) u[y * S.cols + x] = bits[y * cols + x] ? ink : 0;
			S.flush();
		};
		const frame = (now: number) => {
			raf = 0;
			const t = calm ? Infinity : (now - t0) / 1000 - WAIT;
			// the step under way and how far through it; before the first, the hole as it is
			const k = t < 0 ? 0 : Math.min(STEPS.length, Math.floor(t / STEP) + 1), p = t < 0 ? 1 : k >= STEPS.length && t >= STEPS.length * STEP ? 1 : ease(Math.min(1, (t - (k - 1) * STEP) / MOVE));
			st[mid] = k;
			if (k !== was) {
				was = k;
				setUnder(k);
			}
			pr[mid] = t < 0 ? 1 : p;
			const finished = t < 0 ? 0 : Math.min(STEPS.length, Math.floor((t - MOVE) / STEP) + 1);
			if (finished !== shown) {
				shown = finished;
				setDone(finished);
			}
			// fifteen frames a second is plenty for blocks
			if (now - last >= 1000 / 15) {
				last = now;
				paint();
			}
			if (finished < STEPS.length) raf = requestAnimationFrame(frame);
			else paint();
		};
		raf = requestAnimationFrame(frame);
		return () => cancelAnimationFrame(raf);
	}, [lay, run]);

	const v = lay?.view, at = place ? `${signed(place.x)}, ${signed(place.z)}` : '';
	// the chunk's middle, in blocks from 0, 0
	const far = place ? Math.round(Math.hypot(place.x * 16 + 8, place.z * 16 + 8)) : 0;
	// somewhere else: another address that isn't a page, so another world
	const elsewhere = () => {
		const a = 'abcdefghijkmnpqrstuvwxyz23456789';
		let p = '';
		for (let i = 0; i < 6; i++) p += a[Math.floor(Math.random() * a.length)];
		router.push(`/nowhere/${p}`);
	};
	return (
		<div className={cn('relative', className)}>
			<div ref={box} className="relative">
				<canvas
					ref={cv}
					role="img"
					aria-label="A strip of a world with one chunk missing, where this page would be. The server generates it step by step, and the structure it builds there spells 404 in bricks."
					className="block w-full"
					style={{ height: v && lay ? v.rows * lay.cell : 'clamp(280px, 30vw, 560px)' }}
				/>
				{v && lay && (
					<p className="absolute top-full mt-3 grid gap-1.5 border-t border-solid border-ink pt-3 font-mono text-xs leading-none" style={{ left: (v.ox + lay.mid * 16 * v.s) * lay.cell, width: 16 * v.s * lay.cell }}>
						<span className="label leading-none">{done >= STEPS.length ? 'generated' : under === 0 ? 'not generated' : `${String(under).padStart(2, '0')} ${STEPS[under - 1]}`}</span>
						<span className="tabular-nums">chunk {at}</span>
					</p>
				)}
			</div>
			<div className="wrap mt-24 grid grid-cols-1 gap-8 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:gap-10">
				<ol aria-hidden className="grid max-w-[64ch] content-start gap-1.5 rule p-5 font-mono text-xs leading-normal">
					<li className="[overflow-wrap:anywhere]">GET {place?.path ?? '/'}</li>
					<li>chunk {at} has never been generated; generating it</li>
					{STEPS.slice(0, done).map((s, i) => (
						<li key={s} className="flex gap-3">
							<span className="w-[22ch] shrink-0 whitespace-nowrap tabular-nums">
								{String(i + 1).padStart(2, '0')} {s}
							</span>
							done
						</li>
					))}
					{done >= STEPS.length && (
						<li className="mt-2 [overflow-wrap:anywhere]">
							chunk {at} generated. There&apos;s still no page at {place?.path}.
						</li>
					)}
				</ol>
				<div className="flex flex-col items-start gap-6">
					<p className="sr-only">The server looked for this address, found nothing, and generated a chunk of world in its place. It spells 404.</p>
					<p className="max-w-[44ch] leading-normal">Each address has a world of its own, from a hash of it, and a chunk in that world. This one is here:</p>
					<dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 font-mono text-xs tabular-nums">
						<dt className="label">seed</dt>
						<dd>{place ? place.seed.toLocaleString('en-US') : ''}</dd>
						<dt className="label">chunk</dt>
						<dd>{at}</dd>
						<dt className="label">from 0, 0</dt>
						<dd>{far.toLocaleString('en-US')} blocks</dd>
					</dl>
					<div className="flex flex-wrap gap-x-6 gap-y-3 font-mono text-xs">
						<button type="button" className="link disabled:opacity-40" onClick={() => setRun((r) => r + 1)} disabled={done < STEPS.length}>
							generate it again
						</button>
						<button type="button" className="link" onClick={elsewhere}>
							go somewhere else
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}
