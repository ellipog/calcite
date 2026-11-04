'use client';

// A range control in the Dither / One ink style. No knob: the whole track takes clicks and drags.
// The empty track is a pale pattern in the ink, the filled part is solid ink, and the fill's
// leading edge steps down through ordered-dither densities (75, 50, 25%) into the empty pattern.
// Everything is drawn in cells of 2 CSS px rounded to whole device pixels, so it stays sharp at
// any screen density. While dragging, the fill sits right under the pointer; on release or a key
// step it eases to the step over 80 ms, or jumps there with reduced motion.

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { INK } from '@/lib/dither/math';
import { still } from '@/lib/dither/motion';
import { d4, q4, q8, tileURL, type Cell } from '@/lib/dither/tiles';

const md = (v: number, n: number) => ((v % n) + n) % n;
// Bayer 4×4 ranks below which a cell is ink, two cells each: 75, 50 and 25%.
const STEP = [12, 8, 4];

interface Pattern {
	tile: [number, number];
	band: number;
	slant?: boolean;
	empty: Cell;
	edge: (x: number, y: number, d: number) => boolean;
}
// Each pattern, in cells: the tile the empty track repeats in, how wide the leading edge is, the
// empty track, and the edge itself, where d counts cells from its start. Every level nests in the
// one above it, so the edge runs into the empty pattern without a seam.
export const PATTERNS: Record<'dots' | 'bars' | 'halftone' | 'stripes', Pattern> = {
	dots: { tile: [4, 4], band: 6, empty: (x, y) => q4(x, y) < 1, edge: (x, y, d) => q4(x, y) < STEP[d >> 1] },
	bars: {
		tile: [4, 2], band: 6,
		empty: (x) => md(x, 4) === 0,
		edge: (x, y, d) => q4(x, y) < STEP[d >> 1] || md(x, 4) === 0,
	},
	halftone: { tile: [8, 8], band: 16, empty: (x, y) => q8(x, y) < 6, edge: (x, y, d) => q8(x, y) + 0.5 < 64 * (1 - (d + 0.5) / 16) },
	// The stripes' edge leans with them and steps down along the diagonal: three lines in four,
	// then every other, then one in four, into the empty track's one in eight.
	stripes: { tile: [8, 8], band: 6, slant: true, empty: (x, y) => md(x + y, 8) === 0, edge: (x, y, d) => d4(x + y) < 3 - (d >> 1) },
};
export type SliderPattern = keyof typeof PATTERNS;
const ROWS = 13; // the track's height in cells: odd, and one more than a multiple of four

const places = (v: number) => {
	const s = String(v), i = s.indexOf('.');
	return i < 0 ? 0 : s.length - i - 1;
};
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export interface SliderProps {
	label: string;
	min?: number;
	max?: number;
	step?: number;
	value?: number;
	defaultValue?: number;
	unit?: string;
	unitOne?: string;
	decimals?: number;
	pattern?: SliderPattern;
	ticks?: boolean;
	disabled?: boolean;
	name?: string;
	format?: (v: number) => string;
	onValueChange?: (v: number) => void;
	onValueCommit?: (v: number) => void;
	className?: string;
}

