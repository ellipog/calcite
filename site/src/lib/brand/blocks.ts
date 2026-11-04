// A world of blocks, generated a chunk at a time and drawn as a Minecraft client draws it: a
// forest, as vanilla's are, on rolling grass hills with rivers and lakes through them.
//
// Each column's height comes from a few broad fields: how far inland it is (lakes or land), how
// eroded (gentle ground or taller hills), and a field whose middle line is a river. The broad
// fields are read on a 4-block grid and interpolated, so a chunk costs a few thousand noise reads.
// Oaks and birches grow on the grass, as thick as a forest field says: a trunk of logs and a crown
// of leaves in vanilla's oak shape, two wide layers, a narrower one and a cross on top.
//
// The drawing is voxel-space, one ray a screen column, nearest first: each block's top lit, its
// sides shaded by the way they face, water flat at sea level, fog toward the edge of the view, and
// a flat layer of clouds. A crown hangs over its trunk, so a column keeps which rows are drawn and
// the ground shows under the leaves. Each pixel is worked out once and written straight into the
// image as ink or nothing: the edges' fade and the Bayer threshold are one table a row.

import { INK, noise, rgb, type Noise } from '../dither/math';
import { bayer } from '../dither/bayer';
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
// Each material's ink, three to a material: its top, its sides facing north or south, and its
// sides facing east or west.
const TONE = Float32Array.from([
	0.34, 0.34, 0.34,
	0.04, 0.2, 0.3,
	0.14, 0.42, 0.56,
	0.36, 0.54, 0.68,
	0.6, 0.78, 0.9,
	0.1, 0.16, 0.26,
	0.5, 0.68, 0.82,
	0.34, 0.5, 0.64,
]);

// The fields' noise, made when the first world is seeded rather than when the module loads.
let NC: Noise, NE: Noise, NH: Noise, NR: Noise, ND: Noise, NF: Noise;
let SALT = 0, seeded = false;

/** A new world: every field drawn from the seed, and the trees placed by it. Forgets every chunk. */
export function reseed(seed: number) {
	const k = (i: number) => (Math.imul(seed ^ (i * 0x9e3779b9), 2654435761) >>> 0) % 2147483647 || 1;
	// (128 lattice points a side repeat every 82,000 blocks on the broadest field, far past any flight)
	[NC, NE, NH, NR, ND, NF] = [1, 2, 3, 4, 5, 6].map((i) => noise(k(i), 128));
	SALT = k(7) & 0xffff;
	seeded = true;
	forget();
}
const ready = () => seeded || reseed(1);

// The broad fields at a block: continentalness, erosion, river, forest, and the hills, all of them
// slow enough to read on a 4-block grid.
const F = 5;
function broad(x: number, y: number, out: Float32Array, o: number) {
	out[o] = NC.fbm(x / 640, y / 640, 4, 0.5);
	out[o + 1] = NE.fbm(x / 260, y / 260, 3, 0.5);
	out[o + 2] = Math.abs(NR.fbm(x / 170, y / 170, 3, 0.5) - 0.5);
	out[o + 3] = NF.fbm(x / 70, y / 70, 2, 0.5);
	out[o + 4] = NH.fbm(x / 90, y / 90, 3, 0.5);
}

// A column's height, in blocks, from its broad fields.
function height(x: number, y: number, f: Float32Array, o: number) {
	const c = f[o], e = f[o + 1], rv = f[o + 2];
	// lakes where the land dips, the land rising slowly away from them
	let h = c < 0.38 ? SEA - 3 - (0.38 - c) * 60 : c < 0.42 ? SEA - 3 + ((c - 0.38) / 0.04) * 6 : SEA + 3 + (c - 0.42) * 30;
	const land = smooth(0.4, 0.46, c), tall = smooth(0.5, 0.34, e) * land;
	h += (f[o + 4] - 0.5) * (16 + 30 * tall) * land;
	h += tall * 10;
	h += (ND.fbm(x / 22, y / 22, 2, 0.5) - 0.5) * 4 * land;
	// rivers cut down below the sea through the land
	if (c > 0.41) h = SEA - 3 + (h - SEA + 3) * smooth(0.01, 0.028, rv);
	return Math.floor(h);
}

