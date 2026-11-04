'use client';

import { useState } from 'react';
import { Bitmap } from '@/components/mark';
import { Panel, Rules } from '@/components/ui/text';
import { Slider } from '@/components/ui/slider';
import { Sub } from '@/components/ui/sub';
import { diffuse, ordered, rank, type Bits } from '@/lib/dither/bayer';
import { rng } from '@/lib/dither/math';
import { level8, tileURL } from '@/lib/dither/tiles';
import { ICONS } from '@/lib/brand/icons';
import { CAMS, still } from '@/lib/brand/terrain';
import { Crystal, Drawn, drawMap } from '@/components/pictures';
import { cn } from '@/lib/cn';
import { Cap, H3, Section } from './_parts';

const R8 = rank(8);

/* ---- 05 · dither ------------------------------------------------------------------------------- */

const PATS: [string, string, (t: Float32Array, c: number, r: number) => Bits][] = [
	['Bayer 2×2', '5 levels · favicons', (t, c, r) => ordered(t, c, r, 2)],
	['Bayer 4×4', '17 levels · icons', (t, c, r) => ordered(t, c, r, 4)],
	['Bayer 8×8', '65 levels · the house pattern', (t, c, r) => ordered(t, c, r, 8)],
	['Atkinson', 'photos and screenshots only', (t, c, r) => diffuse(t, c, r, 'atkinson')],
	['Floyd–Steinberg', 'not used: wormy', (t, c, r) => diffuse(t, c, r, 'floyd')],
	[
		'Random',
		'not used: noisy',
		(t) => {
			const rn = rng(7);
			return Uint8Array.from(t, (v) => (v > rn() ? 1 : 0));
		},
	],
];

export function Dither() {
	const [k, setK] = useState(23);
	return (
		<Section id="dither" n={5} name="Dither" title="Bayer 8×8, almost always." lead="Every shade comes from one 8×8 threshold matrix. A cell is inked when the tone is above its number, so a tone of 23 inks the 23 lowest cells, spread as evenly as 64 cells allow. It tiles without seams, stays still from frame to frame, and gives that even cross-hatch that reads as printed.">
			<div className="grid grid-cols-1 items-start gap-9 md:grid-cols-[auto_minmax(0,1fr)]">
				<div className="grid w-max grid-cols-[repeat(8,34px)] grid-rows-[repeat(8,34px)] border border-ink xs:grid-cols-[repeat(8,44px)] xs:grid-rows-[repeat(8,44px)]" aria-label="The Bayer 8 by 8 matrix">
					{R8.map((v, i) => (
						<div key={i} className={cn('grid place-items-center font-mono text-[10px] leading-none xs:text-xs', i % 8 < 7 && 'rule-r', i < 56 && 'rule-b', v < k && 'bg-ink text-paper')}>
							{v}
						</div>
					))}
				</div>
				<div className="grid gap-3.5">
					<div className="font-display text-[56px] leading-none font-extrabold tracking-title">
						{k}
						<small className="ml-2 font-mono text-sm font-normal tracking-normal">
							/ 64 · {Math.round((k / 64) * 100)}%
						</small>
					</div>
					<Slider label="Tone" min={0} max={64} step={1} value={k} onValueChange={setK} format={(v) => `${v} of 64 cells`} pattern="halftone" />
					<div className={cn('h-[120px] rule bg-size-[16px_16px]', k >= 64 && 'bg-ink')} style={k > 0 && k < 64 ? { backgroundImage: tileURL(8, 8, level8((k / 64) * 100)) } : undefined} />
					<p className="note">Drag to change the tone. The inked cells in the matrix are the ones the tile repeats.</p>
				</div>
			</div>
			<Sub>The same ramp, six ways</Sub>
			<div>
				{PATS.map(([name, note, fn], i) => (
					<div key={name} className={cn('grid items-center gap-1.5 rule-t py-2.5 sm:grid-cols-[190px_minmax(0,1fr)] sm:gap-4', i === PATS.length - 1 && 'rule-b')}>
						<b className="font-mono text-[13px] leading-[1.4] font-medium">
							{name}
							<small className="block font-normal">{note}</small>
						</b>
						<Drawn
							className="h-11 w-full"
							draw={(s) => {
								const t = new Float32Array(s.cols * s.rows);
								for (let y = 0; y < s.rows; y++) for (let x = 0; x < s.cols; x++) t[y * s.cols + x] = x / (s.cols - 1);
								s.bits(fn(t, s.cols, s.rows));
								s.flush();
							}}
						/>
					</div>
				))}
			</div>
			<div className="mt-7 grid grid-cols-1 gap-5 md:grid-cols-3">
				<Panel>
					<H3>8×8</H3>
					<p>Everything: pictures, tints, motion, charts, the mark from 32 cells up. 64 levels, so ramps stay smooth.</p>
				</Panel>
				<Panel>
					<H3>4×4 and 2×2</H3>
					<p>Only for grids too small for 8×8 to show its levels: icons, marks under 32 cells, favicons.</p>
				</Panel>
				<Panel>
					<H3>Atkinson</H3>
					<p>Only for real photos and screenshots, where an even pattern would flatten detail. Never Floyd–Steinberg or random noise.</p>
				</Panel>
			</div>
			<Rules className="mt-7" items={['A dot is 2 CSS pixels and a whole number of screen pixels, so it stays crisp at any zoom.', 'Pictures fade to paper at their edges through the same matrix, instead of stopping at a frame.', 'Dither pictures and fills, never text. Text that crosses dots gets a block of paper behind it.']} />
		</Section>
	);
}

