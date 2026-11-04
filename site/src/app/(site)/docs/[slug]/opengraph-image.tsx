import { card, CARD } from '@/lib/og-card';
import { docs } from '@/lib/repo';

// Each page of the docs has its card, its title over the world, and alt text naming the page.

export function generateStaticParams() {
	return docs().map((d) => ({ slug: d.slug }));
}

export function generateImageMetadata({ params }: { params: { slug: string } }) {
	const d = docs().find((x) => x.slug === params.slug);
	return [{ id: 'card', alt: `${d?.title ?? 'A page'}, from Calcite's docs`, size: CARD, contentType: 'image/png' }];
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
	const { slug } = await params, d = docs().find((x) => x.slug === slug);
	return card({ kicker: d?.group ?? 'Docs', title: d?.title ?? 'Docs', line: d?.description ?? '', cam: 'site' });
}
