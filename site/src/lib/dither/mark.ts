// The mark, View: the chunks around a player, as a quadtree. A square splits while the edge of
// the player's view, a circle, crosses it and it's still bigger than the smallest square allowed.
// Each square left is a leaf: in view, on the edge, or out of view. The player stands off the
// middle, at 36% and 37%, so the tree splits unevenly. It's always drawn at its size's own grid:
// half as many cells as CSS pixels, so a dot is 2 px, up to the 64-cell master; bigger sizes
// scale the master by whole numbers. Under 32 px a dot is 1 px, so the shape survives at favicon
// sizes. Pure functions: this runs on the server too.

import { bayerFor, threshold, type Bits } from './bayer';
import { INK } from './math';

export type Zone = 'in' | 'edge' | 'out';
export interface Leaf {
	x: number;
	y: number;
	s: number;
	zone: Zone;
	d?: number;
}
export interface MarkOptions {
	cx?: number;
	cy?: number;
	r?: number;
	div?: number;
	tones?: Record<Zone, number>;
	bayer?: number;
}

export const MARK = { cx: 0.36, cy: 0.37, r: 0.44, div: 14, tones: { in: 1, edge: 0.5, out: 0.12 } as Record<Zone, number> };

const reach = (x: number, y: number, s: number, cx: number, cy: number) => {
	const nx = Math.max(x, Math.min(cx, x + s)), ny = Math.max(y, Math.min(cy, y + s));
	const near = Math.hypot(nx - cx, ny - cy);
	const far = Math.max(Math.hypot(x - cx, y - cy), Math.hypot(x + s - cx, y - cy), Math.hypot(x - cx, y + s - cy), Math.hypot(x + s - cx, y + s - cy));
	return { near, far };
};

// The leaves of a quadtree over the square at (x, y) of side s, split by the circle (cx, cy, r).
export function quadtree(x: number, y: number, s: number, cx: number, cy: number, r: number, minS: number, out: Leaf[] = []): Leaf[] {
	const { near, far } = reach(x, y, s, cx, cy);
	const cross = near < r && far > r;
	if (cross && s / 2 >= minS) {
		const h = s / 2;
		quadtree(x, y, h, cx, cy, r, minS, out);
		quadtree(x + h, y, h, cx, cy, r, minS, out);
		quadtree(x, y + h, h, cx, cy, r, minS, out);
		quadtree(x + h, y + h, h, cx, cy, r, minS, out);
	} else out.push({ x, y, s, zone: far <= r ? 'in' : cross ? 'edge' : 'out' });
	return out;
}

// The mark's leaves on an n-cell grid: a margin of 6%, a one-cell gap on each leaf's top and left.
export function markLeaves(n: number, o: MarkOptions = {}) {
	const p = Math.max(1, Math.round(n * 0.06)), S = n - 2 * p, gap = n >= 32 ? 1 : 0.6;
	const cx = p + (o.cx ?? MARK.cx) * S, cy = p + (o.cy ?? MARK.cy) * S, r = (o.r ?? MARK.r) * S;
	const leaves = quadtree(p - gap / 2, p - gap / 2, S + gap, cx, cy, r, Math.max(2, n / (o.div ?? MARK.div)));
	return { leaves, gap, p, S, cx, cy, r };
}

// The tone map of a set of leaves; tone(leaf, i) gives each one's tone.
export function leafTones(n: number, leaves: Leaf[], gap: number, tone: (l: Leaf, i: number) => number) {
	const t = new Float32Array(n * n);
	leaves.forEach((l, i) => {
		const v = tone(l, i);
		if (!v) return;
		const x0 = Math.max(0, Math.round(l.x + gap)), y0 = Math.max(0, Math.round(l.y + gap));
		const x1 = Math.min(n, Math.round(l.x + l.s)), y1 = Math.min(n, Math.round(l.y + l.s));
		for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) t[y * n + x] = v;
	});
	return t;
}

export function markBits(n: number, o: MarkOptions = {}): Bits {
	const { leaves, gap } = markLeaves(n, o), T = o.tones || MARK.tones, b = o.bayer || bayerFor(n);
	const t = leafTones(n, leaves, gap, (l) => T[l.zone]);
	const bits = new Uint8Array(n * n);
	for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) bits[y * n + x] = t[y * n + x] > threshold(x, y, b) ? 1 : 0;
	return bits;
}

// The quadtree cut off at a depth: what the mark looks like partway through being worked out.
export function treeTo(n: number, maxD: number, o: MarkOptions = {}) {
	const { p, S, gap, cx, cy, r } = markLeaves(n, o), minS = Math.max(2, n / MARK.div), out: Leaf[] = [];
	let deepest = 0;
	const rec = (x: number, y: number, s: number, d: number) => {
		deepest = Math.max(deepest, d);
		const { near, far } = reach(x, y, s, cx, cy);
		const cross = near < r && far > r;
		if (cross && s / 2 >= minS && d < maxD) {
			const h = s / 2;
			rec(x, y, h, d + 1);
			rec(x + h, y, h, d + 1);
			rec(x, y + h, h, d + 1);
			rec(x + h, y + h, h, d + 1);
		} else out.push({ x, y, s, d, zone: far <= r ? 'in' : cross ? 'edge' : 'out' });
	};
	rec(p - gap / 2, p - gap / 2, S + gap, 0);
	return { leaves: out, gap, deepest, cx, cy };
}

export const cellsFor = (css: number) => (css >= 128 ? 64 : css >= 32 ? Math.round(css / 2) : Math.round(css));

// Bits as one SVG path: a rect per run of ink in a row.
export function bitsPath(bits: Bits, n: number) {
	let d = '';
	for (let y = 0; y < n; y++)
		for (let x = 0; x < n; ) {
			if (!bits[y * n + x]) {
				x++;
				continue;
			}
			let e = x;
			while (e < n && bits[y * n + e]) e++;
			d += `M${x} ${y}h${e - x}v1h${x - e}z`;
			x = e;
		}
	return d;
}

export function markSVG(n = 64, { ink = INK, paper = null as string | null, size = 512, ...o }: MarkOptions & { ink?: string; paper?: string | null; size?: number } = {}) {
	const d = bitsPath(markBits(n, o), n);
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n} ${n}" width="${size}" height="${size}" shape-rendering="crispEdges">${paper ? `<rect width="${n}" height="${n}" fill="${paper}"/>` : ''}<path fill="${ink}" d="${d}"/></svg>`;
}
