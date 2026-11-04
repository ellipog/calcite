import { Panel, Rules } from '@/components/ui/text';
import { Sub } from '@/components/ui/sub';
import { contrast, INK, PAPER } from '@/lib/dither/math';
import { cn } from '@/lib/cn';
import { Cap, H3, Section } from './_parts';

// The guide's sections with nothing drawn by script: rendered on the server as they are.

export function Idea() {
	const q = 'flex aspect-square flex-col justify-end pt-11 max-lg:aspect-auto max-lg:min-h-[220px] max-sm:min-h-0';
	return (
		<Section id="idea" n={1} name="Idea" title="One ink. Paper does the rest." lead="Even the boxes on this page are leaves of the mark: one square split into four beside a whole one, solid where it matters, dotted out of view.">
			<div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
				<Panel label="in view" inverse className="flex aspect-square flex-col justify-between px-[34px] pt-9 pb-[30px] sm:col-span-2 lg:row-span-2 max-lg:aspect-auto max-lg:min-h-[380px]">
					<p className="max-w-[34ch] font-display text-[clamp(24px,2.6vw,34px)] leading-[1.22] font-semibold tracking-tight text-balance">Everything is printed in one cobalt ink on white. There are no tints and no greys: every shade is a pattern of dots, the way a one-colour print or a 1-bit screen does it.</p>
					<div className="mt-7 flex flex-wrap gap-2">
						{['one ink', 'dots', 'printed', 'generated', 'exact', 'light'].map((k) => (
							<span key={k} className="border border-dotted border-paper px-3 py-[9px] font-mono text-[13px] leading-none">
								{k}
							</span>
						))}
					</div>
				</Panel>
				<Panel label="one ink" className={q}>
					<H3>One ink</H3>
					<p>Cobalt and paper, nothing else. Hierarchy comes from size, weight and density, never from a second colour.</p>
				</Panel>
				<Panel label="dots" className={q}>
					<H3>Dots, not tints</H3>
					<p>A lighter blue is a Bayer 8×8 pattern of solid dots: in the mark, the pictures, a state like busy or off.</p>
				</Panel>
				<Panel label="generated" className={q}>
					<H3>Generated</H3>
					<p>The pictures are worlds made by code, as Calcite&apos;s are. The mark is too: a quadtree, worked out.</p>
				</Panel>
				<Panel label="out of view" className={cn(q, 'justify-between tint-12')}>
					<span />
					<p className="bg-paper px-2.5 py-2 font-mono text-xs leading-[1.6]">12% · the squares the view doesn&apos;t reach</p>
				</Panel>
			</div>
		</Section>
	);
}

const LEVELS = [6, 12, 25, 31, 38, 50, 62, 75, 88, 100];
const TINT: Record<number, string> = { 6: 'tint-6', 12: 'tint-12', 25: 'tint-25', 31: 'tint-31', 38: 'tint-38', 50: 'tint-50', 62: 'tint-62', 75: 'tint-75', 88: 'tint-88', 100: 'tint-100' };
export { TINT };

export function Colour() {
	return (
		<Section id="colour" n={3} name="Colour" title="Cobalt on paper." lead="Two colours, and only two. Text is always solid ink, or solid paper on a block of ink. Every lighter blue is one of the densities below.">
			<div className="grid grid-cols-1 rule sm:grid-cols-2">
				<div className="flex min-h-[220px] flex-col justify-between bg-ink p-[22px] text-paper">
					<b className="font-display text-[40px] leading-none font-extrabold tracking-title">Cobalt</b>
					<span className="font-mono text-[13px] leading-[1.7]">
						#1838D0
						<br />
						rgb 24 56 208
						<br />
						the one ink
					</span>
				</div>
				<div className="flex min-h-[220px] flex-col justify-between p-[22px]">
					<b className="font-display text-[40px] leading-none font-extrabold tracking-title">Paper</b>
					<span className="font-mono text-[13px] leading-[1.7]">
						#F8F8F5
						<br />
						rgb 248 248 245
						<br />
						everything else
					</span>
				</div>
			</div>
			<Sub>Densities · levels of the 8×8 matrix</Sub>
			<div className="grid grid-cols-5 rule md:grid-cols-10">
				{LEVELS.map((p, i) => (
					<div key={p} className={cn('relative h-[120px]', TINT[p], i < LEVELS.length - 1 && 'rule-r', i < 5 && 'max-md:rule-b', i === 4 && 'max-md:border-r-0')}>
						<span className="absolute bottom-1.5 left-1.5 bg-paper px-[5px] py-[3px] font-mono text-[11px] leading-[1.3]">
							{p}%
							<br />
							{Math.round((p * 64) / 100)}/64
						</span>
					</div>
				))}
			</div>
			<Cap>Each is a 16 px tile, 2 px a dot, made from the matrix in section 05. In CSS a tint is a background image, never a colour: the tint-* utilities.</Cap>
			<Sub>Contrast</Sub>
			<div className="flex flex-wrap items-stretch gap-5">
				<div className="flex-[1_1_220px] rule px-5 py-[18px]">
					<span className="note">cobalt on paper</span>
					<b className="mt-2 mb-1.5 block font-display text-[44px] leading-none font-extrabold tracking-[-0.03em]">{contrast(INK, PAPER).toFixed(1)} : 1</b>
					<span className="note">AAA for text at any size</span>
				</div>
				<div className="flex-[1_1_220px] border border-ink bg-ink px-5 py-[18px] text-paper">
					<span className="note">paper on cobalt</span>
					<b className="mt-2 mb-1.5 block font-display text-[44px] leading-none font-extrabold tracking-[-0.03em]">{contrast(PAPER, INK).toFixed(1)} : 1</b>
					<span className="note">reversed text and buttons</span>
				</div>
				<div className="grid flex-[1_1_220px] content-start justify-items-start gap-2 rule px-5 py-[18px] tint-25">
					<span className="note bg-paper px-1.5 py-0.5">text over dots</span>
					<b className="bg-paper px-2 pb-1 font-display text-[44px] leading-none font-extrabold tracking-[-0.03em]">on paper</b>
					<span className="note bg-paper px-1.5 py-0.5">always on a block of its own</span>
				</div>
			</div>
		</Section>
	);
}

