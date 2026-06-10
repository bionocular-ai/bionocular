'use client';

import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { UserMenu } from '@/components/user-menu';
import { useSession } from '@/lib/supabase/hooks';

/** Global navigation banner shown across all dashboard category pages, above the page content. */
export function DashboardTopNav() {
  const { data: session } = useSession();

  return (
    <header className="sticky top-0 z-40 border-b border-(--brand-border) bg-(--brand-surface) shadow-sm">
      <div className="flex h-14 items-center justify-between gap-4 px-6">
        <Link href="/" className="brand flex-shrink-0">
          <Logo height={32} />
          <span className="brand-text text-lg">
            bi<span className="brand-o">o</span>nocular
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <HomeNavLink />
          <DashboardNavLink />
          {session?.user && (
            <UserMenu
              email={session.user.email || null}
              name={(session.user.user_metadata?.full_name as string) || null}
            />
          )}
        </div>
      </div>
    </header>
  );
}
