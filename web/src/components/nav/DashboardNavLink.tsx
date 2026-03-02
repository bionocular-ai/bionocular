'use client';

import Link from 'next/link';
import { LayoutDashboard } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DashboardNavLinkProps {
  className?: string;
}

/**
 * Primary nav link back to the dashboard. Shared styling and behavior
 * across trial pages and dashboard subpages.
 */
export function DashboardNavLink({ className }: DashboardNavLinkProps) {
  return (
    <Link
      href="/dashboard"
      aria-label="Go to dashboard"
      className={cn(
        'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium',
        'bg-[var(--primary)] border-transparent text-white',
        'transition-all duration-200 ease-out',
        'hover:bg-[var(--accent-dark)] hover:shadow-md',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        'min-h-[36px] sm:min-h-[38px]',
        'active:scale-[0.98]',
        className
      )}
    >
      <LayoutDashboard className="h-4 w-4 shrink-0 sm:h-[18px] sm:w-[18px]" aria-hidden />
      <span>Dashboard</span>
    </Link>
  );
}
