'use client';

// Who may join: a name looked up with Mojang as it's typed, through /api/player, then listed with
// its face and UUID, and a box to make it an op. In offline mode nothing is looked up: the server
// makes each player's UUID from their name, and so does this.

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox, Field } from '@/components/ui/form';
import { cn } from '@/lib/cn';
import { idOn, offlineId, VALID_NAME, type Player, type Setup } from '@/lib/setup/settings';
import { Face } from './parts';

type Found = { name: string; id: string; skin: string | null };
type Look = { state: 'idle' } | { state: 'looking'; name: string } | { state: 'found'; player: Found } | { state: 'none' | 'error'; message: string };
/** A lookup's answer, for the name it was for. */
type Answer = { name: string; look: Look };

async function lookUp(name: string, signal?: AbortSignal): Promise<Found | { error: string; status: number }> {
	const r = await fetch(`/api/player/${encodeURIComponent(name)}`, { signal });
	const j = await r.json();
	return r.ok ? (j as Found) : { error: j.error ?? `The lookup said ${r.status}`, status: r.status };
}

export function Players({ s, set }: { s: Setup; set: (f: (s: Setup) => Setup) => void }) {
	const [query, setQuery] = useState('');
	const [answer, setAnswer] = useState<Answer | null>(null);
	const q = query.trim();
	const listed = s.players.some((p) => p.name.toLowerCase() === q.toLowerCase());
	const lookable = s.onlineMode && VALID_NAME.test(q);
	const look: Look = !q || !s.onlineMode ? { state: 'idle' } : !lookable ? { state: 'error', message: 'A name is 1 to 16 letters, digits or _.' } : answer?.name === q ? answer.look : { state: 'looking', name: q };

	// look the name up a moment after typing stops; a newer name cancels the older lookup
	useEffect(() => {
		if (!lookable) return;
		const ac = new AbortController();
		const t = setTimeout(async () => {
			let next: Look;
			try {
				const r = await lookUp(q, ac.signal);
				next = 'error' in r ? { state: r.status === 404 ? 'none' : 'error', message: r.error } : { state: 'found', player: r };
			} catch {
				if (ac.signal.aborted) return;
				next = { state: 'error', message: 'The lookup didn’t answer.' };
			}
			setAnswer({ name: q, look: next });
		}, 350);
		return () => {
			clearTimeout(t);
			ac.abort();
		};
	}, [q, lookable]);

	// Players added in offline mode are looked up once online mode is on, and those from a link,
	// which carries no skins, for their faces: one at a time, each once. A UUID from the link stays,
	// even if the name has since gone to another account.
	const pending = s.onlineMode ? s.players.find((p) => !p.missing && !p.failed && (p.id === null || p.skin === undefined)) : undefined;
	useEffect(() => {
		if (!pending) return;
		let live = true;
		const settle = (r: Found | { error: string; status: number }) => (p: Player): Player => {
			if ('error' in r) return p.id ? { ...p, skin: null } : { ...p, missing: r.status === 404, failed: r.status !== 404 };
			const same = !p.id || p.id === r.id;
			return { ...p, name: same ? r.name : p.name, id: p.id ?? r.id, skin: same ? r.skin : null, missing: false };
		};
		lookUp(pending.name)
			.catch(() => ({ error: 'The lookup didn’t answer.', status: 0 }))
			.then((r) => {
				if (live) set((x) => ({ ...x, players: x.players.map((p) => (p.name === pending.name ? settle(r)(p) : p)) }));
			});
		return () => {
			live = false;
		};
	}, [pending, set]);

	const add = () => {
		if (listed || !q) return;
		let p: Player | null = null;
		if (!s.onlineMode && VALID_NAME.test(q)) p = { name: q, id: null, op: false };
		else if (look.state === 'found') p = { name: look.player.name, id: look.player.id, skin: look.player.skin, op: false };
		if (!p) return;
		set((x) => ({ ...x, players: [...x.players, p] }));
		setQuery('');
	};

	const result = (() => {
		if (!q) return null;
		if (listed) return <span>{q} is listed already.</span>;
		if (!s.onlineMode) return VALID_NAME.test(q) ? <span>Offline UUID {offlineId(q)}</span> : <span>A name is 1 to 16 letters, digits or _.</span>;
		switch (look.state) {
			case 'looking':
				return <span>Looking up {look.name}…</span>;
			case 'found':
				return (
					<span className="flex items-center gap-2.5">
						<Face skin={look.player.skin} size={24} />
						<b className="font-medium text-ink">{look.player.name}</b>
						<span className="text-soft">{look.player.id}</span>
					</span>
				);
			case 'none':
			case 'error':
				return <span>{look.message}</span>;
			default:
				return null;
		}
	})();
	const canAdd = !listed && !!q && (s.onlineMode ? look.state === 'found' : VALID_NAME.test(q));

	return (
		<div className="grid gap-4">
			<form
				className="flex flex-wrap items-end gap-3"
				onSubmit={(e) => {
					e.preventDefault();
					add();
				}}
			>
				<Field label="Add a player" placeholder="their Minecraft name" value={query} maxLength={16} autoComplete="off" onChange={(e) => setQuery(e.target.value)} className="min-w-0 flex-[1_1_220px]" />
				<Button type="submit" variant="secondary" disabled={!canAdd}>
					add
				</Button>
			</form>
			<div className="min-h-6 font-mono text-xs leading-6 text-deep" aria-live="polite">
				{result}
			</div>
			{s.players.length > 0 && (
				<ul className="rule-t">
					{s.players.map((p) => {
						const id = idOn(s, p);
						return (
							<li key={p.name} className="flex flex-wrap items-center gap-x-4 gap-y-2 rule-b py-2.5">
								<Face skin={s.onlineMode ? p.skin : null} size={32} />
								<div className="grid min-w-0 flex-[1_1_200px]">
									<b className="font-medium text-ink">{p.name}</b>
									<span className={cn('truncate font-mono text-xs', id ? 'text-soft' : 'text-ink')}>{id ?? (p.missing ? 'No account has this name, so it’s left out' : p.failed ? 'Couldn’t be looked up, so it’s left out' : 'looking up…')}</span>
								</div>
								<Checkbox checked={p.op} onChange={(e) => set((x) => ({ ...x, players: x.players.map((o) => (o.name === p.name ? { ...o, op: e.target.checked } : o)) }))}>
									op
								</Checkbox>
								<Button variant="secondary" size="sm" onClick={() => set((x) => ({ ...x, players: x.players.filter((o) => o.name !== p.name) }))}>
									remove
								</Button>
							</li>
						);
					})}
				</ul>
			)}
		</div>
	);
}
