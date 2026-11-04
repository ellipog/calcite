// Draws the repo's Markdown with the site's components: fenced code as code blocks with a copy
// button, tables as dotted tables, and each link sent where it belongs on the site, or to the file
// on GitHub. Directives, HTML comments on lines of their own, are filled in by the page.

import type { ReactNode } from 'react';
import Link from 'next/link';
import { posix } from 'node:path';
import { CodeBlock } from '@/components/ui/overlay';
import { Table } from '@/components/ui/feedback';
import { cn } from '@/lib/cn';
import { inline, parse, plain, type Block, type Inline } from '@/lib/markdown';
import { decisions } from '@/lib/repo';
import { SITE } from '@/lib/site';

export interface MarkdownProps {
	source: string;
	/** The file's path in the repo, which relative links start from. */
	path: string;
	/** Repo paths that are pages on the site, and their addresses. */
	routes?: Record<string, string>;
	directives?: Record<string, ReactNode>;
	/** Leaves out the first heading, which the page shows as its title. */
	skipTitle?: boolean;
	className?: string;
}

/** Where a link in the file at `from` goes: a page of the site, or the file on GitHub. */
export function resolve(href: string, from: string, routes: Record<string, string> = {}) {
	if (/^[a-z]+:/i.test(href) || href.startsWith('#') || href.startsWith('/')) return href;
	const [p, hash] = href.split('#');
	const target = posix.normalize(posix.join(posix.dirname(from), p)).replace(/\/$/, '');
	const site = routes[target];
	if (site !== undefined) return site + (hash ? `#${hash}` : '');
	const dir = !posix.extname(target);
	return (dir ? SITE.tree : SITE.blob) + target + (hash ? `#${hash}` : '');
}

// A decision's id, such as D16, links to the decision log, and says the decision when pointed at.
function Text({ v, ctx }: { v: string; ctx: Ctx }): ReactNode {
	if (ctx.inLink || !/\bD\d/.test(v)) return v;
	const log = decisions();
	return v.split(/\b(D\d{1,3})\b/).map((part, j) => {
		const said = j % 2 === 1 ? log.get(part) : undefined;
		return said ? (
			<a key={j} href={`${SITE.blob}docs/decisions.md`} title={said} className="link">
				{part}
			</a>
		) : (
			part
		);
	});
}

function Runs({ c, ctx }: { c: Inline[]; ctx: Ctx }): ReactNode {
	return c.map((i, k) => {
		switch (i.t) {
			case 'text':
				return <Text key={k} v={i.v} ctx={ctx} />;
			case 'code':
				// short code stays on one line; a long path or command may break anywhere
				return (
					<code key={k} className={cn('font-mono text-[0.9em] font-medium', i.v.length > 28 ? '[overflow-wrap:anywhere]' : 'whitespace-nowrap')}>
						{i.v}
					</code>
				);
			case 'strong':
				return (
					<strong key={k} className="font-semibold">
						<Runs c={i.c} ctx={ctx} />
					</strong>
				);
			case 'em':
				return (
					<em key={k}>
						<Runs c={i.c} ctx={ctx} />
					</em>
				);
			case 'link': {
				const href = resolve(i.href, ctx.path, ctx.routes);
				const inner = <Runs c={i.c} ctx={{ ...ctx, inLink: true }} />;
				return href.startsWith('/') || href.startsWith('#') ? (
					<Link key={k} href={href} className="link">
						{inner}
					</Link>
				) : (
					<a key={k} href={href} className="link">
						{inner}
					</a>
				);
			}
		}
	});
}

interface Ctx {
	path: string;
	routes: Record<string, string>;
	directives: Record<string, ReactNode>;
	/** Inside a link, where another link can't go. */
	inLink?: boolean;
}

const COMMENT: Record<string, string> = { sh: '#', bash: '#', powershell: '#', properties: '#', toml: '#', calx: '//' };

