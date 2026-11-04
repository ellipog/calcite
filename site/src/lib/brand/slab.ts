// A strip of the world, one chunk deep, seen from the front and a little above, with its chunks at
// successive steps of vanilla's generation: empty, structure starts, biomes, noise, surface,
// carvers, features and light. Vanilla generates this way: a chunk is only made full once the
// chunks around it have reached the steps before, so the edge of a world being made looks like
// this strip, from nothing to finished.
//
// What each step does is drawn as vanilla's does it, simplified:
// - structure starts decide where structures go, before any block: a box;
// - biomes are chosen at every fourth block, as vanilla stores them;
// - noise fills the ground with stone, and the sea with water;
// - surface puts grass, dirt and sand on top, and deepslate and bedrock at the bottom (vanilla's
//   surface rules place both, not noise);
// - carvers cut caves;
// - features grow the trees and place the ores;
// - light lights it: deep underground and in caves is dark.
//
// Every chunk can be drawn part way through its step, so each replays it. The drawing is an oblique
// view, a block's front face square, with its top and its right side seen at half depth. Faces are
// drawn back to front as ink or paper, each with a texture of its own, dithered from its own
// corner as a block's texture is. No DOM here: gen-steps.tsx draws it.

import { bayer } from '../dither/bayer';
import { noise } from '../dither/math';
import { hash } from './blocks';

/** Blocks high, blocks deep, and the sea's level. */
export const H = 22, D = 16, SEA = 8;
export const STEPS = 8;
export const enum Step {
	Empty,
	Structures,
	Biomes,
	Noise,
	Surface,
	Carvers,
	Features,
	Light,
}

const enum K {
	Air,
	Stone,
	Deepslate,
	Dirt,
	Grass,
	Sand,
	Gravel,
	Water,
	Bedrock,
	Log,
	Leaves,
	Coal,
	Iron,
	Diamond,
	Bricks,
}

// Each block's ink on its front, its top and its right side, in sixteenths of the 4×4 matrix: lit
// from above, so the top is lightest and the right side darkest. Marks of its own go over it.
const TONE: number[][] = [
	[0, 0, 0],
	[4, 1, 8],
	[9, 5, 12],
	[5, 3, 10],
	[5, 1, 10],
	[2, 1, 5],
	[6, 3, 9],
	[3, 1, 6],
	[10, 8, 13],
	[8, 6, 12],
	[7, 5, 10],
	[4, 1, 8],
	[4, 1, 8],
	[9, 5, 12],
	[15, 4, 13],
].map((r) => r.map((v) => v / 16));

const h3 = (x: number, y: number, z: number) => hash(x + Math.imul(z, 4099), Math.imul(y, 131) + z);
const solid = (k: number) => k !== K.Air && k !== K.Water;

/** A structure's box, in blocks. */
interface Box {
	x0: number;
	y0: number;
	z0: number;
	x1: number;
	y1: number;
	z1: number;
}

export class Slab {
	/** Blocks long, and chunks. */
	readonly L: number;
	readonly C: number;
	/** The blocks after each step, a step to an array: index (z·H + y)·L + x. */
	readonly stage: Uint8Array[] = [];
	/** When, through carvers and through features, each block that step changes changes. */
	private carveAt: Float32Array;
	private featAt: Float32Array;
	/** The ground's height a column, the canopy's lowest leaf a column, and each column's biome. */
	readonly height: Int8Array;
	private canopy: Int8Array;
	private biome: Uint8Array;
	private boxes: Box[] = [];

