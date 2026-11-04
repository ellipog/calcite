import type { Metadata } from 'next';
import { meta } from '@/lib/meta';
import { notFound } from 'next/navigation';
import { DocPage } from '@/components/site/doc-page';
import { article, JsonLd, STUDIO, trail, WEBSITE } from '@/lib/ld';
import { changed, docs } from '@/lib/repo';

export const dynamicParams = false;

export function generateStaticParams() {
	return docs().map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
	const { slug } = await params;
	const d = docs().find((x) => x.slug === slug);
	if (!d) return {};
	return meta({ title: d.title, description: d.description, path: `/docs/${slug}`, modified: changed(d.path) });
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
	const { slug } = await params;
	const d = docs().find((x) => x.slug === slug);
	if (!d) notFound();
	const path = `/docs/${slug}`;
	return (
		<>
			<JsonLd things={[trail([['Docs', '/docs'], [d.title, path]]), article({ title: d.title, description: d.description, path, modified: changed(d.path) }), WEBSITE, STUDIO]} />
			<DocPage doc={d} />
		</>
	);
}
