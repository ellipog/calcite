'use client';

import { cloneElement, createContext, useCallback, useContext, useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { still } from '@/lib/dither/motion';
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

export function CodeBlock({ code, copy = true, className }: { code: string; copy?: boolean; className?: string }) {
	const toast = useToast();
	const [done, setDone] = useState(0);
	const lines = code.split('\n');
	const run = async () => {
		const keep = lines.filter((l) => l.trim() && !l.trim().startsWith('#'));
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
			<pre key={done} className={cn('d-code m-0 overflow-x-auto py-4 pr-[76px] pl-[22px] font-mono text-[13.5px] leading-[1.7] font-medium whitespace-pre', done > 0 && 'done')}>
				{lines.map((l, i) => (
					<span key={i} className={l.trim().startsWith('#') ? 'font-normal' : undefined}>
						{l}
						{i < lines.length - 1 && '\n'}
					</span>
				))}
			</pre>
			{copy && (
				<Button variant="secondary" size="sm" className="absolute top-2.5 right-2.5 bg-paper" onClick={run}>
					{done ? 'copied' : 'copy'}
				</Button>
			)}
		</div>
	);
}
