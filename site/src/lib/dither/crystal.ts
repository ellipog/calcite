// Calcite's cleavage rhombohedron. Three equal edges from one corner, each pair 101.9° apart:
// every face is then a rhombus of 78.1° and 101.9°, as a cleaved piece of Iceland spar is.

import { clamp01 } from './math';

type V3 = [number, number, number];
type P2 = [number, number];

const v3 = {
	add: (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
	sub: (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
	dot: (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
	cross: (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
	norm: (a: V3): V3 => {
		const l = Math.hypot(a[0], a[1], a[2]) || 1;
		return [a[0] / l, a[1] / l, a[2] / l];
	},
};

export const RHOMB = (() => {
	const a = (101.92 * Math.PI) / 180;
	const s = Math.sqrt((1 - Math.cos(a)) / 1.5), c = Math.sqrt(1 - s * s);
	const e = [0, 1, 2].map((k): V3 => [s * Math.cos((2 * Math.PI * k) / 3), s * Math.sin((2 * Math.PI * k) / 3), c]);
	const V: V3[] = [];
	for (let m = 0; m < 8; m++) {
		let p: V3 = [0, 0, -1.5 * c];
		for (let k = 0; k < 3; k++) if (m & (1 << k)) p = v3.add(p, e[k]);
		V.push(p);
	}
	const F: number[][] = [];
	for (let k = 0; k < 3; k++) {
		const i = 1 << ((k + 1) % 3), j = 1 << ((k + 2) % 3);
		for (const b of [0, 1 << k]) F.push([b, b | i, b | i | j, b | j]);
	}
	return { V, F, R: Math.max(...V.map((p) => Math.hypot(...p))) };
})();

function rotate([x, y, z]: V3, spin: number, tilt: number, turn: number): V3 {
	let c = Math.cos(spin), s = Math.sin(spin);
	[x, y] = [x * c - y * s, x * s + y * c];
	c = Math.cos(tilt);
	s = Math.sin(tilt);
	[y, z] = [y * c - z * s, y * s + z * c];
	c = Math.cos(turn);
	s = Math.sin(turn);
	[x, z] = [x * c + z * s, -x * s + z * c];
	return [x, y, z];
}
export function inside(poly: P2[], x: number, y: number) {
	let sign = 0;
	for (let i = 0; i < poly.length; i++) {
		const a = poly[i], b = poly[(i + 1) % poly.length];
		const c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]);
		if (c > 0) {
			if (sign < 0) return false;
			sign = 1;
		} else if (c < 0) {
			if (sign > 0) return false;
			sign = -1;
		}
	}
	return true;
}
function segment(x: number, y: number, a: P2, b: P2) {
	const dx = b[0] - a[0], dy = b[1] - a[1];
	const t = clamp01(((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy || 1));
	return Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy);
}

const LIGHT = v3.norm([-0.55, 0.75, 0.6]);
// The crystal turned, then seen from the front in screen axes (x right, y down).
export function crystal(spin: number, tilt: number, turn: number, light: V3 = LIGHT) {
	const P = RHOMB.V.map((p) => rotate(p, spin, tilt, turn));
	const pts = P.map(([x, y]): P2 => [x, -y]);
	const faces = RHOMB.F.map((f) => {
		const q = f.map((i) => P[i]);
		let n = v3.norm(v3.cross(v3.sub(q[1], q[0]), v3.sub(q[3], q[0])));
		const mid = q.reduce(v3.add).map((x) => x / 4) as V3;
		if (v3.dot(n, mid) < 0) n = n.map((x) => -x) as V3;
		return { p: f.map((i) => pts[i]), lit: Math.max(0, v3.dot(n, light)), front: n[2] > 1e-6 };
	});
	const front = faces.filter((f) => f.front);
	return {
		R: RHOMB.R,
		at(x: number, y: number) {
			for (const f of front)
				if (inside(f.p, x, y)) {
					let d = Infinity;
					for (let k = 0; k < 4; k++) d = Math.min(d, segment(x, y, f.p[k], f.p[(k + 1) % 4]));
					return { lit: f.lit, edge: d };
				}
			return null;
		},
	};
}
