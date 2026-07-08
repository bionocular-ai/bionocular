import * as React from 'react';

/**
 * Kaplan–Meier step curve with a censoring tick — the actual shape this page renders,
 * used in place of a generic pulse/heartbeat glyph.
 */
export function SurvivalCurveIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M3 6 L10 6 L10 12 L16 12 L16 18 L21 18" />
      <path d="M13 9 L13 12" />
    </svg>
  );
}
