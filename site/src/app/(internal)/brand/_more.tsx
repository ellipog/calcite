'use client';

import { useMemo, useRef } from 'react';
import { Bitmap, Mark } from '@/components/mark';
import { Button, ButtonLink } from '@/components/ui/button';
import { Callout, Disclosure, Table } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Sub } from '@/components/ui/sub';
import { Field } from '@/components/ui/form';
import { Panel, Rules, TextLink } from '@/components/ui/text';
import { ordered, threshold } from '@/lib/dither/bayer';
import { painter, surface, type Surface } from '@/lib/dither/canvas';
import { markBits, markSVG, MARK } from '@/lib/dither/mark';
import { PAPER } from '@/lib/dither/math';
import { useFrames, useSized, useSteps, still as stillMotion } from '@/lib/dither/motion';
import { DATA } from '@/lib/data';
import { markPNG, pngBlob, save, socialCard, wordMask } from '@/lib/brand/files';
import { ICONS } from '@/lib/brand/icons';
import { BANNER_SEED, firstFrame } from '@/lib/brand/hero';
import { CAMS, still } from '@/lib/brand/terrain';
import { SITE } from '@/lib/site';
import { cn } from '@/lib/cn';
import { BarChart, LineChart, type LineCfg } from '@/components/charts';
import { Cap, Section, Wm } from './_parts';

const fmt = (v: number, d = 1) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const threads = (n: number) => `${n} thread${n > 1 ? 's' : ''}`;
// Vanilla's own worldgen through the whole server, now (data.ts) and at 868e0a0 (bench/README.md).
const BEFORE: Record<number, number> = Object.fromEntries(DATA.worldgen.runs.map((r, i) => [r.threads, DATA.worldgen.before.cps[i]]));
const GEN = DATA.worldgen.runs.map((r) => ({ th: r.threads, now: r.cps, then: BEFORE[r.threads], steady: r.steady, mem: Math.round(r.mem) }));
const FLY = DATA.flight.runs;

/* ---- 08 · UI: a few of them, and the sheet with all of them ----------------------------------- */

export function UI() {
	return (
		<Section id="ui" n={8} name="UI" title="Square, dotted, solid when it matters." lead="Components for the website and docs. Corners are square, borders are dotted, the one solid thing in a view is the action you want. Changes of state step through the matrix; hovers are crisp, a frame or line going solid, never dots under the pointer.">
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel label="A few of them" className="grid content-start gap-[18px]">
					<div className="flex flex-wrap gap-2.5">
						<Button>Download</Button>
						<Button variant="secondary">Read the docs</Button>
					</div>
					<Field label="Server address" placeholder="play.example.net" />
					<Slider label="View distance" min={2} max={32} step={1} defaultValue={12} unit="chunks" />
					<Progress label="pregen" value={0.61} />
				</Panel>
				<Panel label="All of them" className="grid content-start gap-[18px]">
					<p>Every component, with every state, is on the component sheet: buttons, fields, checks, switches, segments, the slider in its four patterns, tabs, disclosures, tags, callouts, progress, placeholders, toasts, dialogs, code and tables.</p>
					<div>
						<ButtonLink href="/components" variant="secondary">
							Open the component sheet
						</ButtonLink>
					</div>
					<p className="note">They live in src/components/ui and are shared with the public site. The sheet and this guide are internal: they exist under next dev only.</p>
				</Panel>
			</div>
		</Section>
	);
}

/* ---- 09 · charts -------------------------------------------------------------------------------- */

