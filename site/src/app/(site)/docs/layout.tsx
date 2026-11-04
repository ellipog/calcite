import { DocsNav } from '@/components/site/docs-nav';
import { docHref, groups } from '@/lib/docs';

export default function DocsLayout({ children }: { children: React.ReactNode }) {
	const nav = groups().map((g) => ({ name: g.name, pages: g.pages.map((p) => ({ href: docHref(p), title: p.title })) }));
	return (
		<div className="wrap grid grid-cols-1 gap-x-14 pt-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:pt-14">
			<aside>
				<DocsNav groups={nav} />
			</aside>
			<div className="min-w-0">{children}</div>
		</div>
	);
}
