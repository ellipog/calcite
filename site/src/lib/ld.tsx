import { SITE } from '@/lib/site';

// Structured data, for search engines: what the site is and who makes it, what Calcite is, where
// each page sits under the home page, and the docs as articles. Each thing has an @id, so a page
// can point at the site or the software without saying it all again; a page that points at one
// it doesn't also hold says it again, as search engines read each page alone, except the software,
// which only the home page describes.

type Thing = Record<string, unknown>;

const id = (name: string) => `${SITE.url}/#${name}`;
const abs = (path: string) => SITE.url + (path === '/' ? '' : path);

export const STUDIO: Thing = { '@type': 'Organization', '@id': id('studio'), name: 'Aaen Studios', url: SITE.studio };

export const WEBSITE: Thing = { '@type': 'WebSite', '@id': id('site'), name: 'calcite', url: SITE.url, description: SITE.description, inLanguage: 'en', publisher: { '@id': id('studio') } };

export const SOFTWARE: Thing = {
	'@type': 'SoftwareApplication',
	'@id': id('software'),
	name: 'Calcite',
	description: SITE.description,
	url: SITE.url,
	applicationCategory: 'GameApplication',
	applicationSubCategory: 'Minecraft: Java Edition server',
	softwareRequirements: `Minecraft: Java Edition ${SITE.minecraft} to join`,
	isAccessibleForFree: true,
	license: 'https://opensource.org/licenses/MIT',
	author: { '@id': id('studio') },
	sameAs: [SITE.github],
};

/** The trail from the home page to a page: each step's name and address. */
export function trail(steps: [name: string, path: string][]): Thing {
	return {
		'@type': 'BreadcrumbList',
		itemListElement: [['calcite', '/'] as const, ...steps].map(([name, path], i) => ({ '@type': 'ListItem', position: i + 1, name, item: abs(path) })),
	};
}

/** A page of the docs, as an article about Calcite. */
export function article({ title, description, path, modified }: { title: string; description: string; path: string; modified?: string }): Thing {
	return {
		'@type': 'TechArticle',
		headline: title,
		description,
		url: abs(path),
		inLanguage: 'en',
		...(modified ? { dateModified: modified } : {}),
		isPartOf: { '@id': id('site') },
		about: { '@id': id('software') },
		publisher: { '@id': id('studio') },
	};
}

/** Things as one JSON-LD script; '<' is escaped, so no string in them can close the tag. */
export function JsonLd({ things }: { things: Thing[] }) {
	const data = { '@context': 'https://schema.org', '@graph': things };
	return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }} />;
}
