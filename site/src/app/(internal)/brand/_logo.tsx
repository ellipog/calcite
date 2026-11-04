'use client';

import { useRef, useState, type ReactNode } from 'react';
import { Mark } from '@/components/mark';
import { Panel, Rules } from '@/components/ui/text';
import { Sub } from '@/components/ui/sub';
import { bayerFor, ordered, rank, toBits } from '@/lib/dither/bayer';
import { canvasOf, painter, surface } from '@/lib/dither/canvas';
import { cellsFor, leafTones, MARK, markBits, markLeaves, treeTo } from '@/lib/dither/mark';
import { clamp01, INK, PAPER, smoothstep } from '@/lib/dither/math';
import { useSized, useSteps } from '@/lib/dither/motion';
import { wordMask } from '@/lib/brand/files';
import { Cap, Section, Wm } from './_parts';

const ZT = MARK.tones;

// A canvas painted in n cells at css pixels by paint(k) each step while it's on screen.
function Stepper({ n, css, ms, frame, last, className }: { n: number; css: number; ms: number; frame: (k: number) => Uint8Array; last: number; className?: string }) {
	const ref = useRef<HTMLCanvasElement>(null), paint = useRef<ReturnType<typeof painter> | null>(null);
	useSized(ref, () => {
		paint.current = painter(ref.current!, n, css);
		paint.current(frame(last));
	});
	useSteps(ref, ms, (k) => paint.current?.(frame(k)), last);
	return <canvas ref={ref} className={className} style={{ width: css, height: css }} />;
}

// The mark, live: the pointer moves the player, a click sends it home; until someone touches it,
// it walks a slow loop round home, in steps.
function Live() {
	const stage = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	const home: [number, number] = [MARK.cx, MARK.cy];
	const [pos, setPos] = useState<[number, number]>(home);
	const [cells, setCells] = useState(128);
	const touched = useRef(false), geo = useRef({ n: 128, paint: null as ReturnType<typeof painter> | null });
	const draw = (p: [number, number]) => geo.current.paint?.(markBits(geo.current.n, { cx: p[0], cy: p[1] }));
	useSized(stage, () => {
		const css = Math.max(200, Math.min(320, stage.current!.getBoundingClientRect().width - 72));
		geo.current.n = Math.round(css / 2);
		setCells(geo.current.n);
		geo.current.paint = painter(cv.current!, geo.current.n, css);
		draw(pos);
	});
	useSteps(stage, 120, (k) => {
		if (touched.current) return;
		const a = (k / 60) * Math.PI * 2;
		const p: [number, number] = k === 0 ? home : [Math.round((home[0] + 0.16 * Math.sin(a)) * 100) / 100, Math.round((home[1] + 0.12 * Math.sin(2 * a)) * 100) / 100];
		setPos(p);
		draw(p);
	});
	const ml = markLeaves(cells, { cx: pos[0], cy: pos[1] }), c = { in: 0, edge: 0, out: 0 };
	ml.leaves.forEach((l) => c[l.zone]++);
	const at = (e: React.PointerEvent): [number, number] => {
		const r = cv.current!.getBoundingClientRect(), n = geo.current.n, p = Math.max(1, Math.round(n * 0.06)), S = n - 2 * p;
		const f = (v: number) => Math.round(clamp01(v) * 100) / 100;
		return [f((((e.clientX - r.left) / r.width) * n - p) / S), f((((e.clientY - r.top) / r.height) * n - p) / S)];
	};
	const move = (p: [number, number]) => {
		touched.current = true;
		setPos(p);
		draw(p);
	};
	const rows: [string, ReactNode][] = [
		['player', `${Math.round(pos[0] * 100)}%, ${Math.round(pos[1] * 100)}%${pos[0] === home[0] && pos[1] === home[1] ? ' · home' : ''}`],
		['squares', ml.leaves.length],
		['in view', c.in],
		['on the edge', c.edge],
		['out of view', c.out],
	];
	return (
		<div className="grid grid-cols-1 gap-5 md:grid-cols-[auto_minmax(0,1fr)]">
			<div ref={stage}>
				<Panel label="Move the player · click to send it home" className="grid place-items-center px-9 pt-12 pb-9">
					<canvas ref={cv} className="cursor-crosshair touch-none" aria-label="The mark, live: move the pointer to move the player" onPointerMove={(e) => move(at(e))} onClick={() => move(home)} />
				</Panel>
			</div>
			<Panel label="Where it moves">
				<p>The printed mark never moves: its player is always at 36%, 37%. On screen it can. In the top bar it watches the pointer, at each section&apos;s number it has walked a little further, and in the hero it&apos;s the window you see the world through.</p>
				<dl className="mt-[22px] grid grid-cols-[auto_1fr] gap-x-[18px] gap-y-1.5 font-mono text-[13px] leading-normal">
					{rows.map(([k, v]) => (
						<div key={k} className="contents">
							<dt className="font-medium">{k}</dt>
							<dd>{v}</dd>
						</div>
					))}
				</dl>
				<Rules className="mt-[22px]" items={['Only live, on-screen copies move. Files and print use the master.', 'It moves the player, nothing else: same circle, same rule, same three densities.']} />
			</Panel>
		</div>
	);
}