	/**
	 * front: a tunnel along the front of every chunk, for the strip, where the cut should show one.
	 * open: a chunk levelled and kept clear of trees, in front and in the sky over it, for a structure
	 * built() in it.
	 */
	constructor(chunks: number, seed = 149, front = true, open = -1) {
		const L = (this.L = chunks * 16), C = (this.C = chunks), N = L * D * H;
		this.height = new Int8Array(L * D);
		this.canopy = new Int8Array(L * D).fill(H);
		this.biome = new Uint8Array(L * D);
		this.carveAt = new Float32Array(N);
		this.featAt = new Float32Array(N);
		const n1 = noise(seed * 3 + 1, 256), n2 = noise(seed * 3 + 2, 256), nb = noise(seed * 3 + 3, 256);
		const at = (x: number, y: number, z: number) => (z * H + y) * L + x;

		// the ground's height, from two fields
		for (let z = 0; z < D; z++)
			for (let x = 0; x < L; x++) {
				const h = 10.5 + 13 * (n1.fbm(x / 34, z / 34, 3, 0.5) - 0.5) + 3 * (n2(x / 7, z / 7) - 0.5) + z * 0.1;
				this.height[z * L + x] = Math.max(4, Math.min(14, Math.round(h)));
			}
		// a structure's ground is levelled for it, as the game's terrain adaptation levels a village's:
		// the open chunk flat at about its own height, over the sea, and the ground beside eased to it
		if (open >= 0) {
			const a = open * 16;
			let sum = 0;
			for (let z = 0; z < D; z++) for (let x = a; x < a + 16; x++) sum += this.height[z * L + x];
			const lv = Math.max(SEA + 1, Math.min(H - 8, Math.round(sum / (16 * D))));
			for (let z = 0; z < D; z++)
				for (let x = Math.max(0, a - 5); x < Math.min(L, a + 21); x++) {
					const out = x < a ? a - x : x >= a + 16 ? x - a - 15 : 0, k = 1 - out / 5, i = z * L + x;
					this.height[i] = Math.round(this.height[i] + (lv - this.height[i]) * k * k * (3 - 2 * k));
				}
		}
		// biomes at every fourth block: river where the ground dips under the sea, forest or plains
		for (let qz = 0; qz < D / 4; qz++)
			for (let qx = 0; qx < L / 4; qx++) {
				let low = 0;
				for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) if (this.height[(qz * 4 + z) * L + qx * 4 + x] < SEA) low++;
				const b = low > 6 ? 2 : nb.fbm(qx / 2.5, qz / 2.5, 2, 0.5) > 0.5 ? 1 : 0;
				for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) this.biome[(qz * 4 + z) * L + qx * 4 + x] = b;
			}

		const empty = new Uint8Array(N);
		this.stage[Step.Empty] = this.stage[Step.Structures] = this.stage[Step.Biomes] = empty;

		// noise: stone to the ground's height, water to the sea's
		const noiseS = new Uint8Array(N);
		for (let z = 0; z < D; z++)
			for (let x = 0; x < L; x++) {
				const g = this.height[z * L + x];
				for (let y = 0; y < H; y++) noiseS[at(x, y, z)] = y <= g ? K.Stone : y <= SEA ? K.Water : K.Air;
			}
		this.stage[Step.Noise] = noiseS;

		// surface: grass on dirt above the sea, sand and gravel at and under it; deepslate and bedrock
		const surf = noiseS.slice();
		for (let z = 0; z < D; z++)
			for (let x = 0; x < L; x++) {
				const g = this.height[z * L + x], wet = g < SEA, shore = g <= SEA;
				for (let d = 0; d < 4 && g - d > 0; d++) {
					const y = g - d;
					// under water, gravel in patches on sand
					surf[at(x, y, z)] = wet ? (d === 0 && h3(x >> 2, 7, z >> 2) < 0.45 ? K.Gravel : K.Sand) : shore ? K.Sand : d === 0 ? K.Grass : K.Dirt;
				}
				for (let y = 0; y < 5; y++) {
					const i = at(x, y, z);
					if (surf[i] === K.Stone && (y < 3 || h3(x, y, z) < (5 - y) / 3)) surf[i] = K.Deepslate;
				}
				surf[at(x, 0, z)] = K.Bedrock;
				if (h3(x, 1, z) < 0.5) surf[at(x, 1, z)] = K.Bedrock;
			}
		this.stage[Step.Surface] = surf;

		// carvers: worms of cave. The first in every chunk bores along its front, under the grass, so
		// the cut shows a tunnel opening as it's carved; the rest wander through the slab behind. With
		// no tunnels along the front, as in the footer's cut, most start near the front instead.
		const carved = surf.slice(), r = rngOf(seed * 7 + 5);
		for (let c = 0; c < C; c++) {
			const worms = 2 + (r() < 0.4 ? 1 : 0);
			for (let w = 0; w < worms; w++) {
				const along = front && w === 0;
				let px = c * 16 + (along ? 1 + r() * 2 : r() * 16), py = along ? 6 + r() * 1.2 : 2.5 + r() * 4.5, pz = along ? 0.5 + r() * 0.5 : !front && r() < 0.6 ? r() * 2.5 : 2 + r() * 10;
				let yaw = along ? (r() - 0.5) * 0.3 : (r() < 0.5 ? 0 : Math.PI / 2) + (r() - 0.5) * 0.9, pitch = (r() - 0.5) * 0.3;
				const steps = along ? 13 + Math.floor(r() * 2) : 22 + Math.floor(r() * 18);
				for (let s = 0; s < steps; s++) {
					const t = s / steps, rad = (along ? 1.5 + 0.5 * Math.sin(t * Math.PI) : 1.1 + 0.9 * Math.sin(t * Math.PI)) + r() * 0.3;
					for (let z = Math.floor(pz - rad); z <= pz + rad; z++)
						for (let y = Math.floor(py - rad); y <= py + rad; y++)
							for (let x = Math.floor(px - rad); x <= px + rad; x++) {
								// the along tunnel stays in its chunk, so it's carved when its chunk is
								if (x < 0 || x >= L || z < 0 || z >= D || y < 1 || y >= H || (along && x >> 4 !== c)) continue;
								const dx = x + 0.5 - px, dy = (y + 0.5 - py) / 0.75, dz = z + 0.5 - pz;
								if (dx * dx + dy * dy + dz * dz > rad * rad) continue;
								const i = at(x, y, z), k = carved[i];
								if (!solid(k) || k === K.Bedrock || y > this.height[z * L + x] - 2) continue;
								carved[i] = K.Air;
								this.carveAt[i] = t * 0.92 + r() * 0.08;
							}
					px += Math.cos(yaw) * Math.cos(pitch);
					pz += Math.sin(yaw) * Math.cos(pitch);
					py += Math.sin(pitch) * 0.8;
					yaw += (r() - 0.5) * (along ? 0.3 : 0.5);
					pitch = Math.max(-0.45, Math.min(0.45, pitch + (r() - 0.5) * 0.3));
					if (py < 2) pitch = Math.abs(pitch);
					if (py > 8) pitch = -Math.abs(pitch);
					if (along) {
						pz = Math.max(0.3, Math.min(1.2, pz));
						py = Math.max(5.5, Math.min(7.5, py));
						yaw = Math.max(-0.4, Math.min(0.4, yaw));
					}
				}
			}
		}
		this.stage[Step.Carvers] = carved;

		// features: ores in blobs through the stone, and a lump of each set in the front so the cut
		// shows them; then oaks on the grass, two near the front of every chunk and more behind, as
		// thick as the biome has them. The ores come first, then each oak grows, logs and then leaves.
		const feat = carved.slice();
		for (let z = 0; z < D; z++)
			for (let y = 1; y < 12; y++)
				for (let x = 0; x < L; x++) {
					const i = at(x, y, z), k = feat[i], blob = h3(x >> 1, y >> 1, (z >> 1) + 99);
					if (k === K.Stone && y >= 4 && blob < 0.07) feat[i] = K.Coal;
					else if (k === K.Stone && y <= 8 && blob > 0.955) feat[i] = K.Iron;
					else if (k === K.Deepslate && blob > 0.93) feat[i] = K.Diamond;
					else continue;
					this.featAt[i] = h3(x, y, z) * 0.45;
				}
		for (let c = 0; c < C; c++)
			for (let k = 0; k < 3; k++) {
				const kind = [K.Coal, K.Iron, K.Diamond][k], host = kind === K.Diamond ? K.Deepslate : K.Stone, u = hash(c, k + 30);
				const bx = c * 16 + 1 + k * 5 + Math.floor(hash(c * 3 + k, 17) * 3), by = kind === K.Diamond ? 2 + Math.floor(u * 2) : kind === K.Iron ? 4 + Math.floor(u * 3) : 5 + Math.floor(u * 4);
				for (let dy = 0; dy < 2; dy++)
					for (let dx = 0; dx < 2; dx++) {
						const x = bx + dx, y = by + dy, i = at(x, y, 0);
						if (x >= L || feat[i] !== host || (dx + dy > 0 && hash(x * 7 + y, c + k) < 0.3)) continue;
						feat[i] = kind;
						this.featAt[i] = 0.04 + k * 0.12 + (dx + dy) * 0.03;
					}
			}
		const spots: [number, number][] = [];
		// the front two take the nearest grass to where they'd go, a little further back if need be
		const grass = (x: number, z: number) => feat[at(x, this.height[z * L + x], z)] === K.Grass && this.height[z * L + x] + 7 < H;
		for (let c = 0; c < C; c++)
			for (let k = 0; k < (c === open ? 0 : front || hash(c, 71) < 0.5 ? 2 : 1); k++) {
				// evenly in the strip, so each chunk shows two; anywhere in a cut
				const x0 = c * 16 + (front ? 3 + k * 8 + Math.floor(hash(c, k + 50) * 3) : 1 + Math.floor(hash(c, k + 70) * 14)), z0 = 2 + Math.floor(hash(c + 9, k) * 2);
				find: for (let dz = 0; dz < 5; dz++)
					for (const dx of [0, 1, -1, 2, -2]) {
						const x = x0 + dx, z = z0 + dz;
						if (x < L && z < D && grass(x, z)) {
							spots.push([x, z]);
							break find;
						}
					}
			}
		for (let gz = 0; gz < D; gz += 5)
			for (let gx = 0; gx < L; gx += 5) {
				const x = gx + Math.floor(hash(gx, gz + 7) * 5), z = gz + Math.floor(hash(gx + 3, gz) * 5);
				const p = x < L && z < D ? (this.biome[z * L + x] === 1 ? 0.3 : this.biome[z * L + x] === 0 ? 0.06 : 0) : 0;
				if (hash(x + 11, z + 5) < p) spots.push([x, z]);
			}
		for (const [x, z] of spots) {
			// none in front of the open chunk's structure, or behind it, where it would show over it
			if (x >= L || z >= D || (open >= 0 && x + (z >> 1) >= open * 16 - 3 && x + (z >> 1) < open * 16 + 19)) continue;
			const g = this.height[z * L + x], top = g + 4 + (hash(x, z) < 0.5 ? 1 : 0);
			if (feat[at(x, g, z)] !== K.Grass || top + 1 >= H) continue;
			const tz = hash(x, z + 1);
			for (let y = g + 1; y <= top; y++) {
				feat[at(x, y, z)] = K.Log;
				this.featAt[at(x, y, z)] = 0.4 + 0.06 * (y - g) + tz * 0.05;
			}
			for (let y = top - 2; y <= top + 1; y++) {
				const w = y >= top ? 1 : 2;
				for (let dz = -w; dz <= w; dz++)
					for (let dx = -w; dx <= w; dx++) {
						const lx = x + dx, lz = z + dz, corner = Math.abs(dx) === w && Math.abs(dz) === w;
						if (lx < 0 || lx >= L || lz < 0 || lz >= D) continue;
						if (corner && (y === top + 1 || hash(lx * 3 + y, lz) < 0.5)) continue;
						const i = at(lx, y, lz);
						if (feat[i] !== K.Air) continue;
						feat[i] = K.Leaves;
						this.featAt[i] = 0.68 + 0.08 * (y - top + 2) + h3(lx, y, lz) * 0.08;
						this.canopy[lz * L + lx] = Math.min(this.canopy[lz * L + lx], y);
					}
			}
		}
		this.stage[Step.Features] = this.stage[Step.Light] = feat;

		// a structure's start in every chunk that will hold one: a house's box, say
		for (let c = 0; c < C; c++) {
			const x0 = c * 16 + 3 + Math.floor(r() * 3), z0 = 3 + Math.floor(r() * 4), w = 7 + Math.floor(r() * 3), d = 5 + Math.floor(r() * 3);
			let g = 0;
			for (let z = z0; z < z0 + d; z++) for (let x = x0; x < x0 + w; x++) g = Math.max(g, this.height[z * L + Math.min(L - 1, x)]);
			this.boxes.push({ x0, y0: g + 1, z0, x1: x0 + w, y1: g + 6, z1: z0 + d });
		}
	}

	/** The block at x, y, z when its chunk is p of the way through step k. */
	block(x: number, y: number, z: number, k: number, p: number) {
		const i = (z * H + y) * this.L + x, now = this.stage[k][i];
		if (p >= 1 || k < Step.Noise || k === Step.Light) return now;
		const was = this.stage[k - 1][i];
		if (was === now) return now;
		return p >= this.when(x, y, z, k, i) ? now : was;
	}

	// When, through step k, the block at i changes.
	private when(x: number, y: number, z: number, k: number, i: number) {
		if (k === Step.Noise) return Math.min(0.97, (y / 15) * 0.85 + h3(x, y, z) * 0.12);
		if (k === Step.Surface) return Math.min(0.97, (((x & 15) + z * 0.6) / 25.6) * 0.86 + h3(x, y + 40, z) * 0.1);
		if (k === Step.Carvers) return this.carveAt[i];
		return this.featAt[i];
	}

	/** How dark light leaves a face: deeper under the ground and in caves, darker; under leaves, shaded. */
	shade(x: number, y: number, z: number, face: 0 | 1 | 2) {
		const g = this.height[z * this.L + x];
		if (face === 1) return this.canopy[z * this.L + x] > y ? 0.12 : 0;
		let s = y < g ? Math.min(0.16, (g - y) * 0.02) : 0;
		const nx = face === 2 ? x + 1 : x, nz = face === 0 ? z - 1 : z;
		if (nz >= 0 && nx < this.L && y < g && this.stage[Step.Carvers][(nz * H + y) * this.L + nx] === K.Air) s += 0.12;
		return s;
	}

	/** The structure's box in chunk c. */
	box(c: number) {
		return this.boxes[c];
	}

	/**
	 * Builds rows of text into chunk c as its structure, during features: '#' is a block of bricks
	 * and the first row is the top. It stands a block back from the front, centred, on a plinth
	 * up out of the ground or the sea, and goes up a course at a time. Its start's box is set to
	 * fit, so the first step shows where it will be.
	 */
	build(c: number, rows: string[]) {
		const L = this.L, w = rows[0].length, n = rows.length, x0 = c * 16 + ((16 - w) >> 1), z0 = 1, z1 = 2;
		const feat = this.stage[Step.Features], at = (x: number, y: number, z: number) => (z * H + y) * L + x;
		let g = SEA, low = H;
		for (let z = z0; z < z1; z++)
			for (let x = x0; x < x0 + w; x++) {
				g = Math.max(g, this.height[z * L + x]);
				low = Math.min(low, this.height[z * L + x] + 1);
			}
		const top = g + n;
		if (top >= H) return;
		const put = (x: number, y: number, z: number) => {
			const i = at(x, y, z);
			feat[i] = K.Bricks;
			this.featAt[i] = 0.3 + (0.62 * (y - low)) / (top - low + 1) + (x - x0) * 0.003;
		};
		for (let z = z0; z < z1; z++)
			for (let x = x0; x < x0 + w; x++) {
				for (let y = this.height[z * L + x] + 1; y <= g; y++) put(x, y, z);
				for (let r = 0; r < n; r++) if (rows[r][x - x0] === '#') put(x, top - r, z);
			}
		this.boxes[c] = { x0, y0: low, z0, x1: x0 + w, y1: top + 1, z1 };
	}

	/** The biome a column has: 0 plains, 1 forest, 2 river. */
	biomeAt(x: number, z: number) {
		return this.biome[z * this.L + x];
	}

	/** The finished block at x, y, z; and mining it, which leaves air. */
	at(x: number, y: number, z: number) {
		return x < 0 || y < 0 || z < 0 || x >= this.L || y >= H || z >= D ? K.Air : this.stage[Step.Light][(z * H + y) * this.L + x];
	}
	mine(x: number, y: number, z: number) {
		this.stage[Step.Light][(z * H + y) * this.L + x] = K.Air;
	}
}

