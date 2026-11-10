import { dashed, VALID_NAME } from '@/lib/setup/settings';

// A Minecraft account by name, for the download page's whitelist: its exact name, its UUID and
// its skin, for the face. Mojang's API sends no CORS headers, so the page asks here. Answers are
// kept a day, and a name with no account ten minutes, which also keeps under Mojang's rate limit.

interface Textures {
	textures?: { SKIN?: { url?: string } };
}

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
	const { name } = await params;
	if (!VALID_NAME.test(name)) return Response.json({ error: 'A name is 1 to 16 letters, digits or _.' }, { status: 400 });
	let r: Response;
	try {
		r = await fetch(`https://api.mojang.com/users/profiles/minecraft/${name}`, { next: { revalidate: 86400 }, signal: AbortSignal.timeout(5000) });
	} catch {
		return Response.json({ error: 'Mojang didn’t answer.' }, { status: 502 });
	}
	if (r.status === 404 || r.status === 204) return Response.json({ error: 'No account has that name.' }, { status: 404, headers: { 'Cache-Control': 'public, s-maxage=600' } });
	if (r.status === 429) return Response.json({ error: 'Mojang asked us to slow down. Try again in a minute.' }, { status: 429 });
	if (!r.ok) return Response.json({ error: `Mojang said ${r.status}.` }, { status: 502 });
	const profile = (await r.json()) as { id: string; name: string };
	// The skin is a nicety: without it the face is left blank.
	let skin: string | null = null;
	try {
		const s = await fetch(`https://sessionserver.mojang.com/session/minecraft/profile/${profile.id}`, { next: { revalidate: 86400 }, signal: AbortSignal.timeout(5000) });
		if (s.ok) {
			const p = (await s.json()) as { properties?: { name: string; value: string }[] };
			const t = p.properties?.find((x) => x.name === 'textures');
			const url = t ? (JSON.parse(Buffer.from(t.value, 'base64').toString('utf8')) as Textures).textures?.SKIN?.url : undefined;
			if (url && /^https?:\/\/textures\.minecraft\.net\/texture\/[0-9a-f]+$/.test(url)) skin = url.replace(/^http:/, 'https:');
		}
	} catch {}
	return Response.json({ name: profile.name, id: dashed(profile.id), skin }, { headers: { 'Cache-Control': 'public, s-maxage=86400' } });
}
