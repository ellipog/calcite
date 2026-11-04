// What the public site says about itself, in one place.

const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL;

export const SITE = {
	name: 'calcite',
	title: 'calcite · a multithreaded Minecraft server written in Calx',
	description: 'Calcite is a Minecraft: Java Edition server written from scratch in Calx that runs the world on every core of the machine.',
	/** Where the site lives: SITE_URL when it's set, else Vercel's production address, else here. */
	url: (process.env.SITE_URL ?? (vercel ? `https://${vercel}` : 'http://localhost:3000')).replace(/\/$/, ''),
	github: 'https://github.com/ellipog/calcite',
	blob: 'https://github.com/ellipog/calcite/blob/main/',
	tree: 'https://github.com/ellipog/calcite/tree/main/',
	acta: 'https://acta.aaenz.no/p/aaen-studios/calcite',
	calx: 'https://calxlang.com',
	/** Aaen Studios, which makes Calcite and Calx. */
	studio: 'https://aaenz.no',
	calxInstall: 'https://calxlang.com/guide/install/',
	minecraft: '26.3',
} as const;

export const NAV = [
	{ href: '/docs', label: 'Docs' },
	{ href: '/benchmarks', label: 'Benchmarks' },
	{ href: '/plugins', label: 'Plugins' },
	{ href: '/roadmap', label: 'Roadmap' },
] as const;

/** Minecraft's usage guidelines ask for this on anything made for the game that isn't Mojang's. */
export const NOT_MOJANG = 'Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.';
