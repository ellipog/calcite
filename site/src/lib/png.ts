// One-bit pictures as PNG files, on the server or in a script: each cell k × k pixels of ink or
// paper, or transparent where there's no paper. A palette PNG, deflated with node's zlib.

import { deflateSync } from 'node:zlib';
import { rgb } from './dither/math';

const CRC = (() => {
	const t = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		t[n] = c >>> 0;
	}
	return t;
})();

function crc(buf: Uint8Array) {
	let c = 0xffffffff;
	for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Uint8Array) {
	const out = Buffer.alloc(12 + data.length);
	out.writeUInt32BE(data.length, 0);
	out.write(type, 4, 'ascii');
	out.set(data, 8);
	out.writeUInt32BE(crc(out.subarray(4, 8 + data.length)), 8 + data.length);
	return out;
}

/** bits, cols × rows, as a PNG of k pixels a cell, ink on paper, or on nothing with paper null.
 *  A palette PNG, unless rgba asks for full color, as an .ico's PNGs must be. */
export function bitsToPNG(bits: ArrayLike<number>, cols: number, rows: number, k: number, ink: string, paper: string | null, rgba = false): Buffer {
	const W = cols * k, H = rows * k, px = rgba ? 4 : 1, raw = Buffer.alloc((W * px + 1) * H);
	const [ir, ig, ib] = rgb(ink), [pr, pg, pb] = paper ? rgb(paper) : [0, 0, 0];
	for (let y = 0; y < H; y++) {
		const row = y * (W * px + 1), src = Math.floor(y / k) * cols;
		for (let x = 0; x < W; x++) {
			const on = bits[src + Math.floor(x / k)] ? 1 : 0, at = row + 1 + x * px;
			if (!rgba) raw[at] = on;
			else raw.set(on ? [ir, ig, ib, 255] : [pr, pg, pb, paper ? 255 : 0], at);
		}
	}
	const head = Buffer.alloc(13);
	head.writeUInt32BE(W, 0);
	head.writeUInt32BE(H, 4);
	head[8] = 8; // bit depth
	head[9] = rgba ? 6 : 3; // RGBA, or a palette
	return Buffer.concat([
		Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
		chunk('IHDR', head),
		...(rgba ? [] : [chunk('PLTE', Uint8Array.from([pr, pg, pb, ir, ig, ib]))]),
		...(rgba || paper ? [] : [chunk('tRNS', Uint8Array.from([0, 255]))]),
		chunk('IDAT', deflateSync(raw, { level: 9 })),
		chunk('IEND', new Uint8Array(0)),
	]);
}

/** PNGs in an .ico file, which every browser reads, each at its own size. */
export function ico(pngs: { size: number; png: Buffer }[]): Buffer {
	const head = Buffer.alloc(6 + 16 * pngs.length);
	head.writeUInt16LE(0, 0);
	head.writeUInt16LE(1, 2);
	head.writeUInt16LE(pngs.length, 4);
	let at = head.length;
	pngs.forEach((p, i) => {
		const e = 6 + 16 * i;
		head[e] = p.size >= 256 ? 0 : p.size;
		head[e + 1] = p.size >= 256 ? 0 : p.size;
		head.writeUInt16LE(1, e + 4);
		head.writeUInt16LE(32, e + 6);
		head.writeUInt32LE(p.png.length, e + 8);
		head.writeUInt32LE(at, e + 12);
		at += p.png.length;
	});
	return Buffer.concat([head, ...pngs.map((p) => p.png)]);
}
