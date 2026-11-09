import type { MetadataRoute } from 'next';
import { changed, docs, GUIDE } from '@/lib/repo';
import { SITE } from '@/lib/site';

// Every public page. The docs say when they last changed, from git, as each is one file; the other
// pages are drawn from many, so they don't.
export default function sitemap(): MetadataRoute.Sitemap {
	const pages: [string, string?][] = [['/'], ['/docs', GUIDE], ['/benchmarks'], ['/plugins'], ['/roadmap'], ['/download'], ...docs().map((d): [string, string] => [`/docs/${d.slug}`, d.path])];
	return pages.map(([p, file]) => {
		const at = file ? changed(file) : undefined;
		return { url: SITE.url + (p === '/' ? '' : p), ...(at ? { lastModified: at } : {}), changeFrequency: 'weekly', priority: p === '/' ? 1 : p.startsWith('/docs/') ? 0.6 : 0.8 };
	});
}
