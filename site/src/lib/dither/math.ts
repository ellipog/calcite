// Numbers the drawings share: easing, a seeded generator, colour contrast and tiling value noise.

export const INK = '#1838D0';
export const PAPER = '#F8F8F5';

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export function smoothstep(a: number, b: number, x: number) {
	x = clamp01((x - a) / (b - a));
	return x * x * (3 - 2 * x);
}

// mulberry32: small, fast, and the same numbers everywhere for the same seed.
export function rng(seed: number) {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) | 0;
		let t = Math.imul(a ^ (a >>> 15), 1 | a);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

export type RGB = [number, number, number];
export function rgb(hex: string): RGB {
	const n = parseInt(hex.replace('#', ''), 16);
	return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
// WCAG contrast between two hex colours.
export function contrast(a: string, b: string) {
	const L = (h: string) => {
		const [r, g, bl] = rgb(h).map((v) => {
			v /= 255;
			return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
		});
		return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
	};
	const [x, y] = [L(a), L(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

export interface Noise {
	(x: number, y: number): number;
	fbm(x: number, y: number, octaves?: number, gain?: number): number;
}
// Value noise on a lattice that repeats every `period` cells (a power of two), with fractal sums.
// Every octave repeats on the same period, so a map sampled over one period tiles.
export function noise(seed = 1, period = 256): Noise {
	const r = rng(seed), m = period - 1, L = new Float32Array(period * period);
	for (let i = 0; i < L.length; i++) L[i] = r();
	const at = (x: number, y: number) => L[(y & m) * period + (x & m)];
	const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
	const n = ((x: number, y: number) => {
		const xi = Math.floor(x), yi = Math.floor(y), fx = fade(x - xi), fy = fade(y - yi);
		return lerp(lerp(at(xi, yi), at(xi + 1, yi), fx), lerp(at(xi, yi + 1), at(xi + 1, yi + 1), fx), fy);
	}) as Noise;
	n.fbm = (x, y, octaves = 5, gain = 0.5) => {
		let s = 0, amp = 1, f = 1, norm = 0;
		for (let o = 0; o < octaves; o++) {
			s += amp * n(x * f + o * 31, y * f + o * 17);
			norm += amp;
			amp *= gain;
			f *= 2;
		}
		return s / norm;
	};
	return n;
}
