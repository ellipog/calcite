import type { Metadata } from 'next';
import { meta } from '@/lib/meta';
import { notFound } from 'next/navigation';
import { DocPage } from '@/components/site/doc-page';
import { docs } from '@/lib/repo';

export const dynamicParams = false;

export function generateStaticParams() {
	return docs().map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
	const { slug } = await params;
	const d = docs().find((x) => x.slug === slug);
	if (!d) return {};
	return meta({ title: d.title, description: d.description, path: `/docs/${slug}` });
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
	const { slug } = await params;
	const d = docs().find((x) => x.slug === slug);
	if (!d) notFound();
	return <DocPage doc={d} />;
}
