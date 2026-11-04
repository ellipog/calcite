import type { Metadata } from 'next';
import { JsonLd, trail } from '@/lib/ld';
import { meta } from '@/lib/meta';
import { PAGES } from '@/lib/pages';
import { MarkdownLine } from '@/components/markdown';
import { PageHead, PhaseStrip } from '@/components/site/parts';
import { Disclosure, Tag } from '@/components/ui/feedback';
import { phases, type Phase } from '@/lib/repo';
import { SITE } from '@/lib/site';
import { cn } from '@/lib/cn';

export const metadata: Metadata = meta(PAGES.roadmap);

// The board's public roadmap on Acta, read again at most once an hour. It lists only tasks marked
// public, and the site shows them only when there are some.
export const revalidate = 3600;
const FEED = 'https://acta.aaenz.no/api/public/aaen-studios/calcite';

interface Task {
	id: string;
	title: string;
	stage: 'planned' | 'progress' | 'shipped';
}

async function board(): Promise<{ stages: Record<string, string>; tasks: Task[] } | null> {
	try {
		const r = await fetch(FEED, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(5000) });
		if (!r.ok) return null;
		const f = await r.json();
		return { stages: f.page?.stages ?? {}, tasks: (f.tasks ?? []).map((t: Task) => ({ id: t.id, title: t.title, stage: t.stage })) };
	} catch {
		return null;
	}
}

const STATE = { done: ['done', 'passed'], now: ['running', 'in progress'], next: ['planned', 'to come'] } as const;

// A phase across the page: its rule runs from one edge of the window to the other, solid for the
// phase in progress. On a wide screen the number, what it builds and its gate are on the left, and
// the gate's checklist and the tasks are on the right, on the head's lead line.
function PhaseRow({ p }: { p: Phase }) {
	const [status, word] = STATE[p.state];
	return (
		<section id={`phase-${p.n}`} className={cn('scroll-mt-16 rule-t', p.state === 'now' && 'border-t-2 border-solid')}>
			<div className="wrap grid grid-cols-1 gap-x-10 gap-y-5 py-10 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] xl:py-12">
				<div className="grid grid-cols-1 gap-x-10 gap-y-4 md:grid-cols-[120px_minmax(0,1fr)]">
					<div className="flex items-start gap-4 md:block">
						<b className={cn('block font-display text-[64px] leading-[0.8] font-extrabold tracking-display tabular-nums xl:text-[88px]', p.state === 'next' && 'font-bold')}>{String(p.n).padStart(2, '0')}</b>
						<div className="md:mt-4">
							<Tag status={status}>{word}</Tag>
						</div>
					</div>
					<div className="min-w-0">
						<h2 className="font-display text-[clamp(28px,3.4vw,48px)] leading-none font-extrabold tracking-title text-balance">{p.builds}</h2>
						<p className="mt-4 max-w-[64ch] text-lg leading-normal">
							<span className="label mr-2 align-[2px]">gate</span>
							<MarkdownLine text={p.gate} path="docs/PLAN.md" />.
						</p>
					</div>
				</div>
				<div className="min-w-0 md:max-xl:pl-[160px] xl:pt-1">
					{p.gates.length > 0 && (
						<ul className="grid max-w-[70ch] gap-2">
							{p.gates.map((g) => (
								<li key={g.id} className="relative pl-8 text-[15px] leading-normal">
									<span aria-hidden className={cn('absolute top-[0.3em] left-0 grid size-4 place-items-center border border-ink', !g.done && 'border-dotted')}>
										{g.done && <i className="size-2 bg-ink" />}
									</span>
									<span className="mr-2 font-mono text-xs">{g.id}</span>
									<MarkdownLine text={g.text} path="docs/PLAN.md" />
									<span className="sr-only">{g.done ? ' (passed)' : ' (not yet)'}</span>
								</li>
							))}
						</ul>
					)}
					{p.tasks.length > 0 && (
						<Disclosure summary={`The ${p.tasks.length} tasks`} className="mt-5">
							<ul className="grid max-w-[76ch] gap-2.5 pt-2 pb-2">
								{p.tasks.map((t) => (
									<li key={t.id} className="grid grid-cols-[52px_minmax(0,1fr)] gap-2 text-[15px] leading-normal">
										<span className="pt-0.5 font-mono text-xs">{t.id}</span>
										<span>
											<MarkdownLine text={t.text} path="docs/PLAN.md" />
										</span>
									</li>
								))}
							</ul>
						</Disclosure>
					)}
				</div>
			</div>
		</section>
	);
}

export default async function Roadmap() {
	const { phases: plan, passed } = phases();
	const live = await board();
	const tasks = live?.tasks ?? [];
	return (
		<>
			<JsonLd things={[trail([[PAGES.roadmap.title, PAGES.roadmap.path]])]} />
			<PageHead
				title="Roadmap"
				lead={
					<p>
						Calcite is built in {plan.length} phases, and none starts until the one before it has passed its gate. {passed + 1 >= plan.length ? 'All of them have passed.' : `Phases 0 to ${passed} have passed.`} The plan, with every task and decision, is in the repo, and the work is tracked on Acta.
					</p>
				}
			>
				<PhaseStrip phases={plan} className="mt-12" />
			</PageHead>

			{plan.map((p) => (
				<PhaseRow key={p.n} p={p} />
			))}

			{tasks.length > 0 && (
				<section className="wrap mt-16 rule-t pt-12">
					<h2 className="font-display text-[clamp(28px,3.4vw,40px)] leading-none font-extrabold tracking-title">From the board</h2>
					<div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-3">
						{(['progress', 'planned', 'shipped'] as const).map((s) => (
							<div key={s} className="rule p-5">
								<p className="label mb-4">{live?.stages[s] ?? s}</p>
								<ul className="grid gap-3 text-[15px] leading-snug">
									{tasks
										.filter((t) => t.stage === s)
										.map((t) => (
											<li key={t.id}>
												<span className="mr-2 font-mono text-xs">{t.id}</span>
												{t.title}
											</li>
										))}
								</ul>
							</div>
						))}
					</div>
				</section>
			)}

			<section className={cn('rule-t', tasks.length > 0 && 'mt-16')}>
				<div className="wrap flex flex-wrap gap-x-8 gap-y-3 pt-8">
					<a href={`${SITE.blob}docs/PLAN.md`} className="link">
						The whole plan
					</a>
					<a href={`${SITE.blob}docs/decisions.md`} className="link">
						The decision log
					</a>
					<a href={SITE.acta} className="link">
						The board, on Acta
					</a>
				</div>
			</section>
		</>
	);
}
