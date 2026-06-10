'use client';

import Link from 'next/link';
import { Home } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

export interface HomeNavLinkProps {
  className?: string;
}

export function HomeNavLink({ className }: HomeNavLinkProps) {
  return (
    <Link
      href={ROUTES.DASHBOARD}
      aria-label="Go to home"
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium',
        'border-(--brand-primary) bg-transparent text-(--brand-primary)',
        'transition-all duration-200 ease-out',
        'hover:bg-(--brand-accent-light)',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        'min-h-[34px]',
        'active:scale-[0.98]',
        className
      )}
    >
      <Home className="h-4 w-4 shrink-0" aria-hidden />
      <span>Home</span>
    </Link>
  );
}