export function Slider({ label, min = 0, max = 100, step = 1, value, defaultValue, unit, unitOne, decimals, pattern = 'dots', ticks, disabled, name, format, onValueChange, onValueCommit, className }: SliderProps) {
	max = Math.max(min, max);
	const snap = useCallback(
		(v: number) => {
			v = clamp(v, min, max);
			if (step > 0) v = clamp(min + Math.round((v - min) / step) * step, min, max);
			return +v.toFixed(Math.max(places(step), places(min)));
		},
		[min, max, step],
	);
	const frac = useCallback((v: number) => (max > min ? (v - min) / (max - min) : 0), [min, max]);
	const [inner, setInner] = useState(() => snap(defaultValue ?? value ?? (min + max) / 2));
	const val = value !== undefined ? snap(value) : inner;
	// The value the handlers work from: set at once by them, and synced after every render.
	const valRef = useRef(val);
	useLayoutEffect(() => {
		valRef.current = val;
	});

	const id = useId();
	const wrap = useRef<HTMLDivElement>(null), track = useRef<HTMLDivElement>(null), fill = useRef<HTMLDivElement>(null), edge = useRef<HTMLCanvasElement>(null), tickC = useRef<HTMLCanvasElement>(null);
	const S = useRef({ pos: frac(val), f: NaN, cols: 0, D: 2, cell: 2, raf: 0, drag: null as null | { id: number; left: number; width: number; from: number } });
	const P = PATTERNS[pattern];

	// Draws the fill at S.pos: a solid run, then the edge, in a canvas only as wide as the edge.
	// The pattern is fixed to the track, not to the edge, so nothing swims as the fill moves.
	const draw = useCallback(
		(force = false) => {
			const s = S.current, c = edge.current, fl = fill.current;
			if (!c || !fl || !s.cols) return;
			const B = P.band, half = P.slant ? (ROWS - 1) / 2 : 0, cols = s.cols;
			const f = Math.round(-B - half + s.pos * (cols + B + 2 * half));
			if (f === s.f && !force) return;
			s.f = f;
			const x0 = f - half, w = B + 2 * half, D = s.D, g = c.getContext('2d')!;
			fl.style.width = x0 >= cols ? '100%' : Math.max(0, x0) * s.cell + 'px';
			c.style.transform = `translateX(${x0 * s.cell}px)`;
			g.clearRect(0, 0, c.width, c.height);
			g.fillStyle = INK;
			for (let y = 0; y < ROWS; y++) {
				const lean = P.slant ? y - half : 0;
				for (let i = 0; i < w; i++) {
					const x = x0 + i, d = x - f + lean;
					let on = d < 0 || (d < B && P.edge(x, y, d));
					if (disabled) on = on && q4(x, y) < 8;
					if (on) g.fillRect(i * D, y * D, D, D);
				}
			}
		},
		[P, disabled],
	);

	// A mark under each step when they're at least 3 cells apart, the current one taller.
	const drawTicks = useCallback(() => {
		const c = tickC.current, s = S.current;
		if (!c || !ticks || !(step > 0) || !s.cols) return;
		const n = Math.round((max - min) / step), cols = s.cols, D = s.D;
		c.hidden = n < 1 || (cols - 1) / n < 3;
		if (c.hidden) return;
		c.width = cols * D;
		c.height = 3 * D;
		c.style.width = cols * s.cell + 'px';
		c.style.height = 3 * s.cell + 'px';
		const g = c.getContext('2d')!, now = Math.round(frac(valRef.current) * n);
		g.fillStyle = INK;
		for (let i = 0; i <= n; i++) g.fillRect(Math.round((i / n) * (cols - 1)) * D, 0, D, (i === now ? 3 : 1) * D);
	}, [ticks, step, max, min, frac]);

	// Cell size from the screen density, and the canvas sized to the edge.
	const layout = useCallback(() => {
		const t = track.current, c = edge.current, s = S.current;
		if (!t || !c) return;
		const dpr = devicePixelRatio || 1, D = Math.max(1, Math.round(2 * dpr)), cell = D / dpr;
		s.D = D;
		s.cell = cell;
		s.cols = Math.floor(t.clientWidth / cell);
		wrap.current!.style.setProperty('--cell', cell + 'px');
		const [tw, th] = P.tile, half = P.slant ? (ROWS - 1) / 2 : 0, w = P.band + 2 * half;
		t.style.setProperty('--tile', `${tw * cell}px ${th * cell}px`);
		c.width = w * D;
		c.height = ROWS * D;
		c.style.width = w * cell + 'px';
		c.style.height = ROWS * cell + 'px';
		c.hidden = false;
		draw(true);
		drawTicks();
	}, [P, draw, drawTicks]);

	useLayoutEffect(() => {
		layout();
		const ro = new ResizeObserver(() => layout());
		ro.observe(track.current!);
		return () => ro.disconnect();
	}, [layout]);
	useEffect(() => () => cancelAnimationFrame(S.current.raf), []);

	// A value from outside (controlled) jumps; one from the pointer or keys is drawn by them.
	useEffect(() => {
		const s = S.current;
		if (!s.drag && !s.raf) {
			s.pos = frac(val);
			draw();
		}
		drawTicks();
	}, [val, frac, draw, drawTicks]);

	const glide = (to: number) => {
		const s = S.current;
		cancelAnimationFrame(s.raf);
		s.raf = 0;
		const from = s.pos;
		if (still() || Math.abs(to - from) < 1e-9) {
			s.pos = to;
			return draw();
		}
		const t0 = performance.now();
		const tick = (now: number) => {
			const k = Math.min(1, (now - t0) / 80);
			s.pos = from + (to - from) * (1 - (1 - k) ** 3);
			draw();
			s.raf = k < 1 ? requestAnimationFrame(tick) : 0;
		};
		s.raf = requestAnimationFrame(tick);
	};
	const set = (v: number) => {
		v = snap(v);
		if (v === valRef.current) return false;
		valRef.current = v;
		if (value === undefined) setInner(v);
		onValueChange?.(v);
		return true;
	};
	const follow = (clientX: number) => {
		const s = S.current, d = s.drag!;
		const k = clamp((clientX - d.left) / d.width, 0, 1);
		s.pos = k;
		set(min + k * (max - min));
		draw();
	};
	const end = (pointerId: number) => {
		const s = S.current, d = s.drag;
		if (!d || d.id !== pointerId) return;
		s.drag = null;
		glide(frac(valRef.current));
		if (valRef.current !== d.from) onValueCommit?.(valRef.current);
	};

	const unitText = (val === 1 && unitOne) || unit;
	const text = format ? format(val) : val.toLocaleString('en-US', { minimumFractionDigits: decimals ?? places(step), maximumFractionDigits: decimals ?? places(step) }) + (unitText ? ' ' + unitText : '');
	const empty = tileURL(P.tile[0], P.tile[1], P.empty);

	return (
		<div className={cn('block font-mono text-[13px] leading-[1.2] text-ink select-none', className)} data-own-focus>
			<div className="mb-2.5 flex items-baseline justify-between gap-4">
				<span id={`${id}-l`}>{label}</span>
				<span className="whitespace-nowrap tabular-nums" aria-hidden>
					{text}
				</span>
			</div>
			<div
				ref={wrap}
				role="slider"
				tabIndex={disabled ? -1 : 0}
				aria-labelledby={`${id}-l`}
				aria-valuemin={min}
				aria-valuemax={max}
				aria-valuenow={val}
				aria-valuetext={text}
				aria-disabled={disabled || undefined}
				className={cn(
					'group relative touch-pan-y outline-none [--cell:2px]',
					disabled ? 'cursor-not-allowed' : 'cursor-pointer',
					// the focus ring: diagonal halves, two cells wide, a cell clear of the track, marching
					"after:pointer-events-none after:absolute after:inset-[calc(-3*var(--cell))] after:p-[calc(2*var(--cell))] after:opacity-0 after:content-['']",
					'after:bg-(image:--ring) after:bg-size-[calc(4*var(--cell))_calc(4*var(--cell))] after:[mask:linear-gradient(#000_0_0)_content-box_exclude,linear-gradient(#000_0_0)] after:[-webkit-mask-composite:xor]',
					// only for the keyboard: a click or drag never lights it, a key press on the slider does
					'[&:focus-visible:not([data-pointer])]:after:animate-[march-cell_0.48s_steps(4)_infinite] [&:focus-visible:not([data-pointer])]:after:opacity-100',
				)}
				style={{ ['--ring' as string]: tileURL(4, 4, (x, y) => (x + y) % 4 < 2) }}
				onBlur={() => delete wrap.current!.dataset.pointer}
				onPointerDown={(e) => {
					if (disabled || e.button > 0) return;
					e.preventDefault();
					wrap.current!.dataset.pointer = '';
					wrap.current!.focus({ preventScroll: true, focusVisible: false } as FocusOptions);
					wrap.current!.setPointerCapture(e.pointerId);
					const r = track.current!.getBoundingClientRect(), s = S.current;
					s.drag = { id: e.pointerId, left: r.left, width: r.width, from: valRef.current };
					cancelAnimationFrame(s.raf);
					s.raf = 0;
					follow(e.clientX);
				}}
				onPointerMove={(e) => {
					if (S.current.drag?.id === e.pointerId) follow(e.clientX);
				}}
				onPointerUp={(e) => end(e.pointerId)}
				onPointerCancel={(e) => end(e.pointerId)}
				onLostPointerCapture={(e) => end(e.pointerId)}
				onKeyDown={(e) => {
					if (disabled) return;
					delete wrap.current!.dataset.pointer;
					const st = step || (max - min) / 100, big = Math.max(st, Math.round((max - min) / 10 / st) * st);
					let v = valRef.current;
					switch (e.key) {
						case 'ArrowRight':
						case 'ArrowUp':
							v += st;
							break;
						case 'ArrowLeft':
						case 'ArrowDown':
							v -= st;
							break;
						case 'PageUp':
							v += big;
							break;
						case 'PageDown':
							v -= big;
							break;
						case 'Home':
							v = min;
							break;
						case 'End':
							v = max;
							break;
						default:
							return;
					}
					e.preventDefault();
					if (set(v)) {
						glide(frac(valRef.current));
						onValueCommit?.(valRef.current);
					}
				}}
			>
				<div
					ref={track}
					className={cn('relative h-[calc(13*var(--cell))] overflow-hidden bg-(image:--empty) bg-size-(--tile) [contain:layout_paint]')}
					style={{ ['--empty' as string]: empty, ['--tile' as string]: `${P.tile[0] * 2}px ${P.tile[1] * 2}px` }}
				>
					<div
						ref={fill}
						className={cn('absolute inset-y-0 left-0', disabled ? 'bg-(image:--half) bg-size-[calc(2*var(--cell))_calc(2*var(--cell))]' : 'bg-ink')}
						style={{ width: `${frac(val) * 100}%`, ['--half' as string]: tileURL(2, 2, (x, y) => (x + y) % 2 === 0) }}
					/>
					<canvas ref={edge} hidden className="absolute top-0 left-0 [image-rendering:pixelated]" />
				</div>
				{ticks && <canvas ref={tickC} className="mt-[calc(2*var(--cell))] block [image-rendering:pixelated]" />}
			</div>
			{name && <input type="hidden" name={name} value={val} />}
		</div>
	);
}
