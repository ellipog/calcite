import type { Metadata, Viewport } from 'next';
import { Bricolage_Grotesque, DM_Mono } from 'next/font/google';
import { FocusRing } from '@/components/ui/focus-ring';
import { MarchWatch } from '@/components/ui/march-watch';
import { Toaster } from '@/components/ui/overlay';
import { SUFFIX } from '@/lib/meta';
import { SITE } from '@/lib/site';
import './globals.css';

// Weight and optical size only: the type is never condensed or stretched, and the width axis was
// 54 KB of the 131 KB file.
const bricolage = Bricolage_Grotesque({ subsets: ['latin'], axes: ['opsz'], variable: '--font-bricolage', display: 'swap' });
const dmMono = DM_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-dm-mono', display: 'swap' });

export const metadata: Metadata = {
	metadataBase: new URL(SITE.url),
	title: { default: SITE.title, template: `%s${SUFFIX}` },
	description: SITE.description,
	applicationName: 'calcite',
	openGraph: { type: 'website', siteName: 'calcite', title: SITE.title, description: SITE.description, url: '/', locale: 'en_US' },
	twitter: { card: 'summary_large_image', title: SITE.title, description: SITE.description },
	formatDetection: { telephone: false, address: false, email: false },
};

export const viewport: Viewport = { themeColor: '#F8F8F5', colorScheme: 'light' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en" className={`${bricolage.variable} ${dmMono.variable}`}>
			<body>
				<Toaster>{children}</Toaster>
				<FocusRing />
				<MarchWatch />
			</body>
		</html>
	);
}
