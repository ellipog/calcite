// Aaen Studios' mark, the ring over the chevron, traced from aaenz.no's logo-mark.png in its own
// pixel coordinates and drawn in currentColor, so it takes the ink of whatever it sits in.
export function AaenMark({ size = 16, className }: { size?: number; className?: string }) {
	return (
		<svg width={size} height={size} viewBox="79 74 720 720" className={className} aria-hidden style={{ flex: 'none' }}>
			<path
				fill="currentColor"
				fillRule="evenodd"
				d="M100 156a338.5 61 0 1 0 677 0a338.5 61 0 1 0 -677 0Z M117 148.5a321.5 45.5 0 1 0 643 0a321.5 45.5 0 1 0 -643 0Z M90 782L440 303L788 782L781 782L440 386L97 782Z"
			/>
		</svg>
	);
}
