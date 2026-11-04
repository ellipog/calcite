import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { ordered } from '@/lib/dither/bayer';
import { markBits } from '@/lib/dither/mark';
import { INK, PAPER } from '@/lib/dither/math';
import { CAMS, fade, view } from '@/lib/brand/terrain';
import { snippet } from '@/lib/meta';
import { bitsToPNG } from '@/lib/png';

// A page's card for link previews: the mark and the name small, the section, the page's title
// large and what it's about, over a strip of the world, in one ink, every dot a whole 2 × 2
// pixels. Each section looks at the world from somewhere else. The home page's card, with the
// name large, is app/opengraph-image.tsx.

export const CARD = { width: 1200, height: 630 };

const url = (png: Buffer) => `data:image/png;base64,${png.toString('base64')}`;

export async function card({ kicker, title, line, cam = 'social' }: { kicker: string; title: string; line: string; cam?: keyof typeof CAMS }) {
	const fonts = join(process.cwd(), 'src/app/fonts');
	const [display, mono] = await Promise.all([readFile(join(fonts, 'BricolageGrotesque-ExtraBold.ttf')), readFile(join(fonts, 'DMMono-Regular.ttf'))]);

	const cols = 600, rows = 90, tone = new Float32Array(cols * rows);
	view(tone, cols, rows, CAMS[cam], { horizon: 0.3 });
	fade(tone, cols, rows, { t: 0.6 });
	const world = url(bitsToPNG(ordered(tone, cols, rows, 8), cols, rows, 2, INK, PAPER));
	const mark = url(bitsToPNG(markBits(32), 32, 32, 2, INK, null));
	// a long title steps down a size, so it stays on a line and the words under it clear the world
	const big = title.length > 16 ? 84 : 112;

	return new ImageResponse(
		(
			<div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: PAPER, color: INK, position: 'relative' }}>
				{/* eslint-disable-next-line @next/next/no-img-element */}
				<img src={world} width={1200} height={180} alt="" style={{ position: 'absolute', left: 0, bottom: 0 }} />
				<div style={{ display: 'flex', alignItems: 'center', padding: '60px 72px 0', gap: 18 }}>
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src={mark} width={64} height={64} alt="" />
					<div style={{ fontFamily: 'Bricolage', fontSize: 64, lineHeight: 0.86, letterSpacing: '-0.05em' }}>calcite</div>
					<div style={{ fontFamily: 'DM Mono', fontSize: 24, letterSpacing: '0.08em', textTransform: 'uppercase', marginLeft: 'auto' }}>{kicker}</div>
				</div>
				<div style={{ display: 'flex', padding: '56px 72px 0', fontFamily: 'Bricolage', fontSize: big, lineHeight: 0.92, letterSpacing: '-0.045em', maxWidth: 1100 }}>{title}</div>
				<div style={{ display: 'flex', padding: '28px 76px 0', fontFamily: 'DM Mono', fontSize: 26, lineHeight: 1.4, maxWidth: 1080 }}>{snippet(line, 160)}</div>
			</div>
		),
		{
			...CARD,
			fonts: [
				{ name: 'Bricolage', data: display, weight: 800, style: 'normal' },
				{ name: 'DM Mono', data: mono, weight: 400, style: 'normal' },
			],
		},
	);
}
