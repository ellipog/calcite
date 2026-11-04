// A world of blocks, generated a chunk at a time and drawn as a Minecraft client draws it: a
// forest, as vanilla's are, on rolling grass hills with rivers and lakes through them.
//
// Each column's height comes from a few broad fields: how far inland it is (lakes or land), how
// eroded (gentle ground or taller hills), and a field whose middle line is a river. The broad
// fields are read on a 4-block grid and interpolated, so a chunk costs a few thousand noise reads.
// Oaks and birches grow on the grass, as thick as a forest field says: a trunk of logs and a crown
// of leaves in vanilla's oak shape, two wide layers, a narrower one and a cross on top.
//
// The drawing is voxel-space, one ray a column, nearest first: each block's top lit, its sides
// shaded by the way they face, water flat at sea level, fog toward the edge of the view, and a
// flat layer of clouds. A crown hangs over its trunk, so a column keeps which rows are drawn and
// the ground shows under the leaves.

import { noise } from '../dither/math';
import type { Cam } from './terrain';

/** World units a block, and a chunk of 16 blocks. */
export const B = 2, CHUNK = 16 * B, SEA = 62;

export const hash = (x: number, y: number) => {
	let h = Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263);
	h = Math.imul(h ^ (h >>> 13), 1274126177);
	return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};
const smooth = (a: number, b: number, x: number) => {
	const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
	return t * t * (3 - 2 * t);
};

const enum Mat {
	Water,
	Sand,
	Grass,
	Stone,
	OakLog,
	BirchLog,
	OakLeaves,
	BirchLeaves,
}
// Each material's ink: its top, its sides facing north or south, and its sides facing east or west.
const TONE: [number, number, number][] = [
	[0.34, 0.34, 0.34],
	[0.04, 0.2, 0.3],
	[0.14, 0.42, 0.56],
	[0.36, 0.54, 0.68],
	[0.6, 0.78, 0.9],
	[0.1, 0.16, 0.26],
	[0.5, 0.68, 0.82],
	[0.34, 0.5, 0.64],
];

let NC = noise(3, 256), NE = noise(7, 256), NH = noise(13, 256), NR = noise(17, 256), ND = noise(29, 256), NF = noise(31, 256);
let SALT = 0;

/** A new world: every field drawn from the seed, and the trees placed by it. Forgets every chunk. */
export function reseed(seed: number) {
	const k = (i: number) => (Math.imul(seed ^ (i * 0x9e3779b9), 2654435761) >>> 0) % 2147483647 || 1;
	[NC, NE, NH, NR, ND, NF] = [1, 2, 3, 4, 5, 6].map((i) => noise(k(i), 256));
	SALT = k(7) & 0xffff;
	forget();
}

// The broad fields at a block: continentalness, erosion, river, forest.
const F = 4;
function broad(x: number, y: number, out: Float32Array, o: number) {
	out[o] = NC.fbm(x / 640, y / 640, 4, 0.5);
	out[o + 1] = NE.fbm(x / 260, y / 260, 3, 0.5);
	out[o + 2] = Math.abs(NR.fbm(x / 170, y / 170, 3, 0.5) - 0.5);
	out[o + 3] = NF.fbm(x / 70, y / 70, 2, 0.5);
}

// A column's height, in blocks, from its broad fields.
function height(x: number, y: number, f: Float32Array, o: number) {
	const c = f[o], e = f[o + 1], rv = f[o + 2];
	// lakes where the land dips, the land rising slowly away from them
	let h = c < 0.38 ? SEA - 3 - (0.38 - c) * 60 : c < 0.42 ? SEA - 3 + ((c - 0.38) / 0.04) * 6 : SEA + 3 + (c - 0.42) * 30;
	const land = smooth(0.4, 0.46, c), tall = smooth(0.5, 0.34, e) * land;
	h += (NH.fbm(x / 90, y / 90, 3, 0.5) - 0.5) * (16 + 30 * tall) * land;
	h += tall * 10;
	h += (ND.fbm(x / 22, y / 22, 2, 0.5) - 0.5) * 4 * land;
	// rivers cut down below the sea through the land
	if (c > 0.41) h = SEA - 3 + (h - SEA + 3) * smooth(0.01, 0.028, rv);
	return Math.floor(h);
}