// The chunks drawn, in a window 32 chunks square around the camera (the view is 29 across), each
// slot holding the chunk at its coordinates modulo 32. Heights are in blocks, 0 for no crown.
const W = 32, WM = W - 1, WS = 5, SLOTS = W * W;
// Everything a ray reads of a column is one word, so a column is one memory read: the ground's
// top (9 bits), the crown's top (9, 0 for none), the ground's material (3), the crown's (3) and
// the column's shade (7). The crown's bottom, read only when a crown shows, is apart.
let slotX: Int32Array, slotZ: Int32Array, slotMax: Int16Array, CELL: Int32Array, CBOT: Int16Array;
let stored = false;
function store() {
	if (stored) return;
	stored = true;
	slotX = new Int32Array(SLOTS);
	slotZ = new Int32Array(SLOTS);
	slotMax = new Int16Array(SLOTS);
	CELL = new Int32Array(SLOTS * 256);
	CBOT = new Int16Array(SLOTS * 256);
}
// a chunk's columns while it's generated, before they're packed
const TOP = new Int16Array(256), MAT = new Uint8Array(256), SHADE = new Uint8Array(256), CTOP = new Int16Array(256), CB = new Int16Array(256), CMAT = new Uint8Array(256);
const SHADE_K = 0.08 / 126;
const slotOf = (cx: number, cz: number) => ((cz & WM) << WS) | (cx & WM);

export const isLoaded = (cx: number, cz: number) => {
	if (!stored) return false;
	const s = slotOf(cx, cz);
	return slotX[s] === cx && slotZ[s] === cz;
};
export function forget() {
	store();
	slotX.fill(0x7fffffff);
	slotZ.fill(0x7fffffff);
	slotMax.fill(0);
}

// Generates the chunk at chunk coordinates (cx, cz) into its slot.
const PAD = 2, R = 16 + 2 * PAD, GN = 7, grid = new Float32Array(GN * GN * F), col = new Float32Array(F), hs = new Int16Array(R * R), wet = new Uint8Array(R * R);
export function generate(cx: number, cz: number) {
	ready();
	store();
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
	const s = slotOf(cx, cz), base = s * 256;
	let max = 0;
	for (let lz = 0; lz < 16; lz++)
		for (let lx = 0; lx < 16; lx++) {
			const r = (lz + PAD) * R + lx + PAD, h = hs[r];
			const steep = Math.max(Math.abs(h - hs[r - 1]), Math.abs(h - hs[r + 1]), Math.abs(h - hs[r - R]), Math.abs(h - hs[r + R]));
			// sand where the ground meets the water
			const shore = h <= SEA + 1 && (wet[r - 1] | wet[r + 1] | wet[r - R] | wet[r + R] | wet[r - 2] | wet[r + 2] | wet[r - 2 * R] | wet[r + 2 * R]);
			const i = lz * 16 + lx;
			TOP[i] = Math.max(h, SEA);
			MAT[i] = h < SEA ? Mat.Water : shore ? Mat.Sand : steep >= 4 ? Mat.Stone : Mat.Grass;
			SHADE[i] = 64 + Math.round((hash(x0 + lx, z0 + lz) - 0.5) * 126);
			CTOP[i] = 0;
			CB[i] = 0;
			max = Math.max(max, TOP[i]);
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
					const i = az * 16 + ax;
					if (top > CTOP[i]) {
						CTOP[i] = top;
						CMAT[i] = leaves;
					}
					CB[i] = CB[i] ? Math.min(CB[i], T - 2) : T - 2;
					max = Math.max(max, top);
				}
			if (lx >= 0 && lx < 16 && lz >= 0 && lz < 16) {
				const i = lz * 16 + lx;
				TOP[i] = T;
				MAT[i] = birch ? Mat.BirchLog : Mat.OakLog;
			}
		}
	for (let i = 0; i < 256; i++) {
		CELL[base + i] = TOP[i] | (CTOP[i] << 9) | (MAT[i] << 18) | (CMAT[i] << 21) | (SHADE[i] << 24);
		CBOT[base + i] = CB[i];
	}
	slotX[s] = cx;
	slotZ[s] = cz;
	slotMax[s] = max;
}

