import type { MetadataRoute } from 'next';
import { SITE } from '@/lib/site';

// Every public page may be crawled. The brand guide and the component sheet aren't in a
// production build at all, and say noindex where they are.
export default function robots(): MetadataRoute.Robots {
	return { rules: { userAgent: '*', allow: '/' }, sitemap: `${SITE.url}/sitemap.xml`, host: SITE.url };
}
