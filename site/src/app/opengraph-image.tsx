import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { ordered } from '@/lib/dither/bayer';
import { markBits } from '@/lib/dither/mark';
import { INK, PAPER } from '@/lib/dither/math';
import { CAMS, fade, view } from '@/lib/brand/terrain';
import { bitsToPNG } from '@/lib/png';

// The card link previews show: the mark and the name over the world, seen from the ground, in one
// ink, every dot a whole 2 × 2 pixels. The text is set, not dithered, as the brand has it.

export const alt = 'calcite: a Minecraft server written in Calx';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const url = (png: Buffer) => `data:image/png;base64,${png.toString('base64')}`;

export default async function Image() {
	const fonts = join(process.cwd(), 'src/app/fonts');
	const [display, mono] = await Promise.all([readFile(join(fonts, 'BricolageGrotesque-ExtraBold.ttf')), readFile(join(fonts, 'DMMono-Regular.ttf'))]);

	const cols = 600, rows = 170, tone = new Float32Array(cols * rows);
	view(tone, cols, rows, CAMS.social, { horizon: 0.18 });
	fade(tone, cols, rows, { t: 0.4 });
	const world = url(bitsToPNG(ordered(tone, cols, rows, 8), cols, rows, 2, INK, PAPER));
	const mark = url(bitsToPNG(markBits(32), 32, 32, 4, INK, null));

	return new ImageResponse(
		(
			<div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: PAPER, color: INK, position: 'relative' }}>
				<div style={{ display: 'flex', alignItems: 'center', padding: '72px 72px 0', gap: 34 }}>
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src={mark} width={128} height={128} alt="" />
					<div style={{ fontFamily: 'Bricolage', fontSize: 168, lineHeight: 0.86, letterSpacing: '-0.05em' }}>calcite</div>
				</div>
				<div style={{ display: 'flex', padding: '40px 76px 0', fontFamily: 'DM Mono', fontSize: 30, lineHeight: 1.4 }}>a Minecraft: Java Edition server written in Calx</div>
				{/* eslint-disable-next-line @next/next/no-img-element */}
				<img src={world} width={1200} height={340} alt="" style={{ position: 'absolute', left: 0, bottom: 0 }} />
			</div>
		),
		{
			...size,
			fonts: [
				{ name: 'Bricolage', data: display, weight: 800, style: 'normal' },
				{ name: 'DM Mono', data: mono, weight: 400, style: 'normal' },
			],
		},
	);
}
