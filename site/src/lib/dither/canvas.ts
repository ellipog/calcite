// Canvases drawn in square cells, each a whole number of screen pixels, so dots stay crisp at
// any zoom and any screen density. Browser only.

import { INK, rgb, type RGB } from './math';
import type { Bits } from './bayer';

export interface Surface {
	cols: number;
	rows: number;
	px: number;
	dpr: number;
	W: number;
	H: number;
	w: number;
	h: number;
	ctx: CanvasRenderingContext2D;
	/** The cells' pixels as little-endian RGBA words, for drawings that write them directly. */
	u32: Uint32Array;
	set(i: number, c: RGB | null): void;
	bits(bits: ArrayLike<number>, ink?: RGB, paper?: RGB | null): void;
	flush(): void;
}

const INK_RGB = rgb(INK);

// A canvas filling its CSS box, drawn in cells of about `dot` CSS pixels.
export function surface(canvas: HTMLCanvasElement, dot = 2): Surface {
	const r = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
	const px = Math.max(1, Math.round(dot * dpr));
	const W = Math.max(1, Math.round(r.width * dpr)), H = Math.max(1, Math.round(r.height * dpr));
	canvas.width = W;
	canvas.height = H;
	const cols = Math.ceil(W / px), rows = Math.ceil(H / px);
	const off = document.createElement('canvas');
	off.width = cols;
	off.height = rows;
	const octx = off.getContext('2d')!, img = octx.createImageData(cols, rows), ctx = canvas.getContext('2d')!;
	const d = img.data;
	const S: Surface = {
		cols, rows, px, dpr, W, H, ctx,
		u32: new Uint32Array(d.buffer, d.byteOffset, cols * rows),
		w: r.width,
		h: r.height,
		set(i, c) {
			const j = i * 4;
			if (!c) {
				d[j + 3] = 0;
				return;
			}
			d[j] = c[0];
			d[j + 1] = c[1];
			d[j + 2] = c[2];
			d[j + 3] = 255;
		},
		bits(bits, ink = INK_RGB, paper = null) {
			for (let i = 0; i < bits.length; i++) S.set(i, bits[i] ? ink : paper);
		},
		flush() {
			octx.putImageData(img, 0, 0);
			ctx.imageSmoothingEnabled = false;
			ctx.clearRect(0, 0, W, H);
			ctx.drawImage(off, 0, 0, cols * px, rows * px);
		},
	};
	return S;
}

// Sizes a canvas for an n×n grid at about css pixels, each cell whole screen pixels, and returns
// a function that paints bits into it.
export function painter(canvas: HTMLCanvasElement, n: number, css: number) {
	const dpr = window.devicePixelRatio || 1, D = Math.max(1, Math.round((css * dpr) / n));
	canvas.width = canvas.height = n * D;
	canvas.style.width = canvas.style.height = (n * D) / dpr + 'px';
	canvas.style.imageRendering = 'pixelated';
	canvas.style.maxWidth = 'none';
	const g = canvas.getContext('2d')!;
	return (bits: Bits, ink = INK, paper: string | null = null) => {
		g.clearRect(0, 0, canvas.width, canvas.height);
		if (paper) {
			g.fillStyle = paper;
			g.fillRect(0, 0, canvas.width, canvas.height);
		}
		g.fillStyle = ink;
		for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (bits[y * n + x]) g.fillRect(x * D, y * D, D, D);
	};
}

// A canvas of exactly w×h pixels, for files.
export function canvasOf(w: number, h: number) {
	const c = document.createElement('canvas');
	c.width = w;
	c.height = h;
	return c;
}

// n×n bits at k pixels a cell, for files and previews.
export function bitsPNG(bits: Bits, n: number, k: number, ink = INK, paper: string | null = null) {
	const c = canvasOf(n * k, n * k), g = c.getContext('2d')!;
	if (paper) {
		g.fillStyle = paper;
		g.fillRect(0, 0, c.width, c.height);
	}
	g.fillStyle = ink;
	for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (bits[y * n + x]) g.fillRect(x * k, y * k, k, k);
	return c;
}
