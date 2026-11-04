import type { MetadataRoute } from 'next';
import { PAPER } from '@/lib/dither/math';
import { SITE } from '@/lib/site';

// What a browser or a phone's home screen takes the site to be: its name, its icons and its paper.
export default function manifest(): MetadataRoute.Manifest {
	return {
		name: SITE.title,
		short_name: 'calcite',
		description: SITE.description,
		start_url: '/',
		display: 'browser',
		background_color: PAPER,
		theme_color: PAPER,
		icons: [
			{ src: '/icon.svg', type: 'image/svg+xml', sizes: 'any' },
			{ src: '/apple-icon.png', type: 'image/png', sizes: '180x180' },
		],
	};
}
