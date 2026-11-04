'use client';

// Charts in one ink. Series differ by line (solid for what the chart is about, dotted for what
// it's compared with), never by colour. A line chart rises from its baseline through the 8×8
// matrix as it comes into view; the area under a line is a gradient in the matrix, dense at the
// baseline and thinning upwards. Hover or focus for values; arrow keys step through them.

import { useEffect, useRef, useState } from 'react';
import { threshold } from '@/lib/dither/bayer';
import { surface, type Surface } from '@/lib/dither/canvas';
import { clamp01 } from '@/lib/dither/math';
import { still } from '@/lib/dither/motion';
import { cn } from '@/lib/cn';

export interface Series {
	pts: readonly (readonly [number, number])[];
	area?: number;
	dotted?: boolean;
	markers?: boolean;
	end: string;
}
export interface LineCfg {
	x: [number, number];
	y: [number, number];
	xTicks: number[];
	yTicks: number[];
	xFmt: (v: number) => string;
	yFmt: (v: number) => string;
	series: Series[];
	endW?: number;
	tip: (x: number, vals: (readonly [number, number])[]) => string;
}

function interp(pts: Series['pts'], x: number) {
	if (x <= pts[0][0]) return pts[0][1];
	for (let i = 1; i < pts.length; i++)
		if (x <= pts[i][0]) {
			const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
			return y0 + ((y1 - y0) * (x - x0)) / (x1 - x0 || 1);
		}
	return pts[pts.length - 1][1];
}

// The shared tooltip: paper in a solid frame, above the point.
function useTip() {
	const [tip, setTip] = useState<{ html: string; x: number; y: number } | null>(null);
	const node = tip && (
		<div
			className="pointer-events-none fixed z-[60] -translate-x-1/2 -translate-y-[calc(100%+14px)] animate-dis-in border border-ink bg-paper px-2.5 py-2 font-mono text-xs leading-normal whitespace-nowrap [&_b]:font-medium"
			style={{ left: tip.x, top: tip.y }}
			role="status"
			dangerouslySetInnerHTML={{ __html: tip.html }}
		/>
	);
	return [node, setTip] as const;
}

