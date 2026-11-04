import { card, CARD } from '@/lib/og-card';
import { docs } from '@/lib/repo';

// Each page of the docs has its card, its title over the world.

export const alt = "A page of Calcite's docs, its title over a strip of a world";
export const size = CARD;
export const contentType = 'image/png';

export function generateStaticParams() {
	return docs().map((d) => ({ slug: d.slug }));
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
	const { slug } = await params, d = docs().find((x) => x.slug === slug);
	return card({ kicker: d?.group ?? 'Docs', title: d?.title ?? 'Docs', line: d?.description ?? '', cam: 'site' });
}
