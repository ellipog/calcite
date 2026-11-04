// One tick across the window: the tick's 50 ms are the window's width, and what the server took
// of it is marked to the same scale at its left end: solid to the mean, half-tone to the 99th
// percentile, and a line at the longest. Almost all of the band is left over, which is the point.
// Plain CSS, no script; the legend under it says the same in words.

import { cn } from '@/lib/cn';

const TICK = 50;
const at = (ms: number) => `${(ms / TICK) * 100}%`;

export function TickBand({ mean, p99, max, runs, className }: { mean: number; p99: number; max: number; runs: number; className?: string }) {
	const ms = (v: number) => `${v.toFixed(2)} ms`;
	return (
		<figure className={cn('m-0', className)}>
			<div aria-hidden className="bleed">
				<div className="relative h-14 rule-t rule-b tint-6">
					<i className="absolute inset-y-0 left-0 tint-50" style={{ width: at(p99) }} />
					<i className="absolute inset-y-0 left-0 bg-ink" style={{ width: at(mean) }} />
					<i className="absolute inset-y-0 w-0.5 bg-ink" style={{ left: at(max) }} />
					{[10, 20, 30, 40].map((v) => (
						<i key={v} className="absolute bottom-0 h-2 w-0.5 -translate-x-1/2 bg-ink" style={{ left: at(v) }} />
					))}
				</div>
				<div className="relative h-6 font-mono text-[11px] leading-none tabular-nums">
					{[10, 20, 30, 40].map((v) => (
						// on a phone, 40 ms would run into the label at the end
						<span key={v} className={cn('absolute top-2 -translate-x-1/2', v === 40 && 'max-sm:hidden')} style={{ left: at(v) }}>
							{v} ms
						</span>
					))}
					<span className="absolute top-2 right-(--side)">50 ms, one tick</span>
				</div>
			</div>
			<figcaption className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:gap-10">
				<p className="max-w-[60ch] font-mono text-xs leading-normal">
					A tick has 50 ms, here the window&apos;s width. At its left end is how much of it Calcite took with 100 players joining, walking outward and chatting, over {runs} runs. The rest of the band is time the tick had to spare.
				</p>
				<ul className="grid gap-2 font-mono text-xs leading-none tabular-nums">
					<li className="flex items-center gap-2.5">
						<i className="inline-block h-3 w-5 bg-ink" />
						{ms(mean)} on average
					</li>
					<li className="flex items-center gap-2.5">
						<i className="inline-block h-3 w-5 tint-50" />
						{ms(p99)} at the 99th percentile
					</li>
					<li className="flex items-center gap-2.5">
						<i className="inline-flex h-3 w-5 justify-center">
							<i className="h-3 w-0.5 bg-ink" />
						</i>
						{ms(max)} the longest
					</li>
				</ul>
			</figcaption>
		</figure>
	);
}