export function LineChart({ cfg, label, className }: { cfg: LineCfg; label: string; className?: string }) {
	const plot = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null), xh = useRef<HTMLDivElement>(null);
	const dots = useRef<(HTMLDivElement | null)[]>([]);
	const [labels, setLabels] = useState<{ cls: string; html: string; x: number; y: number }[]>([]);
	const [tipNode, setTip] = useTip();
	const G = useRef<{ L: number; R: number; T: number; B: number; X: (v: number) => number; Y: (v: number) => number; dot: number } | null>(null);

	useEffect(() => {
		const el = plot.current!, canvas = cv.current!;
		let S: Surface, T: Float32Array, p = still() ? 1 : 0, dead = false;
		const ML = 46, MR = cfg.endW ?? 150, MT = 14, MB = 28;
		const layout = () => {
			S = surface(canvas, 2);
			const { cols, rows } = S, dot = S.w / cols;
			const L = Math.round(ML / dot), R = cols - Math.round(MR / dot), Tp = Math.round(MT / dot), B = rows - Math.round(MB / dot);
			const X = (x: number) => L + ((x - cfg.x[0]) / (cfg.x[1] - cfg.x[0])) * (R - L), Y = (y: number) => B - ((y - cfg.y[0]) / (cfg.y[1] - cfg.y[0])) * (B - Tp);
			G.current = { L, R, T: Tp, B, X, Y, dot };
			T = new Float32Array(cols * rows);
			const set = (x: number, y: number, v: number) => {
				x = Math.round(x);
				y = Math.round(y);
				if (x >= 0 && y >= 0 && x < cols && y < rows) T[y * cols + x] = Math.max(T[y * cols + x], v);
			};
			// the area: s.area at the baseline, thinning to a few dots at the top, a cell of paper below the line
			for (const s of cfg.series)
				if (s.area)
					for (let x = L; x <= R; x++) {
						const xv = cfg.x[0] + ((x - L) / (R - L)) * (cfg.x[1] - cfg.x[0]);
						if (xv < s.pts[0][0] || xv > s.pts[s.pts.length - 1][0]) continue;
						for (let y = Math.ceil(Y(interp(s.pts, xv))) + 2; y < B; y++) set(x, y, 0.04 + (s.area - 0.04) * Math.pow(1 - (B - y) / (B - Tp), 1.6));
					}
			// gridlines: ink dots over paper, paper dots where they cross the denser part of an area
			for (const v of cfg.yTicks)
				if (v !== cfg.y[0])
					for (let x = L; x <= R; x += 4) {
						const y = Math.round(Y(v)), i = y * cols + x;
						if (T[i] > 0.2) T[i] = 0;
						else set(x, y, 1);
					}
			for (const s of cfg.series) {
				let along = 0;
				for (let i = 1; i < s.pts.length; i++) {
					const ax = X(s.pts[i - 1][0]), ay = Y(s.pts[i - 1][1]), bx = X(s.pts[i][0]), by = Y(s.pts[i][1]);
					const n = Math.max(1, Math.ceil(Math.max(Math.abs(bx - ax), Math.abs(by - ay))));
					for (let k = 0; k <= n; k++) if (!s.dotted || Math.floor(along + k) % 2 === 0) set(ax + ((bx - ax) * k) / n, ay + ((by - ay) * k) / n, 1);
					along += n;
				}
				for (const [mx, my] of s.markers ? s.pts : [s.pts[s.pts.length - 1]]) {
					const cx = Math.round(X(mx)), cy = Math.round(Y(my));
					for (let dy = -2; dy <= 2; dy++)
						for (let dx = -2; dx <= 2; dx++) {
							const ring = Math.abs(dx) === 2 || Math.abs(dy) === 2;
							if (s.dotted && !ring) T[(cy + dy) * cols + cx + dx] = 0;
							else set(cx + dx, cy + dy, 1);
						}
				}
			}
			for (let x = L; x <= R; x++) set(x, B, 1);
			for (const v of cfg.xTicks) for (let d = 1; d <= 2; d++) set(X(v), B + d, 1);
			const ends = cfg.series.map((s) => Y(s.pts[s.pts.length - 1][1]) * dot);
			if (ends.length === 2 && Math.abs(ends[0] - ends[1]) < 30) {
				const mid = (ends[0] + ends[1]) / 2, up = ends[0] < ends[1] ? -1 : 1;
				ends[0] = mid + up * 15;
				ends[1] = mid - up * 15;
			}
			setLabels([
				...cfg.yTicks.map((v) => ({ cls: 'yl', html: cfg.yFmt(v), x: L * dot, y: Y(v) * dot })),
				...cfg.xTicks.map((v) => ({ cls: 'xl', html: cfg.xFmt(v), x: X(v) * dot, y: (B + 2) * dot })),
				...cfg.series.map((s, i) => ({ cls: 'el', html: s.end, x: (X(s.pts[s.pts.length - 1][0]) + 3) * dot, y: ends[i] })),
			]);
			xh.current!.style.top = Tp * dot + 'px';
			xh.current!.style.height = (B - Tp) * dot + 'px';
			render();
		};
		// The front is a band of the matrix: below it the chart is whole, in it the chart thins out
		// to nothing, and across the plot it carries a light wash of its own, gone once it's passed.
		const render = () => {
			const { cols, rows } = S, g = G.current!, bits = new Uint8Array(cols * rows), band = 28, F = p * (rows + band);
			for (let y = 0; y < rows; y++) {
				const h = rows - y, m = clamp01((F - h) / band);
				if (m <= 0) continue;
				const wash = p < 1 && y >= g.T && y < g.B ? 0.3 * Math.max(0, 1 - Math.abs(F - band / 2 - h) / (band / 2)) : 0;
				for (let x = 0; x < cols; x++) {
					const i = y * cols + x, inPlot = x >= g.L && x <= g.R;
					bits[i] = Math.max(T[i] * m, inPlot ? wash : 0) > threshold(x, y, 8) ? 1 : 0;
				}
			}
			S.bits(bits);
			S.flush();
		};
		document.fonts.ready.then(() => !dead && layout());
		let w = el.getBoundingClientRect().width, rid = 0;
		const ro = new ResizeObserver(() => {
			const nw = el.getBoundingClientRect().width;
			if (nw === w) return;
			w = nw;
			clearTimeout(rid);
			rid = window.setTimeout(layout, 150);
		});
		ro.observe(el);
		// the reveal: a front of the matrix rising from the baseline, 50 ms a step, once
		let tid = 0;
		const io = new IntersectionObserver(
			([e]) => {
				if (!e.isIntersecting || p >= 1) return;
				io.disconnect();
				let k = 0;
				const go = () => {
					p = Math.min(1, ++k / 18);
					if (S) render();
					if (p < 1) tid = window.setTimeout(go, 50);
				};
				go();
			},
			{ threshold: 0.4 },
		);
		io.observe(el);
		return () => {
			dead = true;
			ro.disconnect();
			io.disconnect();
			clearTimeout(tid);
			clearTimeout(rid);
		};
	}, [cfg]);

	// hover, focus and arrow keys
	const base = cfg.series[0].pts;
	const idx = useRef(base.length - 1);
	const show = (i: number, clientX?: number) => {
		const g = G.current;
		if (!g) return;
		idx.current = Math.max(0, Math.min(base.length - 1, i));
		const xv = base[idx.current][0], r = plot.current!.getBoundingClientRect(), vals: (readonly [number, number])[] = [];
		xh.current!.style.display = 'block';
		xh.current!.style.left = g.X(xv) * g.dot + 'px';
		cfg.series.forEach((s, j) => {
			let best = s.pts[0];
			for (const q of s.pts) if (Math.abs(q[0] - xv) < Math.abs(best[0] - xv)) best = q;
			vals.push(best);
			const d = dots.current[j]!;
			d.style.display = 'block';
			d.style.left = g.X(best[0]) * g.dot + 'px';
			d.style.top = g.Y(best[1]) * g.dot + 'px';
		});
		setTip({ html: cfg.tip(xv, vals), x: clientX ?? r.left + g.X(xv) * g.dot, y: r.top + g.T * g.dot });
	};
	const hide = () => {
		xh.current!.style.display = 'none';
		dots.current.forEach((d) => d && (d.style.display = 'none'));
		setTip(null);
	};
	return (
		<div
			ref={plot}
			tabIndex={0}
			aria-label={label}
			className={cn('relative h-[300px] outline-none', className)}
			onPointerMove={(e) => {
				const g = G.current;
				if (!g) return;
				const r = plot.current!.getBoundingClientRect(), xv = cfg.x[0] + (((e.clientX - r.left) / g.dot - g.L) / (g.R - g.L)) * (cfg.x[1] - cfg.x[0]);
				let best = 0;
				base.forEach((q, i) => Math.abs(q[0] - xv) < Math.abs(base[best][0] - xv) && (best = i));
				show(best, e.clientX);
			}}
			onPointerLeave={hide}
			onFocus={() => show(idx.current)}
			onBlur={hide}
			onKeyDown={(e) => {
				if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
				e.preventDefault();
				show(idx.current + (e.key === 'ArrowRight' ? 1 : -1));
			}}
		>
			<canvas ref={cv} className="absolute inset-0 size-full" />
			<div ref={xh} className="pointer-events-none absolute top-0 hidden w-px bg-ink" />
			{cfg.series.map((s, j) => (
				<div
					key={j}
					ref={(d) => {
						dots.current[j] = d;
					}}
					className={cn('pointer-events-none absolute -mt-1 -ml-1 hidden size-2', s.dotted ? 'border-2 border-ink bg-paper' : 'bg-ink')}
				/>
			))}
			{labels.map((l, i) => (
				<span
					key={i}
					className={cn(
						'pointer-events-none absolute font-mono text-[11px] leading-none whitespace-nowrap [&_b]:font-medium',
						l.cls === 'yl' && '-translate-x-full -translate-y-1/2 pr-2',
						l.cls === 'xl' && '-translate-x-1/2 pt-2',
						l.cls === 'el' && '-translate-y-1/2 py-0.5 pl-2',
					)}
					style={{ left: l.x, top: l.y }}
					dangerouslySetInnerHTML={{ __html: l.html }}
				/>
			))}
			{tipNode}
		</div>
	);
}