function Blocks({ blocks, ctx, tight }: { blocks: Block[]; ctx: Ctx; tight?: boolean }): ReactNode {
	return blocks.map((b, k) => {
		switch (b.t) {
			case 'h': {
				const Tag = (b.level <= 2 ? 'h2' : b.level === 3 ? 'h3' : 'h4') as 'h2' | 'h3' | 'h4';
				return (
					<Tag
						key={k}
						id={b.id}
						className={cn(
							'group scroll-mt-24 font-display text-ink',
							b.level <= 2 && 'mt-14 mb-4 text-[28px] leading-[1.1] font-bold tracking-tight first:mt-0',
							b.level === 3 && 'mt-10 mb-3 text-[21px] leading-tight font-semibold tracking-tight',
							b.level >= 4 && 'mt-8 mb-2 text-[17px] font-semibold',
						)}
					>
						<Runs c={b.c} ctx={ctx} />
						<a href={`#${b.id}`} aria-label="Link to this section" className="ml-2 font-mono text-[0.7em] font-normal opacity-0 group-hover:opacity-100 focus-visible:opacity-100">
							#
						</a>
					</Tag>
				);
			}
			case 'p':
				return (
					<p key={k} className={cn('max-w-[68ch] text-[17px] leading-[1.65]', tight ? 'mb-2 last:mb-0' : 'mb-5')}>
						<Runs c={b.c} ctx={ctx} />
					</p>
				);
			case 'list': {
				const L = b.ordered ? 'ol' : 'ul';
				return (
					<L key={k} className={cn('mb-5 grid max-w-[68ch] grid-cols-[minmax(0,1fr)] gap-2 text-[17px] leading-[1.6]', tight && 'mt-2')}>
						{b.items.map((it, j) => (
							<li key={j} className="relative min-w-0 pl-7">
								<span aria-hidden className={cn('absolute left-0', b.ordered ? 'top-[0.2em] font-mono text-[13px] font-medium' : 'top-[0.62em] size-[6px] bg-ink')}>
									{b.ordered ? String(j + 1).padStart(2, '0') : null}
								</span>
								<Blocks blocks={it} ctx={ctx} tight />
							</li>
						))}
					</L>
				);
			}
			case 'table':
				return (
					<div key={k} className="mb-6 overflow-x-auto">
						<Table
							stack
								className="text-[15px] leading-[1.45] sm:min-w-[520px] [&_td]:align-top"
							columns={b.head.map((h, j) => ({ label: plain(h), num: b.align[j] === 'r' }))}
							rows={b.rows.map((r) => r.map((c, j) => <Runs key={j} c={c} ctx={ctx} />))}
						/>
					</div>
				);
			case 'code':
				return <CodeBlock key={k} code={b.v} lang={b.lang} comment={COMMENT[b.lang] ?? null} copy={b.lang !== 'text' && b.lang !== 'json' && b.lang !== 'calx'} className="mb-6" />;
			case 'quote':
				return (
					<blockquote key={k} className="mb-6 max-w-[68ch] border-l-2 border-ink pl-5">
						<Blocks blocks={b.c} ctx={ctx} tight />
					</blockquote>
				);
			case 'directive':
				return <div key={k}>{ctx.directives[b.name] ?? null}</div>;
		}
	});
}

/** One line of Markdown, such as a task in the plan, drawn inline. */
export function MarkdownLine({ text, path, routes = {} }: { text: string; path: string; routes?: Record<string, string> }) {
	return <Runs c={inline(text)} ctx={{ path, routes, directives: {} }} />;
}

export function Markdown({ source, path, routes = {}, directives = {}, skipTitle, className }: MarkdownProps) {
	let blocks = parse(source);
	if (skipTitle) {
		const i = blocks.findIndex((b) => b.t === 'h' && b.level === 1);
		if (i >= 0) blocks = blocks.filter((_, j) => j !== i);
	}
	return (
		<div className={className}>
			<Blocks blocks={blocks} ctx={{ path, routes, directives }} />
		</div>
	);
}

export { parse };
