// The home page's flight over a world of blocks, with no DOM in it, so it runs the same in a
// worker, on an OffscreenCanvas the page hands it, or on the page itself where workers can't draw.
//
// The camera drifts over a new world and the pointer turns it. Chunks are generated around the
// camera, nearest first, at the rate Calcite generates them, so the view fills in a fraction of a
// second and new chunks keep loading at its edge. Frames are paced to what they cost and to the
// screen: a still frame for reduced motion, never more than 30 a second on a touch screen, and a
// touch screen's flight rests a while after the last touch.

import { B, CHUNK, forget, frame, generate, groundAt, hash, isLoaded, reseed, SEA } from './blocks';

/** The view distance, in chunks, and the seconds a touch screen's flight goes on after the last touch. */
const VIEW = 14, REST = 30;
/** At most this many cells a frame: past it the cells grow a pixel, so a big screen keeps its frame rate. */
const MAX_CELLS = 240_000;

// The chunks in view around the camera's, nearest first, a little shuffled within each ring as a
// server's generation threads finish them.
const ORDER = (() => {
	const o: [number, number, number][] = [];
	for (let z = -VIEW; z <= VIEW; z++) for (let x = -VIEW; x <= VIEW; x++) if (x * x + z * z <= VIEW * VIEW) o.push([x, z, Math.hypot(x, z) + hash(x + 500, z) * 1.2]);
	return o.sort((a, b) => a[2] - b[2]);
})();

// Somewhere to start: land, a little above the sea, without a hill right in front.
function start() {
	for (let i = 0; i < 400; i++) {
		const x = 1000 + i * 97, y = 3000 - i * 61, g = groundAt(x, y);
		if (g > SEA + 4 && g < SEA + 16 && groundAt(x, y - 260) < SEA + 24) return { x, y };
	}
	return { x: 1000, y: 3000 };
}

type Canvas = HTMLCanvasElement | OffscreenCanvas;
type Ctx = CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;

export interface HeroOptions {
	/** Chunks a second, the fastest recorded worldgen run's. */
	cps: number;
	/** One still frame, for reduced motion or a reader saving data. */
	still: boolean;
	/** A touch screen: at most 30 frames a second, and a rest after the last touch. */
	touch: boolean;
	seed: number;
	/** Told how many chunks around the camera have loaded, when that changes. */
	count?: (n: number) => void;
	/** Asks for draw(seconds) at the next frame; returns a handle cancel takes. */
	raf: (f: (ms: number) => void) => number;
	caf: (id: number) => void;
}

export class Hero {
	private ctx: Ctx;
	private cells: Canvas | null = null;
	private cctx: Ctx | null = null;
	private img: ImageData | null = null;
	private px = new Uint32Array(0);
	private cols = 0;
	private rows = 0;
	private cell = 1;
	private W = 0;
	private H = 0;
	private cam = { x: 0, y: 0 };
	private h = 0;
	private look = { yaw: 0, hor: 0 };
	private aim: [number, number] | null = null;
	private last = -1;
	private budget = 0;
	private full = NaN;
	private shown = -1;
	private next = 0;
	private rest = Infinity;
	private woken = true;
	private cost = 0;
	private drawn = false;
	private visible = true;
	private id = 0;

	constructor(private canvas: Canvas, private o: HeroOptions) {
		this.ctx = canvas.getContext('2d', { alpha: true }) as Ctx;
		reseed(o.seed);
		forget();
		this.cam = start();
		this.h = (groundAt(this.cam.x, this.cam.y) + 24) * B;
	}

	/** The canvas's box, in CSS pixels, and the screen's density. */
	resize(w: number, h: number, dpr: number) {
		const W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
		// cells of 2 CSS pixels, a pixel bigger while there'd be too many of them
		let dot = 2, cell = 1, cols = 1, rows = 1;
		for (; ; dot++) {
			cell = Math.max(1, Math.round(dot * dpr));
			cols = Math.ceil(W / cell);
			rows = Math.ceil(H / cell);
			if (cols * rows <= MAX_CELLS || dot >= 4) break;
		}
		this.canvas.width = W;
		this.canvas.height = H;
		this.W = W;
		this.H = H;
		this.cell = cell;
		this.cols = cols;
		this.rows = rows;
		this.cells = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(cols, rows) : Object.assign(document.createElement('canvas'), { width: cols, height: rows });
		this.cctx = this.cells.getContext('2d') as Ctx;
		this.img = new ImageData(cols, rows);
		this.px = new Uint32Array(this.img.data.buffer);
		this.drawn = false;
		this.kick();
	}

