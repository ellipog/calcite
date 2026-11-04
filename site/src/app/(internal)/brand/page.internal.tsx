import type { Metadata } from 'next';
import { InternalBar } from '@/components/internal-bar';
import { SECTIONS } from './_parts';
import { Idea, Colour, Type, Voice } from './_static';
import { Flyover } from '@/components/flyover';
import { Logo } from './_logo';
import { Dither, Imagery, Icons } from './_pictures';
import { UI, Charts, Motion, InUse, Files } from './_more';

export const metadata: Metadata = { title: 'Brand guide' };

export default function Brand() {
	return (
		<>
			<InternalBar title="brand guide · internal" sections={SECTIONS} here="/brand" />
			<section className="pt-[72px]" id="top">
				<div className="wrap grid grid-cols-1 items-end gap-8 md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
					<div>
						<p className="label text-xs">calcite · brand guide</p>
						<h1 className="mt-[22px] font-display text-[clamp(58px,10vw,152px)] leading-[0.86] font-extrabold tracking-display">Worlds, one dot at a time.</h1>
					</div>
					<p className="max-w-[34ch] pb-3 text-lg leading-normal">Calcite is a Minecraft server written in Calx. Its worldgen matches vanilla&apos;s. Its brand is one cobalt ink on paper, every shade a pattern of dots, and its mark is the view around a player.</p>
				</div>
				<Flyover />
			</section>
			<main>
				<Idea />
				<Logo />
				<Colour />
				<Type />
				<Dither />
				<Imagery />
				<Icons />
				<UI />
				<Charts />
				<Motion />
				<InUse />
				<Voice />
				<Files />
			</main>
			<footer className="rule-t pt-10 pb-16 font-mono text-xs leading-[1.7]">
				<div className="wrap flex flex-wrap justify-between gap-4">
					<span>calcite brand guide · draft · internal</span>
					<span>one ink · Bayer 8×8 · View</span>
				</div>
			</footer>
		</>
	);
}
