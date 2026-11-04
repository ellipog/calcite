// Writes ../assets/logo/calcite-banner.png, the README's header, as the brand guide draws it: the
// world from the README's camera, coming in from the left, and on paper over it the mark and the
// name. 1600 × 400, in one ink, every dot of the world a whole 2 × 2 pixels; it has its own paper,
// so it reads the same on GitHub's light and dark themes. Run from site/: bun run banner

import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { CAMS, fade, view } from '../src/lib/brand/terrain';
import { ordered } from '../src/lib/dither/bayer';
import { cellsFor, markBits } from '../src/lib/dither/mark';
import { INK, PAPER } from '../src/lib/dither/math';
import { bitsToPNG } from '../src/lib/png';

const W = 1600, H = 400, cols = W / 2, rows = H / 2;
const url = (png: Buffer) => `data:image/png;base64,${png.toString('base64')}`;
const fonts = join(process.cwd(), 'src/app/fonts');

const tone = new Float32Array(cols * rows);
view(tone, cols, rows, CAMS.readme, { horizon: 0.22 });
fade(tone, cols, rows, { l: 0.5 });
const world = url(bitsToPNG(ordered(tone, cols, rows, 8), cols, rows, 2, INK, PAPER));
// the mark as the site draws it at 80 px: 40 cells, 2 px each
const MARK = 80, n = cellsFor(MARK), mark = url(bitsToPNG(markBits(n), n, n, MARK / n, INK, null));

// the guide's proportions, in hundredths of the width: the name 6.4 high, the box 4 in from the
// left, padded 1.4 round the mark and 2.4 after the name, with 1.8 between them
const cq = W / 100;
const img = new ImageResponse(
	(
		<div style={{ width: '100%', height: '100%', display: 'flex', background: PAPER, position: 'relative' }}>
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={world} width={W} height={H} alt="" style={{ position: 'absolute', left: 0, top: 0 }} />
			<div style={{ position: 'absolute', left: 4 * cq, top: 0, bottom: 0, display: 'flex', alignItems: 'center' }}>
				<div style={{ display: 'flex', alignItems: 'center', gap: Math.round(1.8 * cq), background: PAPER, padding: `${Math.round(1.4 * cq)}px ${Math.round(2.4 * cq)}px ${Math.round(1.4 * cq)}px ${Math.round(1.4 * cq)}px` }}>
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src={mark} width={MARK} height={MARK} alt="" />
					<div style={{ fontFamily: 'Bricolage', fontSize: Math.round(6.4 * cq), lineHeight: 0.86, letterSpacing: '-0.05em', color: INK }}>calcite</div>
				</div>
			</div>
		</div>
	),
	{ width: W, height: H, fonts: [{ name: 'Bricolage', data: readFileSync(join(fonts, 'BricolageGrotesque-ExtraBold.ttf')), weight: 800, style: 'normal' }] },
);
const out = join(process.cwd(), '../assets/logo/calcite-banner.png');
writeFileSync(out, Buffer.from(await img.arrayBuffer()));
console.log('wrote', out);
