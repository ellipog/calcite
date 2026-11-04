import { SiteFooter } from '@/components/site/footer';
import { SiteHeader } from '@/components/site/header';

export default function SiteLayout({ children }: { children: React.ReactNode }) {
	return (
		<>
			<a href="#main" className="sr-only z-50 bg-ink px-4 py-3 font-mono text-sm text-paper focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
				Skip to the page
			</a>
			<SiteHeader />
			<main id="main">{children}</main>
			<SiteFooter />
		</>
	);
}
