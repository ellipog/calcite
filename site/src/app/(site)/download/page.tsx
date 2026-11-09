import type { Metadata } from 'next';
import Link from 'next/link';
import { Band, PageHead, SectionHead } from '@/components/site/parts';
import { buttonClass } from '@/components/ui/button';
import { Callout } from '@/components/ui/feedback';
import { CodeBlock } from '@/components/ui/overlay';
import { Panel } from '@/components/ui/text';
import { JsonLd, trail } from '@/lib/ld';
import { meta } from '@/lib/meta';
import { PAGES } from '@/lib/pages';
import { SITE } from '@/lib/site';

export const metadata: Metadata = meta(PAGES.download);

// What the nightly workflow (.github/workflows/nightly.yml) writes beside the archives: the commit
// built, when, with which Calx, the glibc the Linux build needs, and each archive's size and
// checksum. Read again at most once an hour. The archives' addresses never change, so the buttons
// give the newest build whatever this says, and without it.
export const revalidate = 3600;

interface Nightly {
	commit: string;
	committed: string;
	calx: string;
	built: string;
	glibc: string;
	assets: { name: string; size: number; sha256: string }[];
}

async function nightly(): Promise<Nightly | null> {
	try {
		const r = await fetch(`${SITE.nightly}nightly.json`, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(5000) });
		if (!r.ok) return null;
		return (await r.json()) as Nightly;
	} catch {
		return null;
	}
}

const BUILDS = [
	{
		system: 'Windows',
		file: 'calcite-windows-x64.zip',
		needs: () => 'Windows 10 or 11, on x86-64.',
		lang: 'powershell',
		start: 'Expand-Archive calcite-windows-x64.zip -DestinationPath .\ncd calcite\n.\\calcite.exe',
	},
	{
		system: 'Linux',
		file: 'calcite-linux-x64.tar.gz',
		needs: (n: Nightly | null) => (n?.glibc ? `Linux on x86-64, with glibc ${n.glibc} or later.` : 'Linux on x86-64.'),
		lang: 'sh',
		start: 'tar -xzf calcite-linux-x64.tar.gz\ncd calcite\n./calcite',
	},
] as const;

const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const mb = (bytes: number) => `${(bytes / 1048576).toFixed(1)} MB`;

export default async function Download() {
	const n = await nightly();
	return (
		<>
			<JsonLd things={[trail([[PAGES.download.title, PAGES.download.path]])]} />
			<PageHead
				title="Download"
				lead={
					<p>
						There&apos;s no release of Calcite yet. Each night the newest commit whose tests passed is built for Windows and Linux, and those builds are here. To build it yourself instead, <Link href="/docs/start" className="link">Getting started</Link> says how.
					</p>
				}
			>
				<div className="mt-10 max-w-[72ch]">
					<Callout title="Development builds" strong>
						A nightly has passed Calcite&apos;s tests and nothing more. Back up a world before you open it with one. <Link href="/docs#what-works-today" className="link">What works today</Link> says what Calcite does so far.
					</Callout>
				</div>
			</PageHead>

			<section className="wrap mt-8">
				<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
					{BUILDS.map((b) => {
						const asset = n?.assets.find((a) => a.name === b.file);
						return (
							<Panel key={b.system} label={b.system} className="grid content-start gap-5">
								<p className="leading-normal">{b.needs(n)}</p>
								<a href={SITE.nightly + b.file} className={buttonClass({ className: 'justify-self-start' })}>
									Download for {b.system}
									{asset && <span className="font-mono text-xs font-normal">{mb(asset.size)}</span>}
								</a>
								<CodeBlock code={b.start} lang={b.lang} comment={null} />
								{asset && (
									<p className="font-mono text-xs leading-normal break-all">
										<span className="label mr-2">sha-256</span>
										{asset.sha256}
									</p>
								)}
							</Panel>
						);
					})}
				</div>
				<p className="mt-6 max-w-[72ch] text-[15px] leading-normal">
					{n ? (
						<>
							Built from{' '}
							<a href={`${SITE.github}/commit/${n.commit}`} className="link font-mono text-sm">
								{n.commit.slice(0, 7)}
							</a>
							, committed on {day(n.committed)}, with Calx at{' '}
							<a href={`https://github.com/ellipog/calx/commit/${n.calx}`} className="link font-mono text-sm">
								{n.calx.slice(0, 7)}
							</a>
							.{' '}
						</>
					) : null}
					Every build&apos;s notes and checksums are on{' '}
					<a href={SITE.nightlyRelease} className="link">
						the release on GitHub
					</a>
					.
				</p>
			</section>

			<Band>
				<SectionHead
					split
					title="The first start"
					lead={<p>Calcite keeps its files in the folder it&apos;s started in, as vanilla does, and the archive unpacks to a folder of its own, so it can start right there.</p>}
				/>
				<div className="grid grid-cols-1 gap-5 md:grid-cols-3">
					{[
						['Settings', 'It writes server.properties with every setting vanilla has, at its default, and calcite.properties with its own.'],
						["Vanilla's data", "It reads vanilla's data from Minecraft 26.3's client jar: the game's copy if a launcher has installed it, or else just the part of the jar that holds it, downloaded from Mojang and checked against its pinned hash."],
						['Players', 'The whitelist is on, as vanilla’s is by default. Turn it off with white-list=false, or list each player in whitelist.json, then restart it.'],
					].map(([title, text]) => (
						<div key={title} className="grid content-start gap-2 rule p-5">
							<h3 className="font-display text-lg leading-tight font-bold">{title}</h3>
							<p className="text-[15px] leading-normal">{text}</p>
						</div>
					))}
				</div>
			</Band>

			<Band>
				<SectionHead
					split
					title="License"
					lead={
						<p>
							Calcite is source-available under the Business Source License 1.1, and each version becomes MIT two years after it&apos;s published. It&apos;s free to run on your own servers, commercial ones included. A company that offers Calcite to its customers as a hosting service needs a host license, which is free for now. Each archive has LICENSE and NOTICE in it.
						</p>
					}
				/>
			</Band>

			<section className="mt-24 rule-t">
				<div className="wrap flex flex-wrap gap-x-8 gap-y-3 pt-8">
					<Link href="/docs/start" className="link">
						Getting started
					</Link>
					<a href={`${SITE.blob}docs/hosting.md`} className="link">
						The host license
					</a>
					<a href={SITE.nightlyRelease} className="link">
						The nightly on GitHub
					</a>
				</div>
			</section>
		</>
	);
}
