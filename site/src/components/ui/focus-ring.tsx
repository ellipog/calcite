'use client';

import { useEffect } from 'react';
import { still } from '@/lib/dither/motion';

// The focus ring: one element of diagonal halves marching round whatever has keyboard focus,
// stepping from control to control. Mount it once, in the root layout. The slider and text
// fields draw their own; an input hidden behind its label (data-ring="next") gets the ring round
// the label's visible part. Without script, :focus-visible keeps a solid outline.
export function FocusRing() {
	useEffect(() => {
		const root = document.documentElement;
		root.classList.add('ui');
		const ring = document.createElement('div');
		ring.className = 'd-ring';
		ring.setAttribute('aria-hidden', 'true');
		ring.hidden = true;
		document.body.append(ring);
		let target: Element | null = null, raf = 0;
		const own = (el: Element) => el.closest('[data-own-focus]') != null || el.matches('.d-input');
		const shown = (el: Element) => (el.getAttribute('data-ring') === 'next' ? el.nextElementSibling ?? el : el);
		const place = () => {
			raf = 0;
			if (!target) return;
			const r = target.getBoundingClientRect(), pad = 6;
			ring.style.transform = `translate(${Math.round(r.left - pad)}px, ${Math.round(r.top - pad)}px)`;
			ring.style.width = Math.round(r.width + 2 * pad) + 'px';
			ring.style.height = Math.round(r.height + 2 * pad) + 'px';
		};
		const hide = () => {
			target = null;
			ring.hidden = true;
		};
		const focusin = (e: FocusEvent) => {
			const el = e.target;
			if (!(el instanceof Element) || own(el) || !el.matches(':focus-visible')) return hide();
			// a dialog is in the top layer, so the ring goes inside it to stay on top
			const host = el.closest('dialog[open]') ?? document.body;
			if (ring.parentNode !== host) {
				host.append(ring);
				ring.hidden = true;
			}
			ring.classList.toggle('go', !ring.hidden && !still());
			target = shown(el);
			ring.hidden = false;
			place();
		};
		const follow = () => {
			if (!target || raf) return;
			ring.classList.remove('go');
			raf = requestAnimationFrame(place);
		};
		document.addEventListener('focusin', focusin);
		document.addEventListener('focusout', hide);
		addEventListener('scroll', follow, { capture: true, passive: true });
		addEventListener('resize', follow);
		return () => {
			document.removeEventListener('focusin', focusin);
			document.removeEventListener('focusout', hide);
			removeEventListener('scroll', follow, { capture: true });
			removeEventListener('resize', follow);
			cancelAnimationFrame(raf);
			ring.remove();
			root.classList.remove('ui');
		};
	}, []);
	return null;
}
