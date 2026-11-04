import { card, CARD } from '@/lib/og-card';
import { guideIndex } from '@/lib/repo';

export const alt = "Calcite's docs: running a Calcite server";
export const size = CARD;
export const contentType = 'image/png';

export default function Image() {
	const d = guideIndex();
	return card({ kicker: 'Docs', title: d.title, line: d.description, cam: 'site' });
}