// The mark, moving the way it's made.
const n = 64;
const split = (() => {
	if (typeof window === 'undefined') return null;
	const full = treeTo(n, 99).deepest, frames: Uint8Array[] = [];
	for (let d = 0; d <= full; d++) {
		const t = treeTo(n, d);
		frames.push(toBits(leafTones(n, t.leaves, t.gap, (l) => ZT[l.zone]), n));
	}
	const seq: number[] = [];
	frames.forEach((_, i) => seq.push(...Array(i === frames.length - 1 ? 14 : 5).fill(i)));
	return { frames, seq };
})();
const near = (() => {
	const ml = markLeaves(n), start = new Array<number>(ml.leaves.length);
	ml.leaves
		.map((l, i) => [Math.hypot(l.x + l.s / 2 - ml.cx, l.y + l.s / 2 - ml.cy), i] as const)
		.sort((a, b) => a[0] - b[0])
		.forEach(([, i], k) => (start[i] = k));
	return { ml, start, total: ml.leaves.length + 8 + 24 };
})();

function Motion() {
	const figs: [string, string, ReactNode][] = [
		[
			'Worked out',
			'Split by split: each step splits every square the view’s edge still crosses, until they’re as small as they go.',
			<Stepper key="s" n={n} css={128} ms={100} last={(split?.seq.length ?? 1) - 1} frame={(k) => (split ? split.frames[split.seq[k % split.seq.length]] : markBits(n))} />,
		],
		[
			'Nearest first',
			'Squares fill in by distance from the player, the way chunks reach a player: nearest first, each in eight steps.',
			<Stepper key="n" n={n} css={128} ms={50} last={near.ml.leaves.length + 8} frame={(k) => toBits(leafTones(n, near.ml.leaves, near.ml.gap, (l, i) => ZT[l.zone] * clamp01(((k % near.total) - near.start[i]) / 8)), n)} />,
		],
		['Loading', 'The view grows out from the player in sixteen steps, and the tree splits wherever its edge passes.', <Stepper key="l" n={n} css={128} ms={80} last={16} frame={(k) => markBits(n, { r: (MARK.r * Math.min(16, k % 30)) / 16 })} />],
		[
			'Walking',
			'The player walks a loop and comes home. Squares split ahead of it and join up again behind.',
			<Stepper
				key="w"
				n={n}
				css={128}
				ms={90}
				last={0}
				frame={(k) => {
					const a = ((k % 48) / 48) * Math.PI * 2;
					return markBits(n, { cx: MARK.cx + 0.22 * Math.sin(a), cy: MARK.cy + 0.2 * Math.sin(a) * Math.cos(a) * 1.6 });
				}}
			/>,
		],
	];
	return (
		<div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
			{figs.map(([label, cap, c]) => (
				<Panel key={label} label={label} className="grid content-start justify-items-center gap-4 px-5 pt-12 pb-[22px]">
					{c}
					<p className="font-mono text-xs leading-[1.6]">{cap}</p>
				</Panel>
			))}
		</div>
	);
}

