// The site's own pages, as search and link previews see them: each one's title, what it's about
// in under 160 characters, so a search result shows all of it, and its address. The page and its
// card (opengraph-image.tsx beside it) both read them from here.

export const PAGES = {
	benchmarks: {
		path: '/benchmarks',
		title: 'Benchmarks',
		description: "Calcite with 100 players and Mojang's client, generating worlds beside vanilla, Paper and C2ME and lighting them beside vanilla, each number with its source.",
	},
	plugins: {
		path: '/plugins',
		title: 'Plugins',
		description: "Calcite's plugin API: native Calx plugins at full speed, WASM plugins in a sandbox, where a plugin's code runs, and the five samples it was designed with.",
	},
	download: {
		path: '/download',
		title: 'Download',
		description: "Calcite's nightly builds for Windows and Linux: the newest commit whose tests passed, built each night, with how to start one and what it does first.",
	},
	roadmap: {
		path: '/roadmap',
		title: 'Roadmap',
		description: "Calcite's plan in ten phases, each with a gate it passes before the next starts: which have passed, what's in progress, and what's to come.",
	},
} as const;
