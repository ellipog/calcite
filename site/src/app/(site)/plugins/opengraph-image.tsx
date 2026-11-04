import { card, CARD } from '@/lib/og-card';
import { PAGES } from '@/lib/pages';

export const alt = `${PAGES.plugins.title}: ${PAGES.plugins.description}`;
export const size = CARD;
export const contentType = 'image/png';

export default function Image() {
	return card({ kicker: 'Plugins', title: PAGES.plugins.title, line: PAGES.plugins.description, cam: 'poster' });
}
