// What the site reads from the rest of the repo as it builds: the guide's Markdown, the plan's
// phases, the deliberate differences, the settings calcite.properties is written with, and the
// sample plugins. Server components only: it reads files.

import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import { join, posix } from 'node:path';

/** The repo, one up from site/. The build checks out the whole repo, so it's there as it builds. */
export const ROOT = join(process.cwd(), '..');
export const read = (path: string) => readFileSync(join(ROOT, path), 'utf8').replace(/\r\n/g, '\n');

export interface Doc {
	slug: string;
	path: string;
	group: string;
	title: string;
	description: string;
	body: string;
}

/** Front matter's plain `key: value` lines, and the Markdown after it. */
export function frontMatter(text: string): { meta: Record<string, string>; body: string } {
	const m = /^---\n([\s\S]*?)\n---\n/.exec(text);
	if (!m) return { meta: {}, body: text };
	const meta: Record<string, string> = {};
	for (const line of m[1].split('\n')) {
		const kv = /^([\w-]+):\s*(.*)$/.exec(line);
		if (kv && kv[2]) meta[kv[1]] = kv[2].replace(/^["']|["']$/g, '');
	}
	return { meta, body: text.slice(m[0].length) };
}

// A page without front matter, such as docs/pregen.md, takes its title from its heading and its
// description from its first paragraph.
function doc(slug: string, path: string, group: string): Doc {
	const { meta, body } = frontMatter(read(path));
	const h1 = /^# (.+)$/m.exec(body)?.[1] ?? slug;
	if (meta.description) return { slug, path, group, title: meta.title ?? h1, description: meta.description, body };
	// the first paragraph becomes the page's lead, so the body goes on from after it
	const rest = body.replace(/^# .+$/m, '').trim(), cut = rest.indexOf('\n\n');
	const first = (cut < 0 ? rest : rest.slice(0, cut)).replace(/[`*]/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\s+/g, ' ');
	return { slug, path, group, title: meta.title ?? h1, description: first, body: `# ${h1}\n\n${cut < 0 ? '' : rest.slice(cut + 2)}` };
}

// When a file last changed, from git, as an ISO date. Nothing in a shallow clone, where a file
// untouched since the clone's oldest commit would look as new as that commit, or without git.
const changes = new Map<string, string | undefined>();
let shallow: boolean | undefined;
export function changed(path: string): string | undefined {
	if (changes.has(path)) return changes.get(path);
	let at: string | undefined;
	try {
		const git = (...args: string[]) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
		shallow ??= git('rev-parse', '--is-shallow-repository') !== 'false';
		if (!shallow) at = git('log', '-1', '--format=%cI', '--', path) || undefined;
	} catch {
		shallow = true;
	}
	changes.set(path, at);
	return at;
}

export const GUIDE = 'docs/guide/README.md';

/** The guide's pages, in the order its README lists them, then the host API sketch. */
export function docs(): Doc[] {
	const index = read(GUIDE);
	const list = index.slice(index.indexOf('## Pages'));
	const pages = [...list.matchAll(/^\d+\. \[[^\]]+\]\(([^)]+)\)$/gm)].map((m) => posix.join('docs/guide', m[1]));
	const slug = (p: string) => posix.basename(p, '.md');
	return [
		...pages.map((p) => doc(slug(p), p, 'Running a server')),
		doc('host-api', 'plugins/api/HOST_API.md', phases().phases.find((p) => p.n === 7)?.state === 'done' ? 'Plugins' : 'Plugins, in design'),
	];
}

export function guideIndex(): Doc {
	return doc('', GUIDE, '');
}

export interface Difference {
	slug: string;
	title: string;
	kind: string;
	body: string;
}

/** How many cases the rig has for a probe: every case in every file in cases/<probe>/. */
export function probeCases(probe: string): number {
	const dir = join(ROOT, 'cases', probe);
	let n = 0;
	for (const f of readdirSync(dir)) if (f.endsWith('.json')) n += (JSON.parse(readFileSync(join(dir, f), 'utf8')).cases ?? []).length;
	return n;
}

export function differences(): Difference[] {
	return readdirSync(join(ROOT, 'rig/differences'))
		.filter((f) => f.endsWith('.md') && f !== 'README.md')
		.sort()
		.map((f) => {
			const { meta, body } = frontMatter(read(`rig/differences/${f}`));
			return { slug: f.replace(/\.md$/, ''), title: meta.title ?? f, kind: meta.kind ?? '', body: body.replace(/^# .+\n+/m, '') };
		});
}

let DECISIONS: Map<string, string> | undefined;

/** The decision log's entries by id, as "Topic: the decision", for the pages that cite them. */
export function decisions(): Map<string, string> {
	if (!DECISIONS) {
		DECISIONS = new Map();
		for (const m of read('docs/decisions.md').matchAll(/^\| (D\d+) \| [^|]+ \| ([^|]+) \| ([^|]+) \|/gm)) DECISIONS.set(m[1], `${m[2].trim()}: ${m[3].trim()}`);
	}
	return DECISIONS;
}

export interface Setting {
	name: string;
	value: string;
	about: string;
}

/** calcite.properties as a new server writes it: each setting, its default and its comment, from
 *  `default_text` in src/server/config.calx, the code that writes the file. */
export function calciteSettings(): Setting[] {
	const src = read('src/server/config.calx');
	const body = src.slice(src.indexOf('pub fn default_text()'));
	const lines = [...body.matchAll(/out\.push_str\("((?:[^"\\]|\\.)*)"\)/g)].map((m) => m[1].replace(/\\n$/, '').replace(/\\"/g, '"'));
	const out: Setting[] = [];
	let about: string[] = [];
	for (const line of lines) {
		if (line.startsWith('#')) {
			const t = line.replace(/^#\s?/, '');
			if (/^[a-z-]+: /.test(t)) about = [t.replace(/^[a-z-]+: /, '')];
			else if (about.length && t) about.push(t);
			continue;
		}
		const kv = /^([a-z-]+)=(.*)$/.exec(line);
		if (kv) {
			const text = about.join(' ');
			out.push({ name: kv[1], value: kv[2], about: text.charAt(0).toUpperCase() + text.slice(1) });
			about = [];
		}
	}
	if (out.length < 5) throw new Error('src/server/config.calx: default_text moved; fix calciteSettings in site/src/lib/repo.ts');
	return out;
}

export interface Phase {
	n: number;
	builds: string;
	gate: string;
	state: 'done' | 'now' | 'next';
	tasks: { id: string; text: string }[];
	gates: { id: string; text: string; done: boolean }[];
}

/** The plan's ten phases, from docs/PLAN.md's table and sections, and which have passed their gates,
 *  from the README's status line. */
export function phases(): { phases: Phase[]; passed: number } {
	const plan = read('docs/PLAN.md');
	const passed = Number(/Phases 0 to (\d+) have passed their gates/.exec(read('README.md'))?.[1] ?? -1);
	const rows = [...plan.matchAll(/^\| (\d) \| ([^|]+) \| ([^|]+) \|$/gm)];
	return {
		passed,
		phases: rows.map((r) => {
			const n = +r[1];
			const at = plan.search(new RegExp(`^## Phase ${n}:`, 'm'));
			const next = plan.slice(at + 1).search(/^## /m);
			const sec = at < 0 ? '' : plan.slice(at, next < 0 ? undefined : at + 1 + next);
			const plain = (t: string) => t.replace(/\*\*/g, '').trim();
			return {
				n,
				builds: r[2].trim(),
				gate: r[3].trim(),
				state: n <= passed ? 'done' : n === passed + 1 ? 'now' : 'next',
				tasks: [...sec.matchAll(/^- \*\*(P\d+\.\d+)\*\* (.+)$/gm)].map((m) => ({ id: m[1], text: plain(m[2]) })),
				gates: [...sec.matchAll(/^- \[( |x)\] \*\*(G\d+\.\d+)\*\* (.+)$/gm)].map((m) => ({ id: m[2], text: plain(m[3]), done: m[1] === 'x' || n <= passed })),
			};
		}),
	};
}

/** A section of a Markdown file: from its heading to the next heading as high or higher, without
 *  the heading itself. */
export function section(md: string, heading: string): string {
	const lines = md.split('\n'), at = lines.findIndex((l) => l.trim() === heading);
	if (at < 0) throw new Error(`no "${heading}" heading to show on the site`);
	const level = /^#+/.exec(heading)![0].length, out: string[] = [];
	let fenced = false;
	for (const l of lines.slice(at + 1)) {
		if (l.startsWith('```')) fenced = !fenced;
		const h = /^(#+) /.exec(l);
		if (!fenced && h && h[1].length <= level) break;
		out.push(l);
	}
	return out.join('\n').trim();
}

export interface Sample {
	id: string;
	name: string;
	stresses: string;
	path: string;
	code: string;
}

/** The five sample plugins, from plugins/samples/README.md's table, with their code. */
export function samples(): Sample[] {
	const index = read('plugins/samples/README.md');
	return [...index.matchAll(/^\| ([^|]+) \| ([^|]+) \| \[`([^`]+)`\]\(([^)]+)\) \|$/gm)].map((m) => {
		const path = posix.join('plugins/samples', m[4]);
		return { id: posix.basename(m[4], '.calx'), name: m[1].trim(), stresses: m[2].trim(), path, code: read(path) };
	});
}
