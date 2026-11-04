'use client';

import { useEffect, useRef, type ComponentProps, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

// Text fields: a dotted line under the text. On focus a solid line wipes in from the left with
// the dithered edge leading, and wipes back out on blur (d-field in dither.css).
const inputClass = 'd-input block w-full border-0 px-0.5 pt-2.5 pb-3 font-sans text-base leading-tight text-ink';

export function Field({ label, hint, className, ...rest }: { label: ReactNode; hint?: ReactNode } & ComponentProps<'input'>) {
	return (
		<div className={cn('max-w-[340px]', className)}>
			<label className="d-field grid gap-0.5">
				<span className="label">{label}</span>
				<input className={inputClass} spellCheck={false} {...rest} />
			</label>
			{hint && <p className="mt-1.5 font-mono text-xs leading-normal">{hint}</p>}
		</div>
	);
}

export function TextArea({ label, hint, className, ...rest }: { label: ReactNode; hint?: ReactNode } & ComponentProps<'textarea'>) {
	return (
		<div className={cn('max-w-[340px]', className)}>
			<label className="d-field grid gap-0.5">
				<span className="label">{label}</span>
				<textarea className={cn(inputClass, 'min-h-[92px] resize-y leading-normal')} {...rest} />
			</label>
			{hint && <p className="mt-1.5 font-mono text-xs leading-normal">{hint}</p>}
		</div>
	);
}

// Dotted, with a pixel chevron. Where the browser lets the list be styled, it's paper in a solid
// frame and dissolves in.
export function Select({ label, className, children, ...rest }: { label: ReactNode } & ComponentProps<'select'>) {
	return (
		<label className={cn('grid max-w-[340px] gap-1.5', className)}>
			<span className="label">{label}</span>
			<select className="d-select w-full rule py-[11px] pr-10 pl-3 font-sans text-[15px] leading-tight text-ink" {...rest}>
				{children}
			</select>
		</label>
	);
}

const choice = 'inline-flex cursor-pointer items-center gap-2.5 text-[15px] has-disabled:cursor-not-allowed';

// Square, both. A check fills in through the matrix; half done is half density.
export function Checkbox({ children, indeterminate, className, ...rest }: { indeterminate?: boolean; children: ReactNode } & Omit<ComponentProps<'input'>, 'type'>) {
	const ref = useRef<HTMLInputElement>(null);
	useEffect(() => {
		if (ref.current) ref.current.indeterminate = !!indeterminate;
	}, [indeterminate]);
	return (
		<label className={cn(choice, className)}>
			<input ref={ref} type="checkbox" className="d-check" {...rest} />
			{children}
		</label>
	);
}

export function Radio({ children, className, ...rest }: { children: ReactNode } & Omit<ComponentProps<'input'>, 'type'>) {
	return (
		<label className={cn(choice, className)}>
			<input type="radio" className="d-check" {...rest} />
			{children}
		</label>
	);
}

// No knob: on is a fill that wipes across, its dithered edge leading, like the slider.
export function Switch({ children, className, ...rest }: { children: ReactNode } & Omit<ComponentProps<'input'>, 'type'>) {
	return (
		<label className={cn(choice, className)}>
			<input type="checkbox" role="switch" className="d-switch" {...rest} />
			{children}
		</label>
	);
}

export function Fieldset({ legend, children, className }: { legend: ReactNode; children: ReactNode; className?: string }) {
	return (
		<fieldset className={cn('m-0 grid min-w-0 content-start gap-3 border-0 p-0', className)}>
			<legend className="label mb-1 p-0">{legend}</legend>
			{children}
		</fieldset>
	);
}

// A row of choices, one solid; the chosen one fills in through the matrix. Radios underneath, so
// it works without script and with arrow keys; FocusRing draws round the visible part.
export function Segmented({ label, name, options, defaultValue, onChange }: { label: string; name: string; options: string[]; defaultValue?: string; onChange?: (v: string) => void }) {
	const id = `seg-${name}`;
	return (
		<div className="grid max-w-[340px] gap-1.5">
			<span className="label" id={id}>
				{label}
			</span>
			<div role="radiogroup" aria-labelledby={id} className="inline-flex max-w-full justify-self-start overflow-x-auto rule [scrollbar-width:none]">
				{options.map((o, i) => (
					<label key={o} className="relative cursor-pointer">
						<input
							type="radio"
							name={name}
							value={o}
							defaultChecked={o === (defaultValue ?? options[0])}
							onChange={() => onChange?.(o)}
							data-ring="next"
							className="peer absolute m-0 size-px opacity-0"
						/>
						<span
							className={cn(
								'block bg-size-[8px_8px] px-3.5 py-[9px] font-mono text-[13px] leading-none whitespace-nowrap [:not(:checked)+&]:hover:underline [:not(:checked)+&]:hover:decoration-2 [:not(:checked)+&]:hover:underline-offset-4',
								'peer-checked:bg-(image:--solid) peer-checked:text-paper peer-checked:animate-[seg-in_0.16s_steps(1)]',
								i > 0 && 'rule-l',
							)}
						>
							{o}
						</span>
					</label>
				))}
			</div>
		</div>
	);
}
