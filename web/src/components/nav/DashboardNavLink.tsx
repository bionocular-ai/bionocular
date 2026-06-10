'use client';

import Link from 'next/link';
import { Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePathname } from 'next/navigation';

export interface DashboardNavLinkProps {
  className?: string;
}

export function DashboardNavLink({ className }: DashboardNavLinkProps) {
  const pathname = usePathname();

  // Extract category slug from /dashboard/[category]/...
  const match = pathname.match(/^\/dashboard\/([^/]+)/);
  const category = match?.[1];

  if (!category) return null;

  return (
    <Link
      href={`/dashboard/${category}`}
      aria-label="Go to dashboard"
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium',
        'bg-(--brand-primary) border-transparent text-white',
        'transition-all duration-200 ease-out',
        'hover:bg-(--brand-primary-hover) hover:shadow-md',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        'min-h-[34px]',
        'active:scale-[0.98]',
        className
      )}
    >
      <Activity className="h-4 w-4 shrink-0" aria-hidden />
      <span>Dashboard</span>
    </Link>
  );
}
