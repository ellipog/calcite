'use client';

// Hooks for drawings that move: in steps while on screen, every frame while on screen, or again
// when their box changes size. Each runs once, still, for readers who ask for less motion.

import { useEffect, useRef, type RefObject } from 'react';

export const still = () => typeof window !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

// Keeps the latest callback in a ref, so effects needn't restart when it changes.
function useLatest<T>(v: T) {
	const r = useRef(v);
	useEffect(() => {
		r.current = v;
	});
	return r;
}

// step(k) every ms milliseconds while el is on screen; just step(last) with reduced motion.
export function useSteps(ref: RefObject<Element | null>, ms: number, step: (k: number) => void, last = 0, deps: unknown[] = []) {
	const fn = useLatest(step);
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		if (still()) {
			fn.current(last);
			return;
		}
		let id = 0, k = 0;
		const go = () => {
			fn.current(k++);
			id = window.setTimeout(go, ms);
		};
		const io = new IntersectionObserver(([e]) => {
			clearTimeout(id);
			if (e.isIntersecting) go();
		});
		io.observe(el);
		return () => {
			io.disconnect();
			clearTimeout(id);
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ref, ms, last, ...deps]);
}

// draw(seconds) every frame while el is on screen; once, at 0, with reduced motion.
export function useFrames(ref: RefObject<Element | null>, draw: (t: number) => void, deps: unknown[] = []) {
	const fn = useLatest(draw);
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const t0 = performance.now();
		if (still()) {
			fn.current(0);
			return;
		}
		let on = false, raf = 0;
		const tick = (now: number) => {
			raf = 0;
			fn.current((now - t0) / 1000);
			if (on) raf = requestAnimationFrame(tick);
		};
		const io = new IntersectionObserver(([e]) => {
			on = e.isIntersecting;
			if (on && !raf) raf = requestAnimationFrame(tick);
		});
		io.observe(el);
		return () => {
			io.disconnect();
			cancelAnimationFrame(raf);
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ref, ...deps]);
}

// fn() once fonts are ready, and again whenever el's width changes.
export function useSized(ref: RefObject<Element | null>, fn: () => void, deps: unknown[] = []) {
	const cb = useLatest(fn);
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		let w = -1, dead = false, id = 0;
		const run = () => {
			const nw = Math.round(el.getBoundingClientRect().width);
			if (nw === w || dead) return;
			w = nw;
			cb.current();
		};
		// drawings with type in them need the fonts, so every run waits for them
		const go = () => document.fonts.ready.then(run);
		const ro = new ResizeObserver(() => {
			clearTimeout(id);
			id = window.setTimeout(go, w < 0 ? 0 : 120);
		});
		ro.observe(el);
		return () => {
			dead = true;
			ro.disconnect();
			clearTimeout(id);
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ref, ...deps]);
}
