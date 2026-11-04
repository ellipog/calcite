// The docs pages, their addresses, and where links between the repo's files go on the site.

import { docs, GUIDE, type Doc } from '@/lib/repo';

export const docHref = (d: Doc) => (d.slug ? `/docs/${d.slug}` : '/docs');

/** Repo files that are pages here; a link to any other file goes to it on GitHub. */
export function routes(): Record<string, string> {
	const r: Record<string, string> = { [GUIDE.replace(/\/README\.md$/, '')]: '/docs', [GUIDE]: '/docs', 'docs/PLAN.md': '/roadmap', 'plugins/samples/README.md': '/plugins' };
	for (const d of docs()) r[d.path] = docHref(d);
	return r;
}

/** The pages in groups, in order, for the sidebar. */
export function groups(): { name: string; pages: Doc[] }[] {
	const out: { name: string; pages: Doc[] }[] = [];
	for (const d of docs()) {
		const g = out.find((x) => x.name === d.group);
		if (g) g.pages.push(d);
		else out.push({ name: d.group, pages: [d] });
	}
	return out;
}
