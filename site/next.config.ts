import type { NextConfig } from 'next';
import { PHASE_DEVELOPMENT_SERVER } from 'next/constants';

// The brand guide and the component sheet are internal: their files end in .internal.tsx, and
// that's only a page extension under `next dev`, or in a build made with CALCITE_INTERNAL=1. A
// production build doesn't see them at all, so they're not routes, not bundled, and 404.
export default function config(phase: string): NextConfig {
	const internal = phase === PHASE_DEVELOPMENT_SERVER || process.env.CALCITE_INTERNAL === '1';
	return {
		pageExtensions: internal ? ['internal.tsx', 'tsx', 'ts'] : ['tsx', 'ts'],
		reactStrictMode: true,
		poweredByHeader: false,
		// site/ is its own project inside the calcite repo; don't look further up for a lockfile
		turbopack: { root: __dirname },
	};
}
