import Link from 'next/link';
import type { ComponentProps, ReactNode } from 'react';
import { cn } from '@/lib/cn';

// Primary is solid ink; secondary is a dotted frame. A hover inverts them, crisply: primary turns
// to paper in a solid frame, secondary fills solid. No dots appear under the pointer. A busy button
// marches paper dots round its label; a disabled one is a few dots, its word still in ink.

type Variant = 'primary' | 'secondary';
type Size = 'md' | 'sm';
interface Common {
	variant?: Variant;
	size?: Size;
	busy?: boolean;
	className?: string;
	children?: ReactNode;
}

export function buttonClass({ variant = 'primary', size = 'md', busy = false, className }: Omit<Common, 'children'> = {}) {
	return cn(
		'group inline-flex items-center justify-center gap-2 border leading-none select-none tile-16',
		size === 'md' ? 'px-[18px] py-[13px] text-[15px] font-bold' : 'px-2.5 py-[7px] font-mono text-xs font-normal',
		variant === 'primary'
			? 'border-ink bg-ink text-paper'
			: 'border-dotted border-ink bg-transparent text-ink',
		!busy &&
			(variant === 'primary'
				? 'enabled:hover:bg-paper enabled:hover:text-ink [a&]:hover:bg-paper [a&]:hover:text-ink'
				: 'enabled:hover:border-solid enabled:hover:bg-ink enabled:hover:text-paper [a&]:hover:border-solid [a&]:hover:bg-ink [a&]:hover:text-paper'),
		'enabled:active:translate-y-px',
		'disabled:cursor-not-allowed disabled:border-dotted disabled:bg-transparent disabled:text-ink disabled:tint-6',
		busy && (variant === 'primary' ? 'cursor-progress tint-paper-12 animate-march16' : 'cursor-progress tint-12 animate-march16'),
		className,
	);
}

// Text that crosses dots gets a block of its own: a busy or disabled button's label sits on one.
const label = (variant: Variant, busy?: boolean) => cn('-mx-1 px-1 group-disabled:bg-paper', busy && (variant === 'primary' ? 'bg-ink' : 'bg-paper'));

export function Button({ variant = 'primary', size, busy, className, type = 'button', children, ...rest }: Common & ComponentProps<'button'>) {
	return (
		<button type={type} aria-busy={busy || undefined} className={buttonClass({ variant, size, busy, className })} {...rest}>
			<span className={label(variant, busy)}>{children}</span>
		</button>
	);
}

export function ButtonLink({ variant, size, className, ...rest }: Common & ComponentProps<typeof Link>) {
	return <Link className={buttonClass({ variant, size, className })} {...rest} />;
}
