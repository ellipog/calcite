import { card, CARD } from '@/lib/og-card';
import { PAGES } from '@/lib/pages';

export const alt = `${PAGES.download.title}: ${PAGES.download.description}`;
export const size = CARD;
export const contentType = 'image/png';

export default function Image() {
	return card({ kicker: 'Download', title: PAGES.download.title, line: PAGES.download.description, cam: 'readme' });
}