export function Charts() {
	const flight = useMemo(() => {
		const cfg = (v: '25' | '100'): LineCfg => ({
			x: [0, 30],
			y: [0, 100],
			xTicks: [0, 10, 20, 30],
			yTicks: [0, 25, 50, 75, 100],
			xFmt: (t) => (t === 30 ? '30 s' : `${t}`),
			yFmt: (p) => (p === 100 ? '100%' : `${p}`),
			series: [{ pts: FLY[v].samples, area: 0.62, end: `<b>${fmt(FLY[v].had[0])}%</b><br>on average` }],
			endW: 96,
			tip: (t, s) => `<b>${fmt(t, 1)} s</b> into the flight at ${v}×<br>${fmt(s[0][1])}% of the view`,
		});
		return { '25': cfg('25'), '100': cfg('100') };
	}, []);
	const gen = useMemo<LineCfg>(
		() => ({
			x: [0, 32],
			y: [0, 2100],
			xTicks: [1, 8, 16, 32],
			yTicks: [0, 500, 1000, 1500, 2000],
			xFmt: (v) => (v === 32 ? '32 threads' : `${v}`),
			yFmt: (v) => v.toLocaleString('en-US'),
			series: [
				{ pts: GEN.map((r) => [r.th, r.now] as const), area: 0.62, markers: true, end: `<b>now</b> · ${fmt(GEN[3].now, 0)}` },
				{ pts: GEN.map((r) => [r.th, r.then] as const), dotted: true, markers: true, end: `868e0a0 · ${fmt(GEN[3].then, 0)}` },
			],
			endW: 128,
			tip: (x, v) => `<b>${threads(x)}</b><br>now ${fmt(v[0][1])} chunks/s<br>868e0a0 ${fmt(v[1][1])}<br>${fmt(v[0][1] / v[1][1], 2)}× as fast`,
		}),
		[],
	);
	const fig = 'flex items-baseline justify-between gap-4 rule-b pb-2.5 mb-3';
	const tiles: [string, string, string][] = [
		['One thread', '150.6', 'chunks a second, each lit, saved and deflated'],
		['Join', '3.1 s', "3,725 chunks to Mojang's client at view 32"],
		['Flying at 25×', '97.9%', 'of its view the client had, on average'],
	];
	return (
		<Section id="charts" n={9} name="Charts" title="Solid for now, dots for the rest." lead="With one ink, a chart can't tell series apart by colour, so it uses the line: solid for what the chart is about, with a gradient of dots under it, densest at the baseline, and a dotted line for what it's compared with. Where the lines would cross and tangle, it's two charts on one scale instead. Every line is named at its end. Charts rise from the baseline through the 8×8 matrix as they come into view.">
			<div className="grid grid-cols-2 rule lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
				<div className="rule-r px-[22px] py-5 max-lg:rule-b">
					<span className="label leading-none">Worldgen · 32 threads</span>
					<b className="mt-2.5 mb-2 block font-display text-[64px] leading-none font-extrabold tracking-[-0.035em]">2,022</b>
					<span className="block font-mono text-xs leading-normal">chunks a second of vanilla&apos;s worldgen, through the whole server</span>
				</div>
				{tiles.map(([l, v, s], i) => (
					<div key={l} className={cn('px-[22px] py-5', i < 2 && 'lg:rule-r', i === 0 && 'max-lg:rule-b', i === 1 && 'max-lg:rule-r')}>
						<span className="label leading-none">{l}</span>
						<b className="mt-2.5 mb-2 block font-display text-4xl leading-none font-extrabold tracking-[-0.035em]">{v}</b>
						<span className="block font-mono text-xs leading-normal">{s}</span>
					</div>
				))}
			</div>
			<figure className="m-0 mt-12">
				<figcaption className={fig}>
					<b className="font-display text-lg leading-tight font-bold">How much of its view Mojang&apos;s client had while flying</b>
					<span className="text-right font-mono text-[11px] leading-[1.4]">% of view distance 32 · 30 s flights · one scale · higher is better</span>
				</figcaption>
				<div className="grid grid-cols-1 gap-10 md:grid-cols-2">
					<div>
						<p className="mb-2 font-mono text-xs leading-[1.4]">At 25× vanilla&apos;s speed, 269 blocks a second</p>
						<LineChart cfg={flight['25']} label="Line chart: share of the view the client had flying at 25 times vanilla's speed" />
					</div>
					<div>
						<p className="mb-2 font-mono text-xs leading-[1.4]">At 100×, faster than chunks can be made</p>
						<LineChart cfg={flight['100']} label="Line chart: share of the view the client had flying at 100 times vanilla's speed" />
					</div>
				</div>
			</figure>
			<div className="mt-12 grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
				<figure className="m-0">
					<figcaption className={fig}>
						<b className="font-display text-lg leading-tight font-bold">Chunks a second, by threads</b>
						<span className="text-right font-mono text-[11px] leading-[1.4]">vanilla&apos;s worldgen · higher is better</span>
					</figcaption>
					<div className="mb-2.5 flex flex-wrap gap-[18px] font-mono text-xs leading-none">
						<span>
							<i className="mr-[7px] inline-block h-0.5 w-4 bg-ink align-[3px]" />
							now
						</span>
						<span>
							<i className="mr-[7px] inline-block h-0.5 w-4 bg-(image:--u50) bg-size-[8px_2px] align-[3px]" />
							at 868e0a0
						</span>
					</div>
					<LineChart cfg={gen} className="h-[260px]" label="Line chart: chunks a second by thread count, now and at 868e0a0" />
				</figure>
				<figure className="m-0">
					<figcaption className={fig}>
						<b className="font-display text-lg leading-tight font-bold">Peak memory</b>
						<span className="text-right font-mono text-[11px] leading-[1.4]">MiB · lower is better</span>
					</figcaption>
					<div className="mb-2.5 font-mono text-xs leading-none">
						<i className="mr-[7px] inline-block h-2.5 w-4 tint-38 align-[-1px]" />
						now
					</div>
					<BarChart rows={GEN.map((r) => ({ name: threads(r.th), v: r.mem, label: `${r.mem}`, aria: `${threads(r.th)}: ${r.mem} MiB at most`, tip: `<b>${threads(r.th)}</b><br>${r.mem} MiB at most` }))} />
				</figure>
			</div>
			<Disclosure summary="Table view" className="mt-7">
				<Table className="mt-2" columns={[{ label: 'threads' }, { label: 'chunks/s', num: true }, { label: 'at 868e0a0', num: true }, { label: 'steady', num: true }, { label: 'peak memory', num: true }]} rows={GEN.map((r) => [r.th, fmt(r.now), fmt(r.then), r.steady ? fmt(r.steady) : '–', `${r.mem} MiB`])} />
				<Table className="mt-5" columns={[{ label: 'flight' }, { label: 'on average', num: true }, { label: 'at least', num: true }, { label: 'samples', num: true }]} rows={Object.entries(FLY).map(([v, f]) => [`${v}× vanilla's speed`, `${fmt(f.had[0])}%`, `${fmt(f.had[1])}%`, f.samples.length])} />
			</Disclosure>
			<Cap>The real-client flights from bench/results/client-windows.json, and vanilla&apos;s worldgen, no packs, through the whole server, from worldgen-windows.json: both on the reference machine, an i9-13900K.</Cap>
			<Rules className="mt-[22px]" items={['Lines are one dot thick, 2 px, with square ends and corners. Bars are square at both ends.', "A bar chart's longest bar fills its width, less room for its value, so a chart that switches what it shows rescales to it.",'Light gridlines of sparse dots, labels in mono outside the plot, values at the line ends. Where a gridline crosses the dense part of an area it turns to paper dots.', 'The reveal is a front of the 8×8 matrix rising from the baseline in 50 ms steps, once. With reduced motion, the chart is simply there.', 'Hover or focus a chart for its values; arrow keys step through them. Every chart has a table view.', 'Two measures, two charts. Never a second axis.']} />
		</Section>
	);
}

