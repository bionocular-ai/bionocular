import * as React from 'react';

/**
 * The agent's mark: a character peering over a pair of binoculars, the
 * antenna ending in the logo's seafoam dot. Inside a `group`, the eyes blink
 * once on hover.
 */
export function PeekIcon(props: React.SVGProps<SVGSVGElement>) {
  const head = React.useId();
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" {...props}>
      <defs>
        <linearGradient id={head} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7AC1A2" />
          <stop offset=".55" stopColor="#2E7A84" />
          <stop offset="1" stopColor="#1B4F65" />
        </linearGradient>
      </defs>
      <path d="M9 31 V22 A15 15 0 0 1 39 22 V31Z" fill={`url(#${head})`} />
      <line x1="24" y1="7" x2="24" y2="4.5" stroke="#2E7A84" strokeWidth="2" strokeLinecap="round" />
      <circle cx="24" cy="3.6" r="2.4" fill="#7AC1A2" />
      <g className="origin-center [transform-box:fill-box] group-hover:animate-[peek-blink_.32s_ease-in-out_1] motion-reduce:group-hover:animate-none">
        <circle cx="18.5" cy="19" r="2.4" fill="#102B36" />
        <circle cx="29.5" cy="19" r="2.4" fill="#102B36" />
        <circle cx="19.3" cy="18.2" r=".8" fill="#fff" />
        <circle cx="30.3" cy="18.2" r=".8" fill="#fff" />
      </g>
      <rect x="19" y="27.5" width="10" height="5" rx="2" fill="#16404F" />
      <rect x="8.5" y="24" width="12.5" height="19" rx="5.5" fill="#16404F" />
      <rect x="27" y="24" width="12.5" height="19" rx="5.5" fill="#16404F" />
      <circle cx="14.75" cy="37.5" r="3.6" fill="#7AC1A2" />
      <circle cx="33.25" cy="37.5" r="3.6" fill="#7AC1A2" />
      <circle cx="13.7" cy="36.4" r="1.1" fill="#DAF0E6" />
      <circle cx="32.2" cy="36.4" r="1.1" fill="#DAF0E6" />
    </svg>
  );
}
