import type { Metadata } from 'next';
import { Mark } from '@/components/mark';
import { SiteFooter } from '@/components/site/footer';
import { SiteHeader } from '@/components/site/header';
import { ButtonLink } from '@/components/ui/button';

export const metadata: Metadata = { title: 'Not found', robots: { index: false } };

// A page that isn't there: the mark with its view shrunk to nothing, so every square is out of it.
export default function NotFound() {
	return (
		<>
			<SiteHeader />
			<main id="main" className="wrap grid min-h-[70svh] grid-cols-1 content-center items-center gap-12 py-20 md:grid-cols-[auto_minmax(0,1fr)]">
				<Mark size={192} r={0.06} title="The mark, with no view: nothing generated" />
				<div>
					<p className="label mb-4">404 · not found</p>
					<h1 className="font-display text-[clamp(48px,7vw,96px)] leading-[0.9] font-extrabold tracking-display text-balance">Page not found</h1>
					<p className="mt-6 max-w-[48ch] text-lg leading-normal">There&apos;s no page at this address. It may have moved, or the link may be wrong.</p>
					<div className="mt-8 flex flex-wrap gap-2.5">
						<ButtonLink href="/">Home</ButtonLink>
						<ButtonLink href="/docs" variant="secondary">
							The docs
						</ButtonLink>
					</div>
				</div>
			</main>
			<SiteFooter />
		</>
	);
}
