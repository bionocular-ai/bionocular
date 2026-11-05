'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

export interface HomeNavLinkProps {
  className?: string;
}

export function HomeNavLink({ className }: HomeNavLinkProps) {
  const current = usePathname() === ROUTES.DASHBOARD;

  return (
    <Link
      href={ROUTES.DASHBOARD}
      aria-label="Go to home"
      aria-current={current ? 'page' : undefined}
      className={cn(
        'relative inline-flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-sm font-medium sm:px-4',
        // A 44 px target around the 34 px pill.
        'before:absolute before:-inset-y-[5px] before:-inset-x-[3px]',
        current
          ? 'border-transparent bg-(--brand-primary) text-white hover:bg-(--brand-primary-hover)'
          : 'border-(--brand-primary) bg-transparent text-(--brand-primary) hover:bg-(--brand-text)/5',
        'transition-all duration-200 ease-out',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        'min-h-[34px]',
        'active:scale-[0.98]',
        className
      )}
    >
      <Home className="h-4 w-4 shrink-0" aria-hidden />
      {/* Icon-only on a phone, where both labels and the avatar overflow the bar. */}
      <span className="hidden sm:inline">Home</span>
    </Link>
  );
}
