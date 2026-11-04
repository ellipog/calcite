import type { Metadata } from 'next';
import { meta } from '@/lib/meta';
import { DocPage } from '@/components/site/doc-page';
import { article, JsonLd, STUDIO, trail, WEBSITE } from '@/lib/ld';
import { changed, GUIDE, guideIndex } from '@/lib/repo';

export function generateMetadata(): Metadata {
	const d = guideIndex();
	return meta({ title: 'Docs: running a server', description: d.description, path: '/docs', modified: changed(GUIDE) });
}

export default function Docs() {
	const d = guideIndex();
	return (
		<>
			<JsonLd things={[trail([['Docs', '/docs']]), article({ title: d.title, description: d.description, path: '/docs', modified: changed(GUIDE) }), WEBSITE, STUDIO]} />
			<DocPage doc={d} kicker="Docs" />
		</>
	);
}
