// A Markdown reader for the repo's docs, which keep to a small, plain subset: headings, paragraphs,
// lists, tables, fenced code, quotes and the inline marks. It gives blocks and inline runs that the
// Markdown component draws with the site's own components. HTML comments are directives: a comment
// alone on its line, such as <!-- differences -->, is a block the page fills in.

export type Inline =
	| { t: 'text'; v: string }
	| { t: 'code'; v: string }
	| { t: 'strong'; c: Inline[] }
	| { t: 'em'; c: Inline[] }
	| { t: 'link'; href: string; c: Inline[] };

export type Block =
	| { t: 'h'; level: number; c: Inline[]; id: string }
	| { t: 'p'; c: Inline[] }
	| { t: 'list'; ordered: boolean; items: Block[][] }
	| { t: 'table'; head: Inline[][]; align: ('l' | 'r')[]; rows: Inline[][][] }
	| { t: 'code'; lang: string; v: string }
	| { t: 'quote'; c: Block[] }
	| { t: 'directive'; name: string };

export function slugify(text: string) {
	return text
		.toLowerCase()
		.replace(/[`*_[\]()]/g, '')
		.replace(/[^\p{L}\p{N}\s-]/gu, '')
		.trim()
		.replace(/\s+/g, '-');
}

export const plain = (c: Inline[]): string => c.map((i) => (i.t === 'text' || i.t === 'code' ? i.v : plain(i.c))).join('');

export function inline(s: string): Inline[] {
	const out: Inline[] = [];
	let text = '';
	const flush = () => {
		if (text) out.push({ t: 'text', v: text });
		text = '';
	};
	for (let i = 0; i < s.length; ) {
		const ch = s[i];
		if (ch === '\\' && i + 1 < s.length && /[\\`*_[\]()#|<>-]/.test(s[i + 1])) {
			text += s[i + 1];
			i += 2;
			continue;
		}
		if (ch === '`') {
			let n = 1;
			while (s[i + n] === '`') n++;
			const fence = '`'.repeat(n), end = s.indexOf(fence, i + n);
			if (end > 0) {
				flush();
				out.push({ t: 'code', v: s.slice(i + n, end).replace(/^ (.*) $/, '$1') });
				i = end + n;
				continue;
			}
		}
		if (s.startsWith('**', i)) {
			const end = s.indexOf('**', i + 2);
			if (end > i + 2) {
				flush();
				out.push({ t: 'strong', c: inline(s.slice(i + 2, end)) });
				i = end + 2;
				continue;
			}
		}
		if (ch === '*' && s[i + 1] !== ' ' && s[i + 1] !== '*') {
			const end = s.indexOf('*', i + 1);
			if (end > i + 1 && s[end - 1] !== ' ') {
				flush();
				out.push({ t: 'em', c: inline(s.slice(i + 1, end)) });
				i = end + 1;
				continue;
			}
		}
		if (ch === '[') {
			// the link text may hold brackets of its own, as in [`x[0]`](...)
			let depth = 0, j = i;
			for (; j < s.length; j++) {
				if (s[j] === '`') j = Math.max(j, s.indexOf('`', j + 1));
				if (s[j] === '[') depth++;
				else if (s[j] === ']' && --depth === 0) break;
			}
			if (s[j + 1] === '(') {
				const close = s.indexOf(')', j + 2);
				if (close > 0) {
					flush();
					out.push({ t: 'link', href: s.slice(j + 2, close).trim(), c: inline(s.slice(i + 1, j)) });
					i = close + 1;
					continue;
				}
			}
		}
		if (ch === '<' && /^<https?:\/\/[^>\s]+>/.test(s.slice(i))) {
			const end = s.indexOf('>', i);
			flush();
			const href = s.slice(i + 1, end);
			out.push({ t: 'link', href, c: [{ t: 'text', v: href }] });
			i = end + 1;
			continue;
		}
		text += ch;
		i++;
	}
	flush();
	return out;
}

const cells = (line: string) =>
	line
		.trim()
		.replace(/^\||\|$/g, '')
		.split(/(?<!\\)\|/)
		.map((c) => c.trim().replace(/\\\|/g, '|'));