/** Seconds a block takes to mine by hand, roughly as the game's are; Infinity if it can't be. */
export function mineTime(id: number) {
	switch (id) {
		case K.Air:
		case K.Water:
		case K.Bedrock:
			return Infinity;
		case K.Leaves:
			return 0.3;
		case K.Dirt:
		case K.Grass:
		case K.Sand:
		case K.Gravel:
			return 0.75;
		case K.Log:
			return 1.5;
		case K.Deepslate:
		case K.Diamond:
			return 2.6;
		default:
			return 1.8;
	}
}

/** Whether light passes a block, so what's behind it shows: air, and water, which is drawn on its own. */
export const clear = (id: number) => id === K.Air || id === K.Water;

/**
 * Cracks for an n-cell block mined in stages, as cells (y·n + x), each stage adding to the last:
 * walked out from the middle by a few tips that wander and sometimes fork.
 */
export function cracks(n: number, stages: number) {
	const out: number[][] = [];
	const seen = new Set<number>(), tips: [number, number][] = [
		[(n >> 1) - 1, n >> 1],
		[n >> 1, (n >> 1) - 1],
	];
	let k = 1;
	const r = () => ((k = Math.imul(k ^ (k >>> 15), 2246822507) + 0x9e3779b9), (k >>> 0) / 4294967296);
	for (let s = 0; s < stages; s++) {
		for (let step = 0; step < Math.ceil(((3 + s) * n) / 16); step++) {
			for (const tip of tips) {
				const a = Math.floor(r() * 8), dx = [1, 1, 0, -1, -1, -1, 0, 1][a], dy = [0, 1, 1, 1, 0, -1, -1, -1][a];
				tip[0] = Math.min(n - 2, Math.max(1, tip[0] + dx));
				tip[1] = Math.min(n - 2, Math.max(1, tip[1] + dy));
				seen.add(tip[1] * n + tip[0]);
			}
			if (r() < 0.25 && tips.length < 6) tips.push([...tips[Math.floor(r() * tips.length)]] as [number, number]);
		}
		out.push([...seen]);
	}
	return out;
}

