import type { Metadata } from 'next';
import { Bricolage_Grotesque, DM_Mono } from 'next/font/google';
import { FocusRing } from '@/components/ui/focus-ring';
import { Toaster } from '@/components/ui/overlay';
import './globals.css';

const bricolage = Bricolage_Grotesque({ subsets: ['latin'], axes: ['opsz', 'wdth'], variable: '--font-bricolage', display: 'swap' });
const dmMono = DM_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-dm-mono', display: 'swap' });

export const metadata: Metadata = {
	title: { default: 'calcite', template: '%s · calcite' },
	description: 'A Minecraft server written in Calx.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en" className={`${bricolage.variable} ${dmMono.variable}`}>
			<body>
				<Toaster>{children}</Toaster>
				<FocusRing />
			</body>
		</html>
	);
}
