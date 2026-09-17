/** A gym badge: an eight-point star in the chassis colour. Decorative, sits beside the word "Badge". */
export function BadgeMark({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false" className="inline-block align-[-1px]">
      <path
        d="M8 0l1.9 3.2 3.6-1 -1 3.6L16 8l-3.5 2.2 1 3.6-3.6-1L8 16l-1.9-3.2-3.6 1 1-3.6L0 8l3.5-2.2-1-3.6 3.6 1z"
        fill="currentColor"
      />
      <circle cx="8" cy="8" r="2.6" fill="var(--surface-raised)" />
    </svg>
  )
}
