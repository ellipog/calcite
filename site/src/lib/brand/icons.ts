// Icons: 16 cells, a solid one-cell outline, fills at 12, 50 and 88% through the 4×4 matrix.
// Square corners only. Pure: drawn on the server as SVG.

import { toBits, type Bits } from '../dither/bayer';

type Pred = (x: number, y: number) => boolean;
const rect = (x0: number, y0: number, x1: number, y1: number): Pred => (x, y) => x > x0 && x < x1 + 1 && y > y0 && y < y1 + 1;
const poly = (P: [number, number][]): Pred => (x, y) => {
	let c = false;
	for (let i = 0, j = P.length - 1; i < P.length; j = i++) {
		const [xi, yi] = P[i], [xj, yj] = P[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
	}
	return c;
};
const and = (a: Pred, b: Pred): Pred => (x, y) => a(x, y) && b(x, y);

interface Pen {
	shape(pred: Pred, fill: number): void;
	solid(pred: Pred): void;
}
function icon(paint: (a: Pen) => void): Bits {
	const g = new Float32Array(256);
	paint({
		shape(pred, fill) {
			const ins = new Uint8Array(256);
			for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) ins[y * 16 + x] = pred(x + 0.5, y + 0.5) ? 1 : 0;
			for (let y = 0; y < 16; y++)
				for (let x = 0; x < 16; x++) {
					const i = y * 16 + x;
					if (!ins[i]) continue;
					const edge = x === 0 || y === 0 || x === 15 || y === 15 || !ins[i - 1] || !ins[i + 1] || !ins[i - 16] || !ins[i + 16];
					g[i] = edge ? 1 : fill;
				}
		},
		solid(pred) {
			for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) if (pred(x + 0.5, y + 0.5)) g[y * 16 + x] = 1;
		},
	});
	return toBits(g, 16, 4);
}

export const ICONS = {
	chunk: icon((a) => {
		const f = [[0.12, 0.5, 0.12], [0.5, 0.88, 0.5], [0.12, 0.5, 0.12]];
		for (let j = 0; j < 3; j++) for (let i = 0; i < 3; i++) a.shape(rect(i * 5, j * 5, i * 5 + 5, j * 5 + 5), f[j][i]);
	}),
	tick: icon((a) => {
		a.shape(rect(0, 0, 15, 15), 0.12);
		a.solid(rect(7, 3, 8, 8));
		a.solid(rect(7, 7, 11, 8));
	}),
	plugin: icon((a) => {
		a.solid(rect(4, 0, 5, 3));
		a.solid(rect(10, 0, 11, 3));
		a.shape(rect(2, 4, 13, 10), 0.5);
		a.shape(rect(5, 11, 10, 12), 0.88);
		a.solid(rect(7, 13, 8, 15));
	}),
	speed: icon((a) => a.shape(poly([[9.5, 0], [2.5, 9.2], [7.3, 9.2], [5.2, 16], [13.6, 6.6], [8.8, 6.6], [11.6, 0]]), 0.5)),
	parity: icon((a) => {
		a.shape(rect(0, 4, 6, 10), 0.5);
		a.shape(rect(9, 4, 15, 10), 0.5);
		a.solid(rect(7, 6, 8, 6));
		a.solid(rect(7, 8, 8, 8));
	}),
	world: icon((a) => {
		const frame = rect(0, 1, 15, 14);
		a.shape(frame, 0.12);
		a.shape(rect(10, 3, 13, 6), 0.5);
		a.shape(and(frame, poly([[0, 15], [6, 5], [9, 9.5], [11.5, 7], [16, 12], [16, 15]])), 0.88);
	}),
	player: icon((a) => {
		a.shape(rect(5, 0, 10, 5), 0.5);
		a.shape(rect(2, 7, 13, 15), 0.88);
	}),
	memory: icon((a) => {
		for (const i of [4, 6, 9, 11]) {
			a.solid(rect(i, 0, i, 2));
			a.solid(rect(i, 13, i, 15));
			a.solid(rect(0, i, 2, i));
			a.solid(rect(13, i, 15, i));
		}
		a.shape(rect(3, 3, 12, 12), 0.5);
		a.shape(rect(6, 6, 9, 9), 0.88);
	}),
};
export type IconName = keyof typeof ICONS;