/* ---- 10 · motion -------------------------------------------------------------------------------- */

function DissolveIn() {
	const cv = useRef<HTMLCanvasElement>(null), st = useRef({ S: null as Surface | null, mask: new Float32Array(0), t0: 0, last: -1 });
	const render = (k: number) => {
		const { S, mask } = st.current;
		if (!S) return;
		S.bits(ordered(mask.map((v) => (v * k) / 8), S.cols, S.rows, 8));
		S.flush();
	};
	useSized(cv, () => {
		const S = (st.current.S = surface(cv.current!, 2));
		st.current.mask = wordMask(S.cols, S.rows, { fit: 0.6 }).mask;
		st.current.last = -1;
		if (stillMotion()) render(8);
	});
	useFrames(cv, () => {
		const t = (performance.now() / 1000 - st.current.t0) % 3.3;
		const k = Math.max(0, Math.min(8, t < 0.4 ? Math.floor(t / 0.05) : t < 2.2 ? 8 : t < 2.6 ? 8 - Math.floor((t - 2.2) / 0.05) : 0));
		if (k === st.current.last) return;
		st.current.last = k;
		render(k);
	});
	return (
		<canvas
			ref={cv}
			className="h-[200px] w-full cursor-pointer"
			aria-label="The wordmark dissolving in, click to replay"
			onClick={() => {
				st.current.t0 = performance.now() / 1000;
				st.current.last = -1;
			}}
		/>
	);
}

