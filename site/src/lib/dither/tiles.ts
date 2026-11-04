// Dither tiles as SVG data URLs: one unit a cell, 2 CSS px a cell, crispEdges, so they stay sharp
// at any screen density and work as backgrounds and as masks. scripts/tiles.ts writes the house
// set into src/styles/tiles.css; the slider builds its own at run time in whatever ink it's in.

import { rank } from './bayer';
import { INK, PAPER } from './math';

export type Cell = (x: number, y: number) => boolean;

export function tileSVG(w: number, h: number, on: Cell, fill = INK) {
	let d = '';
	for (let y = 0; y < h; y++)
		for (let x = 0; x < w; ) {
			if (!on(x, y)) {
				x++;
				continue;
			}
			let r = x;
			while (r < w && on(r, y)) r++;
			d += `M${x} ${y}h${r - x}v1h${x - r}z`;
			x = r;
		}
	return `<svg xmlns='http://www.w3.org/2000/svg' width='${2 * w}' height='${2 * h}' viewBox='0 0 ${w} ${h}' shape-rendering='crispEdges'><path fill='${fill}' d='${d}'/></svg>`;
}
export const tileURL = (w: number, h: number, on: Cell, fill = INK) =>
	`url("data:image/svg+xml,${encodeURIComponent(tileSVG(w, h, on, fill)).replace(/%20/g, ' ').replace(/%3D/g, '=').replace(/%2F/g, '/').replace(/%3A/g, ':').replace(/%2C/g, ',')}")`;

const md = (v: number, n: number) => ((v % n) + n) % n;
const R8 = rank(8), R4 = rank(4), R1 = [0, 2, 1, 3];
export const q4 = (x: number, y: number) => R4[md(y, 4) * 4 + md(x, 4)];
export const q8 = (x: number, y: number) => R8[md(y, 8) * 8 + md(x, 8)];
export const d4 = (v: number) => R1[md(v, 4)];

// Cells of an 8×8 level p%, a 4×4 level k/16.
export const level8 = (p: number): Cell => {
	const k = Math.round((p * 64) / 100);
	return (x, y) => q8(x, y) < k;
};
export const level4 = (k: number): Cell => (x, y) => q4(x, y) < k;

// The house set, by custom property name, with the size each is drawn at.
export function houseTiles(): [name: string, url: string][] {
	const out: [string, string][] = [];
	for (const p of [6, 12, 25, 31, 38, 50, 62, 75, 88]) out.push([`t${p}`, tileURL(8, 8, level8(p))]);
	for (const p of [6, 12, 25, 50]) out.push([`tp${p}`, tileURL(8, 8, level8(p), PAPER)]);
	for (const [p, k] of [[6, 1], [12, 2], [25, 4], [50, 8], [75, 12]]) out.push([`q${p}`, tileURL(4, 4, level4(k))]);
	for (const [p, k] of [[25, 4], [50, 8], [75, 12]]) out.push([`qp${p}`, tileURL(4, 4, level4(k), PAPER)]);
	for (const [p, k] of [[25, 1], [50, 2], [75, 3]]) {
		out.push([`u${p}`, tileURL(4, 1, (x) => d4(x) < k)]);
		out.push([`v${p}`, tileURL(1, 4, (_, y) => d4(y) < k)]);
	}
	// A fill's leading edge: two cells each of 75, 50 and 25%, the Bayer 4×4 levels, which all
	// repeat every 2 cells, so the strip lines up with the fill wherever it lands on an even cell.
	const band = (ks: number[]): Cell => (x, y) => q4(x, y) < ks[x >> 1];
	out.push(['edge', tileURL(6, 2, band([12, 8, 4]))]);
	out.push(['edge-p', tileURL(6, 2, band([12, 8, 4]), PAPER)]);
	out.push(['edge-r', tileURL(6, 2, band([4, 8, 12]))]);
	out.push(['shine', tileURL(10, 2, band([4, 8, 12, 8, 4]))]);
	// The focus ring and anything at work: diagonal halves that march one cell a step.
	out.push(['ring', tileURL(4, 4, (x, y) => (x + y) % 4 < 2)]);
	out.push(['ring-p', tileURL(4, 4, (x, y) => (x + y) % 4 < 2, PAPER)]);
	out.push(['check2', tileURL(2, 2, (x, y) => (x + y) % 2 === 0)]);
	const pic = (rows: string[]): Cell => (x, y) => rows[y][x] === '1';
	out.push(['tail', tileURL(5, 3, pic(['11111', '.111.', '..1..']))]);
	out.push(['chevron', tileURL(5, 4, pic(['1...1', '11.11', '.111.', '..1..']))]);
	out.push(['plus', tileURL(5, 5, pic(['..1..', '..1..', '11111', '..1..', '..1..']))]);
	out.push(['minus', tileURL(5, 5, (_, y) => y === 2)]);
	return out;
}
