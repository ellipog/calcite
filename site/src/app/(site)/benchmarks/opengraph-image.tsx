import { card, CARD } from '@/lib/og-card';
import { PAGES } from '@/lib/pages';

export const alt = `${PAGES.benchmarks.title}: ${PAGES.benchmarks.description}`;
export const size = CARD;
export const contentType = 'image/png';

export default function Image() {
	return card({ kicker: 'Benchmarks', title: PAGES.benchmarks.title, line: PAGES.benchmarks.description, cam: 'cmp' });
}