function Loaders() {
	const box = useRef<HTMLDivElement>(null), refs = [useRef<HTMLCanvasElement>(null), useRef<HTMLCanvasElement>(null), useRef<HTMLCanvasElement>(null)];
	const paints = useRef<ReturnType<typeof painter>[]>([]);
	const n = 24;
	const frames = useMemo(() => {
		const load = Array.from({ length: 9 }, (_, k) => markBits(n, { r: (MARK.r * k) / 8 }));
		const walk = Array.from({ length: 8 }, (_, k) => markBits(n, { cx: 0.5 + 0.2 * Math.cos((k * Math.PI) / 4), cy: 0.5 + 0.2 * Math.sin((k * Math.PI) / 4) }));
		const fills = Array.from({ length: 9 }, (_, k) => {
			const b = new Uint8Array(n * n);
			for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) b[y * n + x] = x === 0 || y === 0 || x === n - 1 || y === n - 1 || k / 8 > threshold(x, y, 4) ? 1 : 0;
			return b;
		});
		return { load, walk, fills };
	}, []);
	const paint = (k: number) => {
		const p = paints.current;
		if (p.length < 3) return;
		p[0](frames.load[Math.min(8, k % 14)]);
		p[1](frames.walk[k % 8]);
		p[2](frames.fills[Math.min(8, k % 12)]);
	};
	useSized(box, () => {
		paints.current = refs.map((r) => painter(r.current!, n, 48));
		paint(8);
	});
	useSteps(box, 100, paint, 8);
	return (
		<div ref={box} className="flex flex-wrap items-center justify-center gap-10">
			{['view loading', 'player walking', 'fill'].map((t, i) => (
				<figure key={t} className="m-0 grid justify-items-center gap-2.5 font-mono text-[11px] leading-none">
					<canvas ref={refs[i]} />
					{t}
				</figure>
			))}
		</div>
	);
}

export function Motion() {
	return (
		<Section id="motion" n={10} name="Motion" title="In steps, never eased." lead="Things appear and change through the matrix, a level at a time, in steps of about 50 ms. Nothing slides, fades smoothly or bounces. With reduced motion on, everything simply appears.">
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				<Panel label="Dissolve in · click to replay" className="overflow-hidden p-0">
					<DissolveIn />
				</Panel>
				<Panel label="Loading · the mark at work" className="grid min-h-[220px] place-items-center pt-11">
					<Loaders />
				</Panel>
			</div>
			<Rules className="mt-7" items={['Eight steps: 0, 8, 16 … 64 ink cells out of 64.', 'About 50 ms a step, 400 ms for a full dissolve.', 'The loader is the mark: the view grows in eight steps, holds, and starts again.', 'Pictures may move smoothly, like the hero’s flight and the turning crystal, and only while they’re on screen. The interface never does; the slider’s 80 ms settle is the one ease, and reduced motion drops it.']} />
		</Section>
	);
}

