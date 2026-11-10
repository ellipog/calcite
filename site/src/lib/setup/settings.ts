// A server set up before it's downloaded: the settings the download page offers, the presets they
// start from, and the files they're written to. Every key here is one Calcite reads
// (src/server/properties.calx and src/server/config.calx), at vanilla's default unless a preset
// says otherwise. Nothing in this file touches the network.

import { md5 } from './md5';

export type GameMode = 'survival' | 'creative' | 'adventure' | 'spectator';
export type Difficulty = 'peaceful' | 'easy' | 'normal' | 'hard';
export type WorldType = 'minecraft:normal' | 'minecraft:flat' | 'minecraft:large_biomes' | 'minecraft:amplified';
export type Dashboard = 'off' | 'bottom' | 'top';

export const MODES: GameMode[] = ['survival', 'creative', 'adventure', 'spectator'];
export const DIFFICULTIES: Difficulty[] = ['peaceful', 'easy', 'normal', 'hard'];
export const WORLDS: { id: WorldType; name: string }[] = [
	{ id: 'minecraft:normal', name: 'Normal' },
	{ id: 'minecraft:flat', name: 'Flat' },
	{ id: 'minecraft:large_biomes', name: 'Large biomes' },
	{ id: 'minecraft:amplified', name: 'Amplified' },
];
export const DASHBOARDS: Dashboard[] = ['off', 'bottom', 'top'];

/** A player on the whitelist, and an op if `op`. */
export interface Player {
	name: string;
	/** The account's UUID with dashes, from Mojang; null until it's looked up, or with no account. */
	id: string | null;
	op: boolean;
	/** The skin's address on Mojang's texture server, for the face; not written anywhere. */
	skin?: string | null;
	/** Looked up, and no account has the name. */
	missing?: boolean;
	/** Looked up, and the lookup failed, so it isn't tried again. */
	failed?: boolean;
}

/** The UUID a player has on this server: the account's in online mode, or the one an
 *  offline-mode server makes from the name. Null for a name with no account, in online mode. */
export const idOn = (s: Setup, p: Player) => (s.onlineMode ? p.id : offlineId(p.name));

export interface Setup {
	/** The folder the archive unpacks to, and the archive's name. Empty is calcite. */
	name: string;
	motd: [string, string];
	gamemode: GameMode;
	forceGamemode: boolean;
	difficulty: Difficulty;
	hardcore: boolean;
	maxPlayers: number;
	allowFlight: boolean;
	spawnProtection: number;
	levelName: string;
	seed: string;
	worldType: WorldType;
	structures: boolean;
	viewDistance: number;
	simulationDistance: number;
	onlineMode: boolean;
	whitelist: boolean;
	players: Player[];
	port: number;
	pauseWhenEmpty: number;
	dashboard: Dashboard;
	loginThrottle: number;
}

/** Vanilla's defaults, which a server started without any of these files would have. */
export const DEFAULTS: Setup = {
	name: '',
	motd: ['A Minecraft Server', ''],
	gamemode: 'survival',
	forceGamemode: false,
	difficulty: 'easy',
	hardcore: false,
	maxPlayers: 20,
	allowFlight: false,
	spawnProtection: 16,
	levelName: 'world',
	seed: '',
	worldType: 'minecraft:normal',
	structures: true,
	viewDistance: 10,
	simulationDistance: 10,
	onlineMode: true,
	whitelist: true,
	players: [],
	port: 25565,
	pauseWhenEmpty: 60,
	dashboard: 'off',
	loginThrottle: 0,
};

/** What a preset sets: how the game plays and who gets in. It leaves the name, the MOTD, the
 *  icon, the players and the port as they are, since those are the server's own. */
const OWN = ['name', 'motd', 'players', 'port', 'levelName', 'seed'] as const;
type Rules = Omit<Setup, (typeof OWN)[number]>;
const RULES = (s: Setup): Rules => {
	const r: Partial<Setup> = { ...s };
	for (const k of OWN) delete r[k];
	return r as Rules;
};

export interface Preset {
	id: string;
	name: string;
	about: string;
	rules: Rules;
}

