import type { Metadata } from 'next';
import { JsonLd, trail } from '@/lib/ld';
import { meta } from '@/lib/meta';
import { PAGES } from '@/lib/pages';
import Link from 'next/link';
import { CpuBars, FlightChart, LightBars, MemoryBars, ThreadsChart } from '@/components/site/bench-charts';
import { PageHead, SectionHead, SPLIT_XL, Stats } from '@/components/site/parts';
import { PageNav } from '@/components/site/page-nav';
import { WorldgenRace } from '@/components/site/worldgen-race';
import { Disclosure, Table } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { DATA } from '@/lib/data';
import { phases } from '@/lib/repo';
import { cn } from '@/lib/cn';
import { SITE } from '@/lib/site';

export const metadata: Metadata = meta(PAGES.benchmarks);

const f1 = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const f2 = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const f3 = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const n0 = (v: number) => Math.round(v).toLocaleString('en-US');

const CONTENTS = [
	['bots', '100 players'],
	['client', 'Joining and flying'],
	['packs', 'Worldgen with data packs'],
	['worldgen', "Vanilla's worldgen"],
	['light', 'Light'],
	['run', 'Running them'],
] as const;

function Fig({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
	return (
		<figure className="m-0 min-w-0">
			<figcaption className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rule-b pb-2.5">
				<b className="font-display text-lg leading-tight font-bold">{title}</b>
				<span className="font-mono text-[11px] leading-[1.4]">{note}</span>
			</figcaption>
			{children}
		</figure>
	);
}

const Src = ({ file, commit }: { file: string; commit: string }) => (
	<p className="mt-5 font-mono text-xs leading-normal">
		Recorded in{' '}
		<a href={`${SITE.blob}bench/results/${file}`} className="link">
			bench/results/{file}
		</a>{' '}
		at commit {commit}.
	</p>
);

const Section = ({ children }: { children: React.ReactNode }) => (
	<section className="mt-24">
		<div className="rule-t pt-16">{children}</div>
	</section>
);

const Points = ({ items }: { items: string[] }) => (
	<ul className="grid content-start gap-3 text-[15px] leading-normal">
		{items.map((t) => (
			<li key={t} className="relative pl-6">
				<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
				{t}
			</li>
		))}
	</ul>
);

// Number tables fit a phone: no fixed width, and smaller type there.
const NUMS = 'max-sm:text-[13px]';

export default function Benchmarks() {
	const M = DATA.machine, P = DATA.packs, W = DATA.worldgen, C = DATA.flight, B = DATA.bots;
	const f25 = C.runs['25'], f100 = C.runs['100'];
	const ratio = (t: number) => P.calcite.find((r) => r.threads === t)!.cps / P.c2me.find((r) => r.threads === t)!.cps;
	const others = phases().phases.find((p) => p.n === 8)?.state !== 'done';
	return (
		<>
			<JsonLd things={[trail([[PAGES.benchmarks.title, PAGES.benchmarks.path]])]} />
			{/* on a wide screen the sections are listed in a column beside the page, as the docs' pages
			    are, and the one being read is marked; on a narrower one they're a row of chips under the head */}
			<div className="wrap xl:grid xl:grid-cols-[200px_minmax(0,1fr)] xl:gap-x-16">
				<aside className="max-xl:hidden">
					<PageNav items={CONTENTS} className="mt-24" />
				</aside>
				<div className="min-w-0">
					<PageHead
						bare
						title="Benchmarks"
						lead={
							<p>
								Every benchmark runs the release build on one machine: an {M.cpu} with {M.cores} cores and {M.threads} threads, {M.memory} GiB of memory and {M.os}. Each number below is a recorded run, with the commit it ran at, and each benchmark runs again with one command. CI runners are too noisy to compare, so none of these come from CI.
							</p>
						}
					>
						<nav aria-label="On this page" className="mt-10 flex flex-wrap gap-2 xl:hidden">
							{CONTENTS.map(([id, t]) => (
								<a key={id} href={`#${id}`} className="rule px-3 py-2 font-mono text-[13px] leading-none hover:bg-ink hover:text-paper hover:[border-style:solid]">
									{t}
								</a>
							))}
						</nav>
					</PageHead>

					{/* ---- 100 players ---- */}
					<Section>
						<SectionHead
							split
							id="bots"
							title="100 players"
							lead={
								<p>
									This one runs on every commit that might change the tick or the network. 100 bots join a flat world, {B.scenario.rate} a second, then walk outward in their own directions so each keeps being sent new chunks, and chat to everyone every 10 seconds, for {B.scenario.seconds} seconds. View and simulation distance are {B.scenario.view}. The numbers are the median of {B.runs} runs.
								</p>
							}
						/>
						<Stats
							items={[
								{ label: 'Tick, mean', value: `${f3(B.windows.mean)} ms`, note: 'of the 50 ms a tick has, on Windows' },
								{ label: 'Tick, p99', value: `${f3(B.windows.p99)} ms`, note: `and ${f3(B.windows.max)} ms at the most` },
								{ label: 'Joining', value: `${n0(B.windows.joinMs)} ms`, note: 'for a bot to have all its chunks, the median' },
								{ label: 'Memory', value: `${n0(B.windows.mem)} MiB`, note: 'at the most, with all 100 in' },
							]}
						/>
						<div className={cn('mt-10', SPLIT_XL)}>
							<div className="overflow-x-auto">
								<Table
									className={NUMS}
									columns={[{ label: '' }, { label: 'Windows 11', num: true }, { label: 'Linux, WSL 2', num: true }]}
									rows={[
										['Tick, mean', `${f3(B.windows.mean)} ms`, `${f3(B.linux.mean)} ms`],
										['Tick, p99', `${f3(B.windows.p99)} ms`, `${f3(B.linux.p99)} ms`],
										['Tick, longest', `${f3(B.windows.max)} ms`, `${f3(B.linux.max)} ms`],
										['Ticks a second', f2(B.windows.tps), f2(B.linux.tps)],
										['Tick while joining, mean', `${f3(B.windows.joinMean)} ms`, `${f3(B.linux.joinMean)} ms`],
										['Joining, median', `${n0(B.windows.joinMs)} ms`, `${n0(B.linux.joinMs)} ms`],
										['CPU time, all threads', `${f2(B.windows.cpu)} s`, `${f2(B.linux.cpu)} s`],
										['Peak memory', `${f1(B.windows.mem)} MiB`, `${f1(B.linux.mem)} MiB`],
										['Chunks sent', n0(B.windows.chunks), n0(B.linux.chunks)],
									]}
								/>
							</div>
							<div>
								<p className="max-w-[72ch] leading-relaxed">
									The tick times come from the server itself, over the steady part of the run. A single run&apos;s mean moves by about 10% with whatever else the machine is doing, so a result more than 5% worse than the recorded one is run ten more times before anyone looks into it. Ticks while players join are slower on Linux than on Windows on the same machine, and the cause isn&apos;t known yet.
									{others && ' The same load on Paper, Folia and Pumpkin is measured in Phase 8.'}
								</p>
								<Src file="bots-windows.json" commit={B.commit} />
							</div>
						</div>
					</Section>

					{/* ---- a real client ---- */}
					<Section>
						<SectionHead
							split
							id="client"
							title="Joining and flying"
							lead={
								<p>
									Bots wait for the server, but a real client asks for chunks as fast as it can take them, so this one uses Mojang&apos;s own {SITE.minecraft} client at render and view distance {C.view}, on a new world. It joins, waits, and then flies straight ahead for {C.seconds} seconds. A relay between them counts, four times a second, how much of the circle of {C.view} chunks around the player the client has.
								</p>
							}
						/>
						<Stats
							items={[
								{ label: 'Joining, 95%', value: `${f2(f25.join.p95)} s`, note: `for the client to have 95% of the ${n0(f25.join.chunks)} chunks in its view` },
								{ label: 'Joining, all', value: `${f2(f25.join.all)} s`, note: `for all ${n0(f25.join.chunks)} of them` },
								{ label: 'Flying at 25×', value: `${f1(f25.had[0])}%`, note: `of its view the client had on average at ${f1(f25.blocks)} blocks a second, and never less than ${f1(f25.had[1])}%` },
								{ label: 'Memory', value: `${n0(f25.memory.still)} MiB`, note: `with one player standing still at view ${C.view}; ${n0(f25.memory.idle)} MiB idle and ${n0(f25.memory.peak)} MiB at the most` },
							]}
						/>
						<div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-2">
							<Fig title={`At 25×, ${n0(f25.blocks)} blocks a second`} note="% of the view · higher is better">
								<FlightChart speed="25" />
							</Fig>
							<Fig title={`At 100×, ${n0(f100.blocks)} blocks a second`} note="% of the view · higher is better">
								<FlightChart speed="100" />
							</Fig>
						</div>
						<div className={cn('mt-6', SPLIT_XL)}>
							<p className="max-w-[72ch] leading-relaxed">
								At 25 times vanilla&apos;s flying speed the client has nearly all of its view the whole way, and what it&apos;s missing is at the edge: the nearest chunk it doesn&apos;t have is {f25.nearest[0]} chunks away, at the median. At 100 times it flies {n0(f100.blocks / 16)} chunks a second. The circle ahead of it then needs more new chunks each second than {M.threads} threads can generate, and within seconds the player has outrun them, while the server keeps sending {n0(f100.sent)} chunks a second.
							</p>
							<Disclosure summary="The whole table" className="self-start">
								<div className="overflow-x-auto">
									<Table
										className={`mt-2 ${NUMS}`}
										columns={[{ label: '' }, { label: '25×', num: true }, { label: '100×', num: true }]}
										rows={[
											['Joining, 95% of the chunks', `${f2(f25.join.p95)} s`, `${f2(f100.join.p95)} s`],
											['Joining, all of them', `${f2(f25.join.all)} s`, `${f2(f100.join.all)} s`],
											['Flight speed, blocks a second', f1(f25.blocks), f1(f100.blocks)],
											['Chunks sent a second', f1(f25.sent), f1(f100.sent)],
											['View the client had, mean', `${f1(f25.had[0])}%`, `${f1(f100.had[0])}%`],
											['View the client had, least', `${f1(f25.had[1])}%`, `${f1(f100.had[1])}%`],
											['Tick while flying, mean', `${f2(f25.mspt.mean)} ms`, `${f2(f100.mspt.mean)} ms`],
											['Tick while flying, p99', `${f2(f25.mspt.p99)} ms`, `${f2(f100.mspt.p99)} ms`],
											['Memory, idle', `${f1(f25.memory.idle)} MiB`, `${f1(f100.memory.idle)} MiB`],
											['Memory, one player still', `${f1(f25.memory.still)} MiB`, `${f1(f100.memory.still)} MiB`],
											['Memory, at the most', `${n0(f25.memory.peak)} MiB`, `${n0(f100.memory.peak)} MiB`],
										]}
									/>
								</div>
							</Disclosure>
						</div>
						<Src file="client-windows.json" commit={C.commit} />
					</Section>

					{/* ---- packs ---- */}
					<Section>
						<SectionHead
							split
							id="packs"
							title="Worldgen with data packs"
							lead={
								<p>
									C2ME publishes a benchmark that generates a world with Terralith and Terratonic, beside Paper and vanilla. Calcite runs it with its own <code className="font-mono text-[0.9em]">pregen</code>, and vanilla, Paper and C2ME run it with Chunky, on the same machine and set up as C2ME&apos;s is. Calcite made {f2(ratio(1))} times as many chunks a second as C2ME on one thread, and {f2(ratio(32))} times as many on 32.
								</p>
							}
						/>
						<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-x-10">
							<Fig title="Chunks a second" note="higher is better">
								<WorldgenRace />
							</Fig>
							<Fig title="CPU time for the whole launch" note="seconds, warm-up included · less is better">
								<p className="mb-2 font-mono text-xs">1 thread</p>
								<CpuBars t={1} />
								<p className="mt-5 mb-2 font-mono text-xs">8 threads</p>
								<CpuBars t={8} />
							</Fig>
						</div>
						<div className="mt-10 overflow-x-auto">
							<Table
								className={NUMS}
								columns={[{ label: 'threads' }, { label: 'Calcite', num: true }, { label: 'C2ME', num: true }, { label: 'Paper', num: true }, { label: 'vanilla', num: true }, { label: "Calcite's memory, MiB", num: true }]}
								rows={P.calcite.map((r, i) => [r.threads, <b key="c">{f1(r.cps)}</b>, f1(P.c2me[i].cps), f1(P.paper[i].cps), f1(P.vanilla[i].cps), n0(r.mem)])}
							/>
						</div>
						<div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:gap-x-10">
							<Points
								items={[
									`The packs are ${P.packs.join(' and ')}, on C2ME's seed, ${P.seed}.`,
									`Each launch starts on a new world with a ${P.warmup}-block warm-up around the origin, then measures a ${n0(P.radius)}-block radius around 1,000,000, 1,000,000: ${n0(P.chunks)} chunks.`,
									'The Java servers run on JDK 25 with C2ME’s flags and a 16 GiB heap touched up front, so their peak memory is that heap and isn’t compared.',
									'On a long run, vanilla with Chunky fills its heap, so it’s given vanilla’s own save-all flush every 120 seconds, which costs it about 8%. C2ME’s benchmark gives vanilla a patched Chunky that isn’t published.',
								]}
							/>
							<Points
								items={[
									`Calcite at ${P.commit}. Vanilla on Fabric ${P.versions.fabric}, Paper ${P.versions.paper} and C2ME ${P.versions.c2me}, each with Chunky ${P.versions.chunky}, at ${P.othersCommit}.`,
									'Paper used the 16 and 32 worker threads it was given, as its log says, and made no more chunks than with 8. Vanilla made about 100 a second at every count from 8 up.',
									'The rig checks a sample of 264 of the chunks Calcite generates with the packs, and every one has what must be vanilla’s.',
									'C2ME’s own benchmark uses a 3,072-block radius, which takes vanilla hours on one thread. This one is smaller, so the whole comparison takes about an hour and a half.',
								]}
							/>
						</div>
						<Src file="terralith-windows.json" commit={P.commit} />
					</Section>

					{/* ---- vanilla's own worldgen ---- */}
					<Section>
						<SectionHead
							split
							id="worldgen"
							title="Vanilla's worldgen"
							lead={
								<p>
									The same benchmark without the packs, through the whole server, the way a player&apos;s chunks are made: each chunk is generated, lit, saved to its region file and compressed, and kept until it&apos;s let go. The dotted line is the same runs at {W.before.commit}.
								</p>
							}
						/>
						<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-x-10">
							<Fig title="Chunks a second, by threads" note="higher is better">
								<div className="mb-3 flex flex-wrap gap-[18px] font-mono text-xs leading-none">
									<span>
										<i className="mr-[7px] inline-block h-0.5 w-4 bg-ink align-[3px]" />
										now, at {W.commit}
									</span>
									<span>
										<i className="mr-[7px] inline-block h-0.5 w-4 bg-(image:--u50) bg-size-[8px_2px] align-[3px]" />
										at {W.before.commit}
									</span>
								</div>
								<ThreadsChart />
							</Fig>
							<Fig title="Peak memory" note="MiB · less is better">
								<MemoryBars which="worldgen" />
							</Fig>
						</div>
						<div className="mt-10 overflow-x-auto">
							<Table
								className="max-sm:text-[12px]"
								columns={[{ label: 'threads' }, { label: 'chunks a second', num: true }, { label: 'steady', num: true }, { label: `at ${W.before.commit}`, num: true }, { label: 'CPU time, s', num: true }, { label: 'memory, MiB', num: true }]}
								rows={W.runs.map((r, i) => [r.threads, <b key="c">{f1(r.cps)}</b>, r.steady ? f1(r.steady) : '–', f1(W.before.cps[i]), r.cpu, n0(r.mem)])}
							/>
						</div>
						<p className="mt-4 max-w-[80ch] font-mono text-xs leading-normal">The steady rate counts from 10% done to 90%. At 16 and 32 threads the run is over before there are two progress lines between those, so it has none.</p>
						<Src file="worldgen-windows.json" commit={W.commit} />
					</Section>

					{/* ---- light ---- */}
					<Section>
						<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-x-10">
							<SectionHead
								id="light"
								className="mb-0"
								title="Light"
								lead={
									<>
										<p>The rig runs its light probe on vanilla&apos;s server and on Calcite, 15 times each after a warm-up, on three workloads, and checks that the two engines give every block the same light level, from 0 to 15. They did in every run.</p>
										<p className="mt-4">A flat world&apos;s light is the sky&apos;s, one level at a time, so there&apos;s little work either way. Terrain is where the difference shows.</p>
									</>
								}
							/>
							<Fig title="Milliseconds to light, median of 15" note="less is better">
								<LightBars />
							</Fig>
						</div>
						<p className="mt-5 font-mono text-xs leading-normal">
							Run by{' '}
							<a href={`${SITE.blob}rig/runner/light_timing.py`} className="link">
								rig/runner/light_timing.py
							</a>{' '}
							at commit {DATA.light.commit}. The results are in{' '}
							<a href={`${SITE.blob}bench/README.md#light`} className="link">
								bench/README.md
							</a>
							.
						</p>
					</Section>

					{/* ---- run them ---- */}
					<Section>
						<SectionHead split id="run" title="Running them" lead={<p>From the repo, with Python 3.10 or later and nothing else. Each one builds the release server with Calx first. The client benchmark needs a desktop with Minecraft {SITE.minecraft} installed.</p>} />
						<div className={SPLIT_XL}>
							<CodeBlock
								lang="sh"
								code={[
									'# 100 players',
									'py -I bench/run.py --record',
									'# a real client, joining and flying',
									'py -I bench/client.py --record',
									'# worldgen with the packs: Calcite, then vanilla, Paper and C2ME',
									'py -I bench/terralith.py --record',
									'py -I bench/others.py --record',
									"# vanilla's own worldgen",
									'py -I bench/terralith.py --no-packs --record',
									"# light, beside vanilla's engine",
									'py -I rig/runner/light_timing.py',
								].join('\n')}
							/>
							<p className="max-w-[72ch] leading-relaxed">
								<a href={`${SITE.blob}bench/README.md`} className="link">
									bench/README.md
								</a>{' '}
								has how each one is set up, and the history of every number. On Linux, use <code className="font-mono text-[0.9em]">python3</code> in place of <code className="font-mono text-[0.9em]">py</code>. The site reads the results files when it&apos;s built, so a newly recorded run shows up here with the next deploy.{' '}
								<Link href="/roadmap" className="link">
									What gets measured next
								</Link>
							</p>
						</div>
					</Section>
				</div>
			</div>
		</>
	);
}