export interface Bar {
	name: string;
	v: number;
	label: string;
	aria: string;
	tip: string;
	/** The bar the chart is about: solid. The rest are dots. */
	strong?: boolean;
}

// One series of bars, square at both ends, its value at the end. When the values change, the bars
// step to their new lengths, never ease.
export function BarChart({ max, rows, nameW = 78, className }: { max: number; rows: Bar[]; nameW?: number; className?: string }) {
	const [tipNode, setTip] = useTip();
	return (
		<div className={className}>
			{rows.map((r) => (
				<div
					key={r.name}
					tabIndex={0}
					aria-label={r.aria}
					style={{ gridTemplateColumns: `${nameW}px minmax(0,1fr)` }}
					className="grid cursor-default items-center gap-2.5 py-[7px] outline-none"
					onPointerMove={(e) => setTip({ html: r.tip, x: e.clientX, y: e.clientY })}
					onPointerLeave={() => setTip(null)}
					onFocus={(e) => {
						const q = e.currentTarget.getBoundingClientRect();
						setTip({ html: r.tip, x: q.left + q.width / 2, y: q.top });
					}}
					onBlur={() => setTip(null)}
				>
					<span className={cn('font-mono text-[13px] leading-tight', r.strong && 'font-medium')}>{r.name}</span>
					<div className="grid gap-[3px] border-l border-ink py-0.5">
						<div className="flex min-h-4 items-center gap-2">
							<i
								className={cn('h-[22px] flex-none transition-[width] duration-300 ease-[steps(6)] motion-reduce:transition-none', r.strong ? 'bg-ink' : 'tint-38')}
								style={{ width: `calc(${(r.v / max) * 100}% - ${(r.v / max) * 64}px)` }}
							/>
							<b className="bg-paper px-[3px] py-0.5 font-mono text-xs leading-none font-normal whitespace-nowrap">{r.label}</b>
						</div>
					</div>
				</div>
			))}
			{tipNode}
		</div>
	);
}
