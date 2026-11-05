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
		// The stylesheet stays a file. Next's experimental inlineCss saves the request the first paint
		// waits on, but puts the stylesheet in the HTML three times, once as <style> and twice in the
		// RSC payload: 104 KB of HTML became 328 KB, and on Lighthouse's mobile run the first paint
		// came 120 ms later and blocking time went from 24 to 123 ms.
		// Every page says not to be framed, sniffed or sent with full referrers, asks for no device
		// features, keeps HTTPS for the domain and its subdomains, and shares no window with another
		// site's. The content security policy holds what doesn't touch scripts: no plugins, no
		// <base>, forms only to this site and no framing. Restricting scripts would take a nonce for
		// Next's inline ones, which makes every page dynamic.
		async headers() {
			return [
				{
					source: '/:path*',
					headers: [
						{ key: 'X-Content-Type-Options', value: 'nosniff' },
						{ key: 'X-Frame-Options', value: 'DENY' },
						{ key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
						{ key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()' },
						{ key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains' },
						{ key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
						{ key: 'Content-Security-Policy', value: "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" },
					],
				},
			];
		},
		// site/ is its own project inside the calcite repo; don't look further up for a lockfile
		turbopack: { root: __dirname },
	};
}
