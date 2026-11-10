// The nightly archive with a setup's files in it, made in the browser. Each archive holds one
// folder, calcite/, which is renamed to the server's name, and the files go into it. The zip's
// entries are copied as they're compressed, never inflated; the tar.gz is unzipped, added to and
// zipped again with the browser's own gzip. No library: both formats are a few headers.

export interface Entry {
	name: string;
	data: string | Uint8Array;
}

const bytes = (d: string | Uint8Array) => (typeof d === 'string' ? new TextEncoder().encode(d) : d);
const ROOT = 'calcite/';

/* ---- CRC-32, which zip and gzip both use ---------------------------------------------------- */

const TABLE = (() => {
	const t = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		t[n] = c >>> 0;
	}
	return t;
})();
export function crc32(d: Uint8Array) {
	let c = 0xffffffff;
	for (let i = 0; i < d.length; i++) c = TABLE[(c ^ d[i]) & 0xff] ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

/* ---- zip ------------------------------------------------------------------------------------ */

// MS-DOS time and date, which zip keeps, for now in local time.
function dos(t = new Date()) {
	return {
		time: (t.getHours() << 11) | (t.getMinutes() << 5) | (t.getSeconds() >> 1),
		date: ((t.getFullYear() - 1980) << 9) | ((t.getMonth() + 1) << 5) | t.getDate(),
	};
}

class Out {
	parts: Uint8Array[] = [];
	size = 0;
	push(b: Uint8Array) {
		this.parts.push(b);
		this.size += b.length;
	}
	header(n: number) {
		const b = new Uint8Array(n);
		this.push(b);
		return new DataView(b.buffer);
	}
}

interface Central {
	name: Uint8Array;
	made: number;
	needed: number;
	flags: number;
	method: number;
	time: number;
	date: number;
	crc: number;
	csize: number;
	usize: number;
	extra: Uint8Array;
	comment: Uint8Array;
	internal: number;
	external: number;
	offset: number;
}

function writeLocal(out: Out, c: Central, data: Uint8Array) {
	const h = out.header(30 + c.name.length);
	h.setUint32(0, 0x04034b50, true);
	h.setUint16(4, c.needed, true);
	h.setUint16(6, c.flags, true);
	h.setUint16(8, c.method, true);
	h.setUint16(10, c.time, true);
	h.setUint16(12, c.date, true);
	h.setUint32(14, c.crc, true);
	h.setUint32(18, c.csize, true);
	h.setUint32(22, c.usize, true);
	h.setUint16(26, c.name.length, true);
	h.setUint16(28, 0, true);
	new Uint8Array(h.buffer).set(c.name, 30);
	out.push(data);
}

function writeCentral(out: Out, list: Central[]) {
	const start = out.size;
	for (const c of list) {
		const h = out.header(46 + c.name.length + c.extra.length + c.comment.length);
		h.setUint32(0, 0x02014b50, true);
		h.setUint16(4, c.made, true);
		h.setUint16(6, c.needed, true);
		h.setUint16(8, c.flags, true);
		h.setUint16(10, c.method, true);
		h.setUint16(12, c.time, true);
		h.setUint16(14, c.date, true);
		h.setUint32(16, c.crc, true);
		h.setUint32(20, c.csize, true);
		h.setUint32(24, c.usize, true);
		h.setUint16(28, c.name.length, true);
		h.setUint16(30, c.extra.length, true);
		h.setUint16(32, c.comment.length, true);
		h.setUint16(34, 0, true);
		h.setUint16(36, c.internal, true);
		h.setUint32(38, c.external, true);
		h.setUint32(42, c.offset, true);
		const u = new Uint8Array(h.buffer);
		u.set(c.name, 46);
		u.set(c.extra, 46 + c.name.length);
		u.set(c.comment, 46 + c.name.length + c.extra.length);
	}
	const e = out.header(22);
	e.setUint32(0, 0x06054b50, true);
	e.setUint16(8, list.length, true);
	e.setUint16(10, list.length, true);
	e.setUint32(12, out.size - 22 - start, true);
	e.setUint32(16, start, true);
}

// A file stored, not compressed: the setup's files are small, and a PNG is compressed already.
function stored(name: string, data: Uint8Array, offset: number): Central {
	const { time, date } = dos();
	const n = new TextEncoder().encode(name);
	return { name: n, made: 20, needed: 10, flags: /[^\x20-\x7e]/.test(name) ? 0x800 : 0, method: 0, time, date, crc: crc32(data), csize: data.length, usize: data.length, extra: new Uint8Array(0), comment: new Uint8Array(0), internal: 0, external: 0, offset };
}

/** The zip `src` with its calcite/ folder renamed to `folder`/ and `add` put in it. */
export function rezip(src: Uint8Array, folder: string, add: Entry[]): Blob {
	const v = new DataView(src.buffer, src.byteOffset, src.byteLength);
	let eocd = -1;
	for (let i = src.length - 22; i >= Math.max(0, src.length - 22 - 65535); i--)
		if (v.getUint32(i, true) === 0x06054b50) {
			eocd = i;
			break;
		}
	if (eocd < 0) throw new Error('not a zip');
	const count = v.getUint16(eocd + 10, true);
	let p = v.getUint32(eocd + 16, true);
	if (count === 0xffff || p === 0xffffffff) throw new Error('zip64 is not handled');
	const dec = new TextDecoder();
	const enc = new TextEncoder();
	const adding = new Set(add.map((a) => folder + '/' + a.name));
	const out = new Out();
	const list: Central[] = [];
	for (let k = 0; k < count; k++) {
		if (v.getUint32(p, true) !== 0x02014b50) throw new Error('bad central directory');
		const nlen = v.getUint16(p + 28, true), xlen = v.getUint16(p + 30, true), clen = v.getUint16(p + 32, true);
		const old = dec.decode(src.subarray(p + 46, p + 46 + nlen));
		const name = old.startsWith(ROOT) ? folder + '/' + old.slice(ROOT.length) : old;
		const c: Central = {
			name: enc.encode(name),
			made: v.getUint16(p + 4, true),
			needed: v.getUint16(p + 6, true),
			// sizes and the CRC go in the local header, so there's no data descriptor after it
			flags: v.getUint16(p + 8, true) & ~0x0008,
			method: v.getUint16(p + 10, true),
			time: v.getUint16(p + 12, true),
			date: v.getUint16(p + 14, true),
			crc: v.getUint32(p + 16, true),
			csize: v.getUint32(p + 20, true),
			usize: v.getUint32(p + 24, true),
			extra: src.slice(p + 46 + nlen, p + 46 + nlen + xlen),
			comment: src.slice(p + 46 + nlen + xlen, p + 46 + nlen + xlen + clen),
			internal: v.getUint16(p + 36, true),
			external: v.getUint32(p + 38, true),
			offset: 0,
		};
		const local = v.getUint32(p + 42, true);
		p += 46 + nlen + xlen + clen;
		if (adding.has(name)) continue;
		if (v.getUint32(local, true) !== 0x04034b50) throw new Error('bad local header');
		const start = local + 30 + v.getUint16(local + 26, true) + v.getUint16(local + 28, true);
		c.offset = out.size;
		writeLocal(out, c, src.subarray(start, start + c.csize));
		list.push(c);
	}
	for (const a of add) {
		const d = bytes(a.data);
		const c = stored(folder + '/' + a.name, d, out.size);
		writeLocal(out, c, d);
		list.push(c);
	}
	writeCentral(out, list);
	return new Blob(out.parts as BlobPart[], { type: 'application/zip' });
}

/** A zip of just these files, in a folder of their own. */
export function zipOf(folder: string, add: Entry[]): Blob {
	const out = new Out();
	const list: Central[] = [];
	for (const a of add) {
		const d = bytes(a.data);
		const c = stored(folder + '/' + a.name, d, out.size);
		writeLocal(out, c, d);
		list.push(c);
	}
	writeCentral(out, list);
	return new Blob(out.parts as BlobPart[], { type: 'application/zip' });
}

/* ---- tar.gz --------------------------------------------------------------------------------- */

async function through(data: Uint8Array | Blob, stream: CompressionStream | DecompressionStream) {
	const body = (data instanceof Blob ? data : new Blob([data as BlobPart])).stream().pipeThrough(stream);
	return new Uint8Array(await new Response(body).arrayBuffer());
}

const field = (h: Uint8Array, at: number, n: number) => {
	const end = h.subarray(at, at + n).indexOf(0);
	return new TextDecoder().decode(h.subarray(at, end < 0 ? at + n : at + end));
};
function put(h: Uint8Array, at: number, n: number, s: string) {
	h.fill(0, at, at + n);
	h.set(new TextEncoder().encode(s).subarray(0, n), at);
}
function checksum(h: Uint8Array) {
	h.fill(0x20, 148, 156);
	let sum = 0;
	for (const b of h) sum += b;
	put(h, 148, 8, sum.toString(8).padStart(6, '0') + '\0 ');
}

/** The tar.gz `src` with its calcite/ folder renamed to `folder`/ and `add` put in it. */
export async function retar(src: Uint8Array, folder: string, add: Entry[]): Promise<Blob> {
	const tar = await through(src, new DecompressionStream('gzip'));
	const adding = new Set(add.map((a) => folder + '/' + a.name));
	const parts: Uint8Array[] = [];
	let p = 0;
	let longName: string | null = null;
	while (p + 512 <= tar.length) {
		const h = tar.slice(p, p + 512);
		if (h.every((b) => b === 0)) break;
		const size = parseInt(field(h, 124, 12).trim() || '0', 8);
		const type = String.fromCharCode(h[156]);
		const blocks = Math.ceil(size / 512) * 512;
		const body = tar.subarray(p + 512, p + 512 + blocks);
		p += 512 + blocks;
		if (type === 'L') {
			// GNU's long name: the next entry's name, as this one's data
			longName = field(body, 0, size);
			continue;
		}
		// POSIX ustar may split a long name into a prefix; GNU's header keeps times there instead
		const posix = field(h, 257, 6) === 'ustar' && h[262] === 0;
		const prefix = posix ? field(h, 345, 155) : '';
		const old = longName ?? (prefix ? prefix + '/' : '') + field(h, 0, 100);
		longName = null;
		const name = old.startsWith(ROOT) ? folder + '/' + old.slice(ROOT.length) : old;
		if (adding.has(name)) continue;
		if (name.length > 100) throw new Error(`a name too long for a plain tar header: ${name}`);
		put(h, 0, 100, name);
		if (prefix) put(h, 345, 155, '');
		checksum(h);
		parts.push(h, body);
	}
	const now = Math.floor(Date.now() / 1000);
	for (const a of add) {
		const d = bytes(a.data);
		const h = new Uint8Array(512);
		put(h, 0, 100, folder + '/' + a.name);
		put(h, 100, 8, '0000644\0');
		put(h, 108, 8, '0000000\0');
		put(h, 116, 8, '0000000\0');
		put(h, 124, 12, d.length.toString(8).padStart(11, '0') + '\0');
		put(h, 136, 12, now.toString(8).padStart(11, '0') + '\0');
		h[156] = 0x30;
		put(h, 257, 6, 'ustar\0');
		put(h, 263, 2, '00');
		checksum(h);
		const body = new Uint8Array(Math.ceil(d.length / 512) * 512);
		body.set(d);
		parts.push(h, body);
	}
	parts.push(new Uint8Array(1024));
	const gz = await through(new Blob(parts as BlobPart[]), new CompressionStream('gzip'));
	return new Blob([gz as BlobPart], { type: 'application/gzip' });
}
