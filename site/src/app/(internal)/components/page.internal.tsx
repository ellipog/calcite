import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { InternalBar } from '@/components/internal-bar';
import { Button } from '@/components/ui/button';
import { Accordion, Callout, Disclosure, Skeleton, Table, Tag } from '@/components/ui/feedback';
import { Checkbox, Field, Fieldset, Radio, Segmented, Select, Switch, TextArea } from '@/components/ui/form';
import { CodeBlock } from '@/components/ui/overlay';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Sub } from '@/components/ui/sub';
import { Tabs } from '@/components/ui/tabs';
import { Kbd, Panel, Tip, TextLink } from '@/components/ui/text';
import { DATA } from '@/lib/brand/data';
import { StopDialog, ToastButton, ViewDistance } from './_demos';

export const metadata: Metadata = { title: 'Components' };

const SECTIONS: [string, string][] = [
	['actions', 'actions'],
	['inputs', 'inputs'],
	['sliders', 'sliders'],
	['navigation', 'navigation'],
	['feedback', 'feedback'],
	['data', 'data'],
];

const Grid = ({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) => (
	<div className={cols === 2 ? 'grid grid-cols-1 gap-5 md:grid-cols-2' : 'grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3'}>{children}</div>
);
const Box = (p: { label: string; children: ReactNode; className?: string }) => (
	<Panel label={p.label} className={`grid grid-cols-1 content-start gap-[18px] ${p.className ?? ''}`}>
		{p.children}
	</Panel>
);
const fmt = (v: number, d = 1) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

export default function Components() {
	return (
		<>
			<InternalBar title="components · internal" sections={SECTIONS} here="/components" />
			<main className="wrap py-16">
				<header className="mb-14 grid grid-cols-1 gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
					<p className="label leading-[2.4]">Components</p>
					<div>
						<h1 className="mb-4 font-display text-[clamp(34px,4.6vw,52px)] leading-[0.98] font-extrabold tracking-title text-balance">Square, dotted, solid when it matters.</h1>
						<p className="max-w-[62ch]">
							Every component the site and docs use, in one place. Corners are square, borders are dotted, the one solid thing in a view is the action you want, and every change of state is a step through the matrix: checks fill in, lines wipe across with the dithered edge leading, and anything at work marches. Hovers are crisp: a frame or a line goes solid, a button inverts, and no dots appear under the pointer. Use the keyboard as well as the pointer: focus is a ring of marching cells. They live in <code className="font-mono text-[15px]">src/components/ui</code>; this page is internal and isn&apos;t built for production.
						</p>
					</div>
				</header>

				<section id="actions">
					<Sub first>Actions</Sub>
					<Grid>
						<Box label="Buttons · hover and press them">
							<div className="flex flex-wrap items-center gap-2.5">
								<Button>Download</Button>
								<Button variant="secondary">Read the docs</Button>
								<Button busy>Downloading</Button>
								<Button variant="secondary" disabled>
									Sold out
								</Button>
							</div>
							<p className="note">Primary is solid ink and turns to paper in a solid frame when you point at it; secondary is a dotted frame that fills solid. A button at work marches dots round its label; one you can&apos;t use is a few dots, with its word on a block of paper, still in ink.</p>
						</Box>
						<Box label="Links, keys, tooltips">
							<p>
								A <TextLink href="#actions">text link</TextLink> sits on a line of half-density cells, which goes solid when you point at it. Press <Kbd>T</Kbd> to open chat, or <Kbd>F3</Kbd> for the debug screen.
							</p>
							<div className="flex flex-wrap gap-2.5">
								<Tip text="12 chunks · 625 sent">
									<Button variant="secondary" size="sm">
										view distance
									</Button>
								</Tip>
								<Tip text="ready in 4.8 ms">
									<Button variant="secondary" size="sm">
										boot time
									</Button>
								</Tip>
							</div>
						</Box>
					</Grid>
				</section>

				<section id="inputs">
					<Sub>Inputs</Sub>
					<Grid cols={3}>
						<Box label="Fields · click into them">
							<Field label="Server address" placeholder="play.example.net" />
							<TextArea label="Message of the day" placeholder="A Calcite server" hint="Shown under the name in the server list, up to two lines." />
						</Box>
						<Box label="Checks, choices, switches">
							<Fieldset legend="Rules">
								<Checkbox defaultChecked>online mode</Checkbox>
								<Checkbox>pvp</Checkbox>
								<Checkbox indeterminate>some plugins on</Checkbox>
								<Checkbox defaultChecked disabled>
									eula, accepted
								</Checkbox>
							</Fieldset>
							<Fieldset legend="Difficulty">
								<Radio name="diff">peaceful</Radio>
								<Radio name="diff" defaultChecked>
									normal
								</Radio>
								<Radio name="diff">hard</Radio>
							</Fieldset>
							<Fieldset legend="Saving">
								<Switch defaultChecked>autosave</Switch>
								<Switch>whitelist</Switch>
								<Switch disabled>backups (needs space)</Switch>
							</Fieldset>
						</Box>
						<Box label="Select, segments">
							<Select label="World type" defaultValue="Large biomes">
								<option>Default</option>
								<option>Large biomes</option>
								<option>Amplified</option>
								<option>Superflat</option>
							</Select>
							<Segmented label="Pregen by" name="by" options={['radius', 'regions', 'world border']} />
							<p className="note">Where the browser lets a select&apos;s list be styled, it&apos;s paper in a solid frame, dissolving in, and the option under the pointer inverts.</p>
						</Box>
					</Grid>
				</section>

				<section id="sliders">
					<Sub>Sliders</Sub>
					<Grid>
						<Box label="dots">
							<Slider label="View distance" min={2} max={32} step={1} defaultValue={12} unit="chunks" pattern="dots" />
						</Box>
						<Box label="bars">
							<Slider label="RAM" min={0.5} max={8} step={0.5} defaultValue={1} unit="GB" pattern="bars" />
						</Box>
						<Box label="halftone">
							<Slider label="Pregen radius" min={500} max={10000} step={500} defaultValue={2000} unit="blocks" pattern="halftone" />
						</Box>
						<Box label="stripes">
							<Slider label="Worldgen threads" min={1} max={32} step={1} defaultValue={8} unit="threads" unitOne="thread" pattern="stripes" />
						</Box>
						<Box label="disabled">
							<Slider label="Simulation distance" min={2} max={32} step={1} defaultValue={10} unit="chunks" disabled />
							<p className="note">Set by the host. The fill drops to half density and the value stays in ink.</p>
						</Box>
						<Box label="stepped · 2 to 32, a step of 1" className="md:col-span-2">
							<ViewDistance />
						</Box>
					</Grid>
					<p className="note mt-3.5 max-w-[80ch]">
						There&apos;s no knob: click or drag anywhere on the track. While you drag, the fill sits right under the pointer; let go, or step with the arrow keys, Page Up and Down, Home and End, and it eases to the step in 80 ms, or jumps there if you&apos;ve asked for less motion. The edge lands on whole cells, 2 px each rounded to device pixels, so it&apos;s sharp at any density. The stepped one draws the mark at its view distance: at 12 chunks it is the mark.
					</p>
				</section>

				<section id="navigation">
					<Sub>Navigation, disclosure</Sub>
					<Grid>
						<Box label="Tabs · arrow keys move between them">
							<Tabs
								label="Docs"
								tabs={[
									{ title: 'Overview', content: <p>A Minecraft server written in Calx, made to match vanilla to the tick.</p> },
									{ title: 'Worldgen', content: <p>Vanilla&apos;s worldgen, checked against the real thing on a grid of seeds, at 150.6 chunks a second on one thread.</p> },
									{ title: 'Plugins', content: <p>Plugins are written in Calx, and each one runs inside a tick budget.</p> },
									{ title: 'Benchmarks', content: <p>Measured with Mojang&apos;s own client at render distance 32, on the machines in the README.</p> },
								]}
							/>
						</Box>
						<Box label="Questions">
							<Accordion
								items={[
									{ q: 'Is it vanilla?', a: "It's a new server that aims to match vanilla to the tick, and the oracle rig checks it against the real thing." },
									{ q: 'How fast is its worldgen?', a: "150.6 chunks a second on one thread and 2,022 on 32, with vanilla's worldgen, on our benchmark." },
									{ q: 'Where does progress show?', a: 'In the terminal, and in chat now and then. Never in a boss bar.' },
								]}
							/>
						</Box>
					</Grid>
				</section>

				<section id="feedback">
					<Sub>Feedback</Sub>
					<Grid>
						<Box label="Status">
							<div className="flex flex-wrap gap-2.5">
								<Tag status="done">gate passed</Tag>
								<Tag status="running">in progress</Tag>
								<Tag>planned</Tag>
							</div>
							<p className="note">Status is density, as the mark&apos;s leaves are: solid is done, half is under way and marches, empty is not started. Always with its word.</p>
							<Callout>Calcite&apos;s worldgen matches vanilla&apos;s, checked by the oracle rig on its seed grid.</Callout>
							<Callout title="Important" strong>
								Back up the world before you try a new build: a backup is the only undo.
							</Callout>
						</Box>
						<Box label="Progress, loading">
							<Progress label="pregen" value={0.61} />
							<Progress label="save" value={1} />
							<Progress label="looking for the world" />
							<Skeleton />
							<p className="note">A bar has the slider&apos;s edge, and its dots march while it works; one that can&apos;t know how far it is sends a block across instead. Long jobs show here and in the terminal, never in a boss bar.</p>
						</Box>
						<Box label="Toasts, dialogs">
							<div className="flex flex-wrap items-center gap-2.5">
								<ToastButton />
								<StopDialog />
							</div>
							<p className="note">A toast dissolves in and out at the bottom. A dialog puts the page under a screen of ink dots, stepping from 6 to 38%, and the box dissolves in. Escape, or a click on the screen, closes it.</p>
						</Box>
						<Box label="Code · copy it">
							<CodeBlock code={'# every chunk within 2000 blocks of 0, 0\npregen radius 2000\npregen start\n# players come first while it runs'} />
							<p className="note">The bar down the left is half density; it fills solid when the code is copied. Comments are left out of the copy.</p>
						</Box>
					</Grid>
				</section>

				<section id="data">
					<Sub>Data</Sub>
					<Panel label="Table · point at a row">
						<Table
							columns={[{ label: 'threads' }, { label: 'chunks/s', num: true }, { label: 'peak memory', num: true }]}
							rows={DATA.worldgen.runs.map((r) => [r.threads, fmt(r.cps), `${Math.round(r.mem)} MiB`])}
							strong={DATA.worldgen.runs.length - 1}
						/>
						<Disclosure summary="Where these come from" className="mt-4">
							<p className="note">bench/results/worldgen-windows.json at {DATA.worldgen.commit}: vanilla&apos;s worldgen through the whole server, on the reference machine.</p>
						</Disclosure>
					</Panel>
				</section>
			</main>
		</>
	);
}
