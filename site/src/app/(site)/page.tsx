import type { Metadata } from 'next';
import { meta } from '@/lib/meta';
import Link from 'next/link';
import { Flyover } from '@/components/flyover';
import { Relief } from '@/components/pictures';
import { Kicker, PhaseStrip, SectionHead, Stats } from '@/components/site/parts';
import { ButtonLink } from '@/components/ui/button';
import { Tag } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { Tabs } from '@/components/ui/tabs';
import { Panel } from '@/components/ui/text';
import { DATA } from '@/lib/data';
import { differences, phases, samples, type Phase } from '@/lib/repo';
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
	{ title: 'Survival as vanilla plays it', text: 'Blocks, mobs, redstone and farms behave as they do on vanilla’s server, and the rig checks them against it. A farm built for vanilla works the same here.', phase: 6 },
	{ title: 'Vanilla’s worlds', text: 'Worlds are generated as vanilla generates them and saved in its format, so one can move to Calcite and back. Data packs such as Terralith work too.', phase: 5 },
	{ title: 'Every core', text: 'The world is split into regions that tick in parallel, in lockstep. A busy server uses the whole machine, and gets the same result on one thread as on 32.', phase: 5 },
	{ title: 'Plugins', text: 'Plugins in Calx run natively, at full speed. Plugins in any language that builds to WASM run in a sandbox. Both use the same API.', phase: 7 },
	{ title: 'Logins and proxies', text: 'Online and offline mode, signed chat, the whitelist, bans and operators as vanilla keeps them, and Velocity’s modern forwarding.', phase: 4 },
	{ title: 'Pregeneration', text: 'The pregen command is built in and takes Chunky’s subcommands. A task carries on after a restart, and steps aside while players are loading in.', phase: 5 },
	{ title: 'The console', text: 'A live dashboard on a terminal, and vanilla’s exact log lines in a file or a pipe, so hosting panels read it as they read vanilla.', phase: 4 },
	{ title: 'Recording and replay', text: 'A server can record everything it’s sent and replay it later, tick for tick, so a bug a player hit can be seen again and its fix checked.', phase: 5 },
];

function Pending({ phase, plan }: { phase: number; plan: Phase[] }) {
	const p = plan.find((x) => x.n === phase);
	if (!p || p.state === 'done') return null;
	return <Tag status={p.state === 'now' ? 'running' : 'planned'}>{p.state === 'now' ? `phase ${p.n}, in progress` : `phase ${p.n}`}</Tag>;
}

