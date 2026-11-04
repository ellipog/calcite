'use client';

import { useId, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

// A dotted rule; the chosen tab's line fills in through the matrix and its panel dissolves in.
// Arrow keys, Home and End move between tabs.
export function Tabs({ label, tabs, className }: { label: string; tabs: { title: string; content: ReactNode }[]; className?: string }) {
	const [on, setOn] = useState(0);
	const id = useId(), refs = useRef<(HTMLButtonElement | null)[]>([]);
	const pick = (i: number, focus = false) => {
		const j = (i + tabs.length) % tabs.length;
		setOn(j);
		if (focus) refs.current[j]?.focus();
	};
	return (
		<div className={className}>
			<div
				role="tablist"
				aria-label={label}
				className="flex gap-[22px] overflow-x-auto rule-b text-[15px] [scrollbar-width:none]"
				onKeyDown={(e) => {
					const j = { ArrowRight: on + 1, ArrowLeft: on - 1, Home: 0, End: tabs.length - 1 }[e.key];
					if (j === undefined) return;
					e.preventDefault();
					pick(j, true);
				}}
			>
				{tabs.map((t, i) => (
					<button
						key={t.title}
						ref={(el) => {
							refs.current[i] = el;
						}}
						role="tab"
						type="button"
						id={`${id}-t${i}`}
						aria-controls={`${id}-p${i}`}
						aria-selected={i === on}
						tabIndex={i === on ? 0 : -1}
						onClick={() => pick(i)}
						className={cn('d-tab relative m-0 border-0 bg-transparent px-0 pt-2.5 pb-[13px] whitespace-nowrap text-ink', i === on && 'font-bold')}
					>
						{t.title}
					</button>
				))}
			</div>
			{tabs.map((t, i) => (
				<div key={t.title} role="tabpanel" id={`${id}-p${i}`} aria-labelledby={`${id}-t${i}`} hidden={i !== on} className="animate-dis-in pt-4">
					{t.content}
				</div>
			))}
		</div>
	);
}
