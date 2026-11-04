import type { Metadata } from 'next';

// Internal pages: the brand guide and the component sheet. They exist under `next dev` and in a
// CALCITE_INTERNAL=1 build only (see next.config.ts), and ask not to be indexed even then.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function InternalLayout({ children }: { children: React.ReactNode }) {
	return children;
}