const SCALE: [string, string, string, string][] = [
	['Display', '800 · 96 / 0.88 · −0.045em', 'font-display text-[clamp(52px,8vw,96px)] leading-[0.88] font-extrabold tracking-display', 'Made of dots.'],
	['Title', '800 · 64 / 0.94 · −0.04em', 'font-display text-[clamp(40px,6vw,64px)] leading-[0.94] font-extrabold tracking-title', 'The same world, made faster.'],
	['Heading', '800 · 44 / 1 · −0.04em', 'font-display text-[clamp(32px,4.4vw,44px)] leading-none font-extrabold tracking-title', 'Pregenerating chunks'],
	['Subhead', '600 · 26 / 1.25 · −0.02em', 'font-display text-[26px] leading-tight font-semibold tracking-tight', 'Every region on its own core, ticking in lockstep.'],
	['Text', '400 · 17 / 1.6', 'max-w-[62ch]', "With Terralith and Terratonic, every one of 264 sampled chunks has what must be vanilla's. The blocks that differ are those the order chunks are decorated in decides, which vanilla doesn't fix either."],
	['Small', '400 · 14 / 1.5', 'max-w-[70ch] text-sm leading-normal', "On the benchmarks' reference machine, an i9-13900K. Calcite targets Minecraft Java Edition 26.3."],
];

export function Type() {
	return (
		<Section id="type" n={4} name="Type" title="Heavy, then plain." lead="Bricolage Grotesque for everything you read, from 800 for display to 400 for text, with its optical sizes on. DM Mono for numbers, units, labels and code.">
			<div className="rule-t">
				{SCALE.map(([k, spec, cls, text]) => (
					<div key={k} className="grid grid-cols-1 items-baseline gap-1.5 rule-b py-[22px] md:grid-cols-[180px_minmax(0,1fr)] md:gap-6">
						<div className="font-mono text-xs leading-[1.6]">
							<b className="block font-medium">{k}</b>
							{spec}
						</div>
						<div className={cn('min-w-0 [overflow-wrap:anywhere]', cls)}>{text}</div>
					</div>
				))}
				<div className="grid grid-cols-1 items-baseline gap-1.5 rule-b py-[22px] md:grid-cols-[180px_minmax(0,1fr)] md:gap-6">
					<div className="font-mono text-xs leading-[1.6]">
						<b className="block font-medium">Mono</b>DM Mono 400 / 500 · 13
					</div>
					<div className="font-mono text-[13px] leading-[1.8]">
						150.6 · 1,014.1 · 2,022.1 chunks/s at 1 · 8 · 32 threads
						<br />
						LABELS IN CAPS, TRACKED 0.06EM
					</div>
				</div>
			</div>
			<div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel>
					<H3>Do</H3>
					<Rules items={['Write the name lowercase: calcite. Calx keeps its capital.', 'Sentence case for headings, a full stop on display lines.', 'Every number in mono, with its unit and where it was measured.']} />
				</Panel>
				<Panel>
					<H3>Don&apos;t</H3>
					<Rules no items={['Italics, outlines or shadows on type.', 'All caps outside small mono labels.', 'Dither, stretch or condense the type, or set it in a tint.']} />
				</Panel>
			</div>
		</Section>
	);
}

export function Voice() {
	const line = 'rule-t py-5 font-display text-[clamp(34px,5vw,62px)] leading-none font-extrabold tracking-display';
	return (
		<Section id="voice" n={12} name="Voice" title="Plain and printed." lead="Short sentences, the name in lowercase, no exclamation marks. It should read like a well-set manual: say what it does, give the number, stop.">
			{[
				['worlds, one dot at a time.', 'for the project'],
				['the same world, made faster.', 'for worldgen and benchmarks'],
				['the same light in every block.', 'for the light engine'],
			].map(([t, s], i) => (
				<div key={t} className={cn(line, i === 2 && 'rule-b')}>
					{t}
					<small className="mt-2.5 block font-mono text-xs leading-[1.6] font-normal tracking-normal">{s}</small>
				</div>
			))}
			<div className="mt-10 grid grid-cols-1 rule sm:grid-cols-2">
				<div className="px-[22px] py-5">
					<H3>Say</H3>
					<p className="font-mono text-sm leading-[2]">
						matches vanilla&apos;s
						<br />
						on our benchmark machine
						<br />
						written in Calx
						<br />
						every region on its own core
						<br />
						chunks in view
					</p>
				</div>
				<div className="px-[22px] py-5 max-sm:rule-t sm:rule-l">
					<H3>Don&apos;t say</H3>
					<p className="font-mono text-sm leading-[2]">
						blazing fast
						<br />
						revolutionary
						<br />
						100% vanilla
						<br />
						the best server
						<br />
						numbers without a source
					</p>
				</div>
			</div>
		</Section>
	);
}