// The master's 64 cells, its circle and its player.
function Construction() {
	const box = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
	useSized(box, () => {
		const c = cv.current!, avail = box.current!.getBoundingClientRect().width - 2;
		const dpr = devicePixelRatio || 1, k = Math.max(3, Math.min(7, Math.floor(avail / 64)));
		const D = Math.round(k * dpr), b = markBits(n), ml = markLeaves(n);
		c.width = c.height = D * n + 1;
		c.style.width = c.style.height = (D * n + 1) / dpr + 'px';
		const g = c.getContext('2d')!;
		g.fillStyle = PAPER;
		g.fillRect(0, 0, c.width, c.height);
		g.fillStyle = INK;
		for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (b[y * n + x]) g.fillRect(x * D + 1, y * D + 1, D - 1, D - 1);
		for (let i = 0; i <= n; i += 8)
			for (let j = 0; j <= D * n; j += 3) {
				g.fillRect(i * D, j, 1, 1);
				g.fillRect(j, i * D, 1, 1);
			}
		g.strokeStyle = INK;
		g.lineWidth = Math.max(1, Math.round(dpr));
		g.setLineDash([4 * dpr, 4 * dpr]);
		g.strokeRect(ml.p * D + 0.5, ml.p * D + 0.5, ml.S * D, ml.S * D);
		g.setLineDash([]);
		g.beginPath();
		g.arc(ml.cx * D, ml.cy * D, ml.r * D, 0, Math.PI * 2);
		g.stroke();
		const q = Math.round(2.5 * D);
		g.fillStyle = PAPER;
		g.fillRect(ml.cx * D - q / 2, ml.cy * D - q / 2, q, q);
		g.strokeRect(Math.round(ml.cx * D - q / 2) + 0.5, Math.round(ml.cy * D - q / 2) + 0.5, q, q);
	});
	const key: [string, string, string][] = [
		['tint-100', 'in view', 'Solid. The square is wholly inside the circle.'],
		['tint-50', 'edge', '32 / 64. The circle still crosses it at the smallest size.'],
		['tint-12', 'out', '8 / 64. The view doesn’t reach it.'],
		['', 'gap', 'One cell of paper on each leaf’s top and left.'],
	];
	return (
		<Panel>
			<div className="grid grid-cols-1 items-center gap-8 md:grid-cols-[auto_minmax(0,1fr)]">
				<div ref={box} className="min-w-0 md:w-[450px]">
					<canvas ref={cv} className="[image-rendering:pixelated]" aria-label="The mark on its 64-cell grid, with the view's circle" />
				</div>
				<div>
					<p className="max-w-[50ch]">The master is 64 × 64 cells. Inside a margin of 4, a quadtree splits every square the circle&apos;s edge crosses, until a square would be smaller than 4.6 cells. The circle is the view: its centre is the player, at 36% across and 37% down, its radius 44% of the square. Each leaf is drawn with a one-cell gap.</p>
					<dl className="mt-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 text-[15px]">
						{key.map(([t, k, v]) => (
							<div key={k} className="contents">
								<dt className="flex items-center gap-2.5 font-mono text-xs leading-normal whitespace-nowrap">
									<i className={`size-6 flex-none outline outline-ink ${t}`} />
									{k}
								</dt>
								<dd>{v}</dd>
							</div>
						))}
					</dl>
				</div>
			</div>
		</Panel>
	);
}

