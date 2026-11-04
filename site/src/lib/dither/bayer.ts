// Ordered and error-diffusion dithering. A tone is ink coverage: 0 is bare paper, 1 is solid ink.
// Bayer 8×8 is the house pattern; 4×4 and 2×2 are for grids too small to show its 64 levels.

export type Bits = Uint8Array;
export type Tone = Float32Array;

// The matrix as ranks 0..n²-1, row by row.
const RANKS = new Map<number, number[]>();
export function rank(n: number): number[] {
	const m = RANKS.get(n);
	if (m) return m;
	let t = [0], s = 1;
	while (s < n) {
		const w = 2 * s, u = new Array<number>(w * w);
		for (let y = 0; y < s; y++)
			for (let x = 0; x < s; x++) {
				const v = 4 * t[y * s + x];
				u[y * w + x] = v;
				u[y * w + x + s] = v + 2;
				u[(y + s) * w + x] = v + 3;
				u[(y + s) * w + x + s] = v + 1;
			}
		t = u;
		s = w;
	}
	RANKS.set(n, t);
	return t;
}

// The matrix as thresholds in (0, 1): a cell is ink when the tone is above its threshold.
const BAYER = new Map<number, Float32Array>();
export function bayer(n: number): Float32Array {
	let m = BAYER.get(n);
	if (!m) BAYER.set(n, (m = Float32Array.from(rank(n), (v) => (v + 0.5) / (n * n))));
	return m;
}
export const threshold = (x: number, y: number, n = 8) => bayer(n)[(((y % n) + n) % n) * n + (((x % n) + n) % n)];
export const bayerFor = (cells: number) => (cells >= 32 ? 8 : cells >= 12 ? 4 : 2);

export function ordered(tone: ArrayLike<number>, cols: number, rows: number, n = 8): Bits {
	const M = bayer(n), out = new Uint8Array(cols * rows);
	for (let y = 0; y < rows; y++)
		for (let x = 0; x < cols; x++) {
			const i = y * cols + x;
			out[i] = tone[i] > M[(y % n) * n + (x % n)] ? 1 : 0;
		}
	return out;
}

const KERNELS = {
	atkinson: [[1, 0, 1 / 8], [2, 0, 1 / 8], [-1, 1, 1 / 8], [0, 1, 1 / 8], [1, 1, 1 / 8], [0, 2, 1 / 8]],
	floyd: [[1, 0, 7 / 16], [-1, 1, 3 / 16], [0, 1, 5 / 16], [1, 1, 1 / 16]],
} as const;
export function diffuse(tone: ArrayLike<number>, cols: number, rows: number, kind: keyof typeof KERNELS = 'atkinson'): Bits {
	const t = Float32Array.from(tone), out = new Uint8Array(cols * rows), K = KERNELS[kind];
	for (let y = 0; y < rows; y++)
		for (let x = 0; x < cols; x++) {
			const i = y * cols + x, v = t[i], q = v > 0.5 ? 1 : 0, e = v - q;
			out[i] = q;
			for (const [dx, dy, w] of K) {
				const xx = x + dx, yy = y + dy;
				if (xx >= 0 && xx < cols && yy < rows) t[yy * cols + xx] += e * w;
			}
		}
	return out;
}

// A square n×n tone map put through the matrix for its size.
export function toBits(t: ArrayLike<number>, n: number, b = bayerFor(n)): Bits {
	const out = new Uint8Array(n * n);
	for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) out[y * n + x] = t[y * n + x] > threshold(x, y, b) ? 1 : 0;
	return out;
}
