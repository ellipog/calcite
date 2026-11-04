import type { SVGProps } from 'react';
import { bitsPath, cellsFor, markBits, type MarkOptions } from '@/lib/dither/mark';
import type { Bits } from '@/lib/dither/bayer';

// The mark as inline SVG, in currentColor: worked out on the server at its size's own grid (2 px
// a cell, 1 px under 32, the 64-cell master above 128), one path of square runs, crispEdges.
export function Mark({ size = 128, cells, className, title, ...o }: { size?: number; cells?: number; className?: string; title?: string } & MarkOptions) {
	const n = cells ?? cellsFor(size);
	return <Bitmap bits={markBits(n, o)} n={n} size={size} className={className} title={title} />;
}

// Any n×n bits as SVG.
export function Bitmap({ bits, n, size, title, ...rest }: { bits: Bits; n: number; size: number; title?: string } & Omit<SVGProps<SVGSVGElement>, 'children'>) {
	return (
		<svg width={size} height={size} viewBox={`0 0 ${n} ${n}`} shapeRendering="crispEdges" role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true} {...rest} style={{ flex: 'none', ...rest.style }}>
			<path fill="currentColor" d={bitsPath(bits, n)} />
		</svg>
	);
}