/** The height of the ground at a point in blocks, generated or not, for the camera to fly over. */
const one = new Float32Array(F);
export function groundAt(wx: number, wy: number) {
	ready();
	const x = Math.floor(wx / B), y = Math.floor(wy / B);
	broad(x, y, one, 0);
	return Math.max(SEA, height(x, y, one, 0));
}

let clouds: Uint8Array | null = null;
const CG = 64, CGM = CG - 1, CS = 24;
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
	/** How far down the view the sky fades in from the page, and up from the bottom the land fades out, as fractions of its height. */
	fadeTop?: number;
	fadeBottom?: number;
}

// The image's ink, as one little-endian RGBA word.
const [IR, IG, IB] = rgb(INK), INK32 = (255 << 24) | (IB << 16) | (IG << 8) | IR;

// Per-frame scratch, kept between frames of the same size.
let size = '', thr = new Float32Array(0), stamp = new Int32Array(0), rowT = new Float32Array(0), rowF = new Float32Array(0), rowSky = new Float32Array(0), mark = 0;
// and the fog by distance: how much of a colour it keeps, and how much haze it adds
const FKEEP = new Float32Array(256), FHZ = new Float32Array(256);
let fogKey = '';

/** Draws the view into a canvas image's pixels, cols × rows of them, as ink or nothing. */
export function frame(px: Uint32Array, cols: number, rows: number, cam: Cam, o: BlockOptions) {
	store();
	const C = getClouds();
	const hor = rows * (o.horizon ?? 0.3), Kp = Math.max(rows * 0.95, cols * 0.36), far = o.far ?? 360, sky = o.sky ?? 0.3, haze = o.haze ?? 0, camH = o.height;
	const fx = Math.sin(cam.yaw), fy = -Math.cos(cam.yaw), rx = -fy, ry = fx;
	const drift = o.drift ?? 0, cloudH = 150 * B - camH, cloudFar = far * 4;
	const fT = o.fadeTop ?? 0, fB = o.fadeBottom ?? 0;

	// Each row's thresholds: Bayer 8×8's over the row's fade, so a tone is ink where it's above
	// them (and never where the fade is nothing). The top's fade is squared, so the sky's first
	// dots come in slowly rather than as a line.
	const key = `${cols}x${rows}:${fT}:${fB}`;
	if (key !== size) {
		size = key;
		const M = bayer(8);
		thr = new Float32Array(rows * 8);
		for (let y = 0; y < rows; y++) {
			const v = y / Math.max(1, rows - 1);
			let k = 1;
			if (fT) k *= smooth(0, fT, v) ** 2;
			if (fB) k *= smooth(0, fB, 1 - v);
			for (let i = 0; i < 8; i++) thr[y * 8 + i] = k > 0 ? M[(y & 7) * 8 + i] / k : Infinity;
		}
		stamp = new Int32Array(rows);
		rowT = new Float32Array(rows);
		rowF = new Float32Array(rows);
		rowSky = new Float32Array(rows);
		mark = 0;
	}
	// the sky's rows: its dots thinning toward the horizon, and where each row meets the clouds
	const skyRows = Math.min(rows, Math.floor(hor));
	for (let y = 0; y < skyRows; y++) {
		rowSky[y] = haze + (sky - haze) * (1 - y / hor) ** 1.6;
		rowT[y] = (cloudH * Kp) / (hor - y);
		rowF[y] = cloudH > 0 ? Math.min(1, rowT[y] / cloudFar) : 1;
	}

	// Nothing taller than the tallest block in the window can show, so a column stops once its
	// drawn edge is above where that would be: at the edge of the view if it's under the camera.
	let top = 0;
	for (let s = 0; s < SLOTS; s++) if (slotX[s] !== 0x7fffffff && slotMax[s] > top) top = slotMax[s];
	const topH = top * B, under = topH < camH;
	const stopFar = Math.ceil(hor + (camH - topH) * (Kp / far));

	// The fog by distance, in a table of 256 steps out to the edge of the view.
	const fkey = `${far}:${haze}`;
	if (fkey !== fogKey) {
		fogKey = fkey;
		const fogFrom = far * 0.55, fogSpan = far * 0.45;
		for (let i = 0; i < 256; i++) {
			const z = ((i + 0.5) / 256) * far, fog = (0.15 * z) / far + 0.85 * smooth(0, fogSpan, z - fogFrom);
			FKEEP[i] = 1 - fog;
			FHZ[i] = haze * fog;
		}
	}
	const fogK = 256 / far, ox = cam.x / B, oy = cam.y / B, Z0 = 3;

	for (let x = 0; x < cols; x++) {
		// the ray, in blocks: each block it crosses is visited once, from the distance it comes in to
		// the distance it goes out, walking the grid (Amanatides and Woo's traversal)
		const u = (x + 0.5 - cols / 2) / Kp, dx = fx + rx * u, dy = fy + ry * u, xb = x & 7;
		if (++mark > 0x3fffffff) {
			stamp.fill(0);
			mark = 1;
		}
		// distances along the ray are in world units; a block is B of them
		const sx = ox + (dx * Z0) / B, sy = oy + (dy * Z0) / B;
		let bx = Math.floor(sx), by = Math.floor(sy);
		const stepX = dx > 0 ? 1 : -1, stepY = dy > 0 ? 1 : -1;
		const tdx = dx !== 0 ? Math.abs(B / dx) : Infinity, tdy = dy !== 0 ? Math.abs(B / dy) : Infinity;
		let tx = dx !== 0 ? Z0 + (dx > 0 ? bx + 1 - sx : sx - bx) * tdx : Infinity, ty = dy !== 0 ? Z0 + (dy > 0 ? by + 1 - sy : sy - by) * tdy : Infinity;
		// (a column stops once nothing in the window could rise over what it has drawn: the
		// ceiling of a value is under ybuf exactly when the value is at most ybuf - 1)
		const stopK = camH - topH;
		let z0 = Z0, iz0 = Kp / Z0, face = 1, ybuf = rows, ph = -1, pct = -1, pcb = 0;
		while (z0 < far && (under ? ybuf > stopFar : stopK * iz0 <= ybuf - 1 - hor)) {
			// where the ray leaves this block, and through which side it'll come into the next
			const xNext = tx < ty, z1 = Math.min(xNext ? tx : ty, far), iz1 = Kp / z1;
			const cx = bx >> 4, cz = by >> 4, s = ((cz & WM) << WS) | (cx & WM);
			if (slotX[s] === cx && slotZ[s] === cz) {
				const c = (s << 8) | ((by & 15) << 4) | (bx & 15), w = CELL[c], h = (w & 511) * B, ct = ((w >>> 9) & 511) * B;
				// the block's top is seen from its near edge to its far one; a side, if it stands over
				// the last block, from its near edge down
				const lim = ybuf - 1 - hor, gUp = (camH - h) * iz1 <= lim, cUp = ct !== 0 && (camH - ct) * iz1 <= lim;
				if (gUp || cUp) {
					const fi = Math.min(255, (z0 * fogK) | 0), keep = FKEEP[fi], hz = FHZ[fi], pxB = B * iz0, sh = (w >>> 24) * SHADE_K - 0.08 * (64 / 126);
					// close up, a line where one block's top meets the next
					const seam = pxB > 11;
					// the crown of leaves over this column, if there is one: its top, and its side where it
					// comes in lower or taller than the crown in front of it
					if (cUp) {
						const cb = CBOT[c] * B, m3 = ((w >>> 21) & 7) * 3, cFar = Math.max(0, Math.ceil(hor + (camH - ct) * iz1)), cNear = Math.max(0, Math.ceil(hor + (camH - ct) * iz0));
						const side = pct < ct || pcb > cb, cBot = Math.min(ybuf, side ? Math.ceil(hor + (camH - cb) * iz0) : cNear + 1);
						const sideInk = TONE[m3 + face] * keep + hz, topInk = (TONE[m3] + sh) * keep + hz, seamInk = topInk + 0.12 * keep, edge = seam ? cNear - 1 : rows;
						for (let y = cFar; y < cBot; y++)
							if (stamp[y] !== mark) {
								stamp[y] = mark;
								const v = side && y >= cNear ? sideInk : y >= edge ? seamInk : topInk;
								px[y * cols + x] = v > thr[(y << 3) | xb] ? INK32 : 0;
							}
					}
					// and the ground
					if (gUp) {
						const gNear = Math.max(0, Math.ceil(hor + (camH - h) * iz0)), gFar = Math.max(0, Math.ceil(hor + (camH - h) * iz1));
						const m = (w >>> 18) & 7, m3 = m * 3, side = ph < h && m !== Mat.Water;
						const topInk = (TONE[m3] + sh) * keep + hz, sideInk = TONE[m3 + face], edge = seam ? gNear - 1 : -1;
						const from = Math.min(gNear, ybuf);
						// the top
						for (let y = gFar; y < from; y++) {
							if (stamp[y] === mark) continue;
							const v = seam && y >= edge ? topInk + 0.14 * keep : topInk;
							px[y * cols + x] = v > thr[(y << 3) | xb] ? INK32 : 0;
						}
						// the side, with the seams between the blocks it's stacked from when it's close
						if (side && gNear < ybuf) {
							if (pxB > 7) {
								const e = 1.2 / pxB, zk = z0 / Kp;
								for (let y = gNear; y < ybuf; y++) {
									if (stamp[y] === mark) continue;
									const hw = (camH - (y - hor) * zk) / B;
									const v = (hw - Math.floor(hw) < e ? sideInk + 0.16 : sideInk) * keep + hz;
									px[y * cols + x] = v > thr[(y << 3) | xb] ? INK32 : 0;
								}
							} else {
								const v = sideInk * keep + hz;
								for (let y = gNear; y < ybuf; y++) if (stamp[y] !== mark) px[y * cols + x] = v > thr[(y << 3) | xb] ? INK32 : 0;
							}
						}
						ybuf = gFar;
					}
				}
				ph = h;
				pct = ct;
				pcb = ct ? CBOT[c] * B : 0;
			} else {
				// not loaded yet: the sky shows through, as it does in the game
				ph = pct = -1;
				pcb = 0;
			}
			// on to the next block
			if (xNext) {
				bx += stepX;
				tx += tdx;
				face = 2;
			} else {
				by += stepY;
				ty += tdy;
				face = 1;
			}
			z0 = z1;
			iz0 = iz1;
		}
		// what the land left: the sky and its clouds above the horizon, haze under it
		for (let y = 0; y < ybuf; y++) {
			if (stamp[y] === mark) continue;
			let v = haze;
			if (y < skyRows) {
				v = rowSky[y];
				const f = rowF[y];
				if (f < 1) {
					const t = rowT[y], wx = cam.x + dx * t + drift, wy = cam.y + dy * t;
					if (C[((Math.floor(wy / CS) & CGM) << 6) | (Math.floor(wx / CS) & CGM)]) v *= f * f;
				}
			}
			px[y * cols + x] = v > thr[(y << 3) | xb] ? INK32 : 0;
		}
	}
}