	/** Where the pointer is over the canvas, 0 to 1 each way, or null once it's left. */
	point(p: [number, number] | null) {
		this.aim = p;
		this.woken = true;
		this.kick();
	}
	/** A touch: a resting flight goes on. */
	wake() {
		this.woken = true;
		this.kick();
	}
	/** Whether the canvas is on screen and the page shown; the flight stops while it isn't. */
	show(on: boolean) {
		this.visible = on;
		if (on) this.kick();
		else this.stop();
	}
	stop() {
		if (this.id) this.o.caf(this.id);
		this.id = 0;
	}

	private kick() {
		if (this.id || !this.visible || !this.cells) return;
		if (this.o.still && this.drawn) return;
		this.id = this.o.raf((ms) => {
			this.id = 0;
			this.tick(ms / 1000);
		});
	}

	private tick(t: number) {
		const o = this.o;
		let draw = true;
		if (o.still) draw = !this.drawn;
		else if (this.last >= 0) {
			if (this.woken) {
				this.woken = false;
				this.rest = t + REST;
			}
			if (t < this.next) draw = false;
			// resting: hold the last frame until a touch, without asking for more
			else if (o.touch && t > this.rest) return;
		}
		if (draw) this.draw(t);
		if (!o.still) this.kick();
	}

	private draw(t: number) {
		const o = this.o, w0 = performance.now(), cam = this.cam;
		const dt = this.last < 0 ? 0 : Math.min(0.05, Math.max(0, t - this.last));
		this.last = t;
		// the pointer turns the camera and tips it a little; without one it looks ahead. The easing
		// is by time, so it answers as quickly at 30 frames a second as at 60
		const ay = this.aim ? (this.aim[0] - 0.5) * 0.9 : 0, ah = this.aim ? (this.aim[1] - 0.5) * 0.12 : 0, k = 1 - Math.exp(-dt * 9);
		this.look.yaw += (ay - this.look.yaw) * k;
		this.look.hor += (ah - this.look.hor) * k;
		const heading = Math.sin(t * 0.045) * 0.5, fx = Math.sin(heading), fy = -Math.cos(heading);
		cam.x += fx * 16 * dt;
		cam.y += fy * 16 * dt;
		// fly over whatever is coming up, not into it
		let ahead = 0;
		for (const d of [0, 40, 80, 120]) ahead = Math.max(ahead, groundAt(cam.x + fx * d, cam.y + fy * d));
		this.h += ((ahead + 24) * B - this.h) * Math.min(1, dt * 0.8);

		// generate the nearest chunks missing, as many as Calcite would in the time since the last
		// frame and at most 4 ms of them (none to look for while the camera stays in a chunk whose
		// view is already whole; a still frame generates the whole view, however long it takes)
		const ccx = Math.floor(cam.x / CHUNK), ccz = Math.floor(cam.y / CHUNK), here = ccx * 65536 + ccz;
		let n = ORDER.length;
		if (this.full !== here) {
			const t0 = performance.now();
			this.budget = o.still ? ORDER.length : Math.min(this.budget + o.cps * (dt || 1 / 60), ORDER.length);
			n = 0;
			for (const [x, z] of ORDER) {
				if (isLoaded(ccx + x, ccz + z)) {
					n++;
					continue;
				}
				if (this.budget < 1 || (!o.still && performance.now() - t0 > 4)) continue;
				generate(ccx + x, ccz + z);
				this.budget--;
				n++;
			}
			if (n === ORDER.length) this.full = here;
		}

		// the sky dissolves into the page above, and the land into it below
		frame(this.px, this.cols, this.rows, { x: cam.x, y: cam.y, yaw: heading + this.look.yaw }, { height: this.h, horizon: 0.22 + this.look.hor, far: VIEW * CHUNK, sky: 0.22, haze: 0.08, drift: t * 3, fadeTop: 0.32, fadeBottom: 0.2 });
		this.cctx!.putImageData(this.img!, 0, 0);
		this.ctx.imageSmoothingEnabled = false;
		this.ctx.clearRect(0, 0, this.W, this.H);
		this.ctx.drawImage(this.cells!, 0, 0, this.cols * this.cell, this.rows * this.cell);
		this.drawn = true;
		if (n !== this.shown) {
			this.shown = n;
			o.count?.(n);
		}
		// 60 frames a second while a frame takes under 12 ms, fewer as it costs more, and never more
		// than 30 on a touch screen
		const ms = performance.now() - w0;
		this.cost = this.cost ? this.cost * 0.9 + ms * 0.1 : ms;
		const fps = this.cost > 24 ? 20 : this.cost > 12 || o.touch ? 30 : 60;
		this.next = t + 1 / fps - 0.004;
	}
}
