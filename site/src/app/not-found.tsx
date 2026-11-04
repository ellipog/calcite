import type { Metadata } from 'next';
import { SiteFooter } from '@/components/site/footer';
import { SiteHeader } from '@/components/site/header';
import { LostChunk } from '@/components/site/lost-chunk';
import { Kicker } from '@/components/site/parts';
import { ButtonLink } from '@/components/ui/button';

// Next marks a page that isn't there noindex itself
export const metadata: Metadata = { title: 'Not found' };

// A page that isn't there: the chunk where it would be was never generated, so the server
// generates it, and what it builds there is the number (lost-chunk.tsx).
export default function NotFound() {
	return (
		<>
			<SiteHeader />
			<main id="main" className="pb-6">
				<div className="wrap grid grid-cols-1 items-end gap-6 pt-12 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:gap-10 md:pt-16">
					<div>
						<Kicker>404 · not found</Kicker>
						<h1 className="font-display text-[clamp(48px,7.4vw,136px)] leading-[0.86] font-extrabold tracking-display text-balance">Nothing was generated here</h1>
					</div>
					<div className="pb-1">
						<p className="max-w-[44ch] text-lg leading-normal">There&apos;s no page at this address. It may have moved, or the link may be wrong. The server is generating the chunk it would be in anyway.</p>
						<div className="mt-6 flex flex-wrap gap-2.5">
							<ButtonLink href="/">Home</ButtonLink>
							<ButtonLink href="/docs" variant="secondary">
								The docs
							</ButtonLink>
						</div>
					</div>
				</div>
				<LostChunk className="mt-8 md:mt-12" />
			</main>
			<SiteFooter />
		</>
	);
}
