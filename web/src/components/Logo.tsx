/**
 * Logo component that properly handles aspect ratio without triggering
 * Next.js Image dimension warnings. Uses regular img since we're unoptimized anyway.
 */
interface LogoProps {
  height?: number;
  className?: string;
}

export function Logo({ height = 36, className = '' }: LogoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- Intentional: unoptimized, fixed aspect via height
    <img
      src="/logo.png"
      alt="Bionocular Logo"
      className={`object-contain flex-shrink-0 ${className}`}
      style={{ height: `${height}px`, width: 'auto' }}
    />
  );
}
