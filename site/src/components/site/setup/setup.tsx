'use client';

// The download page's setup: a preset to start from, the settings a new server needs on its first
// day, and the nightly with them in it. The archive is fetched through /download/archive (GitHub
// sends no CORS headers) and the files go in here, in the browser (lib/setup/archive.ts), so what's
// set never leaves the page. Player names are the one thing sent anywhere, to be looked up.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Callout, Disclosure } from '@/components/ui/feedback';
import { Field, Segmented, Select, Switch } from '@/components/ui/form';
import { CodeBlock, useToast } from '@/components/ui/overlay';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Sub } from '@/components/ui/sub';
import { Tabs } from '@/components/ui/tabs';
import { cn } from '@/lib/cn';
import { retar, rezip, zipOf } from '@/lib/setup/archive';
import {
	applyPreset,
	calciteProperties,
	COLOURS,
	DASHBOARDS,
	decode,
	DEFAULTS,
	DIFFICULTIES,
	encode,
	files,
	FORMATS,
	idOn,
	MODES,
	opsJson,
	plainMotd,
	presetOf,
	PRESETS,
	serverProperties,
	slug,
	whitelistJson,
	WORLDS,
	type Setup as SetupT,
	type WorldType,
} from '@/lib/setup/settings';
import { IconPicker, ServerRow, toIcon, type Fit } from './parts';
import { Players } from './players';

type Os = 'windows' | 'linux';
const ARCHIVE: Record<Os, { file: string; ext: string; title: string }> = {
	windows: { file: 'calcite-windows-x64.zip', ext: 'zip', title: 'Windows' },
	linux: { file: 'calcite-linux-x64.tar.gz', ext: 'tar.gz', title: 'Linux' },
};
const mb = (b: number) => `${(b / 1048576).toFixed(1)} MB`;

interface Job {
	label: string;
	value?: number;
	done?: string;
	error?: string;
}

function save(blob: Blob, name: string) {
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = name;
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(a.href), 30_000);
}

// A random seed, as a signed 64-bit number, as vanilla picks one.
function randomSeed() {
	const b = new BigInt64Array(1);
	crypto.getRandomValues(b);
	return b[0].toString();
}

