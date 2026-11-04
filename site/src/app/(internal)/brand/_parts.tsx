import type { ReactNode } from 'react';
import { Mark } from '@/components/mark';
import { cn } from '@/lib/cn';

// The guide's section frame: a number with a small mark whose player has walked a little further
// at each section, a heading, and the section's body.
export const SECTIONS: [string, string][] = [
	['idea', 'idea'],
	['logo', 'logo'],
	['colour', 'colour'],
	['type', 'type'],
	['dither', 'dither'],
	['imagery', 'imagery'],
	['icons', 'icons'],
	['ui', 'ui'],
	['charts', 'charts'],
	['motion', 'motion'],
	['use', 'in use'],
	['voice', 'voice'],
	['files', 'files'],
];

export function Section({ id, n, name, title, lead, children }: { id: string; n: number; name: string; title: ReactNode; lead?: ReactNode; children: ReactNode }) {
	const f = (n - 1) / 12;
	return (
		<section id={id} className="rule-t py-[60px] md:py-24">
			<div className="wrap">
				<div className="mb-[30px] grid grid-cols-1 gap-1 md:mb-11 md:grid-cols-[220px_minmax(0,1fr)] md:gap-6">
					<div className="label flex items-center gap-2.5 self-start leading-[2.4]">
						<Mark size={24} cx={0.2 + 0.6 * f} cy={0.5 + 0.28 * Math.sin(f * Math.PI * 2.2)} />
						{String(n).padStart(2, '0')} · {name}
					</div>
					<div>
						<h2 className="mb-4 font-display text-[clamp(34px,4.6vw,52px)] leading-[0.98] font-extrabold tracking-title text-balance">{title}</h2>
						{lead && <p className="max-w-[62ch]">{lead}</p>}
					</div>
				</div>
				{children}
			</div>
		</section>
	);
}

export const H3 = ({ children, className }: { children: ReactNode; className?: string }) => <h3 className={cn('mb-2 font-display text-[19px] leading-tight font-bold tracking-[-0.015em]', className)}>{children}</h3>;
export const Cap = ({ children, className }: { children: ReactNode; className?: string }) => <p className={cn('mt-3.5 max-w-[80ch] font-mono text-[13px] leading-[1.6]', className)}>{children}</p>;
export const Wm = ({ className, children = 'calcite' }: { className?: string; children?: ReactNode }) => <span className={cn('font-display leading-[0.86] font-extrabold tracking-[-0.05em]', className)}>{children}</span>;
