// A docs page: its title and description, the Markdown, what's on the page beside it on a wide
// screen, the pages before and after it, and where its source is.

import Link from 'next/link';
import { Markdown } from '@/components/markdown';
import { Accordion, Table } from '@/components/ui/feedback';
import { Kicker } from '@/components/site/parts';
import { docHref, routes } from '@/lib/docs';
import { headings, parse, plain } from '@/lib/markdown';
import { calciteSettings, differences, docs, type Doc } from '@/lib/repo';
import { SITE } from '@/lib/site';

const KIND: Record<string, string> = { bug: 'a vanilla bug, fixed', exploit: 'an exploit, closed', identity: 'Calcite says what it is', performance: 'a shortcut nothing can see', platform: 'where vanilla depends on its system' };

function Settings() {
	return (
		<div className="mb-6 overflow-x-auto">
			<Table
				stack
				className="text-[15px] leading-[1.45] sm:min-w-[560px] [&_tbody>tr>*]:align-top"
				columns={[{ label: 'Setting' }, { label: 'Default' }, { label: 'What it does' }]}
				rows={calciteSettings().map((s) => [
					<code key="n" className="font-mono text-[0.9em] font-medium whitespace-nowrap">
						{s.name}
					</code>,
					<code key="v" className="font-mono text-[0.9em] whitespace-nowrap">
						{s.value === '' ? 'empty' : s.value}
					</code>,
					s.about,
				])}
			/>
		</div>
	);
}

function Differences() {
	const r = routes();
	return (
		<div className="mb-6 max-w-[76ch]">
			<Accordion
				items={differences().map((d) => ({
					q: (
						<span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
							{d.title}
							<span className="font-mono text-xs font-normal">{KIND[d.kind] ?? d.kind}</span>
						</span>
					),
					a: <Markdown source={d.body} path={`rig/differences/${d.slug}.md`} routes={r} className="pt-1 [&_p]:text-base" />,
				}))}
			/>
		</div>
	);
}

export function DocPage({ doc, kicker }: { doc: Doc; kicker?: string }) {
	const all = docs(), i = all.findIndex((d) => d.slug === doc.slug);
	const prev = doc.slug ? (i > 0 ? all[i - 1] : null) : null, next = doc.slug ? all[i + 1] : all[0];
	const toc = headings(parse(doc.body)).filter((h) => h.level === 2);
	return (
		<div className="grid grid-cols-1 gap-x-14 xl:grid-cols-[minmax(0,1fr)_200px]">
			<article className="min-w-0 pt-8 lg:pt-0">
				<Kicker>{kicker ?? doc.group}</Kicker>
				<h1 className="font-display text-[clamp(40px,6vw,68px)] leading-[0.92] font-extrabold tracking-title text-balance">{doc.title}</h1>
				<p className="mt-5 mb-12 max-w-[60ch] text-lg leading-normal md:text-xl">{doc.description}</p>
				<Markdown source={doc.body} path={doc.path} routes={routes()} skipTitle directives={{ 'calcite.properties': <Settings />, differences: <Differences /> }} />
				<nav aria-label="More pages" className="mt-16 grid grid-cols-1 gap-4 rule-t pt-6 sm:grid-cols-2">
					{prev ? (
						<Link href={docHref(prev)} className="group grid gap-1.5 rule p-4">
							<span className="font-mono text-xs">← before</span>
							<span className="font-display text-lg font-bold group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">{prev.title}</span>
						</Link>
					) : (
						<span />
					)}
					{next && (
						<Link href={docHref(next)} className="group grid gap-1.5 rule p-4 text-right">
							<span className="font-mono text-xs">after →</span>
							<span className="font-display text-lg font-bold group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">{next.title}</span>
						</Link>
					)}
				</nav>
				<p className="mt-6 font-mono text-xs leading-normal">
					This page is{' '}
					<a href={SITE.blob + doc.path} className="link">
						{doc.path}
					</a>{' '}
					in the repo. Change it there, and the site follows.
				</p>
			</article>
			{toc.length > 2 && (
				<aside className="max-xl:hidden">
					<nav aria-label="On this page" className="sticky top-24">
						<p className="label mb-3">On this page</p>
						<ul className="grid gap-2 text-sm leading-snug">
							{toc.map((h) => (
								<li key={h.id}>
									<a href={`#${h.id}`} className="hover:underline hover:decoration-2 hover:underline-offset-4">
										{plain(h.c)}
									</a>
								</li>
							))}
						</ul>
					</nav>
				</aside>
			)}
		</div>
	);
}
