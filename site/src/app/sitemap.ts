import type { MetadataRoute } from 'next';
import { docs } from '@/lib/repo';
import { SITE } from '@/lib/site';

export default function sitemap(): MetadataRoute.Sitemap {
	const pages = ['/', '/docs', '/benchmarks', '/plugins', '/roadmap', ...docs().map((d) => `/docs/${d.slug}`)];
	return pages.map((p) => ({ url: SITE.url + (p === '/' ? '' : p), changeFrequency: 'weekly', priority: p === '/' ? 1 : p.startsWith('/docs/') ? 0.6 : 0.8 }));
}