/* ---- 11 · in use -------------------------------------------------------------------------------- */

function Still({ cam, o, className }: { cam: keyof typeof CAMS; o: Parameters<typeof still>[2]; className?: string }) {
	const ref = useRef<HTMLCanvasElement>(null);
	useSized(ref, () => still(ref.current!, CAMS[cam], o));
	return <canvas ref={ref} className={className} />;
}
// The home page's flight, its first frame over a seed's world, drawn once.
function Flight({ seed, className }: { seed: number; className?: string }) {
	const ref = useRef<HTMLCanvasElement>(null);
	useSized(ref, () => {
		const s = surface(ref.current!, 2);
		firstFrame(s.u32, s.cols, s.rows, seed);
		s.flush();
	});
	return <canvas ref={ref} className={className} />;
}
const Chrome = ({ title }: { title: string }) => (
	<div className="flex h-8 items-center gap-1.5 overflow-hidden rule-b px-3 font-mono text-[11px] leading-none whitespace-nowrap">
		<i className="size-2 flex-none border border-ink" />
		<i className="size-2 flex-none border border-ink" />
		<i className="size-2 flex-none border border-ink" />
		<span className="ml-2">{title}</span>
	</div>
);
const frame = 'min-w-0 overflow-hidden rule bg-paper';