// A group of settings, its heading on a dotted rule.
function Group({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
	return (
		<section className={cn('grid gap-6', className)}>
			<Sub first className="mb-0">
				{title}
			</Sub>
			{children}
		</section>
	);
}

export function Setup({ defaults, sizes }: { defaults: string; sizes: Partial<Record<Os, number>> }) {
	const [s, setS] = useState<SetupT>(DEFAULTS);
	const set = useCallback((f: (s: SetupT) => SetupT) => setS(f), []);
	const put = <K extends keyof SetupT>(k: K, v: SetupT[K]) => setS((x) => ({ ...x, [k]: v }));
	const [icon, setIcon] = useState<{ png: Uint8Array; url: string } | null>(null);
	const [from, setFrom] = useState<string>('vanilla');
	const [job, setJob] = useState<Job | null>(null);
	const [os, setOs] = useState<Os>('windows');
	const fetched = useRef<Partial<Record<Os, Uint8Array>>>({});
	const motdAt = useRef(0);
	const toast = useToast();

	// A link's setup, from the address's fragment, and the system this is, for the first button.
	useEffect(() => {
		const m = /^#setup=(.+)$/.exec(location.hash);
		const linked = m ? decode(m[1]) : null;
		const linux = /Linux|X11/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent);
		queueMicrotask(() => {
			if (linux) setOs('linux');
			if (linked) {
				setS(linked);
				setFrom(presetOf(linked) ?? '');
				document.getElementById('setup')?.scrollIntoView();
			}
		});
	}, []);

	const preset = presetOf(s);
	const folder = slug(s.name);
	const add = useMemo(() => files(s, defaults, icon?.png ?? null), [s, defaults, icon]);
	const calcite = calciteProperties(s, defaults);
	const listedCount = s.players.filter((p) => idOn(s, p)).length;

	const warnings: string[] = [];
	if (!s.onlineMode) warnings.push('Online mode is off: anyone can join under any name, an op’s included. Keep the server to your own machine, or a network you trust.');
	if (s.whitelist && listedCount === 0) warnings.push('The whitelist is on and nobody is on it, so nobody can join yet. Add yourself under Whitelist and ops, or turn the whitelist off.');
	const missing = s.onlineMode ? s.players.filter((p) => p.missing) : [];
	if (missing.length) warnings.push(`No account has the name ${missing.map((p) => p.name).join(', ')}, so ${missing.length === 1 ? 'it’s' : 'they’re'} left out.`);

	// The icon is made again from the image whenever it or the fit changes.
	const [image, setImage] = useState<Blob | null>(null);
	const [fit, setFit] = useState<Fit>('fill');
	useEffect(() => {
		if (!image) return;
		let live = true;
		toIcon(image, fit)
			.then(async (png) => {
				const bytes = new Uint8Array(await png.arrayBuffer());
				if (!live) return;
				setIcon((old) => {
					if (old) URL.revokeObjectURL(old.url);
					return { png: bytes, url: URL.createObjectURL(png) };
				});
			})
			.catch(() => {
				if (live) toast('The browser couldn’t read that image');
			});
		return () => {
			live = false;
		};
	}, [image, fit, toast]);
	const pickImage = (b: Blob | null) => {
		setImage(b);
		if (!b) {
			if (icon) URL.revokeObjectURL(icon.url);
			setIcon(null);
		}
	};

	const build = async (which: Os) => {
		const a = ARCHIVE[which];
		const name = `${folder}-${which}-x64.${a.ext}`;
		try {
			let src = fetched.current[which];
			if (!src) {
				setJob({ label: 'Fetching the nightly', value: 0 });
				const r = await fetch(`/download/archive/${a.file}`);
				if (!r.ok || !r.body) throw new Error(`the nightly couldn’t be fetched (${r.status})`);
				const total = Number(r.headers.get('content-length')) || sizes[which] || 0;
				const reader = r.body.getReader();
				const parts: Uint8Array[] = [];
				let got = 0, shown = 0;
				for (;;) {
					const { done, value } = await reader.read();
					if (done) break;
					parts.push(value);
					got += value.length;
					if (total && got - shown > 262_144) {
						shown = got;
						setJob({ label: `Fetching the nightly · ${mb(got)} of ${mb(total)}`, value: Math.min(0.99, got / total) });
					}
				}
				src = new Uint8Array(got);
				let at = 0;
				for (const p of parts) {
					src.set(p, at);
					at += p.length;
				}
				fetched.current[which] = src;
			}
			setJob({ label: `Adding ${add.length} file${add.length === 1 ? '' : 's'}` });
			const blob = which === 'windows' ? rezip(src, folder, add) : await retar(src, folder, add);
			save(blob, name);
			setJob({ label: name, value: 1, done: 'saved' });
			toast(`Saved ${name}`);
		} catch (e) {
			setJob({ label: 'It didn’t work', error: `The download stopped: ${(e as Error).message}. The files alone still work, beside a plain download.` });
		}
	};

	const share = async () => {
		const url = `${location.origin}${location.pathname}#setup=${encode(s)}`;
		try {
			await navigator.clipboard.writeText(url);
			toast(icon ? 'Copied a link to this setup, without the icon' : 'Copied a link to this setup');
		} catch {
			toast('Couldn’t copy: the browser said no');
		}
	};

	const insert = (code: string) => {
		const i = motdAt.current;
		setS((x) => {
			const motd: [string, string] = [...x.motd];
			motd[i] = motd[i] + code;
			return { ...x, motd };
		});
	};

	const start = (which: Os) =>
		which === 'windows'
			? `Expand-Archive ${folder}-windows-x64.zip -DestinationPath .\ncd ${folder}\n.\\calcite.exe`
			: `tar -xzf ${folder}-linux-x64.tar.gz\ncd ${folder}\n./calcite`;

	const other: Os = os === 'windows' ? 'linux' : 'windows';
	const busy = job !== null && job.value !== 1 && !job.error;

	// The buttons, what they give and how it's going: beside the settings, and again under them.
	const downloads = (
		<div className="flex flex-wrap gap-2.5">
			{[os, other].map((w, i) => (
				<Button key={w} variant={i === 0 ? 'primary' : 'secondary'} busy={busy} disabled={busy} onClick={() => build(w)}>
					Download for {ARCHIVE[w].title}
					{sizes[w] && <span className="ml-2 font-mono text-xs font-normal">{mb(sizes[w]!)}</span>}
				</Button>
			))}
		</div>
	);
	const summary = (
		<>
			The nightly, unpacking to <code className="font-mono text-[0.9em] text-ink">{folder}/</code>, with {add.map((f) => f.name).join(', ').replace(/, ([^,]*)$/, ' and $1')} in it. It’s put together here, in your browser.
		</>
	);
	const progress = job && (job.error ? <Callout title={job.label}>{job.error}</Callout> : <Progress label={job.label} value={job.value} done={job.done} />);

	return (
		<div className="grid gap-12">
			{/* ---- presets ---- */}
			<div className="grid gap-3">
				<div className="flex flex-wrap items-baseline justify-between gap-3">
					<span className="label">Start from</span>
					{!preset && from && <span className="font-mono text-xs text-soft">{PRESETS.find((p) => p.id === from)?.name}, changed</span>}
				</div>
				<div role="radiogroup" aria-label="Start from" className="grid grid-cols-1 gap-3 xs:grid-cols-2 md:grid-cols-3 2xl:grid-cols-6">
					{PRESETS.map((p) => {
						const on = preset === p.id;
						return (
							<button
								key={p.id}
								type="button"
								role="radio"
								aria-checked={on}
								onClick={() => {
									setS((x) => applyPreset(x, p));
									setFrom(p.id);
								}}
								className={cn('grid content-start gap-1.5 border p-4 text-left', on ? 'border-ink bg-ink text-paper' : 'border-dotted border-ink hover:border-solid')}
							>
								<b className="font-display text-lg leading-tight font-bold">{p.name}</b>
								<span className={cn('text-sm leading-snug', on ? 'text-paper' : 'text-deep')}>{p.about}</span>
							</button>
						);
					})}
				</div>
			</div>

			<div className="grid grid-cols-1 gap-x-16 gap-y-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
				{/* ---- the settings ---- */}
				<div className="grid min-w-0 content-start gap-12">
					<Group title="The server">
						<div className="grid gap-6 md:grid-cols-2">
							<Field label="Name" placeholder="calcite" value={s.name} maxLength={60} onChange={(e) => put('name', e.target.value)} hint={`It unpacks to ${folder}/`} />
							<Field label="Port" type="number" min={1} max={65535} value={s.port} onChange={(e) => put('port', Math.min(65535, Math.max(1, Number(e.target.value) || 25565)))} hint="25565 needs no port in the address" />
						</div>
						<div className="grid gap-6 md:grid-cols-2">
							{[0, 1].map((i) => (
								<Field
									key={i}
									label={`MOTD, line ${i + 1}`}
									value={s.motd[i]}
									maxLength={120}
									placeholder={i === 1 ? 'a second line, if you like' : undefined}
									onFocus={() => (motdAt.current = i)}
									onChange={(e) => {
										const motd: [string, string] = [...s.motd];
										motd[i] = e.target.value;
										put('motd', motd);
									}}
									hint={plainMotd(s.motd[i]).length > 45 ? `${plainMotd(s.motd[i]).length} letters: about 45 fit` : undefined}
								/>
							))}
						</div>
						<Disclosure summary="Colours and formats">
							<p className="mb-3 max-w-[60ch] text-sm leading-normal">An &amp; and a code changes what follows, as the list shows above. Press one to add it to the line you were last in. A colour ends any format before it, and &amp;r ends both.</p>
							<div className="flex flex-wrap gap-1.5">
								{[...Object.entries(COLOURS).map(([k, c]) => [k, c.name] as const), ...Object.entries(FORMATS)].map(([k, name]) => (
									<Button key={k} variant="secondary" size="sm" onClick={() => insert(`&${k}`)}>
										&amp;{k} {name}
									</Button>
								))}
							</div>
						</Disclosure>
						<IconPicker icon={icon?.url ?? null} fit={fit} onFit={setFit} onImage={pickImage} onError={toast} />
					</Group>

					<Group title="The game">
						<div className="flex flex-wrap gap-x-10 gap-y-6">
							<Segmented label="Game mode" name="gamemode" options={MODES} value={s.gamemode} onChange={(v) => put('gamemode', v as SetupT['gamemode'])} className="max-w-full!" />
							{s.hardcore ? (
								// hardcore is always on hard, so there's nothing to pick
								<div className="grid gap-1.5">
									<span className="label">Difficulty</span>
									<div className="flex items-center gap-3">
										<span className="bg-ink px-3.5 py-[9px] font-mono text-[13px] leading-none text-paper">hard</span>
										<span className="font-mono text-xs text-soft">as hardcore always is</span>
									</div>
								</div>
							) : (
								<Segmented label="Difficulty" name="difficulty" options={DIFFICULTIES} value={s.difficulty} onChange={(v) => put('difficulty', v as SetupT['difficulty'])} className="max-w-full!" />
							)}
						</div>
						<div className="flex flex-wrap gap-x-8 gap-y-3">
							<Switch checked={s.hardcore} onChange={(e) => put('hardcore', e.target.checked)}>
								Hardcore: one life
							</Switch>
							<Switch checked={s.forceGamemode} onChange={(e) => put('forceGamemode', e.target.checked)}>
								Everyone joins in {s.gamemode}
							</Switch>
							<Switch checked={s.allowFlight} onChange={(e) => put('allowFlight', e.target.checked)}>
								Allow flight
							</Switch>
						</div>
						<div className="grid gap-6 md:grid-cols-2">
							<Slider label="Players at once" min={1} max={200} value={s.maxPlayers} onValueChange={(v) => put('maxPlayers', v)} />
							<Slider label="Spawn protection" min={0} max={64} value={s.spawnProtection} unit="blocks" unitOne="block" format={(v) => (v === 0 ? 'off' : `${v} block${v === 1 ? '' : 's'}`)} onValueChange={(v) => put('spawnProtection', v)} />
						</div>
					</Group>

					<Group title="The world">
						<div className="grid gap-6 md:grid-cols-2">
							<Select label="Type" value={s.worldType} onChange={(e) => put('worldType', e.target.value as WorldType)}>
								{WORLDS.map((w) => (
									<option key={w.id} value={w.id}>
										{w.name}
									</option>
								))}
							</Select>
							<div className="flex items-end gap-3">
								<Field label="Seed" placeholder="random" value={s.seed} maxLength={60} onChange={(e) => put('seed', e.target.value)} className="min-w-0 flex-1" />
								<Button variant="secondary" size="sm" className="mb-2.5" onClick={() => put('seed', randomSeed())}>
									pick one
								</Button>
							</div>
							<Field label="Folder" value={s.levelName} maxLength={60} placeholder="world" onChange={(e) => put('levelName', e.target.value.replace(/[\\/:*?"<>|]/g, ''))} hint="Where the world is saved, in the server’s folder" />
							<div className="flex items-end pb-3">
								<Switch checked={s.structures} onChange={(e) => put('structures', e.target.checked)}>
									Villages, temples and other structures
								</Switch>
							</div>
						</div>
						<div className="grid gap-6 md:grid-cols-2">
							<Slider label="View distance" min={2} max={32} value={s.viewDistance} unit="chunks" onValueChange={(v) => put('viewDistance', v)} />
							<Slider label="Simulation distance" min={2} max={32} value={s.simulationDistance} unit="chunks" onValueChange={(v) => put('simulationDistance', v)} />
						</div>
					</Group>

					<Group title="Whitelist and ops">
						<div className="flex flex-wrap gap-x-8 gap-y-3">
							<Switch checked={s.whitelist} onChange={(e) => put('whitelist', e.target.checked)}>
								Whitelist: only the players below can join
							</Switch>
							<Switch checked={s.onlineMode} onChange={(e) => put('onlineMode', e.target.checked)}>
								Check accounts with Mojang
							</Switch>
						</div>
						<p className="max-w-[62ch] text-[15px] leading-normal">
							Everyone you add goes in whitelist.json, and those marked op in ops.json, at level 4, so they can run every command. {s.onlineMode ? 'Each name is looked up with Mojang as you type it, for its UUID.' : 'With accounts not checked, the UUIDs are made from the names, as the server makes them.'}
						</p>
						<Players s={s} set={set} />
					</Group>

					<Group title="Running it">
						<div className="grid gap-6 md:grid-cols-2">
							<Slider label="Pause when empty after" min={0} max={300} step={10} value={s.pauseWhenEmpty} format={(v) => (v === 0 ? 'never' : `${v} s`)} onValueChange={(v) => put('pauseWhenEmpty', v)} />
							<Field label="Login throttle" type="number" min={0} max={60000} step={500} value={s.loginThrottle} onChange={(e) => put('loginThrottle', Math.min(60000, Math.max(0, Number(e.target.value) || 0)))} hint="Milliseconds between logins from one address. 4000 suits a public server" />
						</div>
						<Segmented label="Console dashboard" name="dashboard" options={DASHBOARDS} value={s.dashboard} onChange={(v) => put('dashboard', v as SetupT['dashboard'])} />
						<p className="-mt-3 max-w-[62ch] text-[15px] leading-normal">A bar pinned to the terminal with TPS, MSPT, players, memory, CPU and chunks, with commands typed beside it. Only on a terminal, never in a log or a hosting panel.</p>
					</Group>

					<Group title="Download">
						{downloads}
						<p className="text-sm leading-normal">{summary}</p>
						{progress}
					</Group>
				</div>

				{/* ---- the preview and the download ---- */}
				<aside className="grid min-w-0 content-start gap-8 lg:sticky lg:top-24 lg:self-start [&>*]:min-w-0">
					<div className="grid gap-2">
						<span className="label">In the server list</span>
						<ServerRow s={s} icon={icon?.url ?? null} />
					</div>

					<div className="grid gap-4 rule p-5">
						{downloads}
						<p className="text-sm leading-normal">{summary}</p>
						{progress}
						{warnings.map((w) => (
							<Callout key={w} title="Before you start it">
								{w}
							</Callout>
						))}
						<div className="flex flex-wrap gap-x-6 gap-y-2 text-[15px]">
							<button type="button" className="link" onClick={share}>
								Copy a link to this setup
							</button>
							<button type="button" className="link" onClick={() => save(zipOf(folder, add), `${folder}-setup.zip`)}>
								Just the files, for a server you have
							</button>
						</div>
						<Disclosure summary="How to start it">
							<div className="grid gap-3 pb-1">
								<CodeBlock code={start(os)} lang={os === 'windows' ? 'powershell' : 'sh'} comment={null} />
							</div>
						</Disclosure>
					</div>

					<Tabs
						label="The files"
						tabs={[
							{ title: 'server.properties', content: <CodeBlock code={serverProperties(s).trimEnd()} lang="properties" /> },
							{ title: 'whitelist.json', content: listedCount ? <CodeBlock code={whitelistJson(s).trimEnd()} lang="json" /> : <p className="text-[15px] leading-normal">Not written: nobody is listed.</p> },
							{ title: 'ops.json', content: s.players.some((p) => p.op && idOn(s, p)) ? <CodeBlock code={opsJson(s).trimEnd()} lang="json" /> : <p className="text-[15px] leading-normal">Not written: nobody is an op.</p> },
							{
								title: 'calcite.properties',
								content: calcite ? <CodeBlock code={calcite.trimEnd()} lang="properties" className="max-h-[420px] overflow-y-auto" /> : <p className="text-[15px] leading-normal">Not written: Calcite’s own settings are all at their defaults, and it writes them on its first start.</p>,
							},
						]}
					/>
				</aside>
			</div>
		</div>
	);
}
