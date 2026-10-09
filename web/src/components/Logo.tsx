import { cn } from '@/lib/utils';

/**
 * The brand lockup: the two-leaf mark and the "bionocular" wordmark, sized
 * together by the font size (set it with a text-* class), so the mark keeps its
 * proportion to the text at every size. Colour follows `color` (text-white on
 * dark surfaces).
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('brand-lockup', className)}>
      {/* eslint-disable-next-line @next/next/no-img-element -- a static SVG, sized in em */}
      <img src="/logo.svg" alt="" className="brand-lockup-mark" />
      <span className="brand-text">
        <span className="brand-bio">bio</span>nocular
      </span>
    </span>
  );
}