function Dissolve() {
	const cv = useRef<HTMLCanvasElement>(null);
	useSized(cv, () => {
		const s = surface(cv.current!, 2), { cols, rows } = s;
		const { mask, x0, x1 } = wordMask(cols, rows, { fit: 0.62, left: 0.05 }), tone = new Float32Array(cols * rows), a = x0 + (x1 - x0) * 0.22;
		for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) tone[y * cols + x] = mask[y * cols + x] * (1 - 0.97 * smoothstep(a, x1, x) ** 0.9);
		s.bits(ordered(tone, cols, rows, 8));
		s.flush();
	});
	return <canvas ref={cv} className="h-[220px] w-full" aria-label="The wordmark dissolving into dots" />;
}

// What not to do, each drawn so you can see why.
const R8 = rank(8);
function patternOf(g: CanvasRenderingContext2D, p: number) {
	const c = canvasOf(8, 8), t = c.getContext('2d')!, k = Math.round((p * 64) / 100);
	t.fillStyle = INK;
	for (let i = 0; i < 64; i++) if (R8[i] < k) t.fillRect(i % 8, i >> 3, 1, 1);
	return g.createPattern(c, 'repeat')!;
}
function LeafCanvas({ fill }: { fill: (g: CanvasRenderingContext2D, x: number, y: number, s: number, z: string) => void }) {
	const ref = useRef<HTMLCanvasElement>(null);
	useSized(ref, () => {
		const c = ref.current!, dpr = devicePixelRatio || 1, css = 96, m = 48, k = css / m, ml = markLeaves(m);
		c.width = c.height = Math.round(css * dpr);
		const g = c.getContext('2d')!;
		g.setTransform(dpr, 0, 0, dpr, 0, 0);
		for (const l of ml.leaves) fill(g, (l.x + ml.gap) * k, (l.y + ml.gap) * k, (l.s - ml.gap) * k, l.zone);
	});
	return <canvas ref={ref} style={{ width: 96, height: 96 }} />;
}
function Circle() {
	const ref = useRef<HTMLCanvasElement>(null);
	useSized(ref, () => {
		const c = ref.current!, g = c.getContext('2d')!;
		c.width = c.height = 192;
		g.fillStyle = INK;
		g.beginPath();
		g.arc(86, 88, 74, 0, Math.PI * 2);
		g.fill();
	});
	return <canvas ref={ref} style={{ width: 96, height: 96 }} />;
}
function Misuse() {
	const items: [string, ReactNode][] = [
		['Stretch or squash it', <Mark key="1" size={96} className="scale-x-150" />],
		['Draw the circle: the view is squares', <Circle key="2" />],
		[
			'Round the corners',
			<LeafCanvas
				key="3"
				fill={(g, x, y, s, z) => {
					g.fillStyle = z === 'in' ? INK : patternOf(g, z === 'edge' ? 50 : 12);
					g.beginPath();
					g.roundRect(x, y, s, s, Math.min(4, s / 3));
					g.fill();
				}}
			/>,
		],
		[
			'Make a tint a colour',
			<LeafCanvas
				key="4"
				fill={(g, x, y, s, z) => {
					g.fillStyle = z === 'in' ? INK : z === 'edge' ? '#8C9CE8' : '#DDE2F8';
					g.fillRect(x, y, s, s);
				}}
			/>,
		],
		['Re-centre the player', <Mark key="5" size={96} cx={0.5} cy={0.5} />],
		[
			'Set it on dots',
			<div key="6" className="px-9 py-3.5 tint-38">
				<Mark size={96} />
			</div>,
		],
	];
	return (
		<div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
			{items.map(([cap, c]) => (
				<Panel key={cap} label="Don’t" className="grid min-h-[210px] content-center justify-items-center gap-3 overflow-hidden pt-10">
					<span className="absolute top-1.5 right-2.5 font-mono text-xl leading-none font-medium" aria-hidden>
						×
					</span>
					{c}
					<Cap className="mt-0">{cap}.</Cap>
				</Panel>
			))}
		</div>
	);
}