/* ---- 06 · imagery ------------------------------------------------------------------------------ */

export function Imagery() {
	return (
		<Section id="imagery" n={6} name="Imagery" title="Worlds, made by code." lead="Three kinds of picture, all generated, all one ink: a world seen from the ground, a world seen from above, and the crystal the server is named after.">
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel label="From above · relief and contours" className="overflow-hidden p-0">
					<Drawn className="h-[300px] w-full" draw={(sf) => drawMap(sf)} label="A generated world from above, in relief with contours" />
				</Panel>
				<Panel label="The crystal · drag to turn" className="overflow-hidden p-0">
					<Crystal />
				</Panel>
			</div>
			<Sub>Photos and screenshots</Sub>
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel label="Bayer 8×8 · generated pictures" className="overflow-hidden p-0">
					<Drawn className="h-[300px] w-full" draw={(_, c) => still(c, CAMS.cmp, { fade: { b: 0.12 } })} />
				</Panel>
				<Panel label="Atkinson · photos only" className="overflow-hidden p-0">
					<Drawn className="h-[300px] w-full" draw={(_, c) => still(c, CAMS.cmp, { fade: { b: 0.12 }, diffuse: true })} />
				</Panel>
			</div>
			<Cap>The same view both ways. Generated pictures stay on the 8×8 pattern; a real photo or game screenshot gets Atkinson, because an even pattern would flatten it.</Cap>
		</Section>
	);
}

/* ---- 07 · icons -------------------------------------------------------------------------------- */

export function Icons() {
	const names = Object.keys(ICONS) as (keyof typeof ICONS)[];
	return (
		<Section id="icons" n={7} name="Icons" title="Sixteen cells, three densities." lead="Icons are drawn on a 16-cell grid with a solid one-cell outline, filled at 12, 50 or 88% with the 4×4 matrix. Square corners only. Shown here at 2 px a cell, and below at 1 px.">
			<div className="grid grid-cols-4 rule md:grid-cols-8">
				{names.map((name, i) => (
					<figure key={name} className={cn('m-0 grid justify-items-center gap-3 px-1.5 pt-[22px] pb-3.5 font-mono text-[11px] leading-none', i < names.length - 1 && 'rule-r', i === 3 && 'max-md:border-r-0', i < 4 && 'max-md:rule-b')}>
						<Bitmap bits={ICONS[name]} n={16} size={32} />
						<span>{name}</span>
					</figure>
				))}
			</div>
			<div className="mt-[18px] flex flex-wrap items-center gap-[18px] font-mono text-xs leading-none">
				{names.map((name) => (
					<Bitmap key={name} bits={ICONS[name]} n={16} size={16} />
				))}
				<span>at 16 px, 1 px a cell</span>
			</div>
		</Section>
	);
}
