import type { Metadata } from 'next';
import { meta } from '@/lib/meta';
import { DocPage } from '@/components/site/doc-page';
import { guideIndex } from '@/lib/repo';

export function generateMetadata(): Metadata {
	const d = guideIndex();
	return meta({ title: 'Docs', description: d.description, path: '/docs' });
}

export default function Docs() {
	return <DocPage doc={guideIndex()} kicker="Docs" />;
}
