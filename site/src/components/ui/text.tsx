import Link from 'next/link';
import type { ComponentProps, ReactNode } from 'react';
import { cn } from '@/lib/cn';

// A link sits on a line of half-density cells, which goes solid when you point at it.
export function TextLink({ className, ...rest }: ComponentProps<typeof Link>) {
	return <Link className={cn('link', className)} {...rest} />;
}

export function Kbd({ children }: { children: ReactNode }) {
	return <kbd className="inline-block rule [border-bottom:2px_solid_var(--color-ink)] px-1.5 pt-1 pb-[3px] font-mono text-xs leading-none font-medium">{children}</kbd>;
}

// An ink tooltip with a pixel point, dissolving in, over whatever it wraps.
export function Tip({ text, children, className }: { text: string; children: ReactNode; className?: string }) {
	return (
		<span className={cn('d-tip inline-flex', className)} data-tip={text}>
			{children}
		</span>
	);
}

// A frame with a small label in its corner, as every box in the guide is.
export function Panel({ label, inverse, className, children, ...rest }: { label?: ReactNode; inverse?: boolean } & ComponentProps<'div'>) {
	return (
		<div className={cn('relative min-w-0 rule p-[26px]', label != null && 'pt-[46px]', inverse && 'border-ink bg-ink text-paper', className)} {...rest}>
			{label != null && <span className={cn('label absolute top-0 left-0 z-[2] px-2.5 py-2 leading-none', inverse ? 'bg-ink text-paper' : 'bg-paper')}>{label}</span>}
			{children}
		</div>
	);
}

// + for do, × for don't.
export function Rules({ items, no, className }: { items: ReactNode[]; no?: boolean; className?: string }) {
	return (
		<ul className={cn('grid list-none gap-2.5 p-0', className)}>
			{items.map((it, i) => (
				<li key={i} className="relative pl-[26px]">
					<span className="absolute left-0 font-mono text-[15px] leading-[1.6] font-medium" aria-hidden>
						{no ? '×' : '+'}
					</span>
					{it}
				</li>
			))}
		</ul>
	);
}
