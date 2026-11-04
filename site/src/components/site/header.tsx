'use client';

// The public site's bar: the live mark and the name, the sections, and GitHub. On a phone the
// sections fold into a menu that dissolves in under the bar.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { LiveMark } from '@/components/live-mark';
import { cn } from '@/lib/cn';
import { NAV, SITE } from '@/lib/site';

const on = (path: string, href: string) => path === href || path.startsWith(href + '/');

export function SiteHeader() {
	const path = usePathname();
	const [open, setOpen] = useState(false);
	const [at, setAt] = useState(path);
	// a new page closes the menu, as it's rendered rather than in an effect
	if (at !== path) {
		setAt(path);
		setOpen(false);
	}
	useEffect(() => {
		if (!open) return;
		const key = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
		addEventListener('keydown', key);
		return () => removeEventListener('keydown', key);
	}, [open]);
	return (
		<header className="sticky top-0 z-40 rule-b bg-paper">
			<div className="wrap flex h-16 items-center gap-6">
				<Link href="/" className="mr-auto flex items-center gap-2.5 font-display text-[24px] leading-none font-extrabold tracking-display" aria-label="calcite, home">
					<LiveMark cells={24} size={24} />
					calcite
				</Link>
				<nav aria-label="Site" className="flex items-center gap-1 max-md:hidden">
					{NAV.map((n) => (
						<Link key={n.href} href={n.href} aria-current={on(path, n.href) ? 'page' : undefined} className="group px-2.5 py-2 text-[15px] leading-none">
							<span className={cn('bg-size-[100%_2px] bg-bottom bg-no-repeat pb-1', on(path, n.href) ? 'bg-(image:--solid) font-semibold' : 'group-hover:bg-(image:--solid)')}>{n.label}</span>
						</Link>
					))}
					<a href={SITE.github} className="group ml-2 flex items-center gap-1.5 rule px-3 py-2 font-mono text-[13px] leading-none hover:bg-ink hover:text-paper hover:[border-style:solid]">
						GitHub <span aria-hidden>↗</span>
					</a>
				</nav>
				<button
					type="button"
					className="rule px-3.5 py-2.5 font-mono text-[13px] leading-none md:hidden"
					aria-expanded={open}
					aria-controls="site-menu"
					onClick={() => setOpen((o) => !o)}
				>
					{open ? 'close' : 'menu'}
				</button>
			</div>
			{open && (
				<nav id="site-menu" aria-label="Site" className="absolute inset-x-0 top-full animate-dis-in rule-b bg-paper md:hidden">
					<div className="wrap grid py-2">
						{NAV.map((n) => (
							<Link key={n.href} href={n.href} aria-current={on(path, n.href) ? 'page' : undefined} className="flex items-center justify-between rule-b py-4 font-display text-[28px] leading-none font-bold tracking-tight">
								{n.label}
								{on(path, n.href) && <i className="size-2.5 bg-ink" aria-hidden />}
							</Link>
						))}
						<a href={SITE.github} className="flex items-center justify-between py-4 font-display text-[28px] leading-none font-bold tracking-tight">
							GitHub <span className="font-mono text-base font-normal">↗</span>
						</a>
					</div>
				</nav>
			)}
		</header>
	);
}