export default function Home() {
	const W = DATA.worldgen.runs, F = DATA.flight.runs['25'], B = DATA.bots, M = DATA.machine;
	const top = W[W.length - 1];
	const { phases: plan, passed } = phases();
	const now = plan.find((p) => p.state === 'now');
	const diffs = differences().length;
	const hostBuilt = plan.find((p) => p.n === 7)?.state === 'done';
	return (
		<>
			{/* ---- hero ---- */}
			<section className="pt-14 md:pt-20">
				<div className="wrap grid grid-cols-1 items-end gap-10 md:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
					<div>
						<Kicker>Minecraft: Java Edition {SITE.minecraft}</Kicker>
						<h1 className="font-display text-[clamp(48px,7.4vw,112px)] leading-[0.9] font-extrabold tracking-display text-balance">A Minecraft server written from scratch</h1>
					</div>
					<div className="pb-2">
						<p className="text-lg leading-normal md:text-xl">
							Calcite is built to play exactly like vanilla while using every core of the machine it runs on. It&apos;s written in Calx, and plugins can be written in Calx or in anything that builds to WASM.
						</p>
						<div className="mt-7 flex flex-wrap gap-2.5">
							<ButtonLink href="/docs/start">Get started</ButtonLink>
							<ButtonLink href="/benchmarks" variant="secondary">
								Benchmarks
							</ButtonLink>
						</div>
						{now && (
							<Link href="/roadmap" className="group mt-6 inline-flex items-center gap-3 text-[15px]">
								<Tag status="running">pre-release</Tag>
								<span className="group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">
									Phase {now.n}, {now.builds.toLowerCase()}, is in progress
								</span>
							</Link>
						)}
					</div>
				</div>
				<Flyover className="mt-14" chips={['a world Calcite generated']} />
			</section>

			{/* ---- what it does ---- */}
			<section className="wrap mt-24">
				<SectionHead title="What it does" lead={<p>Calcite shares no code with vanilla, Paper or any other server. It reads the same <code className="font-mono text-[0.9em]">server.properties</code> and the same worlds, and Mojang&apos;s client joins it as it joins vanilla.</p>} />
				<ul className="grid grid-cols-1 rule-t md:grid-cols-2">
					{FEATURES.map((f, i) => (
						<li key={f.title} className={i % 2 === 0 ? 'rule-b py-6 md:pr-10' : 'rule-b py-6 md:rule-l md:pl-10'}>
							<div className="flex flex-wrap items-center gap-x-3 gap-y-2">
								<h3 className="font-display text-[22px] leading-tight font-bold tracking-tight">{f.title}</h3>
								<Pending phase={f.phase} plan={plan} />
							</div>
							<p className="mt-2 max-w-[56ch] leading-relaxed">{f.text}</p>
						</li>
					))}
				</ul>
				<p className="mt-6">
					<Link href="/docs" className="link">
						The guide to running a server
					</Link>
				</p>
			</section>

			{/* ---- performance ---- */}
			<section className="wrap mt-28">
				<SectionHead
					title="Performance"
					lead={
						<p>
							Each tick, the world&apos;s regions run in parallel on every core. The tick never waits for the disk or the network: encoding, compression and saving happen on other threads. These numbers are from recorded runs on one machine, an {M.cpu} with {M.threads} threads on {M.os}.
						</p>
					}
				/>
				<Stats
					items={[
						{ label: '100 players', value: `${f3(B.windows.mean)} ms`, note: `a tick on average, with 100 players joining, walking outward and chatting; a tick has 50 ms` },
						{ label: 'Joining', value: `${n1(F.join.all)} s`, note: `for Mojang's client to load all ${n0(F.join.chunks)} chunks of a new world at view distance ${DATA.flight.view}` },
						{ label: 'Memory', value: `${n0(F.memory.idle)} MiB`, note: `held by an idle server, and ${n0(F.memory.still)} MiB with one player at view distance ${DATA.flight.view}` },
						{ label: 'World generation', value: n0(top.cps), note: `chunks a second on ${top.threads} threads, each one lit, saved and compressed` },
					]}
				/>
				<p className="mt-6">
					<Link href="/benchmarks" className="link">
						How each was measured, and against what
					</Link>
				</p>
			</section>

			{/* ---- parity ---- */}
			<section className="wrap mt-28 grid grid-cols-1 items-center gap-12 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
				<div>
					<SectionHead
						className="mb-7"
						title="Vanilla parity"
						lead={
							<p>
								A test rig gives vanilla&apos;s server and Calcite the same inputs and compares what comes out bit for bit, so a near miss counts as a failure. When matching vanilla and being fast pull apart, vanilla wins wherever a player, a farm or a data pack could notice.
							</p>
						}
					/>
					<ul className="grid gap-3 text-[17px] leading-normal">
						{[
							'Worldgen passes the rig’s suites in the Overworld, the Nether and the End, on a grid of seeds.',
							'With Terralith and Terratonic, every one of 264 sampled chunks has what must be vanilla’s.',
							'Light matches vanilla’s to the nibble.',
							'Logins match vanilla’s packet for packet.',
							'Worlds move between vanilla and Calcite in both directions.',
							`The ${diffs} places Calcite differs on purpose are listed, each a vanilla bug fixed or a limit stated.`,
						].map((t) => (
							<li key={t} className="relative pl-7">
								<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
								{t}
							</li>
						))}
					</ul>
					<p className="mt-7">
						<Link href="/docs/vanilla" className="link">
							Worlds, vanilla and the differences
						</Link>
					</p>
				</div>
				<Panel label="A generated world, from above" className="overflow-hidden p-0 pt-0">
					<Relief className="h-[380px] w-full" />
				</Panel>
			</section>

			{/* ---- plugins ---- */}
			<section className="wrap mt-28 grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
				<div>
					<SectionHead
						className="mb-7"
						title="Plugins"
						lead={<p>Every plugin is written against one host API. Native plugins are Calx and run at full speed. WASM plugins can come from any language that builds to WASM, and run in a sandbox that stops a runaway one.</p>}
					/>
					<ul className="grid gap-3 text-[17px] leading-normal">
						{[
							'A command is a function, and the client tab-completes and checks its arguments.',
							'Events are typed, and run in the region where they happen.',
							'Plugins keep data on players, chunks and entities, saved with the world.',
							'Reloading a plugin keeps its state, and every plugin is profiled all the time.',
						].map((t) => (
							<li key={t} className="relative pl-7">
								<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
								{t}
							</li>
						))}
					</ul>
					<p className="mt-7">
						<Link href="/plugins" className="link">
							More on plugins
						</Link>
					</p>
				</div>
				<div className="min-w-0">
					<CodeBlock code={excerpt()} comment="//" lang="calx" copy={false} />
					<p className="mt-3 font-mono text-xs leading-normal">From the homes sample plugin{hostBuilt ? '.' : ', in the draft syntax the API was designed with. It compiles once the plugin host is built.'}</p>
				</div>
			</section>

			{/* ---- roadmap ---- */}
			<section className="wrap mt-28">
				<SectionHead
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
				/>
				<PhaseStrip phases={plan} />
				<p className="mt-6">
					<Link href="/roadmap" className="link">
						The whole plan
					</Link>
				</p>
			</section>

			{/* ---- get started ---- */}
			<section className="wrap mt-28 grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
				<SectionHead
					className="mb-0"
					title="Get started"
					lead={
						<>
							<p>Install Calx, build Calcite with one command, and start it in a folder of its own, as you would vanilla&apos;s server. The guide has each step, and what to set up after.</p>
							<p className="mt-4">
								<Link href="/docs/start" className="link">
									Getting started
								</Link>
							</p>
						</>
					}
				/>
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
			</section>
		</>
	);
}