// The chunks drawn, in a window 64 chunks square around the camera, each slot holding the
// chunk at its coordinates modulo 64.
const W = 64, WM = W - 1;
const slotX = new Int32Array(W * W).fill(0x7fffffff), slotZ = new Int32Array(W * W).fill(0x7fffffff);
// each block column: the ground's top, its material and shade, and a crown of leaves over it
const TOP = new Float32Array(W * W * 256), MAT = new Uint8Array(W * W * 256), SHADE = new Float32Array(W * W * 256);
const CTOP = new Float32Array(W * W * 256), CBOT = new Float32Array(W * W * 256), CMAT = new Uint8Array(W * W * 256);

export const isLoaded = (cx: number, cz: number) => {
	const s = ((cz & WM) << 6) | (cx & WM);
	return slotX[s] === cx && slotZ[s] === cz;
};
export function forget() {
	slotX.fill(0x7fffffff);
	slotZ.fill(0x7fffffff);
}

// Generates the chunk at chunk coordinates (cx, cz) into its slot.
const PAD = 2, R = 16 + 2 * PAD, GN = 7, grid = new Float32Array(GN * GN * F), col = new Float32Array(F), hs = new Int16Array(R * R), wet = new Uint8Array(R * R);
export function generate(cx: number, cz: number) {
	const x0 = cx * 16, z0 = cz * 16;
	for (let j = 0; j < GN; j++) for (let i = 0; i < GN; i++) broad(x0 - 4 + i * 4, z0 - 4 + j * 4, grid, (j * GN + i) * F);
	const fieldsAt = (lx: number, lz: number) => {
		const gx = (lx + 4) / 4, gz = (lz + 4) / 4, i = Math.min(GN - 2, Math.max(0, Math.floor(gx))), j = Math.min(GN - 2, Math.max(0, Math.floor(gz))), u = gx - i, v = gz - j;
		for (let k = 0; k < F; k++) {
			const a = grid[(j * GN + i) * F + k], b = grid[(j * GN + i + 1) * F + k], c = grid[((j + 1) * GN + i) * F + k], d = grid[((j + 1) * GN + i + 1) * F + k];
			col[k] = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
		}
		return col;
	};
	// heights for the chunk and two blocks around it, so slopes and crowns can see over its edge
	for (let lz = -PAD; lz < 16 + PAD; lz++)
		for (let lx = -PAD; lx < 16 + PAD; lx++) {
			const r = (lz + PAD) * R + lx + PAD, h = height(x0 + lx, z0 + lz, fieldsAt(lx, lz), 0);
			hs[r] = h;
			wet[r] = h < SEA ? 1 : 0;
		}
	const s = ((cz & WM) << 6) | (cx & WM), base = s * 256;
	for (let lz = 0; lz < 16; lz++)
		for (let lx = 0; lx < 16; lx++) {
			const r = (lz + PAD) * R + lx + PAD, h = hs[r];
			const steep = Math.max(Math.abs(h - hs[r - 1]), Math.abs(h - hs[r + 1]), Math.abs(h - hs[r - R]), Math.abs(h - hs[r + R]));
			// sand where the ground meets the water
			const shore = h <= SEA + 1 && (wet[r - 1] | wet[r + 1] | wet[r - R] | wet[r + R] | wet[r - 2] | wet[r + 2] | wet[r - 2 * R] | wet[r + 2 * R]);
			const i = base + lz * 16 + lx;
			TOP[i] = Math.max(h, SEA) * B;
			MAT[i] = h < SEA ? Mat.Water : shore ? Mat.Sand : steep >= 4 ? Mat.Stone : Mat.Grass;
			SHADE[i] = (hash(x0 + lx, z0 + lz) - 0.5) * 0.08;
			CTOP[i] = 0;
			CBOT[i] = 0;
		}
	// trees: at most one in each 4×4 square of blocks, as thick as the forest field says
	for (let gz = Math.floor((z0 - PAD) / 4); gz <= Math.floor((z0 + 15 + PAD) / 4); gz++)
		for (let gx = Math.floor((x0 - PAD) / 4); gx <= Math.floor((x0 + 15 + PAD) / 4); gx++) {
			const tx = gx * 4 + Math.floor(hash(gx + SALT, gz + 7) * 4), tz = gz * 4 + Math.floor(hash(gx + 3 + SALT, gz) * 4);
			const lx = tx - x0, lz = tz - z0;
			if (lx < -PAD || lx >= 16 + PAD || lz < -PAD || lz >= 16 + PAD) continue;
			const r = (lz + PAD) * R + lx + PAD, h = hs[r];
			if (h <= SEA + 1) continue;
			const slope = Math.max(Math.abs(h - hs[r - 1]), Math.abs(h - hs[r + 1]), Math.abs(h - hs[r - R]), Math.abs(h - hs[r + R]));
			const forest = fieldsAt(Math.min(15, Math.max(0, lx)), Math.min(15, Math.max(0, lz)))[3];
			if (slope >= 4 || hash(tx + SALT, tz + 99) > Math.min(0.92, Math.max(0.12, (forest - 0.36) * 3.2))) continue;
			const birch = hash(tx + 41 + SALT, tz) < 0.22, T = h + 4 + Math.floor(hash(tx, tz + 5) * 2) + (birch ? 1 : 0);
			const leaves = birch ? Mat.BirchLeaves : Mat.OakLeaves;
			// the crown: two 5×5 layers missing some corners, a 3×3 layer, and a cross on top
			for (let dz = -2; dz <= 2; dz++)
				for (let dx = -2; dx <= 2; dx++) {
					const ax = lx + dx, az = lz + dz;
					if (ax < 0 || ax > 15 || az < 0 || az > 15) continue;
					const ring = Math.max(Math.abs(dx), Math.abs(dz));
					if (ring === 2 && Math.abs(dx) === 2 && Math.abs(dz) === 2 && hash(tx + dx * 7, tz + dz * 13) < 0.5) continue;
					const top = ring === 2 ? T : Math.abs(dx) + Math.abs(dz) <= 1 ? T + 2 : T + 1;
					const i = base + az * 16 + ax;
					if (top * B > CTOP[i]) {
						CTOP[i] = top * B;
						CMAT[i] = leaves;
					}
					CBOT[i] = CBOT[i] ? Math.min(CBOT[i], (T - 2) * B) : (T - 2) * B;
				}
			if (lx >= 0 && lx < 16 && lz >= 0 && lz < 16) {
				const i = base + lz * 16 + lx;
				TOP[i] = T * B;
				MAT[i] = birch ? Mat.BirchLog : Mat.OakLog;
			}
		}
	slotX[s] = cx;
	slotZ[s] = cz;
}

