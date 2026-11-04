// Writes ../assets/logo/calcite-banner.png, the README's header, as the home page's first screen:
// the kicker and the name on the left, the lead on the right, and under them the flight's world, the
// hero's own first frame (firstFrame in src/lib/brand/hero.ts), its sky dissolving into the paper.
// 1600 × 704, in one ink, every dot of the world 2 × 2 pixels. It has its own paper, so it reads the
// same on GitHub's light and dark themes. Run from site/: bun run banner

import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { BANNER_SEED, firstFrame } from '../src/lib/brand/hero';
import { INK, PAPER } from '../src/lib/dither/math';
import { bitsToPNG } from '../src/lib/png';
import { SITE } from '../src/lib/site';

const W = 1600, H = 704;
/** Where the world's band starts, a little under the name. */
const TOP = 284;
/** The left edge everything lines up on, as the site's frame does. */
const SIDE = 64;

const fonts = join(process.cwd(), 'src/app/fonts');
const url = (png: Buffer) => `data:image/png;base64,${png.toString('base64')}`;

const cols = W / 2, rows = (H - TOP) / 2, px = new Uint32Array(cols * rows);
firstFrame(px, cols, rows, BANNER_SEED);
const bits = new Uint8Array(cols * rows);
for (let i = 0; i < bits.length; i++) bits[i] = px[i] ? 1 : 0;
const world = url(bitsToPNG(bits, cols, rows, 2, INK, PAPER));

const img = new ImageResponse(
	(
		<div style={{ width: '100%', height: '100%', display: 'flex', background: PAPER, color: INK, position: 'relative' }}>
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={world} width={W} height={H - TOP} alt="" style={{ position: 'absolute', left: 0, top: TOP }} />
			<div style={{ position: 'absolute', left: SIDE, right: SIDE, top: 56, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
				<div style={{ display: 'flex', flexDirection: 'column' }}>
					{/* the kicker, its dotted rule after it */}
					<div style={{ display: 'flex', alignItems: 'center', gap: 20, fontFamily: 'DM Mono', fontSize: 20, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
						Minecraft: Java Edition {SITE.minecraft}
						<div style={{ display: 'flex', gap: 6 }}>
							{Array.from({ length: 9 }, (_, i) => (
								<div key={i} style={{ width: 2, height: 2, background: INK }} />
							))}
						</div>
					</div>
					<div style={{ fontFamily: 'Bricolage', fontWeight: 800, fontSize: 236, lineHeight: 0.8, letterSpacing: '-0.045em', marginTop: 22, marginLeft: -8 }}>calcite</div>
				</div>
				<div style={{ display: 'flex', width: 640, fontFamily: 'Bricolage', fontWeight: 400, fontSize: 30, lineHeight: 1.45, marginBottom: 2 }}>{SITE.lead}</div>
			</div>
		</div>
	),
	{
		width: W,
		height: H,
		fonts: [
			{ name: 'Bricolage', data: readFileSync(join(fonts, 'BricolageGrotesque-ExtraBold.ttf')), weight: 800, style: 'normal' },
			{ name: 'Bricolage', data: readFileSync(join(fonts, 'BricolageGrotesque-Regular.woff')), weight: 400, style: 'normal' },
			{ name: 'DM Mono', data: readFileSync(join(fonts, 'DMMono-Regular.ttf')), weight: 400, style: 'normal' },
		],
	},
);
const out = join(process.cwd(), '../assets/logo/calcite-banner.png');
writeFileSync(out, Buffer.from(await img.arrayBuffer()));
console.log('wrote', out);