export function Logo() {
	const sizes = [256, 128, 64, 48, 32, 24, 16];
	return (
		<Section id="logo" n={2} name="Logo" title="View: the chunks around a player." lead="The mark is a quadtree. A square splits wherever the edge of a player’s view crosses it, so it’s whole where the view is sure and fine where it’s being decided. The player stands off the middle, so the tree splits unevenly: big squares on one side, small ones on the other. The wordmark is Bricolage Grotesque at 800, lowercase, set tight.">
			<Panel label="Primary lockup" className="px-9 py-16">
				<div className="flex items-center gap-[clamp(14px,2.4vw,28px)]">
					<Mark size={128} />
					<Wm className="pb-[0.08em] text-[clamp(56px,9vw,116px)]" />
				</div>
			</Panel>
			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-3">
				<Panel label="Small lockup" className="grid min-h-[220px] place-items-center pt-11">
					<div className="flex items-center gap-4">
						<Mark size={48} />
						<Wm className="text-[40px]" />
					</div>
				</Panel>
				<Panel label="Stacked" className="grid min-h-[220px] place-items-center pt-11">
					<div className="grid justify-items-center gap-3">
						<Mark size={96} />
						<Wm className="text-[44px]" />
					</div>
				</Panel>
				<Panel label="Reversed" inverse className="grid min-h-[220px] place-items-center pt-11">
					<div className="flex items-center gap-4">
						<Mark size={48} />
						<Wm className="text-[40px]" />
					</div>
				</Panel>
			</div>

			<Sub>Live · the mark is worked out, so it can move</Sub>
			<Live />

			<Sub>Motion · how it moves comes from how it’s made</Sub>
			<Motion />

			<Sub>Construction</Sub>
			<Construction />

			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel label="Clear space" className="grid min-h-[220px] place-items-center pt-11">
					<div className="relative inline-flex items-center gap-5 p-8 outline outline-dashed outline-ink -outline-offset-1">
						<span className="absolute top-1.5 left-2 font-mono text-[11px] leading-none">x</span>
						<Mark size={64} />
						<Wm className="text-[52px]" />
					</div>
					<Cap className="text-center">Keep x clear on every side, where x is half the mark&apos;s width.</Cap>
				</Panel>
				<Panel label="Minimum sizes">
					<Rules items={['Mark: 16 px on screen, 6 mm in print.', 'Lockup: 72 px wide, so the wordmark’s counters stay open.', 'Every size is worked out again on its own grid, never shrunk from a bigger one. Under 32 px a dot is 1 px.', 'Scale the master by whole numbers only: 128, 256, 512.']} />
				</Panel>
			</div>

			<Sub>Sizes</Sub>
			<Panel>
				<div className="flex flex-wrap items-end gap-[30px]">
					{sizes.map((s) => {
						const c = cellsFor(s), b = bayerFor(c);
						return (
							<figure key={s} className="m-0 grid justify-items-center gap-2.5 text-center font-mono text-[11px] leading-[1.4]">
								<Mark size={s} />
								<span>
									{s} px
									<br />
									{c} cells · {b}×{b}
								</span>
							</figure>
						);
					})}
				</div>
				<Cap>Each size is its own quadtree: 2 px a dot, 1 px under 32. Bayer 8×8 down to 32 cells, 4×4 below that.</Cap>
			</Panel>

			<Sub>Dissolving, for heroes and covers</Sub>
			<Panel className="overflow-hidden p-0">
				<Dissolve />
			</Panel>

			<Sub>Don&apos;t</Sub>
			<Misuse />
			<Cap>How it was chosen: two rounds of marks, then twelve variations of View. This is variation 7.</Cap>
		</Section>
	);
}
