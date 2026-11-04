import Link from 'next/link';
import { AaenMark } from '@/components/aaen-mark';
import { Mark } from '@/components/mark';
import { Wordmark } from '@/components/site/wordmark';
import { NAV, NOT_MOJANG, SITE } from '@/lib/site';

const OUT = [
	{ href: SITE.github, label: 'GitHub' },
	{ href: SITE.acta, label: 'The board, on Acta' },
	{ href: SITE.calx, label: 'Calx, the language' },
];

// The links, split as the pages' heads are, then the name set across the whole frame, sitting on
// the bottom bar.
export function SiteFooter() {
	return (
		<footer className="mt-24 rule-t md:mt-32">
			<div className="wrap grid grid-cols-1 gap-10 py-14 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-x-10">
				<div className="flex items-start gap-5">
					<Link href="/" aria-label="calcite, home" className="shrink-0">
						<Mark size={40} />
					</Link>
					<p className="max-w-[34ch] text-[15px] leading-normal">A Minecraft: Java Edition server written from scratch in Calx.</p>
				</div>
				<div className="grid grid-cols-2 gap-10">
					<nav aria-label="The site">
						<p className="label mb-3">The site</p>
						<ul className="grid gap-2 text-[15px]">
							{NAV.map((n) => (
								<li key={n.href}>
									<Link href={n.href} className="link">
										{n.label}
									</Link>
								</li>
							))}
						</ul>
					</nav>
					<nav aria-label="Elsewhere">
						<p className="label mb-3">Elsewhere</p>
						<ul className="grid gap-2 text-[15px]">
							{OUT.map((n) => (
								<li key={n.href}>
									<a href={n.href} className="link">
										{n.label}
									</a>
								</li>
							))}
						</ul>
					</nav>
				</div>
			</div>
			<div className="wrap">
				<Wordmark />
			</div>
			<div className="rule-t">
				<div className="wrap flex flex-wrap items-center justify-between gap-x-8 gap-y-2 py-6 font-mono text-xs leading-[1.6]">
					<a href={SITE.studio} className="inline-flex items-center gap-2">
						<AaenMark size={16} />
						<span className="link">An Aaen Studios project</span>
					</a>
					<p>MIT licensed. Calcite contains no Mojang code or assets.</p>
					<p>{NOT_MOJANG}</p>
				</div>
			</div>
		</footer>
	);
}
