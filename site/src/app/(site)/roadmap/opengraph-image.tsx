import { card, CARD } from '@/lib/og-card';
import { PAGES } from '@/lib/pages';

export const alt = `${PAGES.roadmap.title}: ${PAGES.roadmap.description}`;
export const size = CARD;
export const contentType = 'image/png';

export default function Image() {
	return card({ kicker: 'Roadmap', title: PAGES.roadmap.title, line: PAGES.roadmap.description, cam: 'readme' });
}
