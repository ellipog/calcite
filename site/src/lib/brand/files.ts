// Browser-side drawing that needs a real canvas: the wordmark as a mask, and the files the guide
// hands out (server icon, mark PNGs, the social card).

import { ordered } from '../dither/bayer';
import { bitsPNG, canvasOf } from '../dither/canvas';
import { markBits } from '../dither/mark';
import { INK, PAPER } from '../dither/math';
import { CAMS, fade, view } from './terrain';

const family = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || 'sans-serif';

// The wordmark as a tone mask, cols×rows, set in Bricolage at 800.
export function wordMask(cols: number, rows: number, { text = 'calcite', fit = 0.6, left = null as number | null } = {}) {
	const c = canvasOf(cols, rows), g = c.getContext('2d', { willReadFrequently: true })!, fam = family('--font-bricolage');
	let fs = rows * 0.9;
	const set = () => {
		g.font = `800 ${fs}px ${fam}`;
		g.letterSpacing = `${-0.05 * fs}px`;
	};
	set();
	let m = g.measureText(text);
	fs = Math.min(fs, (fs * cols * fit) / m.width);
	set();
	m = g.measureText(text);
	const x = left == null ? (cols - m.width) / 2 : cols * left;
	g.fillText(text, x, (rows + m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2);
	const d = g.getImageData(0, 0, cols, rows).data, out = new Float32Array(cols * rows);
	for (let i = 0; i < out.length; i++) out[i] = d[i * 4 + 3] / 255;
	return { mask: out, x0: x, x1: x + m.width };
}

export const markPNG = (n: number, k: number, paper: string | null = null) => bitsPNG(markBits(n), n, k, INK, paper);

export function socialCard() {
	const W = 1280, Hh = 640, c = canvasOf(W, Hh), g = c.getContext('2d')!;
	g.fillStyle = PAPER;
	g.fillRect(0, 0, W, Hh);
	const cols = W / 2, rows = Math.round((Hh / 2) * 0.58), tone = new Float32Array(cols * rows);
	view(tone, cols, rows, CAMS.social, { horizon: 0.18 });
	fade(tone, cols, rows, { t: 0.35 });
	const bits = ordered(tone, cols, rows, 8), y0 = Hh - rows * 2;
	g.fillStyle = INK;
	for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) if (bits[y * cols + x]) g.fillRect(x * 2, y0 + y * 2, 2, 2);
	g.drawImage(markPNG(64, 2), 77, 64);
	g.font = `800 128px ${family('--font-bricolage')}`;
	g.letterSpacing = '-6px';
	g.textBaseline = 'middle';
	g.fillText('calcite', 77 + 128 + 26, 64 + 60);
	g.font = `400 27px ${family('--font-dm-mono')}`;
	g.letterSpacing = '0px';
	g.textAlign = 'right';
	g.textBaseline = 'top';
	g.fillText('a Minecraft server', W - 77, 77);
	g.fillText('written in Calx', W - 77, 77 + 40);
	return c;
}

export function save(name: string, blob: Blob) {
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = name;
	a.click();
	setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export const pngBlob = (c: HTMLCanvasElement) => new Promise<Blob>((r) => c.toBlob((b) => r(b!), 'image/png'));