export function InUse() {
	const aside: (string | [string, boolean])[] = ['Start', ['Install', false], ['Run a server', false], ['Configure', false], 'Worlds', ['Pregenerating chunks', true], ['Data packs', false], ['Saves and vanilla', false], 'Plugins', ['Host API', false], ['WASM addons', false]];
	return (
		<Section id="use" n={11} name="In use" title="Website, docs, GitHub, the game, print.">
			<Sub first>Website</Sub>
			<div className={frame}>
				<Chrome title="calcite" />
				<nav className="flex items-center gap-[22px] rule-b px-[22px] py-3.5 text-[15px]">
					<span className="mr-auto flex items-center gap-2.5 font-display text-2xl leading-none font-extrabold tracking-[-0.05em]">
						<Mark size={28} />
						calcite
					</span>
					{['Docs', 'Benchmarks', 'Plugins', 'GitHub'].map((t) => (
						<TextLink key={t} href="#use" className="max-md:hidden">
							{t}
						</TextLink>
					))}
				</nav>
				<div className="grid grid-cols-1 items-end gap-6 px-[22px] pt-12 pb-7 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
					<div>
						<h3 className="font-display text-[clamp(40px,6vw,84px)] leading-[0.9] font-extrabold tracking-display">The same world, made faster.</h3>
						<p className="mt-4 mb-6 max-w-[40ch]">A Minecraft server written from scratch in Calx. Every region on its own core, and every chunk the same as vanilla&apos;s.</p>
						<div className="flex flex-wrap gap-2.5">
							<ButtonLink href="#use">Download</ButtonLink>
							<ButtonLink href="#use" variant="secondary">
								Benchmarks
							</ButtonLink>
						</div>
					</div>
				</div>
				<Still cam="site" o={{ fade: { t: 0.3, l: 0.04, r: 0.04 }, horizon: 0.16 }} className="h-[230px] w-full" />
				<div className="grid grid-cols-1 rule-t md:grid-cols-3">
					{(
						[
							['chunk', '2,022 chunks a second on 32 threads'],
							['parity', 'Worldgen checked against vanilla’s'],
							['plugin', 'Native Calx and WASM plugins'],
						] as const
					).map(([ic, t], i) => (
						<div key={ic} className={cn('flex items-center gap-3.5 px-[22px] py-[18px] text-[15px] leading-[1.35]', i < 2 && 'md:rule-r max-md:rule-b')}>
							<Bitmap bits={ICONS[ic]} n={16} size={32} />
							{t}
						</div>
					))}
				</div>
			</div>

			<Sub>Docs</Sub>
			<div className={frame}>
				<Chrome title="calcite / docs / pregen" />
				<div className="grid grid-cols-1 min-h-[420px] md:grid-cols-[210px_minmax(0,1fr)]">
					<aside className="grid content-start gap-1 rule-r p-5 text-sm max-md:hidden">
						{aside.map((a, i) =>
							typeof a === 'string' ? (
								<b key={a} className={cn('label mb-1.5 leading-none font-normal', i > 0 && 'mt-3.5')}>
									{a}
								</b>
							) : (
								<a key={a[0]} href="#use" className={cn('py-[3px]', a[1] && 'font-bold underline decoration-2 underline-offset-[5px]')}>
									{a[0]}
								</a>
							),
						)}
					</aside>
					<article className="grid max-w-[70ch] content-start gap-4 px-8 py-7">
						<span className="note">WORLDS</span>
						<h4 className="m-0 font-display text-[40px] leading-none font-extrabold tracking-display">Pregenerating chunks</h4>
						<p>Calcite can generate the chunks of an area ahead of time, as the Chunky mod does, so players exploring there never wait on world generation. It&apos;s built in.</p>
						<CodeBlock code={'pregen radius 5000\npregen start'} />
						<Callout>Players come first: while a player&apos;s chunks are loading, a task starts no new ones.</Callout>
					</article>
				</div>
			</div>

			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
				<div>
					<Sub first>GitHub social card · 1280×640</Sub>
					<div className={cn(frame, 'relative aspect-[2/1] [container-type:inline-size]')}>
						<Still cam="social" o={{ fade: { t: 0.35 }, horizon: 0.18 }} className="absolute inset-x-0 bottom-0 h-[58%] w-full" />
						<div className="absolute top-[10%] left-[6%] flex items-center gap-[2.2cqi]">
							<Mark size={48} />
							<b className="font-display text-[10cqi] leading-[0.86] font-extrabold tracking-[-0.05em]">calcite</b>
						</div>
						<div className="absolute top-[12%] right-[6%] text-right font-mono text-[2.1cqi] leading-normal">
							a Minecraft server
							<br />
							written in Calx
						</div>
					</div>
				</div>
				<div>
					<Sub first>README header</Sub>
					{/* the home page's first screen, as scripts/banner.tsx draws it at 1600 × 704: 1cqi is 16 px of it */}
					<div className={cn(frame, 'relative aspect-[1600/704] [container-type:inline-size]')}>
						<Flight seed={BANNER_SEED} className="absolute inset-x-0 bottom-0 h-[59.66%] w-full" />
						<div className="absolute inset-x-[4cqi] top-[3.5cqi] flex items-end justify-between">
							<div>
								<p className="font-mono text-[1.25cqi] leading-none tracking-label uppercase">Minecraft: Java Edition {SITE.minecraft}</p>
								<b className="mt-[1.4cqi] -ml-[0.5cqi] block font-display text-[14.75cqi] leading-[0.8] font-extrabold tracking-display">calcite</b>
							</div>
							<p className="w-[40cqi] text-[1.875cqi] leading-[1.45]">{SITE.lead}</p>
						</div>
					</div>
					<Sub>Browser tab</Sub>
					<div className={frame}>
						<div className="flex items-end rule-b bg-paper px-2.5 pt-2.5">
							<div className="-mb-px flex min-w-0 items-center gap-2.5 border border-b-0 border-dotted border-ink bg-paper px-3.5 py-2.5 text-[13px]">
								<Mark size={16} />
								<span className="truncate">calcite · a Minecraft server</span>
								<em className="ml-1.5 font-mono not-italic">×</em>
							</div>
							<div className="-mb-px px-3.5 py-2.5 text-[13px]">new tab</div>
						</div>
						<div className="px-3.5 py-2.5 font-mono text-[13px] leading-none">calcite / docs</div>
					</div>
				</div>
			</div>

			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
				<div>
					<Sub first>Server list</Sub>
					{/* The game's server list is dark in the game, so this one mock is dark too. */}
					<div className="bg-[#141519] px-3.5 py-[18px] font-mono">
						<div className="grid grid-cols-[64px_minmax(0,1fr)] gap-2.5 bg-[#000]/50 p-1 outline-2 outline-[#9a9a9a] sm:grid-cols-[64px_minmax(0,1fr)_auto]">
							<div className="grid size-16 place-items-center bg-paper text-ink">
								<Mark size={64} />
							</div>
							<div>
								<div className="text-sm leading-[1.4] text-[#fff]">calcite</div>
								<div className="mt-1 overflow-hidden text-[13px] leading-[1.45] whitespace-nowrap text-[#a8a8a8]">
									<span className="text-[#8fa2ff]">worlds, one dot at a time</span>
									<br />
									written in Calx · 26.3
								</div>
							</div>
							<div className="flex items-center gap-2 text-xs leading-[1.4] text-[#a8a8a8] max-sm:hidden">
								0/100
								<span className="flex h-2.5 items-end gap-px">
									{[3, 5, 7, 9, 10].map((h) => (
										<i key={h} className="w-0.5 bg-[#e8e8e8]" style={{ height: h }} />
									))}
								</span>
							</div>
						</div>
						<p className="mt-3 text-[11px] leading-[1.6] text-[#8a8a8a]">server-icon.png: the mark at 64 × 64 on paper (download it in section 13). On the game&apos;s dark list, the description may use a lighter blue: the one exception to one ink.</p>
					</div>
				</div>
				<div>
					<Sub first>Console</Sub>
					<div className={frame}>
						<pre className="m-0 overflow-x-auto px-5 py-[18px] font-mono text-[13px] leading-[1.65] whitespace-pre">
							{'   '}
							<b className="bg-ink px-1.5 py-px font-medium text-paper">calcite</b>
							{'   Minecraft 26.3 · ready in 4.8 ms\n\n  ›  Address    localhost:25565\n  ›  Accounts   checked with Mojang\n  ›  World      flat, 32 chunks in view, 10 simulated\n  ›  Players    up to 20'}
						</pre>
					</div>
					<Cap>The server&apos;s ready card, as src/README.md shows it. The badge is the ink on paper, reversed.</Cap>
				</div>
			</div>

			<Sub>Print · one ink is a screen print</Sub>
			<div className="grid grid-cols-1 gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
				<Panel label="Sticker · square die cut" className="grid min-h-[420px] place-items-center">
					<div className="relative grid size-[250px] content-center place-items-center gap-3.5 bg-paper shadow-[0_0_0_10px_var(--color-paper),0_0_0_11px_var(--color-ink)] after:absolute after:-inset-[22px] after:border after:border-dashed after:border-ink after:content-['']">
						<Mark size={128} />
						<Wm className="text-[46px] leading-[0.9]" />
					</div>
				</Panel>
				<Panel label="Poster · A-series" className="px-[26px] pt-11 pb-[26px]">
					<div className={cn(frame, 'relative mx-auto aspect-[1/1.414] max-h-[620px] [container-type:inline-size]')}>
						<Still cam="poster" o={{ fade: { t: 0.3 }, horizon: 0.2 }} className="absolute inset-x-0 bottom-0 h-[62%] w-full" />
						<div className="absolute inset-x-[8%] top-[7%]">
							<b className="block font-display text-[14cqi] leading-[0.86] font-extrabold tracking-display">worlds, one dot at a time.</b>
							<span className="mt-[4cqi] block font-mono text-[2.6cqi] leading-normal">calcite · a Minecraft server written in Calx</span>
						</div>
					</div>
				</Panel>
			</div>
		</Section>
	);
}

