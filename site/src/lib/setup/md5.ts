// MD5, for the one thing that needs it: an offline player's UUID, which vanilla makes from
// "OfflinePlayer:" and the name (UUIDUtil.createOfflinePlayerUUID). Web Crypto has no MD5.

const S = [7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21];
const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0);

export function md5(data: Uint8Array): Uint8Array {
	const len = data.length;
	const padded = new Uint8Array((((len + 8) >> 6) + 1) << 6);
	padded.set(data);
	padded[len] = 0x80;
	const view = new DataView(padded.buffer);
	view.setUint32(padded.length - 8, (len * 8) >>> 0, true);
	view.setUint32(padded.length - 4, Math.floor(len / 0x20000000), true);
	let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
	for (let off = 0; off < padded.length; off += 64) {
		let a = a0, b = b0, c = c0, d = d0;
		for (let i = 0; i < 64; i++) {
			let f: number, g: number;
			if (i < 16) {
				f = (b & c) | (~b & d);
				g = i;
			} else if (i < 32) {
				f = (d & b) | (~d & c);
				g = (5 * i + 1) % 16;
			} else if (i < 48) {
				f = b ^ c ^ d;
				g = (3 * i + 5) % 16;
			} else {
				f = c ^ (b | ~d);
				g = (7 * i) % 16;
			}
			const t = d;
			d = c;
			c = b;
			const x = (a + f + K[i] + view.getUint32(off + g * 4, true)) | 0;
			b = (b + ((x << S[i]) | (x >>> (32 - S[i])))) | 0;
			a = t;
		}
		a0 = (a0 + a) | 0;
		b0 = (b0 + b) | 0;
		c0 = (c0 + c) | 0;
		d0 = (d0 + d) | 0;
	}
	const out = new Uint8Array(16);
	const ov = new DataView(out.buffer);
	[a0, b0, c0, d0].forEach((v, i) => ov.setUint32(i * 4, v >>> 0, true));
	return out;
}