function rngOf(seed: number) {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) | 0;
		let t = Math.imul(a ^ (a >>> 15), 1 | a);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** Where and how big the strip is drawn, in cells. */
export interface View {
	cols: number;
	rows: number;
	/** A block's size, and the cell of the floor's front-left corner, world x = 0. */
	s: number;
	ox: number;
	oy: number;
	/**
	 * A cut through the ground seen square on, as the footer's: fronts only, the first few blocks deep
	 * and the far walls of caves behind them, with no chunk borders; what's further back is lighter
	 * in the open and darker underground.
	 */
	cut?: { deep: number };
	/** A chunk to draw at full strength; the rest are drawn quieter, under half, with dotted edges. */
	focus?: number;
}

const M4 = bayer(4);
// the planes and nearness of each cell, kept between drawings of the same size
const scratch = new Map<number, { key: Int32Array; ord: Int32Array; quiet: Uint8Array }>();
// each world's blocks as a drawing shows them, worked out once a drawing
const shown = new WeakMap<Slab, Uint8Array>();

/**
 * Draws the strip as ink or paper into bits, each chunk c at step steps[c], prog[c] of the way
 * through it. Faces are toned by the 4×4 matrix on the screen's grid, and outlined where the ground
 * steps to another plane or another block: so a terrace, a tree, an ore or a cave's mouth is a shape
 * with an edge, as blocks are, and not a field of dots.
 */
