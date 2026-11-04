'use client';

// The docs' list of pages: a sticky column beside the page on a wide screen, and a menu above it on
// a narrow one. The page you're on is marked solid.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';

export interface NavGroup {
	name: string;
	pages: { href: string; title: string }[];
}

function List({ groups, path }: { groups: NavGroup[]; path: string }) {
	return (
		<div className="grid gap-7">
			<Link href="/docs" aria-current={path === '/docs' ? 'page' : undefined} className={cn('text-[15px]', path === '/docs' ? 'font-semibold' : 'hover:underline hover:decoration-2 hover:underline-offset-4')}>
				Overview
			</Link>
			{groups.map((g) => (
				<div key={g.name}>
					<p className="label mb-3">{g.name}</p>
					<ul className="grid gap-0.5">
						{g.pages.map((p) => {
							const here = path === p.href;
							return (
								<li key={p.href}>
									<Link href={p.href} aria-current={here ? 'page' : undefined} className={cn('relative block py-1.5 pl-4 text-[15px] leading-snug', here ? 'font-semibold' : 'hover:underline hover:decoration-2 hover:underline-offset-4')}>
										<span aria-hidden className={cn('absolute top-[0.9em] left-0 size-[6px]', here ? 'bg-ink' : 'border border-dotted border-ink')} />
										{p.title}
									</Link>
								</li>
							);
						})}
					</ul>
				</div>
			))}
		</div>
	);
}

export function DocsNav({ groups }: { groups: NavGroup[] }) {
	const path = usePathname();
	const here = groups.flatMap((g) => g.pages).find((p) => p.href === path)?.title ?? 'Overview';
	return (
		<>
			<nav aria-label="Docs" className="sticky top-24 max-h-[calc(100svh-7rem)] overflow-y-auto pb-10 max-lg:hidden">
				<List groups={groups} path={path} />
			</nav>
			<details key={path} className="d-details rule-b lg:hidden">
				<summary className="py-3.5 font-mono text-[13px] leading-none">
					Docs · <span className="font-medium">{here}</span>
				</summary>
				<div className="pt-2 pb-6 pl-5">
					<List groups={groups} path={path} />
				</div>
			</details>
		</>
	);
}
