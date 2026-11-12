import { card, CARD } from '@/lib/og-card';
import { docs } from '@/lib/repo';

// Each page of the docs has its card, its title over the world. The cards are made as the site
// builds, one for each page generateStaticParams names, and no other slug is served: the docs are
// read from the repo outside site/, which a host may have as it builds but not as it serves. So the alt
// text is the same for every page. generateImageMetadata would give each its own, but with it Next
// leaves the slug to request time, where the card can't read its page and answers 500 (CAL-171).

export const alt = "A page of Calcite's docs, its title over the world";
export const size = CARD;
export const contentType = 'image/png';
export const dynamicParams = false;

export function generateStaticParams() {
	return docs().map((d) => ({ slug: d.slug }));
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
	const { slug } = await params, d = docs().find((x) => x.slug === slug);
	return card({ kicker: d?.group ?? 'Docs', title: d?.title ?? 'Docs', line: d?.description ?? '', cam: 'site' });
}
