// What the public site says about itself, in one place.

export const SITE = {
	name: 'calcite',
	title: 'calcite · a multithreaded Minecraft server written in Calx',
	description: 'Calcite is a Minecraft: Java Edition server written from scratch in Calx that runs the world on every core of the machine.',
	/** Where the site lives. Canonical links, the sitemap and link previews name it from any build,
	 *  so a preview deploy or a local one never passes for the site. */
	url: 'https://calcitemc.com',
	github: 'https://github.com/ellipog/calcite',
	/** The nightly build's files, whose addresses stay the same as each night's replaces the last
	 *  (.github/workflows/nightly.yml). */
	nightly: 'https://github.com/ellipog/calcite/releases/download/nightly/',
	nightlyRelease: 'https://github.com/ellipog/calcite/releases/tag/nightly',
	blob: 'https://github.com/ellipog/calcite/blob/main/',
	tree: 'https://github.com/ellipog/calcite/tree/main/',
	acta: 'https://acta.aaenz.no/p/aaen-studios/calcite',
	calx: 'https://calxlang.com',
	/** Aaen Studios, which makes Calcite and Calx. */
	studio: 'https://aaenz.no',
	calxInstall: 'https://calxlang.com/guide/install/',
	minecraft: '26.3',
	/** The home page's lead, which the README's banner (scripts/banner.tsx) sets beside the name too. */
	lead: "A Minecraft server that runs the world on every core of the machine. It's written in Calx, and plugins can be written in Calx or in anything that builds to WASM.",
} as const;

export const NAV = [
	{ href: '/docs', label: 'Docs' },
	{ href: '/benchmarks', label: 'Benchmarks' },
	{ href: '/plugins', label: 'Plugins' },
	{ href: '/roadmap', label: 'Roadmap' },
	{ href: '/download', label: 'Download' },
] as const;

/** Minecraft's usage guidelines ask for this on anything made for the game that isn't Mojang's. */
export const NOT_MOJANG = 'Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.';
