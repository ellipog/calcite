import type { Metadata } from 'next';
import { SITE } from '@/lib/site';

/** A public page's metadata: its title and description, its one address, and the same for link
 *  previews, which don't take them from the page on their own. The picture is the site's card. */
export function meta({ title, description, path }: { title?: string; description: string; path: string }): Metadata {
	const full = title ? `${title} · calcite` : SITE.title;
	return {
		title: title ?? { absolute: SITE.title },
		description,
		alternates: { canonical: path },
		openGraph: { type: 'website', siteName: 'calcite', title: full, description, url: path, locale: 'en' },
		twitter: { card: 'summary_large_image', title: full, description },
	};
}