const base = RULES(DEFAULTS);
export const PRESETS: Preset[] = [
	{ id: 'vanilla', name: 'Vanilla', about: "Vanilla's own defaults: survival on easy, 20 players, whitelist on.", rules: base },
	{
		id: 'friends',
		name: 'Friends',
		about: 'Survival on normal for a few people you know. Whitelist on, and no spawn protection to argue over.',
		rules: { ...base, difficulty: 'normal', maxPlayers: 10, spawnProtection: 0, viewDistance: 12 },
	},
	{
		id: 'creative',
		name: 'Creative',
		about: 'A flat, peaceful world to build in. Everyone joins in creative and can fly.',
		rules: { ...base, gamemode: 'creative', forceGamemode: true, difficulty: 'peaceful', worldType: 'minecraft:flat', structures: false, allowFlight: true, spawnProtection: 0 },
	},
	{
		id: 'hardcore',
		name: 'Hardcore',
		about: 'One life each, on hard. Whitelist on.',
		rules: { ...base, hardcore: true, difficulty: 'hard', maxPlayers: 10, spawnProtection: 0 },
	},
	{
		id: 'public',
		name: 'Public',
		about: 'Open to anyone with an account. 50 players, a shorter view, spawn protected and logins throttled.',
		rules: { ...base, difficulty: 'normal', whitelist: false, maxPlayers: 50, viewDistance: 8, simulationDistance: 6, loginThrottle: 4000 },
	},
	{
		id: 'test',
		name: 'Flat test',
		about: 'A flat creative world for trying things on your own machine: offline, no whitelist, never paused, with the dashboard on.',
		rules: { ...base, gamemode: 'creative', forceGamemode: true, difficulty: 'peaceful', worldType: 'minecraft:flat', structures: false, allowFlight: true, spawnProtection: 0, onlineMode: false, whitelist: false, maxPlayers: 5, pauseWhenEmpty: 0, dashboard: 'bottom' },
	},
];

export const applyPreset = (s: Setup, p: Preset): Setup => ({ ...s, ...p.rules });

/** The preset the setup is exactly, or null once anything a preset sets has changed. */
export function presetOf(s: Setup): string | null {
	const r = JSON.stringify(RULES(s));
	return PRESETS.find((p) => JSON.stringify({ ...RULES(DEFAULTS), ...p.rules }) === r)?.id ?? null;
}

/* ---- names ---------------------------------------------------------------------------------- */

/** The server's name as a folder: lower case, dashes for spaces, nothing a file system minds. */
export function slug(name: string) {
	const s = name
		.normalize('NFKD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9._-]+/g, '-')
		.replace(/^[-.]+|[-.]+$/g, '')
		.slice(0, 40);
	return s || 'calcite';
}

export const VALID_NAME = /^[A-Za-z0-9_]{1,16}$/;

/** A UUID's 32 hex digits, with vanilla's dashes. */
export const dashed = (hex: string) => hex.replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/, '$1-$2-$3-$4-$5').toLowerCase();

/** The UUID an offline-mode server gives a name, as vanilla's UUIDUtil.createOfflinePlayerUUID makes it. */
export function offlineId(name: string) {
	const h = md5(new TextEncoder().encode(`OfflinePlayer:${name}`));
	h[6] = (h[6] & 0x0f) | 0x30;
	h[8] = (h[8] & 0x3f) | 0x80;
	return dashed([...h].map((b) => b.toString(16).padStart(2, '0')).join(''));
}

/* ---- the MOTD ------------------------------------------------------------------------------- */

// Written with & and a code, as most panels take it; the file gets the section sign vanilla reads.
export const COLOURS: Record<string, { name: string; hex: string }> = {
	'0': { name: 'black', hex: '#000000' },
	'1': { name: 'dark blue', hex: '#0000AA' },
	'2': { name: 'dark green', hex: '#00AA00' },
	'3': { name: 'dark aqua', hex: '#00AAAA' },
	'4': { name: 'dark red', hex: '#AA0000' },
	'5': { name: 'dark purple', hex: '#AA00AA' },
	'6': { name: 'gold', hex: '#FFAA00' },
	'7': { name: 'grey', hex: '#AAAAAA' },
	'8': { name: 'dark grey', hex: '#555555' },
	'9': { name: 'blue', hex: '#5555FF' },
	a: { name: 'green', hex: '#55FF55' },
	b: { name: 'aqua', hex: '#55FFFF' },
	c: { name: 'red', hex: '#FF5555' },
	d: { name: 'light purple', hex: '#FF55FF' },
	e: { name: 'yellow', hex: '#FFFF55' },
	f: { name: 'white', hex: '#FFFFFF' },
};
export const FORMATS: Record<string, string> = { l: 'bold', o: 'italic', n: 'underline', m: 'strikethrough', k: 'obfuscated', r: 'reset' };

export interface Run {
	text: string;
	colour?: string;
	bold?: boolean;
	italic?: boolean;
	underline?: boolean;
	strike?: boolean;
	obfuscated?: boolean;
}