export function drawSlab(w: Slab, v: View, bits: Uint8Array, steps: ArrayLike<number>, prog: ArrayLike<number>) {
	const { cols, rows, s, ox, oy, cut } = v, d = cut ? 0 : Math.max(1, s >> 1), L = w.L, N = cols * rows;
	let sc = scratch.get(N);
	if (!sc) {
		if (scratch.size > 2) scratch.clear();
		scratch.set(N, (sc = { key: new Int32Array(N), ord: new Int32Array(N), quiet: new Uint8Array(N) }));
	}
	const { key, ord, quiet } = sc, focus = v.focus ?? -1;
	bits.fill(0);
	key.fill(0);
	quiet.fill(0);
	ord.fill(0);
	const set = (cx: number, cy: number, on: number) => {
		if (cx >= 0 && cy >= 0 && cx < cols && cy < rows) bits[cy * cols + cx] = on;
	};
	// a cell of tone t: 1 or more ink, 0 or less paper, between them the matrix decides
	const tone = (cx: number, cy: number, t: number) => set(cx, cy, t > M4[(cy & 3) * 4 + (cx & 3)] ? 1 : 0);
	// a line of cells; a dotted one skips every other cell
	const line = (x0: number, y0: number, x1: number, y1: number, dotted: boolean, upTo = 1) => {
		const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1), m = Math.floor(n * upTo);
		for (let i = 0; i <= m; i++) if (!dotted || i % 2 === 0) set(Math.round(x0 + ((x1 - x0) * i) / n), Math.round(y0 + ((y1 - y0) * i) / n), 1);
	};
	// a point in blocks to its cell
	const px = (x: number, z: number) => ox + x * s + z * d, py = (y: number, z: number) => oy - y * s - z * d;
	const edge = (a: number[], b: number[], dotted: boolean, upTo = 1) => line(px(a[0], a[2]), py(a[1], a[2]), px(b[0], b[2]), py(b[1], b[2]), dotted, upTo);

	// the chunks with no blocks yet: their floor's outline, their biomes and their structures' boxes
	for (let c = 0; c < w.C; c++) {
		const k = steps[c], p = prog[c], x0 = c * 16, x1 = x0 + 16;
		if (k > Step.Biomes) continue;
		if (k === Step.Biomes)
			for (let z = D - 1; z >= 0; z--)
				for (let x = x0; x < x1; x++) {
					// a biome every fourth block, each quart arriving in its turn, edged where it ends
					const q = ((x >> 2) & 3) + ((z >> 2) << 2);
					if (p < 1 && hash(q + c * 16, 3) * 0.9 >= p) continue;
					const bi = w.biomeAt(x, z), t = bi === 2 ? 0.69 : bi === 1 ? 0.38 : 0.13;
					for (let a = 0; a < d; a++)
						for (let b = 0; b < s; b++) {
							const rim = ((x & 3) === 3 && b === s - 1) || ((z & 3) === 0 && a === d - 1);
							const cx = px(x, z) + b + (d - a), cy = py(0, z) - d + a;
							tone(cx, cy, rim ? 1 : t);
						}
				}
		const floor = [
			[x0, 0, 0],
			[x1, 0, 0],
			[x1, 0, D],
			[x0, 0, D],
		];
		for (let i = 0; i < 4; i++) edge(floor[i], floor[(i + 1) % 4], true);
		if (k === Step.Structures) {
			const b = w.box(c), up = p >= 1 ? 1 : p;
			const cs = [
				[b.x0, b.y0, b.z0], [b.x1, b.y0, b.z0], [b.x1, b.y0, b.z1], [b.x0, b.y0, b.z1],
				[b.x0, b.y1, b.z0], [b.x1, b.y1, b.z0], [b.x1, b.y1, b.z1], [b.x0, b.y1, b.z1],
			];
			const es = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
			es.forEach(([a, bb], i) => {
				const f = Math.max(0, Math.min(1, up * es.length - i));
				if (f > 0) edge(cs[a], cs[bb], false, f);
			});
		}
	}

	// the blocks, back to front, bottom to top, left to right; each cell keeps which plane of which
	// block it shows, and how near, for the outlines
	const stepOf = (x: number) => steps[x >> 4], progOf = (x: number) => prog[x >> 4];
	const opaque = (b: number) => solid(b) && b !== K.Leaves;
	// a face shows unless the next block over hides it: a solid one, or more of the same, so water
	// and leaves show only their outsides; leaves have holes, so they hide nothing else
	const hides = (n: number, id: number) => opaque(n) || n === id;
	// the blocks as they are now, once each, so a block's neighbours are a lookup; a chunk with no
	// blocks yet is air
	let cur = shown.get(w);
	if (!cur) shown.set(w, (cur = new Uint8Array(L * H * D)));
	for (let c = 0; c < w.C; c++) {
		const k = steps[c], p = prog[c], now = w.stage[Math.max(k, Step.Empty)];
		for (let z = 0; z < D; z++)
			for (let y = 0; y < H; y++) {
				const row = (z * H + y) * L;
				for (let x = c * 16; x < c * 16 + 16; x++) cur[row + x] = k < Step.Noise ? K.Air : p >= 1 ? now[row + x] : w.block(x, y, z, k, p);
			}
	}
	// nearest first, each face filling only the cells nothing nearer has, so a cell hidden behind
	// another is never worked out; it comes to what drawing back to front would, for less
	const HL = H * L;
	let nearness = 1 << 30;
	for (let z = 0; z < D; z++)
		for (let y = H - 1; y >= 0; y--)
			for (let x = L - 1; x >= 0; x--) {
				const i = (z * H + y) * L + x, id = cur[i];
				if (id === K.Air) continue;
				// a cut draws its first few blocks; further back, only the far walls of caves
				if (cut && z >= cut.deep && y >= w.height[z * L + x] - 1) continue;
				const front = z === 0 || !hides(cur[i - HL], id);
				const top = y === H - 1 || !hides(cur[i + L], id);
				const right = x === L - 1 || !hides(cur[i + 1], id);
				if (!front && !top && !right) continue;
				const k = stepOf(x), p = progOf(x);
				const lit = k === Step.Light ? p : k > Step.Light ? 1 : 0;
				const fx = px(x, z), fy = py(y + 1, z), T = TONE[id];
				// grass and dirt are one surface, as are the ores and the stone they're in
				const mat = id === K.Grass ? K.Dirt : id === K.Coal || id === K.Iron ? K.Stone : id === K.Diamond ? K.Deepslate : id;
				// the right side over the top where they meet, as back to front would leave them
				for (let f = 2; f >= 0; f--) {
					if ((f === 0 && !front) || (f === 1 && !top) || (f === 2 && !right)) continue;
					const sh = lit > 0 ? w.shade(x, y, z, f as 0 | 1 | 2) * lit : 0;
					// a face looking into air that's under the ground faces into a cave, so it's in the
					// dark, light or no light; in a cut, a block further back that isn't is fainter
					const cave = f === 0 ? z > 0 && y < w.height[(z - 1) * L + x] : f === 1 ? y + 1 < w.height[z * L + x] : x + 1 < L && stepOf(x + 1) >= Step.Noise && y < w.height[z * L + x + 1];
					const dark = cave ? 0.45 : 0, fade = cut && z > 0 && !cave ? Math.max(0.3, 1 - 0.22 * z) : 1;
					const n = f === 1 ? d : s, m = f === 2 ? d : s, o = nearness--;
					// outside the focus, quieter; but a side facing into it, as the cut side of the chunk
					// beside a hole, is part of it
					const q = focus >= 0 && x >> 4 !== focus && !(f === 2 && (x + 1) >> 4 === focus) ? 1 : 0, mute = q ? 0.45 : 1;
					// what the face is part of: its plane (a front's z, a top's y, a side's x), what it's
					// made of and its chunk, so chunk borders are edges too, as the game's border view
					// draws them on the ground; an ore is a block to itself
					const kk =
						id === K.Coal || id === K.Iron || id === K.Diamond
							? (1 << 30) | (x << 9) | (y << 4) | z
							: ((((f * 512 + (f === 0 ? z : f === 1 ? y : x)) * 16 + mat) * 64 + (cut ? 0 : x >> 4)) << 1) | 1;
					for (let a = 0; a < n; a++)
						for (let b = 0; b < m; b++) {
							// a, b: down and across the face; the cell, by face
							const cx = f === 0 ? fx + b : f === 1 ? fx + b + (d - a) : fx + s + b;
							const cy = f === 0 ? fy + a : f === 1 ? fy - d + a : fy + a - (b + 1);
							if (cx < 0 || cy < 0 || cx >= cols || cy >= rows) continue;
							const j = cy * cols + cx;
							if (key[j]) continue;
							const t = texel(id, f, a, b, s, d, x, y, z, T[f]);
							if (t < 0) continue;
							key[j] = kk;
							ord[j] = o;
							quiet[j] = q;
							tone(cx, cy, ((t + sh) * fade + dark) * mute);
						}
				}
			}

	// the outlines: where two neighbouring cells show different planes or blocks, the nearer is ink
	// (dotted where it's quiet: j is always the cell before i, so of the other parity)
	const outline = (i: number, j: number, odd: number) => {
		if (key[i] === key[j]) return;
		const near = ord[i] >= ord[j] ? i : j;
		if (key[near] && (!quiet[near] || (near === i ? odd : odd ^ 1))) bits[near] = 1;
	};
	for (let cy = 1; cy < rows; cy++)
		for (let cx = 1; cx < cols; cx++) {
			const i = cy * cols + cx, odd = (cx + cy) & 1;
			outline(i, i - 1, odd);
			outline(i, i - cols, odd);
		}

	// and up through the air from each chunk's front corner, dotted, as the border view draws it
	if (cut) return;
	for (let c = 0; c <= w.C; c++) {
		const cx = px(c * 16, 0);
		if (cx < 0 || cx >= cols) continue;
		for (let cy = Math.max(0, py(H, 0)); cy <= oy && cy < rows; cy++) {
			const i = cy * cols + cx;
			if (!key[i]) bits[i] = cy & 1;
		}
	}
}

