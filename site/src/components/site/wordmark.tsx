// The name across the whole frame, at the foot of every page: as large as fits, set in the display
// face with the hero's tracking, and shaded in bands of the 8×8 matrix from solid at the top of the
// letters to a quarter at their foot. It's type, not a picture, so it's sharp at any size and
// needs no script; it's the name again, so it's hidden from screen readers.

import type { CSSProperties } from 'react';
import { cn } from '@/lib/cn';

// The ink of "calcite" at the display tracking, in ems, at sizes from the face's largest optical
// size up, measured in the browser: from the c's left edge to the e's right, and the c's side
// bearing before it. The size is the frame's width over the ink's, so the letters touch both sides.
const INK = 2.6391, BEARING = 0.0231;
const BANDS = ['--solid', '--t88', '--t75', '--t62', '--t50', '--t38', '--t25'];

export function Wordmark({ text = 'calcite', className }: { text?: string; className?: string }) {
	const n = BANDS.length;
	// each band is the word again, clipped to its slice of the letters' height
	const at = (i: number) => (i === 0 ? '0' : `${((i / n) * 100).toFixed(3)}%`);
	const to = (i: number) => (i === n - 1 ? '0' : `${((1 - (i + 1) / n) * 100).toFixed(3)}%`);
	return (
		// clipped, since the face's descent hangs below the baseline and would lengthen the page
		<div aria-hidden className={cn('@container overflow-clip select-none', className)}>
			<div className="relative font-display leading-none font-extrabold tracking-display whitespace-nowrap" style={{ fontSize: `calc(100cqw / ${INK})`, marginLeft: `-${BEARING}em` }}>
				{BANDS.map((b, i) => {
					const style: CSSProperties = { backgroundImage: `var(${b})`, clipPath: `inset(${at(i)} 0 ${to(i)} 0)` };
					// the box is trimmed to the cap height and the baseline, so the letters stand on the
					// rule under them; the padding over it is where the l, the t and the i's dot rise
					// past the caps, since a text's background is painted only inside its box
					return (
						<span key={b} className={cn('block bg-size-[16px_16px] bg-clip-text pt-[0.12em] text-transparent [text-box:trim-both_cap_alphabetic]', i > 0 && 'absolute inset-0')} style={style}>
							{text}
						</span>
					);
				})}
			</div>
		</div>
	);
}