/** The height of the ground at a point in blocks, generated or not, for the camera to fly over. */
const one = new Float32Array(F);
export function groundAt(wx: number, wy: number) {
	const x = Math.floor(wx / B), y = Math.floor(wy / B);
	broad(x, y, one, 0);
	return Math.max(SEA, height(x, y, one, 0));
}

let clouds: Uint8Array | null = null;
const CG = 64, CS = 24;
function getClouds() {
	if (clouds) return clouds;
	const c = new Uint8Array(CG * CG), nz = noise(23, 16);
	for (let y = 0; y < CG; y++) for (let x = 0; x < CG; x++) c[y * CG + x] = nz.fbm(x / 6, y / 6, 3) > 0.57 ? 1 : 0;
	return (clouds = c);
}

export interface BlockOptions {
	/** The camera's height, in world units. */
	height: number;
	horizon?: number;
	far?: number;
	sky?: number;
	haze?: number;
	/** How far the clouds have drifted, in world units. */
	drift?: number;
}

let mask = new Uint8Array(0);
export function blockView(tone: Float32Array, cols: number, rows: number, cam: Cam, o: BlockOptions) {
	const C = getClouds();
	const hor = rows * (o.horizon ?? 0.3), Kp = Math.max(rows * 0.95, cols * 0.36), far = o.far ?? 360, sky = o.sky ?? 0.3, haze = o.haze ?? 0, camH = o.height;
	const fx = Math.sin(cam.yaw), fy = -Math.cos(cam.yaw), rx = -fy, ry = fx;
	const drift = o.drift ?? 0, cloudH = 150 * B - camH, cloudFar = far * 4;
	if (mask.length < rows) mask = new Uint8Array(rows);
	tone.fill(haze);
	// the sky, sparse dots thinning toward the horizon, and the clouds in a flat layer over the land
	const skyRows = Math.min(rows, Math.floor(hor));
	for (let y = 0; y < skyRows; y++) {
		const base = haze + (sky - haze) * (1 - y / hor) ** 1.6, t = (cloudH * Kp) / (hor - y);
		const f = Math.min(1, t / cloudFar);
		for (let x = 0; x < cols; x++) {
			let v = base;
			if (cloudH > 0 && f < 1) {
				const u = (x + 0.5 - cols / 2) / Kp, wx = cam.x + (fx + rx * u) * t + drift, wy = cam.y + (fy + ry * u) * t;
				if (C[(Math.floor(wy / CS) & (CG - 1)) * CG + (Math.floor(wx / CS) & (CG - 1))]) v = base * f * f;
			}
			tone[y * cols + x] = v;
		}
	}
	const proj = (h: number, z: number) => Math.ceil(hor + ((camH - h) * Kp) / z);
	for (let x = 0; x < cols; x++) {
		const u = (x + 0.5 - cols / 2) / Kp, dx = fx + rx * u, dy = fy + ry * u;
		let ybuf = rows, z = 3, dz = 0.25, pc = -1, pbx = 0, ph = -1, pct = -1;
		mask.fill(0, 0, rows);
		while (z < far && ybuf > 0) {
			const wx = cam.x + dx * z, wy = cam.y + dy * z, bx = Math.floor(wx / B), by = Math.floor(wy / B);
			const cx = bx >> 4, cz = by >> 4, s = ((cz & WM) << 6) | (cx & WM);
			if (slotX[s] !== cx || slotZ[s] !== cz) {
				// not loaded yet: the sky shows through, as it does in the game
				pc = -1;
				ph = pct = -1;
				z += dz;
				dz += 0.005;
				continue;
			}
			const c = s * 256 + ((by & 15) << 4) + (bx & 15), enter = c !== pc, face = pbx !== bx ? 2 : 1;
			const d = z / far, fog = 0.15 * d + 0.85 * smooth(0.55, 1, d), px = (B * Kp) / z;
			const ex = wx / B - bx, ey = wy / B - by, e = 1.2 / px, seam = px > 11 && (ex < e || ex > 1 - e || ey < e || ey > 1 - e);
			// the crown of leaves over this column, if there is one
			const ct = CTOP[c];
			if (ct > 0) {
				const y0 = Math.max(0, proj(ct, z)), y1 = Math.min(ybuf, proj(CBOT[c], z));
				if (y0 < y1) {
					const T = TONE[CMAT[c]], side = enter && pct < ct;
					let ink = side ? T[face] : T[0] + SHADE[c];
					if (!side && seam) ink += 0.12;
					ink = ink * (1 - fog) + haze * fog;
					for (let y = y0; y < y1; y++)
						if (!mask[y]) {
							mask[y] = 1;
							tone[y * cols + x] = ink;
						}
				}
			}
			// and the ground
			const h = TOP[c], yi = Math.max(0, proj(h, z));
			if (yi < ybuf) {
				const m = MAT[c], T = TONE[m], side = enter && ph < h && m !== Mat.Water;
				let ink = side ? T[face] : T[0] + SHADE[c];
				if (!side && seam) ink += 0.14;
				for (let y = yi; y < ybuf; y++) {
					if (mask[y]) continue;
					let v = ink;
					// the seams between the blocks a side is stacked from
					if (side && px > 7) {
						const hw = (camH - ((y - hor) * z) / Kp) / B;
						if (hw - Math.floor(hw) < 1.2 / px) v += 0.16;
					}
					tone[y * cols + x] = v * (1 - fog) + haze * fog;
				}
				ybuf = yi;
			}
			pc = c;
			pbx = bx;
			ph = h;
			pct = ct;
			z += dz;
			dz += 0.005;
		}
	}
}