/** A line of the MOTD as runs of text, each with its colour and formats. A colour code resets the
 *  formats before it, as the game's does. */
export function runs(line: string): Run[] {
	const out: Run[] = [];
	let cur: Run = { text: '' };
	const parts = line.split(/[&§]([0-9a-fk-or])/i);
	parts.forEach((p, i) => {
		if (i % 2 === 0) {
			if (p) cur.text += p;
			return;
		}
		if (cur.text) out.push(cur);
		const c = p.toLowerCase();
		const keep = { ...cur, text: '' };
		if (COLOURS[c]) cur = { text: '', colour: COLOURS[c].hex };
		else if (c === 'r') cur = { text: '' };
		else cur = { ...keep, [{ l: 'bold', o: 'italic', n: 'underline', m: 'strike', k: 'obfuscated' }[c] as string]: true };
	});
	if (cur.text) out.push(cur);
	return out;
}

/** The MOTD as it reads, without codes, to count what fits. */
export const plainMotd = (line: string) => line.replace(/[&§][0-9a-fk-or]/gi, '');

/* ---- the files ------------------------------------------------------------------------------ */

// A .properties value: vanilla reads the file as UTF-8 and falls back to ISO-8859-1, so anything
// past ASCII, the section sign among it, is written as a \u escape, which either reads the same.
function value(v: string) {
	return v
		.replace(/\\/g, '\\\\')
		.replace(/\n/g, '\\n')
		.replace(/^ /, '\\ ')
		.replace(/[^\x20-\x7e]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0'));
}

/** server.properties with the keys the setup decides, sorted as vanilla writes them. Calcite adds
 *  every other key, at its default, when it first starts. */
export function serverProperties(s: Setup): string {
	const motd = s.motd
		.map((l) => l.replace(/&([0-9a-fk-or])/gi, '§$1'))
		.filter((l, i) => i === 0 || l)
		.join('\n');
	const keys: Record<string, string | number | boolean> = {
		'allow-flight': s.allowFlight,
		difficulty: s.hardcore ? 'hard' : s.difficulty,
		'force-gamemode': s.forceGamemode,
		gamemode: s.gamemode,
		'generate-structures': s.structures,
		hardcore: s.hardcore,
		'level-name': s.levelName || 'world',
		'level-seed': s.seed,
		'level-type': s.worldType,
		'max-players': s.maxPlayers,
		motd,
		'online-mode': s.onlineMode,
		'pause-when-empty-seconds': s.pauseWhenEmpty,
		'server-port': s.port,
		'simulation-distance': s.simulationDistance,
		'spawn-protection': s.spawnProtection,
		'view-distance': s.viewDistance,
		'white-list': s.whitelist,
	};
	const lines = Object.keys(keys)
		.sort()
		.map((k) => `${k}=${value(String(keys[k]))}`);
	return ['#Minecraft server properties', '#Set up on calcitemc.com/download', '#Calcite adds the other settings, at their defaults, on its first start', ...lines].join('\n') + '\n';
}

/** The players with a UUID on this server, each with it. */
const listed = (s: Setup) => s.players.flatMap((p) => (idOn(s, p) ? [{ ...p, uuid: idOn(s, p)! }] : []));

/** whitelist.json, as vanilla writes it: everyone listed, ops too. */
export const whitelistJson = (s: Setup) => JSON.stringify(listed(s).map((p) => ({ uuid: p.uuid, name: p.name })), null, 2) + '\n';

/** ops.json: the players marked op, at level 4, as /op makes them. */
export const opsJson = (s: Setup) =>
	JSON.stringify(
		listed(s)
			.filter((p) => p.op)
			.map((p) => ({ uuid: p.uuid, name: p.name, level: 4, bypassesPlayerLimit: false })),
		null,
		2,
	) + '\n';

/** calcite.properties, Calcite's own defaults (`defaults`, from config.calx) with the setup's
 *  values in place, or null when they're all still the defaults. */
export function calciteProperties(s: Setup, defaults: string): string | null {
	if (s.dashboard === 'off' && s.loginThrottle === 0) return null;
	return defaults.replace(/^console-dashboard=.*$/m, `console-dashboard=${s.dashboard}`).replace(/^login-throttle=.*$/m, `login-throttle=${s.loginThrottle}`);
}

/** Every file the setup ships, by name, as text or as bytes (the icon). */
export function files(s: Setup, defaults: string, icon: Uint8Array | null): { name: string; data: string | Uint8Array }[] {
	const out: { name: string; data: string | Uint8Array }[] = [{ name: 'server.properties', data: serverProperties(s) }];
	const l = listed(s);
	if (l.length) out.push({ name: 'whitelist.json', data: whitelistJson(s) });
	if (l.some((p) => p.op)) out.push({ name: 'ops.json', data: opsJson(s) });
	const c = calciteProperties(s, defaults);
	if (c) out.push({ name: 'calcite.properties', data: c });
	if (icon) out.push({ name: 'server-icon.png', data: icon });
	return out;
}

/* ---- the link ------------------------------------------------------------------------------- */

// A setup as a link: what differs from the defaults, as JSON in the address's fragment, which
// browsers never send to the server. The icon stays out, since it's too big for an address.
export function encode(s: Setup): string {
	const diff: Record<string, unknown> = {};
	for (const k of Object.keys(DEFAULTS) as (keyof Setup)[]) {
		const v = k === 'players' ? s.players.map((p) => [p.name, p.id ?? '', p.op ? 1 : 0]) : s[k];
		if (JSON.stringify(v) !== JSON.stringify(k === 'players' ? [] : DEFAULTS[k])) diff[k] = v;
	}
	const bytes = new TextEncoder().encode(JSON.stringify(diff));
	let bin = '';
	bytes.forEach((b) => (bin += String.fromCharCode(b)));
	return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** A setup from a link, each value checked against its default's type and range. */
export function decode(text: string): Setup | null {
	try {
		const bin = atob(text.replace(/-/g, '+').replace(/_/g, '/'));
		const raw = JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)))) as Record<string, unknown>;
		const s: Setup = { ...DEFAULTS, motd: [...DEFAULTS.motd], players: [] };
		const pick = <T>(v: unknown, ok: (v: unknown) => boolean, d: T): T => (ok(v) ? (v as T) : d);
		const str = (n: number) => (v: unknown) => typeof v === 'string' && v.length <= n;
		const int = (a: number, b: number) => (v: unknown) => Number.isInteger(v) && (v as number) >= a && (v as number) <= b;
		const bool = (v: unknown) => typeof v === 'boolean';
		const one = <T>(list: readonly T[]) => (v: unknown) => list.includes(v as T);
		s.name = pick(raw.name, str(60), s.name);
		if (Array.isArray(raw.motd) && raw.motd.length === 2 && raw.motd.every(str(120))) s.motd = [raw.motd[0], raw.motd[1]];
		s.gamemode = pick(raw.gamemode, one(MODES), s.gamemode);
		s.forceGamemode = pick(raw.forceGamemode, bool, s.forceGamemode);
		s.difficulty = pick(raw.difficulty, one(DIFFICULTIES), s.difficulty);
		s.hardcore = pick(raw.hardcore, bool, s.hardcore);
		s.maxPlayers = pick(raw.maxPlayers, int(1, 1000), s.maxPlayers);
		s.allowFlight = pick(raw.allowFlight, bool, s.allowFlight);
		s.spawnProtection = pick(raw.spawnProtection, int(0, 256), s.spawnProtection);
		s.levelName = pick(raw.levelName, str(60), s.levelName);
		s.seed = pick(raw.seed, str(60), s.seed);
		s.worldType = pick(raw.worldType, one(WORLDS.map((w) => w.id)), s.worldType);
		s.structures = pick(raw.structures, bool, s.structures);
		s.viewDistance = pick(raw.viewDistance, int(2, 32), s.viewDistance);
		s.simulationDistance = pick(raw.simulationDistance, int(2, 32), s.simulationDistance);
		s.onlineMode = pick(raw.onlineMode, bool, s.onlineMode);
		s.whitelist = pick(raw.whitelist, bool, s.whitelist);
		s.port = pick(raw.port, int(1, 65535), s.port);
		s.pauseWhenEmpty = pick(raw.pauseWhenEmpty, int(0, 3600), s.pauseWhenEmpty);
		s.dashboard = pick(raw.dashboard, one(DASHBOARDS), s.dashboard);
		s.loginThrottle = pick(raw.loginThrottle, int(0, 60000), s.loginThrottle);
		if (Array.isArray(raw.players))
			s.players = raw.players
				.filter((p): p is [string, string, number] => Array.isArray(p) && VALID_NAME.test(String(p[0])) && /^(?:[0-9a-f-]{36})?$/.test(String(p[1])))
				.slice(0, 200)
				.map(([name, id, op]) => ({ name, id: id || null, op: !!op }));
		return s;
	} catch {
		return null;
	}
}
