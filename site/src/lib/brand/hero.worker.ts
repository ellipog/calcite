// The home page's flight, in a worker: the page hands it an OffscreenCanvas and tells it the
// canvas's size, the pointer, touches and whether it's on screen, and it draws on its own thread,
// so the flight never holds up the page's scrolling or input. It says back how many chunks have
// loaded.

import { Hero, type HeroOptions } from './hero';

type Message =
	| { type: 'init'; canvas: OffscreenCanvas; o: Pick<HeroOptions, 'cps' | 'still' | 'touch' | 'seed'> }
	| { type: 'size'; w: number; h: number; dpr: number }
	| { type: 'point'; p: [number, number] | null }
	| { type: 'wake' }
	| { type: 'show'; on: boolean };

// a worker's own frames where it has them, and a timer at 60 a second where it doesn't
const scope = self as unknown as {
	requestAnimationFrame?: (f: (ms: number) => void) => number;
	cancelAnimationFrame?: (id: number) => void;
	postMessage: (m: unknown) => void;
	onmessage: ((e: MessageEvent<Message>) => void) | null;
};
const raf = scope.requestAnimationFrame ? (f: (ms: number) => void) => scope.requestAnimationFrame!(f) : (f: (ms: number) => void) => setTimeout(() => f(performance.now()), 16) as unknown as number;
const caf = scope.cancelAnimationFrame ? (id: number) => scope.cancelAnimationFrame!(id) : (id: number) => clearTimeout(id);

let hero: Hero | null = null;
scope.onmessage = (e) => {
	const m = e.data;
	if (m.type === 'init') hero = new Hero(m.canvas, { ...m.o, raf, caf, count: (n) => scope.postMessage({ type: 'count', n }) });
	else if (!hero) return;
	else if (m.type === 'size') hero.resize(m.w, m.h, m.dpr);
	else if (m.type === 'point') hero.point(m.p);
	else if (m.type === 'wake') hero.wake();
	else if (m.type === 'show') hero.show(m.on);
};
