/**
 * Rotom's face, as it appears on the Rotom Dex screen: two plasma eyes and a zigzag grin inside the
 * orange chassis. Drawn inline so it needs no asset and takes the current tokens for its colours.
 * Decorative by default; pass `label` when it stands in for the product name.
 */

export function RotomMark({ size = 32, blink = false, label }: { size?: number; blink?: boolean; label?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={`rotom-mark${blink ? ' rotom-mark-blink' : ''}`}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
      focusable="false"
    >
      {/* chassis */}
      <rect x="2" y="6" width="60" height="52" rx="16" fill="var(--chassis)" />
      {/* antenna nub, the Rotom Dex's top-left bump */}
      <circle cx="14" cy="8" r="6" fill="var(--chassis)" />
      {/* screen */}
      <rect x="9" y="14" width="46" height="36" rx="11" fill="var(--rotom-screen)" />
      {/* eyes */}
      <g className="rotom-eyes">
        <ellipse cx="23" cy="30" rx="6" ry="7" fill="var(--plasma)" />
        <ellipse cx="41" cy="30" rx="6" ry="7" fill="var(--plasma)" />
        <circle cx="25" cy="27.5" r="2" fill="#fff" />
        <circle cx="43" cy="27.5" r="2" fill="#fff" />
      </g>
      {/* grin */}
      <polyline
        points="18,40 23,44 28,40 33,44 38,40 43,44 47,40"
        fill="none"
        stroke="var(--plasma)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