// A face's tone at a, b (down, across): the block's tone and its marks. 1 or more is ink, 0 or
// less paper, and below -0.5 a hole that shows what's behind, as leaves have.
function texel(id: number, f: number, a: number, b: number, s: number, d: number, x: number, y: number, z: number, t: number) {
	switch (id) {
		case K.Grass:
			// tufts on top; down the sides a band of green over the dirt, ragged where it ends
			if (f === 1) return g(x, y, z, f, b, a) < 0.08 ? 1 : t;
			if (a < Math.max(1, s >> 2) + (g(x, y, z, f, b, 99) < 0.5 ? 1 : 0)) return 1;
			if (g(x, y, z, f, b, a) < 0.06) return 1;
			return TONE[K.Dirt][f];
		case K.Dirt:
			return g(x, y, z, f, b, a) < 0.06 ? 1 : t;
		case K.Coal:
		case K.Iron:
		case K.Diamond: {
			// a few lumps in the stone: coal's solid, iron's checked, diamond's bright in the dark
			if (f === 1) return t;
			const u = b - 1, w = a - 1, lump = u >= 0 && w >= 0 && u < s - 2 && w < s - 2 && g(x, y, z, f, u >> 1, w >> 1) < 0.45;
			if (!lump) return t;
			return id === K.Coal ? 1 : id === K.Iron ? ((u + w) & 1) ^ 1 : 0;
		}
		case K.Gravel:
			// pebbles
			return g(x, y, z, f, b >> 1, a >> 1) < 0.25 && (a & 1 || b & 1) ? 1 : t * 0.4;
		case K.Bedrock:
			return g(x, y, z, f, b >> 1, a >> 1) < 0.5 ? 1 : 0.19;
		case K.Log:
			if (f === 1) return a === 0 || a === d - 1 || b === 0 || b === s - 1 ? 1 : 0.19;
			return b % 3 === 1 ? 1 : 0.31;
		case K.Leaves: {
			const h = g(x, y, z, f, b >> 1, a >> 1);
			if (h < 0.18) return -1;
			return h < 0.42 ? 1 : t * 0.5;
		}
		case K.Water:
			// ripples on top, laid along the screen's rows so they stay level over the slant
			if (f === 1) return a === d - 1 && (b + x * 5 + z * 3) % 7 < 3 ? 1 : 0.06;
			// and level lines down the front, the one-ink sign for water, broken now and then
			if (f === 0) return a % 3 === 1 && (b + x * 7 + y * 3) % 11 !== 0 ? 1 : 0;
			break;
		case K.Bricks: {
			// courses of bricks half a block high, their joints alternating, in paper mortar
			if (f === 1) return t;
			const h = Math.max(2, s >> 1);
			if (a % h === h - 1) return 0;
			if (f === 0 && (b + (Math.floor(a / h) & 1 ? s >> 1 : 0)) % s === s - 1) return 0;
			return t;
		}
		case K.Stone:
			// a fleck here and there
			if (f !== 1 && g(x, y, z, f, b, a) < 0.07) return 1;
			break;
	}
	return t;
}

// A face's noise at a, b, the same each time for the same block and face.
function g(x: number, y: number, z: number, f: number, u: number, w: number) {
	return h3(x * 16 + u, y * 16 + w + f * 300, z * 9 + f);
}
