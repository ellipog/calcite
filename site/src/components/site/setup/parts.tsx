'use client';

// The setup's pictures: a player's face, the server as the game's server list shows it, and the
// icon picker. The face, the icon and the MOTD's colours are the player's own, so they're drawn
// in their colours; everything round them is the one ink.

import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Button } from '@/components/ui/button';
import { Segmented } from '@/components/ui/form';
import { cn } from '@/lib/cn';
import { runs, type Run, type Setup } from '@/lib/setup/settings';

/** A player's face, the skin's front square and its hat over it, cut out with CSS so the skin
 *  needn't be read across origins. Blank dots with no skin. */
export function Face({ skin, size = 32, className }: { skin?: string | null; size?: number; className?: string }) {
	if (!skin) return <span aria-hidden className={cn('block flex-none rule tint-25', className)} style={{ width: size, height: size }} />;
	const k = size / 8;
	const layer = (x: number): CSSProperties => ({
		backgroundImage: `url(${skin})`,
		backgroundSize: `${64 * k}px auto`,
		backgroundPosition: `${-x * k}px ${-8 * k}px`,
		imageRendering: 'pixelated',
	});
	return (
		<span aria-hidden className={cn('relative block flex-none', className)} style={{ width: size, height: size }}>
			<span className="absolute inset-0" style={layer(8)} />
			<span className="absolute inset-0" style={layer(40)} />
		</span>
	);
}

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
const scramble = (t: string) => t.replace(/\S/g, () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)]);

function Line({ text, tick }: { text: string; tick: number }) {
	return (
		<div className="h-[18px] overflow-hidden whitespace-pre" data-tick={tick}>
			{runs(text).map((r: Run, i) => (
				<span
					key={i}
					style={{
						color: r.colour,
						fontWeight: r.bold ? 500 : undefined,
						fontStyle: r.italic ? 'italic' : undefined,
						textDecoration: [r.underline && 'underline', r.strike && 'line-through'].filter(Boolean).join(' ') || undefined,
					}}
				>
					{r.obfuscated ? scramble(r.text) : r.text}
				</span>
			))}
		</div>
	);
}

// The connection bars at full strength, as the list draws a server that answered quickly.
function Bars() {
	return (
		<span aria-hidden className="inline-flex h-3.5 items-end gap-px">
			{[3, 5, 8, 11, 14].map((h) => (
				<i key={h} className="block w-[3px] bg-paper" style={{ height: h }} />
			))}
		</span>
	);
}

/** The server as a player's server list shows it once it's running: its icon, the name they save
 *  it as, the MOTD's two lines, the count of players and the bars. */
export function ServerRow({ s, icon }: { s: Setup; icon: string | null }) {
	// obfuscated text changes a few times a second, as the game's does
	const moving = /[&§]k/i.test(s.motd.join(''));
	const [tick, setTick] = useState(0);
	useEffect(() => {
		if (!moving || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		const id = setInterval(() => setTick((t) => t + 1), 120);
		return () => clearInterval(id);
	}, [moving]);
	return (
		<div className="flex gap-3 bg-ink p-2 font-mono text-[14px] leading-[18px] text-paper" aria-label="How the server list will show it">
			{icon ? (
				// eslint-disable-next-line @next/next/no-img-element -- a blob URL, made in the browser
				<img src={icon} width={64} height={64} alt="" className="size-16 flex-none [image-rendering:pixelated]" />
			) : (
				<span aria-hidden className="size-16 flex-none tint-paper-25" />
			)}
			<div className="min-w-0 flex-1">
				<div className="flex items-start justify-between gap-3">
					<span className="truncate">{s.name || 'Minecraft Server'}</span>
					<span className="flex flex-none items-end gap-2 whitespace-nowrap">
						0/{s.maxPlayers}
						<Bars />
					</span>
				</div>
				<Line text={s.motd[0]} tick={tick} />
				<Line text={s.motd[1]} tick={tick} />
			</div>
		</div>
	);
}

export type Fit = 'fill' | 'fit';

/** Any image as the 64 × 64 PNG the server list wants: filling the square, its middle cut out, or
 *  fitted whole, on a clear ground. A picture that's small already, as pixel art is, is scaled
 *  without smoothing. */
export async function toIcon(file: Blob, fit: Fit = 'fill'): Promise<Blob> {
	const bmp = await createImageBitmap(file);
	const c = document.createElement('canvas');
	c.width = c.height = 64;
	const g = c.getContext('2d')!;
	const k = (fit === 'fill' ? Math.max : Math.min)(64 / bmp.width, 64 / bmp.height);
	const w = bmp.width * k, h = bmp.height * k;
	g.imageSmoothingEnabled = bmp.width > 64 || bmp.height > 64;
	g.imageSmoothingQuality = 'high';
	g.drawImage(bmp, (64 - w) / 2, (64 - h) / 2, w, h);
	bmp.close();
	return new Promise((ok, no) => c.toBlob((b) => (b ? ok(b) : no(new Error('The browser made no PNG'))), 'image/png'));
}

/** Picks the icon's image, any size or shape; the setup scales it (toIcon) as `fit` says. */
export function IconPicker({ icon, fit, onFit, onImage, onError }: { icon: string | null; fit: Fit; onFit: (f: Fit) => void; onImage: (image: Blob | null) => void; onError: (message: string) => void }) {
	const input = useRef<HTMLInputElement>(null);
	const [over, setOver] = useState(false);
	const take = (f: File | undefined) => {
		if (!f) return;
		if (!f.type.startsWith('image/')) return onError('That isn’t an image');
		onImage(f);
	};
	return (
		<div className="grid max-w-[460px] gap-1.5">
			<span className="label">Icon</span>
			<div
				className={cn('flex items-center gap-4 p-3', over ? 'border border-ink' : 'rule')}
				onDragOver={(e) => {
					e.preventDefault();
					setOver(true);
				}}
				onDragLeave={() => setOver(false)}
				onDrop={(e) => {
					e.preventDefault();
					setOver(false);
					take(e.dataTransfer.files[0]);
				}}
			>
				{icon ? (
					// eslint-disable-next-line @next/next/no-img-element -- a blob URL, made in the browser
					<img src={icon} width={64} height={64} alt="The server's icon" className="size-16 flex-none [image-rendering:pixelated]" />
				) : (
					<span aria-hidden className="size-16 flex-none rule tint-12" />
				)}
				<div className="grid min-w-0 gap-2">
					<p className="text-sm leading-snug">{icon ? 'Scaled to 64 × 64 for you, as server-icon.png.' : 'Drop any image here, or choose one. It’s scaled to the 64 × 64 the server list wants for you.'}</p>
					<div className="flex flex-wrap gap-2">
						<Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
							{icon ? 'change' : 'choose an image'}
						</Button>
						{icon && (
							<Button variant="secondary" size="sm" onClick={() => onImage(null)}>
								remove
							</Button>
						)}
					</div>
				</div>
				<input
					ref={input}
					type="file"
					accept="image/*"
					className="sr-only"
					tabIndex={-1}
					onChange={(e) => {
						take(e.target.files?.[0]);
						e.target.value = '';
					}}
				/>
			</div>
			{icon && <Segmented label="Not square?" name="icon-fit" options={['fill', 'fit']} value={fit} onChange={(v) => onFit(v as Fit)} className="mt-2" />}
			{icon && <p className="font-mono text-xs leading-normal">{fit === 'fill' ? 'Fill: the middle square of it, edge to edge.' : 'Fit: all of it, with clear space beside it.'}</p>}
		</div>
	);
}
