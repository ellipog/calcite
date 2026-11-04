// The world the guide's pictures show: one tiling heightmap, lit from the north-west, seen from
// the ground (voxel-space, one ray a column, nearest first) or from above. Built once, on first use.

import { diffuse, ordered } from '../dither/bayer';
import { surface } from '../dither/canvas';
import { clamp01, noise, smoothstep } from '../dither/math';

export const N = 512, M = N - 1, HS = 110, WATER = 0.04;

let world: { H: Float32Array; LIT: Float32Array } | null = null;
export function getWorld() {
	if (world) return world;
	const H = new Float32Array(N * N), LIT = new Float32Array(N * N), nz = noise(5, 8);
	for (let y = 0; y < N; y++)
		for (let x = 0; x < N; x++) {
			const v = nz.fbm(x / 64, y / 64, 5, 0.45);
			H[y * N + x] = Math.pow(Math.max(0, v - 0.3) / 0.7, 1.35);
		}
	const L = [-0.5, -0.6, 0.62], l = Math.hypot(...L);
	for (let y = 0; y < N; y++)
		for (let x = 0; x < N; x++) {
			const gx = ((H[y * N + ((x + 2) & M)] - H[y * N + ((x - 2) & M)]) * HS) / 4;
			const gy = ((H[((y + 2) & M) * N + x] - H[((y - 2) & M) * N + x]) * HS) / 4;
			LIT[y * N + x] = clamp01((-gx * L[0] - gy * L[1] + L[2]) / (Math.hypot(gx, gy, 1) * l));
		}
	return (world = { H, LIT });
}

// The heightmap blurred, for contours.
let blurred: Float32Array | null = null;
export function getBlurred() {
	if (blurred) return blurred;
	const { H } = getWorld(), t = new Float32Array(N * N), o = new Float32Array(N * N), r = 3, w = 2 * r + 1;
	for (let y = 0; y < N; y++)
		for (let x = 0; x < N; x++) {
			let s = 0;
			for (let k = -r; k <= r; k++) s += H[y * N + ((x + k) & M)];
			t[y * N + x] = s / w;
		}
	for (let y = 0; y < N; y++)
		for (let x = 0; x < N; x++) {
			let s = 0;
			for (let k = -r; k <= r; k++) s += t[((y + k) & M) * N + x];
			o[y * N + x] = s / w;
		}
	return (blurred = o);
}

export function at(A: Float32Array, x: number, y: number) {
	const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
	const x0 = xi & M, x1 = (xi + 1) & M, y0 = (yi & M) * N, y1 = ((yi + 1) & M) * N;
	return (A[y0 + x0] * (1 - fx) + A[y0 + x1] * fx) * (1 - fy) + (A[y1 + x0] * (1 - fx) + A[y1 + x1] * fx) * fy;
}

export interface Cam {
	x: number;
	y: number;
	yaw: number;
}
export interface ViewOptions {
	horizon?: number;
	K?: number;
	far?: number;
	sky?: number;
	haze?: number;
}
// The world from the ground. The sky is sparse dots, the land darker as it turns from the light,
// snow and distance paper (or haze).
export function view(tone: Float32Array, cols: number, rows: number, cam: Cam, o: ViewOptions = {}) {
	const { H, LIT } = getWorld();
	const hor = rows * (o.horizon ?? 0.3), Kp = o.K ?? Math.max(rows * 0.95, cols * 0.36), far = o.far ?? 700, sky = o.sky ?? 0.1, haze = o.haze ?? 0;
	const camH = Math.max(Math.max(WATER, at(H, cam.x, cam.y)) * HS + 30, HS * 0.74);
	const fx = Math.sin(cam.yaw), fy = -Math.cos(cam.yaw), rx = -fy, ry = fx;
	tone.fill(haze);
	const top = Math.min(rows, Math.floor(hor));
	for (let y = 0; y < top; y++) tone.fill(haze + (sky - haze) * (1 - y / hor) ** 1.6, y * cols, (y + 1) * cols);
	for (let x = 0; x < cols; x++) {
		const u = (x + 0.5 - cols / 2) / Kp, dx = fx + rx * u, dy = fy + ry * u;
		let ybuf = rows, z = 6, dz = 0.5;
		while (z < far && ybuf > 0) {
			const wx = cam.x + dx * z, wy = cam.y + dy * z;
			let h = at(H, wx, wy);
			const water = h < WATER;
			if (water) h = WATER;
			const yi = Math.max(0, Math.ceil(hor + ((camH - h * HS) * Kp) / z));
			if (yi < ybuf) {
				let ink = water ? 0.3 : 0.05 + 0.82 * (1 - at(LIT, wx, wy)) ** 1.35;
				if (!water && h > 0.55) ink *= 0.35;
				const f = (z / far) ** 1.1;
				ink = ink * (1 - f) + haze * f;
				for (let y = yi; y < ybuf; y++) tone[y * cols + x] = ink;
				ybuf = yi;
			}
			z += dz;
			dz += 0.01;
		}
	}
}

export interface Fade {
	l?: number;
	r?: number;
	t?: number;
	b?: number;
}
// Fades a picture to paper at its edges, each side a fraction of its size.
const FADES = new Map<string, Float32Array>();
export function fade(tone: Float32Array, cols: number, rows: number, f?: Fade) {
	if (!f) return;
	const key = `${cols}x${rows}:${f.l || 0},${f.r || 0},${f.t || 0},${f.b || 0}`;
	let m = FADES.get(key);
	if (!m) {
		m = new Float32Array(cols * rows);
		for (let y = 0; y < rows; y++)
			for (let x = 0; x < cols; x++) {
				const u = x / (cols - 1), v = y / (rows - 1);
				let k = 1;
				if (f.l) k *= smoothstep(0, f.l, u);
				if (f.r) k *= smoothstep(0, f.r, 1 - u);
				if (f.t) k *= smoothstep(0, f.t, v);
				if (f.b) k *= smoothstep(0, f.b, 1 - v);
				m[y * cols + x] = k;
			}
		FADES.set(key, m);
	}
	for (let i = 0; i < tone.length; i++) tone[i] *= m[i];
}

// A still of the world into a canvas.
export function still(canvas: HTMLCanvasElement, cam: Cam, o: ViewOptions & { fade?: Fade; diffuse?: boolean } = {}) {
	const s = surface(canvas, 2), tone = new Float32Array(s.cols * s.rows);
	view(tone, s.cols, s.rows, cam, o);
	fade(tone, s.cols, s.rows, o.fade);
	s.bits(o.diffuse ? diffuse(tone, s.cols, s.rows, 'atkinson') : ordered(tone, s.cols, s.rows, 8));
	s.flush();
}

export const CAMS = {
	site: { x: 300, y: 120, yaw: 0.35 },
	social: { x: 90, y: 410, yaw: -0.25 },
	readme: { x: 210, y: 300, yaw: 0.9 },
	poster: { x: 400, y: 60, yaw: -0.6 },
	cmp: { x: 140, y: 230, yaw: 0.2 },
} satisfies Record<string, Cam>;