const START = /^(#{1,6} |```|\s*[-*] |\s*\d+\. |> |\||<!--)/;

export function parse(md: string): Block[] {
	const lines = md.replace(/\r\n/g, '\n').split('\n');
	const blocks: Block[] = [];
	let i = 0;
	while (i < lines.length) {
		const line = lines[i];
		if (!line.trim()) {
			i++;
			continue;
		}
		const dir = /^<!--\s*([\w.-]+)\s*-->$/.exec(line.trim());
		if (dir) {
			blocks.push({ t: 'directive', name: dir[1] });
			i++;
			continue;
		}
		if (line.trim().startsWith('<!--')) {
			while (i < lines.length && !lines[i].includes('-->')) i++;
			i++;
			continue;
		}
		const fence = /^```\s*([\w-]*)/.exec(line);
		if (fence) {
			const body: string[] = [];
			i++;
			while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++]);
			i++;
			blocks.push({ t: 'code', lang: fence[1] || 'text', v: body.join('\n') });
			continue;
		}
		const h = /^(#{1,6}) (.+)$/.exec(line);
		if (h) {
			const c = inline(h[2].trim());
			blocks.push({ t: 'h', level: h[1].length, c, id: slugify(plain(c)) });
			i++;
			continue;
		}
		if (line.startsWith('|') && /^\|?\s*:?-{3,}/.test(lines[i + 1] ?? '')) {
			const head = cells(line), spec = cells(lines[i + 1]);
			const align = spec.map((s) => (s.endsWith(':') && !s.startsWith(':') ? 'r' : 'l')) as ('l' | 'r')[];
			const rows: Inline[][][] = [];
			i += 2;
			while (i < lines.length && lines[i].startsWith('|')) rows.push(cells(lines[i++]).map(inline));
			blocks.push({ t: 'table', head: head.map(inline), align, rows });
			continue;
		}
		if (line.startsWith('> ')) {
			const body: string[] = [];
			while (i < lines.length && lines[i].startsWith('>')) body.push(lines[i++].replace(/^> ?/, ''));
			blocks.push({ t: 'quote', c: parse(body.join('\n')) });
			continue;
		}
		const item = /^([-*]|\d+\.) /.exec(line);
		if (item) {
			const ordered = /\d/.test(item[1]);
			const items: Block[][] = [];
			while (i < lines.length) {
				const m = /^([-*]|\d+\.) (.*)$/.exec(lines[i]);
				if (!m || /\d/.test(m[1]) !== ordered) break;
				const indent = m[1].length + 1, body = [m[2]];
				i++;
				// the item goes on while lines are indented under it, blank lines between them included
				while (i < lines.length) {
					if (!lines[i].trim()) {
						const next = lines.slice(i).find((l) => l.trim());
						if (next && /^\s{2,}/.test(next)) {
							body.push('');
							i++;
							continue;
						}
						break;
					}
					if (/^\s{2,}/.test(lines[i])) body.push(lines[i++].replace(new RegExp(`^ {0,${Math.max(indent, 2)}}`), ''));
					else if (!START.test(lines[i]) && body[body.length - 1] !== '') body.push(lines[i++]);
					else break;
				}
				items.push(parse(body.join('\n')));
				while (i < lines.length && !lines[i].trim() && /^([-*]|\d+\.) /.test(lines.slice(i).find((l) => l.trim()) ?? '')) i++;
			}
			blocks.push({ t: 'list', ordered, items });
			continue;
		}
		const para: string[] = [];
		while (i < lines.length && lines[i].trim() && !(para.length && START.test(lines[i]))) para.push(lines[i++].trim());
		blocks.push({ t: 'p', c: inline(para.join(' ')) });
	}
	return blocks;
}

/** The h2 and h3 headings, for a page's table of contents. */
export const headings = (blocks: Block[]) => blocks.filter((b): b is Extract<Block, { t: 'h' }> => b.t === 'h' && (b.level === 2 || b.level === 3));
