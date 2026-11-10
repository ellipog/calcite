import { SITE } from '@/lib/site';

// The nightly archives, passed through from GitHub so the download page's setup can read them:
// GitHub's release downloads send no CORS headers, so a page can't fetch them itself. The page
// adds its files in the browser (lib/setup/archive.ts); nothing it sets comes here. Only the two
// archives' names are served, and a CDN may keep each for an hour, as the nightly changes daily.

const TYPES: Record<string, string> = {
	'calcite-windows-x64.zip': 'application/zip',
	'calcite-linux-x64.tar.gz': 'application/gzip',
};

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
	const { file } = await params;
	const type = TYPES[file];
	if (!type) return new Response('No such archive', { status: 404 });
	let r: Response;
	try {
		// not into Next's data cache, which isn't for files this size
		r = await fetch(SITE.nightly + file, { cache: 'no-store', signal: AbortSignal.timeout(60_000) });
	} catch {
		return new Response('GitHub didn’t answer', { status: 502 });
	}
	if (!r.ok || !r.body) return new Response(`GitHub said ${r.status}`, { status: 502 });
	const headers = new Headers({ 'Content-Type': type, 'Cache-Control': 'public, max-age=0, s-maxage=3600' });
	const length = r.headers.get('content-length');
	if (length) headers.set('Content-Length', length);
	return new Response(r.body, { headers });
}
