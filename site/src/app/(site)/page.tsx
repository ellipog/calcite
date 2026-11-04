import { Mark } from '@/components/mark';
import { ButtonLink } from '@/components/ui/button';

// The public site isn't built yet: this is a holding page, made of the same components the brand
// guide documents.
export default function Home() {
	return (
		<main className="wrap grid min-h-svh content-center gap-8 py-20">
			<div className="flex items-center gap-5">
				<Mark size={96} title="calcite" />
				<h1 className="font-display text-[clamp(56px,10vw,116px)] leading-[0.86] font-extrabold tracking-display">calcite</h1>
			</div>
			<p className="max-w-[44ch] text-lg leading-normal">A Minecraft server written in Calx, made to match vanilla to the tick. The website comes later.</p>
			<div className="flex flex-wrap gap-2.5">
				<ButtonLink href="https://github.com/ellipog/calcite">Source</ButtonLink>
			</div>
		</main>
	);
}
