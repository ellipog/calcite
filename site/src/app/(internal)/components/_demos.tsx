'use client';

import { useState } from 'react';
import { Bitmap } from '@/components/mark';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Dialog, useToast } from '@/components/ui/overlay';
import { MARK, markBits, markLeaves } from '@/lib/dither/mark';

// The stepped slider drives the mark: its view radius is the view distance, scaled so that 12
// chunks is the printed mark exactly.
export function ViewDistance() {
	const [v, setV] = useState(12);
	const r = (MARK.r * v) / 12, n = 64, ml = markLeaves(n, { r });
	const c = { in: 0, edge: 0, out: 0 };
	ml.leaves.forEach((l) => c[l.zone]++);
	const side = 2 * v + 1;
	return (
		<div className="grid grid-cols-1 items-center gap-9 md:grid-cols-[minmax(0,1fr)_auto]">
			<div>
				<Slider label="View distance" min={2} max={32} step={1} value={v} onValueChange={setV} unit="chunks" ticks />
				<p className="note mt-3.5">
					{side} × {side} = {(side * side).toLocaleString('en-US')} chunks sent · the mark: {ml.leaves.length} squares, {c.in} in view, {c.edge} on the edge{v === 12 ? ' · this is the mark' : ''}
				</p>
			</div>
			<Bitmap bits={markBits(n, { r })} n={n} size={128} title={`The mark at view distance ${v}`} />
		</div>
	);
}

export function ToastButton() {
	const toast = useToast();
	return (
		<Button variant="secondary" onClick={() => toast('World saved · 3,725 chunks')}>
			Show a toast
		</Button>
	);
}

export function StopDialog() {
	return (
		<Dialog
			title="Stop the server?"
			trigger={<Button>Stop the server</Button>}
			actions={(close) => (
				<>
					<Button onClick={close}>Stop it</Button>
					<Button variant="secondary" onClick={close}>
						Keep it running
					</Button>
				</>
			)}
		>
			<p>Three players are online. They&apos;ll be sent to the server list, and the world is saved first.</p>
		</Dialog>
	);
}
