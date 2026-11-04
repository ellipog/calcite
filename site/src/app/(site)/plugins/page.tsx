import type { Metadata } from 'next';
import { JsonLd, trail } from '@/lib/ld';
import { meta } from '@/lib/meta';
import { PAGES } from '@/lib/pages';
import Link from 'next/link';
import { Markdown } from '@/components/markdown';
import { Band, PageHead, SectionHead } from '@/components/site/parts';
import { Callout } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { Tabs } from '@/components/ui/tabs';
import { Panel } from '@/components/ui/text';
import { cn } from '@/lib/cn';
import { routes } from '@/lib/docs';
import { inline, plain } from '@/lib/markdown';
import { phases, read, samples, section } from '@/lib/repo';
import { SITE } from '@/lib/site';

export const metadata: Metadata = meta(PAGES.plugins);

const API = 'plugins/api/HOST_API.md', SAMPLES = 'plugins/samples/README.md';

// The sketch's table of what plugin development needs: each need, and the section that meets it.
// Decision ids such as (D36) mean something in the repo, not to a reader here, so they go.
function needs() {
	const rows = [...section(read(API), '## What great plugin development needs from this API').matchAll(/^\| \*\*(.+?)\*\*(.*?) \| \[(.+?)\]\(#.+?\) \|$/gm)];
	return rows.map((r) => ({ title: r[1], rest: plain(inline(r[2].trim())).replace(/^[,:]\s*/, '').replace(/\s*\(D\d+\)/g, ''), where: r[3] }));
}

// On a wide screen the needs go as many across as fill every row, so no row is left with a gap.
const across = (n: number) => (n % 5 === 0 ? 'xl:grid-cols-5' : n % 4 === 0 ? 'xl:grid-cols-4' : 'xl:grid-cols-3');

export default function Plugins() {
	const host = read(API), drafts = read(SAMPLES), r = routes();
	const p7 = phases().phases.find((p) => p.n === 7);
	return (
		<>
			<JsonLd things={[trail([[PAGES.plugins.title, PAGES.plugins.path]])]} />
			<PageHead
				title="Plugins"
				lead={
					<p>
						Calcite has one plugin API and two ways to run a plugin. Native plugins are written in Calx and compiled, and run at full speed. WASM plugins can be written in any language that builds to WASM, and run in a sandbox.
					</p>
				}
			>
				{p7?.state !== 'done' && (
					<div className="mt-10 max-w-[72ch]">
						<Callout title="Not built yet" strong>
							The plugin host is Phase 7 of the plan. Until then the API on this page is a sketch, and the samples are in Calx&apos;s draft syntax. Phase 7 is done when all five samples run on it.
						</Callout>
					</div>
				)}
			</PageHead>

			<section className="wrap mt-8">
				<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
					<Panel className="grid content-start gap-4">
						<h2 className="font-display text-3xl leading-tight font-bold tracking-tight">Native Calx plugins</h2>
						<ul className="grid gap-2.5 leading-normal">
							{[
								'Each one compiles to a shared library against the host API, and they load in parallel as the server starts.',
								'The compiler checks where code may run, so a handler can’t touch another region’s part of the world.',
								'The compiler puts cheap budget checks in loops, so a plugin stuck in one is stopped without a sandbox. A panic stops only the plugin that panicked.',
								'A new build can be swapped in between ticks, with a hook to carry the old one’s state over.',
							].map((t) => (
								<li key={t} className="relative pl-6">
									<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
									{t}
								</li>
							))}
						</ul>
					</Panel>
					<Panel className="grid content-start gap-4">
						<h2 className="font-display text-3xl leading-tight font-bold tracking-tight">WASM plugins</h2>
						<ul className="grid gap-2.5 leading-normal">
							{[
								'The same API, as imports, in Wasmtime. Each plugin is granted its capabilities one by one.',
								'The runtime keeps the budgets, so a plugin from someone you don’t know can’t hold up the tick.',
								'Any language that builds to WASM can be used. SDKs are generated from the API, starting with Rust.',
								'A Calx plugin that stays within the API can be built either way from the same source.',
							].map((t) => (
								<li key={t} className="relative pl-6">
									<span aria-hidden className="absolute top-[0.55em] left-0 size-[6px] bg-ink" />
									{t}
								</li>
							))}
						</ul>
					</Panel>
				</div>
			</section>

			<Band>
				<SectionHead split title="What the API covers" lead={<p>The API was sketched against one rule: anything plugins commonly need should take a few lines, and work the same in both kinds of plugin.</p>} />
				{/* each cell draws its top and left rules and the grid its right and bottom, so every dotted line is drawn once */}
				<div className={cn('grid grid-cols-1 rule-r rule-b md:grid-cols-2', across(needs().length))}>
					{needs().map((n) => (
						<div key={n.title} className="grid content-start gap-2 rule-t rule-l p-5">
							<h3 className="font-display text-lg leading-tight font-bold">{n.title}</h3>
							<p className="text-[15px] leading-normal">{n.rest.charAt(0).toUpperCase() + n.rest.slice(1)}</p>
						</div>
					))}
				</div>
			</Band>

			<Band>
				<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:gap-16">
					<SectionHead
						className="mb-0"
						title="Where code runs"
						lead={<p>Calcite splits the world into regions that tick on every core. A plugin has one instance in each region and one global instance, and they talk by messages, so plugins scale with the server and never tie it to one thread.</p>}
					/>
					<div className="min-w-0">
						<Markdown source={section(host, '## Where code runs')} path={API} routes={r} />
					</div>
				</div>
			</Band>

			<Band>
				<SectionHead
					split
					title="The five samples"
					lead={<p>These were written before Calx or the API existed, to find out what both would need. Phase 7 ports them to the real syntax and tests the plugin host with them, and Phase 9 turns them into tutorials.</p>}
				/>
				{/* on a wide screen, what a sample tests sits beside its code, and the code gets the height to show more of itself */}
				<Tabs
					label="Sample plugins"
					tabs={samples().map((s) => ({
						title: s.name.replace(/ \(.+\)$/, ''),
						content: (
							<div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,2.6fr)] xl:gap-x-10 xl:pt-4">
								<div className="grid content-start gap-3 text-[15px]">
									<p className="max-w-[48ch]">
										<b className="font-semibold">Stresses:</b> {s.stresses.charAt(0).toLowerCase() + s.stresses.slice(1)}.
									</p>
									<a href={SITE.blob + s.path} className="link justify-self-start font-mono text-xs">
										{s.path}
									</a>
								</div>
								<CodeBlock code={s.code.trimEnd()} lang="calx" comment="//" copy={false} className="max-h-[560px] overflow-y-auto xl:max-h-[min(760px,80svh)]" />
							</div>
						),
					}))}
				/>
			</Band>

			<Band>
				<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:gap-16">
					<SectionHead className="mb-0" title="What the samples settled" lead={<p>Writing them settled how the API has to work. The points that became decisions are in the decision log.</p>} />
					<div className="min-w-0">
						<Markdown source={section(drafts, '## What the drafts found').replace(/^These are the design results.*\n+/, '')} path={SAMPLES} routes={r} />
					</div>
				</div>
			</Band>

			<section className="mt-24 rule-t">
				<div className="wrap flex flex-wrap gap-x-8 gap-y-3 pt-8">
					<Link href="/docs/host-api" className="link">
						The host API, call by call
					</Link>
					<a href={`${SITE.tree}plugins/samples`} className="link">
						The samples on GitHub
					</a>
					<Link href="/roadmap#phase-7" className="link">
						Phase 7, the plugin host
					</Link>
				</div>
			</section>
		</>
	);
}