/* ---- 13 · files ---------------------------------------------------------------------------------- */

export function Files() {
	const FILES: { name: string; info: string; pv: React.ReactNode; blob: () => Blob | Promise<Blob> }[] = [
		{ name: 'server-icon.png', info: '64 × 64 · 32 cells at 2 px, on paper · goes next to server.properties', pv: <div className="bg-paper outline outline-dotted outline-ink"><Mark size={64} /></div>, blob: () => pngBlob(markPNG(32, 2, PAPER)) },
		{ name: 'calcite-mark.svg', info: 'the 64-cell master as vector squares · scale it by whole numbers', pv: <Mark size={80} cells={64} />, blob: () => new Blob([markSVG(64)], { type: 'image/svg+xml' }) },
		{ name: 'calcite-mark-512.png', info: '512 × 512 · the master at 8 px a cell · transparent', pv: <Mark size={80} cells={64} />, blob: () => pngBlob(markPNG(64, 8)) },
		{ name: 'favicon-32.png', info: '32 × 32 · 16 cells at 2 px, on paper', pv: <div className="bg-paper outline outline-dotted outline-ink"><Mark size={32} cells={16} /></div>, blob: () => pngBlob(markPNG(16, 2, PAPER)) },
		{ name: 'social-card.png', info: '1280 × 640 · GitHub’s social preview', pv: <span className="font-mono text-xs">made from the guide&apos;s world</span>, blob: () => pngBlob(socialCard()) },
		{
			name: 'calcite-tiles.css',
			info: 'every tile the components use, as SVG custom properties',
			pv: (
				<div className="flex gap-1">
					{['tint-12', 'tint-31', 'tint-50', 'tint-75', 'tint-88'].map((t) => (
						<i key={t} className={cn('h-12 w-[26px] outline outline-dotted outline-ink', t)} />
					))}
				</div>
			),
			blob: () => {
				const cs = getComputedStyle(document.documentElement), names = ['solid', ...[6, 12, 25, 31, 38, 50, 62, 75, 88].map((p) => 't' + p), 'tp6', 'tp12', 'tp25', 'tp50', 'q6', 'q12', 'q25', 'q50', 'q75', 'qp25', 'qp50', 'qp75', 'u25', 'u50', 'u75', 'v25', 'v50', 'v75', 'edge', 'edge-p', 'edge-r', 'shine', 'ring', 'ring-p', 'check2', 'tail', 'chevron', 'plus', 'minus'];
				return new Blob([`/* Calcite dither tiles: SVG, 2 px a cell. */\n:root {\n\t--color-ink: #1838D0;\n\t--color-paper: #F8F8F5;\n${names.map((n) => `\t--${n}: ${cs.getPropertyValue('--' + n).trim()};`).join('\n')}\n}\n`], { type: 'text/css' });
			},
		},
	];
	return (
		<Section id="files" n={13} name="Files" title="Take the mark with you." lead="Made in your browser from the same code as this page, so they always match it.">
			<div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
				{FILES.map((f) => (
					<div key={f.name} className="grid min-h-[200px] content-between gap-3 rule p-[18px]">
						<div className="grid h-[90px] place-items-center">{f.pv}</div>
						<div>
							<b className="font-mono text-[13px] leading-[1.4] font-medium">{f.name}</b>
							<br />
							<span className="font-mono text-xs leading-normal">{f.info}</span>
						</div>
						<div>
							<Button variant="secondary" onClick={async () => save(f.name, await f.blob())}>
								Download
							</Button>
						</div>
					</div>
				))}
			</div>
		</Section>
	);
}
