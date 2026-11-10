import type { Metadata } from 'next';
import { JsonLd, SOFTWARE, STUDIO, WEBSITE } from '@/lib/ld';
import { meta } from '@/lib/meta';
import Link from 'next/link';
import { Flyover } from '@/components/flyover';
import { GenSteps } from '@/components/site/gen-steps';
import { TickBand } from '@/components/site/tick-band';
import { Band, Kicker, PhaseStrip, SectionHead, Stats } from '@/components/site/parts';
import { buttonClass, ButtonLink } from '@/components/ui/button';
import { Disclosure, Tag } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { Tabs } from '@/components/ui/tabs';
import { cn } from '@/lib/cn';
import { DATA } from '@/lib/data';
import { differences, phases, probeCases, samples, type Phase } from '@/lib/repo';
import { SITE } from '@/lib/site';

export const metadata: Metadata = meta({ description: SITE.description, path: '/' });

const n1 = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 1 });
const n0 = (v: number) => Math.round(v).toLocaleString('en-US');
const f3 = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 });

// The homes sample's saved data and its /sethome, the shortest look at what a plugin is.
function excerpt() {
	const s = samples().find((x) => x.id === 'homes');
	if (!s) return '';
	const lines = s.code.split('\n');
	const from = (re: RegExp) => lines.findIndex((l) => re.test(l));
	const block = (i: number) => {
		const out: string[] = [];
		let depth = 0;
		for (let j = i; j < lines.length; j++) {
			out.push(lines[j]);
			depth += (lines[j].match(/{/g) ?? []).length - (lines[j].match(/}/g) ?? []).length;
			if (depth === 0 && lines[j].includes('}')) break;
		}
		return out;
	};
	const save = from(/^@save\(per: Player\)/), cmd = from(/@command\("sethome"/);
	if (save < 0 || cmd < 0) return lines.slice(0, 30).join('\n');
	const code = (ls: string[]) => ls.filter((l) => !/^\s*\/\//.test(l));
	return [...code(block(save)), '', ...code(block(cmd)).map((l) => l.replace(/^ {4}/, ''))].join('\n');
}

// What a server does, each with the phase of the plan that builds it. Until that phase has passed
// its gate, the item says so; once every phase has, the tags are gone.
const FEATURES: { title: string; text: string; phase: number }[] = [
	{ title: 'Every core', text: 'The world is split into regions that tick in parallel, in lockstep. A busy server uses the whole machine, and gets the same result on one thread as on 32.', phase: 5 },
	{ title: 'Plugins', text: 'Plugins in Calx run natively, at full speed. Plugins in any language that builds to WASM run in a sandbox. Both use the same API.', phase: 7 },
	{ title: 'The same files', text: 'server.properties, the operators, the whitelist and the ban lists are read where vanilla keeps them, so moving a server over is starting a different program in the same folder.', phase: 4 },
	{ title: 'Worlds and data packs', text: 'Worlds are saved in vanilla’s format, so an existing one moves to Calcite and back. Data packs such as Terralith generate as they do on vanilla.', phase: 5 },
	{ title: 'Logins and proxies', text: 'Online and offline mode, signed chat, and Velocity’s modern forwarding.', phase: 4 },
	{ title: 'Pregeneration', text: 'The pregen command is built in and takes Chunky’s subcommands. A task carries on after a restart, and steps aside while players are loading in.', phase: 5 },
	{ title: 'The console', text: 'A live dashboard on a terminal, and vanilla’s exact log lines in a file or a pipe, so hosting panels read it as they read vanilla.', phase: 4 },
	{ title: 'Recording and replay', text: 'A server can record everything it’s sent and replay it later, tick for tick, so a bug a player hit can be seen again and its fix checked.', phase: 5 },
];

// The features' cells: one column on a phone, two on a tablet, four across a wide screen, with a
// dotted rule between cells in a row and none on the outside.
const cell = (i: number) => cn('rule-b py-7', i % 2 === 1 ? 'md:max-xl:rule-l md:max-xl:pl-10' : 'md:max-xl:pr-10', i % 4 !== 0 && 'xl:rule-l xl:pl-8', i % 4 !== 3 && 'xl:pr-8');

function Pending({ phase, plan }: { phase: number; plan: Phase[] }) {
	const p = plan.find((x) => x.n === phase);
	if (!p || p.state === 'done') return null;
	return <Tag status={p.state === 'now' ? 'running' : 'planned'}>{p.state === 'now' ? `phase ${p.n}, in progress` : `phase ${p.n}`}</Tag>;
}

// The steps of generation the strip by "Vanilla parity" shows, each with the rig's cases for it.
const GEN = () => [
	{ name: 'structure starts', cases: probeCases('structures') },
	{ name: 'biomes', cases: probeCases('biomes') },
	{ name: 'noise', cases: probeCases('noise') + probeCases('density') },
	{ name: 'surface', cases: probeCases('surface') },
	{ name: 'carvers', cases: probeCases('carvers') },
	{ name: 'features', cases: probeCases('features') },
	{ name: 'light', cases: probeCases('light') },
];

const Points = ({ items, className }: { items: string[]; className?: string }) => (
	<ul className={cn('grid gap-3 text-[17px] leading-normal', className)}>
		{items.map((t) => (
			<li key={t} className="relative pl-7">
				<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
				{t}
			</li>
		))}
	</ul>
);

export default function Home() {
	const W = DATA.worldgen.runs, F = DATA.flight.runs['25'], B = DATA.bots, M = DATA.machine;
	const top = W[W.length - 1];
	const { phases: plan, passed } = phases();
	const now = plan.find((p) => p.state === 'now');
	const diffs = differences().length;
	const hostBuilt = plan.find((p) => p.n === 7)?.state === 'done';
	return (
		<>
			<JsonLd things={[WEBSITE, STUDIO, SOFTWARE]} />
			{/* ---- hero ---- */}
			{/* the heading shrinks on short screens too, so a laptop sees most of the world above the fold */}
			<section className="flex min-h-[calc(100svh-4rem-1px)] flex-col pt-8 md:pt-[min(3.5rem,5svh)]">
				<div className="wrap grid grid-cols-1 items-end gap-6 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:gap-10">
					<div>
						<Kicker>Minecraft: Java Edition {SITE.minecraft}</Kicker>
						<h1 className="font-display text-[clamp(64px,min(13vw,20svh),240px)] leading-[0.8] font-extrabold tracking-display">
							calcite<span className="sr-only">, a Minecraft: Java Edition server written in Calx</span>
						</h1>
					</div>
					<div className="pb-1">
						<p className="max-w-[44ch] text-lg leading-normal md:text-xl">
							{SITE.lead}
						</p>
						<div className="mt-6 flex flex-wrap gap-2.5">
							<ButtonLink href="/download">Download</ButtonLink>
							<ButtonLink href="/benchmarks" variant="secondary">
								Benchmarks
							</ButtonLink>
						</div>
						{now && (
							<Link href="/roadmap" className="group mt-5 inline-flex items-center gap-3 text-[15px]">
								<Tag status="running">pre-release</Tag>
								<span className="group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">
									Phase {now.n}, {now.builds.toLowerCase()}, is in progress
								</span>
							</Link>
						)}
					</div>
				</div>
				<Flyover className="mt-4 flex-1 md:mt-6" cue cps={top.cps} />
			</section>

			{/* ---- what it does ---- */}
			<Band id="more">
				<SectionHead
					split
					title="What it does"
					lead={<p>Calcite is written from scratch, with no code from vanilla, Paper or any other server.</p>}
					more={
						<Link href="/docs" className="link">
							The guide to running a server
						</Link>
					}
				/>
				<ul className="grid grid-cols-1 rule-t md:grid-cols-2 xl:grid-cols-4">
					{FEATURES.map((f, i) => (
						<li key={f.title} className={cell(i)}>
							<div className="flex flex-wrap items-center gap-x-3 gap-y-2">
								<h3 className="font-display text-[22px] leading-tight font-bold tracking-tight">{f.title}</h3>
								<Pending phase={f.phase} plan={plan} />
							</div>
							<p className="mt-2 max-w-[56ch] leading-relaxed">{f.text}</p>
						</li>
					))}
				</ul>
			</Band>

			{/* ---- performance ---- */}
			<Band>
				<SectionHead
					split
					title="Performance"
					lead={
						<p>
							Each tick, the world&apos;s regions run in parallel on every core. The tick never waits for the disk or the network: encoding, compression and saving happen on other threads. These numbers are from recorded runs on one machine, an {M.cpu} with {M.threads} threads on {M.os}.
						</p>
					}
					more={
						<Link href="/benchmarks" className="link">
							How each was measured, and against what
						</Link>
					}
				/>
				{/* a tick across the window, and what 100 players took of it, to scale */}
				<TickBand className="mb-14" mean={B.windows.mean} p99={B.windows.p99} max={B.windows.max} runs={B.runs} />
				<Stats
					bleed
					items={[
						{ label: '100 players', value: `${f3(B.windows.mean)} ms`, note: `a tick on average, with 100 players joining, walking outward and chatting; a tick has 50 ms` },
						{ label: 'Joining', value: `${n1(F.join.all)} s`, note: `for Mojang's client to load all ${n0(F.join.chunks)} chunks of a new world at view distance ${DATA.flight.view}` },
						{ label: 'Memory', value: `${n0(F.memory.idle)} MiB`, note: `held by an idle server, and ${n0(F.memory.still)} MiB with one player at view distance ${DATA.flight.view}` },
						{ label: 'World generation', value: n0(top.cps), note: `chunks a second on ${top.threads} threads, each one lit, saved and compressed` },
					]}
				/>
			</Band>

			{/* ---- parity ---- */}
			{/* a strip of a world across the window, a chunk at each step of generation, each replaying its step */}
			<Band id="parity">
				<SectionHead
					split
					title="Vanilla parity"
					lead={
						<p>
							A test rig gives vanilla&apos;s server and Calcite the same inputs and compares what comes out bit for bit, so a near miss counts as a failure. When matching vanilla and being fast pull apart, vanilla wins wherever a player, a farm or a data pack could notice.
						</p>
					}
					more={
						<Link href="/docs/vanilla" className="link">
							Worlds, vanilla and the differences
						</Link>
					}
				/>
				<GenSteps className="bleed" steps={GEN()} />
				<p className="mt-4 max-w-[96ch] font-mono text-xs leading-normal">
					A world is made in steps, and a chunk takes its next only once the chunks around it have taken theirs, so the edge of a world being made looks like this strip. Each chunk here is a step further on than the one to its left, and replays that step. Under each step is how many of the rig&apos;s cases compare it with vanilla&apos;s.
				</p>
				<Points
					className="mt-14 md:grid-cols-2 md:gap-x-10 xl:grid-cols-3"
					items={[
						'Worldgen passes the rig’s suites in the Overworld, the Nether and the End, on a grid of seeds.',
						'With Terralith and Terratonic, every one of 264 sampled chunks has what must be vanilla’s.',
						'Light matches vanilla’s exactly: every block gets the same light level, from 0 to 15.',
						'Logins match vanilla’s packet for packet.',
						'Worlds move between vanilla and Calcite in both directions.',
						`The ${diffs} places Calcite differs on purpose are listed, each a vanilla bug fixed or a limit stated.`,
					]}
				/>
			</Band>

			{/* ---- plugins ---- */}
			<Band>
				<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:gap-16">
					<div>
						<SectionHead
							className="mb-7"
							title="Plugins"
							lead={<p>Every plugin is written against one host API. Native plugins are Calx and run at full speed. WASM plugins can come from any language that builds to WASM, and run in a sandbox that stops a runaway one.</p>}
						/>
						<Points
							items={[
								'A command is a function, and the client tab-completes and checks its arguments.',
								'Events are typed, and run in the region where they happen.',
								'Plugins keep data on players, chunks and entities, saved with the world.',
								'Reloading a plugin keeps its state, and every plugin is profiled all the time.',
							]}
						/>
						<p className="mt-7">
							<Link href="/plugins" className="link">
								More on plugins
							</Link>
						</p>
					</div>
					<div className="min-w-0 self-center">
						<CodeBlock code={excerpt()} comment="//" lang="calx" copy={false} />
						<p className="mt-3 font-mono text-xs leading-normal">From the homes sample plugin{hostBuilt ? '.' : ', in the draft syntax the API was designed with. It compiles once the plugin host is built.'}</p>
					</div>
				</div>
			</Band>

			{/* ---- roadmap ---- */}
			<Band>
				<SectionHead
					split
					title="Roadmap"
					lead={
						now ? (
							<p>
								Calcite is built in {plan.length} phases, and each ends at a gate it has to pass before the next starts. Phases 0 to {passed} have passed. Phase {now.n}, {now.builds.toLowerCase()}, is in progress, and it&apos;s done when {(now.gates[now.gates.length - 1]?.text ?? now.gate).replace(/^./, (c) => c.toLowerCase())}.
							</p>
						) : (
							<p>Calcite was built in {plan.length} phases, and each ended at a gate it had to pass before the next started. All of them have passed.</p>
						)
					}
					more={
						<Link href="/roadmap" className="link">
							The whole plan
						</Link>
					}
				/>
				<PhaseStrip phases={plan} />
			</Band>

			{/* ---- get started ---- */}
			<Band>
				<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:gap-16">
					<SectionHead
						className="mb-0"
						title="Get started"
						lead={<p>Download last night&apos;s build for Windows or Linux and start it in a folder of its own, as you would vanilla&apos;s server. Or set it up first, and the download comes with its settings, its whitelist and its icon in it.</p>}
						more={
							<Link href="/docs/start" className="link">
								Getting started
							</Link>
						}
					/>
					<div className="grid min-w-0 content-start gap-6">
						<div className="flex flex-wrap gap-2.5">
							<a href={SITE.nightly + 'calcite-windows-x64.zip'} className={buttonClass()}>
								Download for Windows
							</a>
							<a href={SITE.nightly + 'calcite-linux-x64.tar.gz'} className={buttonClass({ variant: 'secondary' })}>
								Download for Linux
							</a>
						</div>
						<p className="text-[17px] leading-normal">
							<Link href="/download#setup" className="link">
								Set it up first
							</Link>
							: start from a preset, list who may join, give it a name and an icon, and the download comes ready to start.
						</p>
						<Disclosure summary="Or build it from source">
							<p className="mb-4 max-w-[62ch] text-[15px] leading-normal">Install Calx, then build Calcite with one command.</p>
							<Tabs
								label="Your system"
								tabs={[
							{
								title: 'Windows',
								content: (
									<CodeBlock
										lang="powershell"
										code={['# install Calx', 'irm https://calxlang.com/install.ps1 | iex', '# build Calcite', 'git clone https://github.com/ellipog/calcite', 'cd calcite', 'calx build --release src/calcite.calx -o server/calcite.exe', '# start it, then join localhost', 'cd server', '.\\calcite.exe'].join('\n')}
									/>
								),
							},
							{
								title: 'Linux',
								content: (
									<CodeBlock
										lang="sh"
										code={['# install Calx', 'curl -fsSL https://calxlang.com/install.sh | sh', '# build Calcite', 'git clone https://github.com/ellipog/calcite', 'cd calcite', 'calx build --release src/calcite.calx -o server/calcite', '# start it, then join localhost', 'cd server', './calcite'].join('\n')}
									/>
								),
							},
						]}
							/>
						</Disclosure>
					</div>
				</div>
			</Band>
		</>
	);
}
