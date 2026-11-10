// Code highlighting for the site's code blocks, in the text blues (globals.css). A small tokenizer
// a line at a time for the languages the site shows: Calx, shell, PowerShell, .properties, TOML
// and JSON. None of them has a token that spans lines as the site writes them, so no state carries
// from one line to the next. Anything else, and `text`, comes back as plain lines.

/** What a run of code is, which picks its blue: see `.hl-*` in globals.css. */
export type Kind = 'plain' | 'kw' | 'key' | 'type' | 'fn' | 'str' | 'num' | 'attr' | 'var' | 'punct' | 'com';
export type Token = [Kind, string];

// Calx's keywords, from CALX_KEYWORDS in calx/compiler/src/lexer.h, and `region` from the plugin
// API's draft syntax. true, false and none are literals, drawn as numbers are.
const CALX_KW = new Set(
	'and break checkout const continue dyn else enum extern fail fn for if impl import in interface let loop match module mut not or own parallel pub return self struct try type unsafe var while region'.split(' '),
);
const CALX_LIT = new Set(['true', 'false', 'none']);
const CALX_PRIM = /^(?:[iuf](?:8|16|32|64)|bool|char|str|usize|isize|void)$/;

type Rule = [RegExp, Kind | ((m: RegExpExecArray, line: string, at: number) => Kind)];

// Each rule is tried in order at each place; the first that matches there takes it.
function run(line: string, rules: Rule[]): Token[] {
	const out: Token[] = [];
	const push = (k: Kind, s: string) => {
		if (!s) return;
		const last = out[out.length - 1];
		if (last && last[0] === k) last[1] += s;
		else out.push([k, s]);
	};
	let i = 0;
	outer: while (i < line.length) {
		for (const [re, kind] of rules) {
			re.lastIndex = i;
			const m = re.exec(line);
			if (m && m.index === i && m[0].length > 0) {
				push(typeof kind === 'function' ? kind(m, line, i) : kind, m[0]);
				i += m[0].length;
				continue outer;
			}
		}
		push('plain', line[i]);
		i++;
	}
	return out;
}

// what comes after position `at` on the line, past any spaces
const next = (line: string, at: number) => line.slice(at).trimStart()[0];
const prevWord = (line: string, at: number) => /(\w+)\s*$/.exec(line.slice(0, at))?.[1];

const CALX: Rule[] = [
	[/\/\/.*/y, 'com'],
	[/[a-z]?"(?:[^"\\]|\\.)*"?/y, 'str'],
	[/'(?:[^'\\]|\\.)'/y, 'str'],
	[/@[A-Za-z_]\w*/y, 'attr'],
	[/0[xX][\da-fA-F_]+\w*|0[bB][01_]+\w*|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?(?:[iuf](?:8|16|32|64))?/y, 'num'],
	[
		/[A-Za-z_]\w*/y,
		(m, line, at) => {
			const w = m[0];
			if (CALX_LIT.has(w)) return 'num';
			if (CALX_KW.has(w)) return 'kw';
			if (CALX_PRIM.test(w)) return 'type';
			if (/^[A-Z][A-Z\d_]+$/.test(w)) return 'num';
			if (/^[A-Z]/.test(w)) return 'type';
			if (prevWord(line, at) === 'fn' || next(line, at + w.length) === '(') return 'fn';
			return 'plain';
		},
	],
	[/[{}()[\],.:;?=<>+\-*/%!&|^~]+/y, 'punct'],
];

const SH: Rule[] = [
	[/(?:^|(?<=\s))#.*/y, 'com'],
	[/'[^']*'?/y, 'str'],
	[/"(?:[^"\\]|\\.)*"?/y, 'str'],
	[/\$\{[^}]*\}|\$\w+/y, 'var'],
	[/(?<=^|\s)--?[A-Za-z][\w-]*/y, 'attr'],
	[/(?<=\s|^)\d+(?:\.\d+)*(?=\s|$)/y, 'num'],
	// the command: the first word of the line, or the first after a pipe, && or ;
	[/(?<=^\s*|[|;&]\s*)(?:\.{0,2}\/)?[\w.\\/-]+/y, 'fn'],
	[/[|&;<>]+/y, 'punct'],
];

const PS: Rule[] = [
	[/(?:^|(?<=\s))#.*/y, 'com'],
	[/'[^']*'?/y, 'str'],
	[/"(?:[^"`]|`.)*"?/y, 'str'],
	[/\$[\w:]+/y, 'var'],
	[/(?<=^|\s)-[A-Za-z][\w]*/y, 'attr'],
	[/(?<=\s|^)\d+(?:\.\d+)*(?=\s|$)/y, 'num'],
	[/(?<=^\s*|[|;]\s*)(?:\.{0,2}[\\/])?[\w.\\/-]+/y, 'fn'],
	[/[|;]+/y, 'punct'],
];

// a value after = or :, as these files write one
const value = (v: string): Kind => (/^(?:true|false|null|-?\d[\d_.]*(?:e[+-]?\d+)?)$/i.test(v.trim()) ? 'num' : 'str');

function properties(line: string): Token[] {
	if (/^\s*[#!]/.test(line)) return [['com', line]];
	const m = /^(\s*)([^=:\s]+)(\s*[=:]\s*)(.*)$/.exec(line);
	if (!m) return [['plain', line]];
	return ([['plain', m[1]], ['key', m[2]], ['punct', m[3]], [value(m[4]), m[4]]] as Token[]).filter((t) => t[1]);
}

const TOML: Rule[] = [
	[/#.*/y, 'com'],
	[/(?<=^\s*)\[\[?[^\]]*\]\]?/y, 'type'],
	[/(?<=^\s*)[\w.-]+(?=\s*=)/y, 'key'],
	[/"(?:[^"\\]|\\.)*"?|'[^']*'?/y, 'str'],
	[/\b(?:true|false)\b|[+-]?\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?/y, 'num'],
	[/[=[\]{},]/y, 'punct'],
];

const JSON_: Rule[] = [
	[/"(?:[^"\\]|\\.)*"(?=\s*:)/y, 'key'],
	[/"(?:[^"\\]|\\.)*"?/y, 'str'],
	[/\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y, 'num'],
	[/[{}[\],:]/y, 'punct'],
];

const BY_LANG: Record<string, (line: string) => Token[]> = {
	calx: (l) => run(l, CALX),
	sh: (l) => run(l, SH),
	bash: (l) => run(l, SH),
	powershell: (l) => run(l, PS),
	properties,
	toml: (l) => run(l, TOML),
	json: (l) => run(l, JSON_),
};

/** Whether `lang` is one the site highlights. */
export const highlights = (lang?: string) => lang != null && lang in BY_LANG;

/** The code's lines as runs of tokens. A language the site doesn't highlight is one plain run a line. */
export function highlight(code: string, lang?: string): Token[][] {
	const f = lang ? BY_LANG[lang] : undefined;
	return code.split('\n').map((l) => (f ? f(l) : l ? [['plain', l] as Token] : []));
}
