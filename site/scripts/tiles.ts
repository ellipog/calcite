// Writes src/styles/tiles.css, the dither tiles every component draws with, and the icons in
// src/app: icon.svg, favicon.ico (16 and 32 px) and apple-icon.png (180 px, the master at 2 px a
// cell on paper). Run from site/: bun run tiles

import { writeFileSync } from 'node:fs';
import { houseTiles } from '../src/lib/dither/tiles';
import { markBits, markSVG } from '../src/lib/dither/mark';
import { INK, PAPER } from '../src/lib/dither/math';
import { bitsToPNG, ico } from '../src/lib/png';

const tiles = houseTiles();
const lines = [
	'/* Calcite dither tiles. Made by scripts/tiles.ts from src/lib/dither/tiles.ts; edit those, not this.',
	'   Each is an SVG drawn 2 px a cell, so give it its natural size:',
	'     --t*   Bayer 8x8 levels in ink (16px)    --tp*  the same in paper',
	'     --q*   Bayer 4x4 levels in ink (8px)     --qp*  the same in paper',
	'     --u*   a one-cell line across (8px 2px)  --v*   a one-cell line down (2px 8px)',
	"     --edge a fill's leading edge, 75, 50, 25% (12px 4px, repeat-y); --edge-p in paper,",
	'            --edge-r the same facing left; --shine 25, 50, 75, 50, 25% (20px 4px)',
	'     --ring diagonal halves for the focus ring and work under way (8px); --ring-p in paper',
	"     --check2 a 50% bar (4px), --tail a tooltip's point (10px 6px), --chevron (10px 8px),",
	'     --plus and --minus (10px); --solid is plain ink, for layering with the rest.',
	'   The tint utilities: tint-{6..88} and tint-100, tint-paper-{6,12,25,50}, tint4-{6..75}, and',
	'   tile-ring. Each also sets --tile, its tile, which march-8 and march-16 draw moving. */',
	'',
	':root {',
	'\t--solid: linear-gradient(var(--color-ink), var(--color-ink));',
	...tiles.map(([n, u]) => `\t--${n}: ${u};`),
	'}',
	'',
];
const tint = (name: string, n: string, size: number) => `@utility ${name} {\n\t--tile: var(--${n});\n\tbackground-image: var(--${n});\n\tbackground-size: ${size}px ${size}px;\n}`;
for (const [n] of tiles) {
	let m;
	if ((m = /^t(\d+)$/.exec(n))) lines.push(tint(`tint-${m[1]}`, n, 16));
	else if ((m = /^tp(\d+)$/.exec(n))) lines.push(tint(`tint-paper-${m[1]}`, n, 16));
	else if ((m = /^q(\d+)$/.exec(n))) lines.push(tint(`tint4-${m[1]}`, n, 8));
}
lines.push(tint('tile-ring', 'ring', 8), '@utility tint-100 {\n\tbackground-color: var(--color-ink);\n}', '');
writeFileSync('src/styles/tiles.css', lines.join('\n'));
writeFileSync('src/app/icon.svg', markSVG(16, { paper: PAPER, size: 32 }) + '\n');
const m16 = markBits(16);
writeFileSync('src/app/favicon.ico', ico([16, 32].map((size) => ({ size, png: bitsToPNG(m16, 16, 16, size / 16, INK, PAPER, true) }))));
// the master, 64 cells at 2 px, in the middle of 90 cells of paper
const apple = new Uint8Array(90 * 90), m64 = markBits(64);
for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) apple[(y + 13) * 90 + x + 13] = m64[y * 64 + x];
writeFileSync('src/app/apple-icon.png', bitsToPNG(apple, 90, 90, 2, INK, PAPER));
console.log(`${tiles.length} tiles, icon.svg, favicon.ico, apple-icon.png`);
