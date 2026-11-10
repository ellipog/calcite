'use client';

import { cloneElement, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { still } from '@/lib/dither/motion';
import { highlight, type Kind } from '@/lib/highlight';
import { cn } from '@/lib/cn';
import { Button } from './button';

// Runs fn once el's exit animation ends, or at once with no motion; a timer covers a lost event.
function after(el: Element, fn: () => void) {
	if (still()) return fn();
	let done = false;
	const go = () => {
		if (done) return;
		done = true;
		fn();
	};
	el.addEventListener('animationend', go, { once: true });
	setTimeout(go, 400);
}

/* ---- toasts: ink, bottom centre, in and out through the matrix -------------------------------- */

const ToastContext = createContext<(text: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function Toaster({ children }: { children: ReactNode }) {
	const [list, setList] = useState<{ id: number; text: string; out: boolean }[]>([]);
	const next = useRef(0);
	const toast = useCallback((text: string) => {
		const id = next.current++;
		setList((l) => [...l, { id, text, out: false }]);
		setTimeout(() => setList((l) => l.map((t) => (t.id === id ? { ...t, out: true } : t))), 2200);
		setTimeout(() => setList((l) => l.filter((t) => t.id !== id)), still() ? 2200 : 2420);
	}, []);
	return (
		<ToastContext.Provider value={toast}>
			{children}
			<div role="status" aria-live="polite" className="pointer-events-none fixed bottom-6 left-1/2 z-[900] grid -translate-x-1/2 justify-items-center gap-2">
				{list.map((t) => (
					<div
						key={t.id}
						className={cn(
							"flex items-center gap-2.5 bg-ink px-4 py-3 font-mono text-[13px] leading-none text-paper before:size-2.5 before:flex-none before:bg-paper before:content-['']",
							t.out ? 'animate-dis-out' : 'animate-dis-in',
						)}
					>
						{t.text}
					</div>
				))}
			</div>
		</ToastContext.Provider>
	);
}

/* ---- dialogs: the page goes under a screen of ink dots; Escape or a click outside closes ---- */

export function Dialog({ trigger, title, children, actions }: { trigger: ReactElement<{ onClick?: () => void }>; title: string; children: ReactNode; actions: (close: () => void) => ReactNode }) {
	// The element is held in state, not a ref, so the trigger and the actions can be handed
	// functions that use it while rendering.
	const [d, setD] = useState<HTMLDialogElement | null>(null);
	const close = useCallback(() => {
		if (!d?.open || d.classList.contains('out')) return;
		d.classList.add('out');
		after(d, () => {
			d.classList.remove('out');
			d.close();
		});
	}, [d]);
	useEffect(() => {
		if (!d) return;
		const cancel = (e: Event) => {
			e.preventDefault();
			close();
		};
		const click = (e: MouseEvent) => {
			if (e.target !== d) return;
			const r = d.getBoundingClientRect();
			if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) close();
		};
		d.addEventListener('cancel', cancel);
		d.addEventListener('click', click);
		return () => {
			d.removeEventListener('cancel', cancel);
			d.removeEventListener('click', click);
		};
	}, [d, close]);
	return (
		<>
			{cloneElement(trigger, { onClick: () => d?.showModal() })}
			<dialog ref={setD} aria-label={title} className="d-dialog m-auto w-[min(460px,calc(100vw-32px))] border border-ink bg-paper p-7 text-ink">
				<h3 className="mb-2.5 font-display text-[22px] leading-tight font-bold tracking-tight">{title}</h3>
				{children}
				<div className="mt-[22px] flex flex-wrap items-center gap-2.5">{actions(close)}</div>
			</dialog>
		</>
	);
}

/* ---- code: a half-density bar down the left, solid once copied; comments aren't copied ------ */

const LANGS: Record<string, string> = { sh: 'shell', bash: 'shell', powershell: 'PowerShell', properties: '.properties', toml: '.toml', json: '.json', calx: 'Calx' };

// Each kind of token in its text blue (globals.css). Code is DM Mono 400 in the deep blue; the
// words that give a line its shape, keywords and the names being called, are 500.
export const HL: Record<Kind, string | undefined> = {
	plain: undefined,
	kw: 'text-ink font-medium',
	key: 'text-ink',
	type: 'text-indigo',
	fn: 'font-medium',
	str: 'text-ice',
	num: 'text-sky',
	attr: 'text-sky',
	var: 'text-indigo',
	punct: 'text-soft',
	com: 'text-faint',
};

export function CodeBlock({
	code,
	copy = true,
	comment = '#',
	lang,
	className,
}: {
	code: string;
	copy?: boolean;
	/** What a line starts with to be a comment, which is fainter and isn't copied; null for none. */
	comment?: string | null;
	/** Highlights the code, if it's one of the languages in lib/highlight.ts, and is shown in the
	 * corner, as `sh` or `powershell`, where it helps to know. */
	lang?: string;
	className?: string;
}) {
	const toast = useToast();
	const [done, setDone] = useState(0);
	const lines = code.split('\n');
	const tokens = useMemo(() => highlight(code, lang), [code, lang]);
	const isComment = (l: string) => comment != null && l.trim().startsWith(comment);
	const run = async () => {
		const keep = lines.filter((l) => l.trim() && !isComment(l));
		try {
			await navigator.clipboard.writeText(keep.join('\n') + '\n');
		} catch {
			return toast('Couldn’t copy: the browser said no');
		}
		setDone((k) => k + 1);
		toast(`Copied ${keep.length} line${keep.length === 1 ? '' : 's'}`);
	};
	useEffect(() => {
		if (!done) return;
		const id = setTimeout(() => setDone(0), 1800);
		return () => clearTimeout(id);
	}, [done]);
	return (
		<div className={cn('relative min-w-0', className)}>
			{lang && LANGS[lang] && Math.max(...lines.map((l) => l.length)) <= 56 && <span className="pointer-events-none absolute top-0 right-0 font-mono text-[11px] leading-none text-soft select-none max-sm:hidden" style={{ right: copy ? 72 : 10, top: 15 }}>{LANGS[lang]}</span>}
			{/* on a phone the button gets a strip of its own above the code, so no line starts under it */}
			<pre key={done} className={cn('d-code m-0 overflow-x-auto py-4 pl-[22px] font-mono text-[13.5px] leading-[1.7] font-normal text-deep whitespace-pre', copy ? 'pr-[76px] max-sm:pt-[50px] max-sm:pr-[18px]' : 'pr-[18px]', done > 0 && 'done')}>
				{lines.map((l, i) => (
					<span key={i} className={isComment(l) ? HL.com : undefined}>
						{isComment(l)
							? l
							: tokens[i].map(([k, s], j) =>
									HL[k] ? (
										<span key={j} className={HL[k]}>
											{s}
										</span>
									) : (
										s
									),
								)}
						{i < lines.length - 1 && '\n'}
					</span>
				))}
			</pre>
			{copy && (
				// paper under the button hides code scrolled beneath it, and leaves the button's own
				// ground free to fill on a hover
				<div className="absolute top-2.5 right-2.5 bg-paper">
					<Button variant="secondary" size="sm" onClick={run}>
						{done ? 'copied' : 'copy'}
					</Button>
				</div>
			)}
		</div>
	);
}
