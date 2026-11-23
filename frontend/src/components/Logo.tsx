/** Logo « Prisme » : quatre carrés (indigo, lavande, ambre). */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden="true">
      <rect x="2" y="2" width="14" height="14" rx="4" fill="#4338CA" />
      <rect x="20" y="2" width="14" height="14" rx="4" fill="#818CF8" />
      <rect x="2" y="20" width="14" height="14" rx="4" fill="#818CF8" />
      <rect x="20" y="20" width="14" height="14" rx="4" fill="#F59E0B" />
    </svg>
  );
}
