import type { Metadata } from 'next';
import { SITE } from '@/lib/site';

/** Cut text to at most n characters, at the end of a sentence if one ends late enough, else a word. */
export function snippet(text: string, n = 160) {
	const t = text.replace(/\s+/g, ' ').trim();
	if (t.length <= n) return t;
	const cut = t.slice(0, n), stop = cut.lastIndexOf('. ');
	if (stop > n * 0.5) return cut.slice(0, stop + 1);
	return `${cut.slice(0, cut.lastIndexOf(' ')).replace(/[,;:]$/, '')}…`;
}

/** What follows each page's title: the name, and what it is, which is what people search for. */
export const SUFFIX = ' · calcite Minecraft server';

/** A public page's metadata: its title and description, cut to what a search result shows, its one
 *  address, and the same for link previews, which don't take them from the page on their own. The
 *  picture is the page's card, from the opengraph-image.tsx beside it. */
export function meta({ title, description, path }: { title?: string; description: string; path: string }): Metadata {
	const full = title ? title + SUFFIX : SITE.title, about = snippet(description);
	return {
		title: title ?? { absolute: SITE.title },
		description: about,
		alternates: { canonical: path },
		openGraph: { type: 'website', siteName: 'calcite', title: full, description: about, url: path, locale: 'en_US' },
		twitter: { card: 'summary_large_image', title: full, description: about },
	};
}
