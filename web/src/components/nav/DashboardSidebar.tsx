'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname, useSearchParams } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { UserMenu } from '@/components/user-menu';
import { useSession } from '@/lib/supabase/hooks';
import { DASHBOARD_NAV_ITEMS, slugToCategory } from '@/lib/dashboard-constants';
import type { DashboardNavItem } from '@/lib/dashboard-constants';
import { ROUTES, dashboardRoute } from '@/lib/constants';
import { cn } from '@/lib/utils';

/** Default analytics mode used by the analytics page when no `?mode` is present. */
const DEFAULT_ANALYTICS_MODE = 'efficacy';

function isItemActive(
  item: DashboardNavItem,
  pathname: string,
  currentMode: string,
): boolean {
  if (!item.section) return false;
  if (!pathname.endsWith(`/${item.section}`)) return false;
  // Analytics items differ only by query.mode — disambiguate on the resolved mode.
  if (item.query?.mode) {
    return item.query.mode === currentMode;
  }
  return true;
}

interface NavListProps {
  slug: string;
  pathname: string;
  currentMode: string;
  onNavigate?: () => void;
}

function NavList({ slug, pathname, currentMode, onNavigate }: NavListProps) {
  return (
    <nav className="flex flex-1 flex-col items-stretch gap-1.5 overflow-y-auto px-2 py-3">
      {DASHBOARD_NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active = isItemActive(item, pathname, currentMode);
        const href = item.section
          ? dashboardRoute(slug, item.section, item.query)
          : undefined;
        const isUpcoming = item.status === 'upcoming';
        // Disabled when an upcoming item has no destination, or any item lacks an href.
        const isDisabled = (isUpcoming && !item.section) || !href;

        const content = (
          <>
            <span className="relative flex h-9 w-9 items-center justify-center">
              <Icon className="h-5 w-5 shrink-0" aria-hidden />
              {isUpcoming && item.section && !active && (
                <span
                  aria-hidden
                  className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-(--brand-accent) ring-2 ring-(--brand-surface)"
                />
              )}
            </span>
            <span className="text-center text-[11px] font-medium leading-tight tracking-tight">
              {item.label}
            </span>
          </>
        );

        const baseClasses = cn(
          'group flex flex-col items-center gap-1 rounded-xl px-1.5 py-2.5',
          'text-center transition-all duration-200 ease-out',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 focus-visible:ring-offset-(--brand-surface)',
        );

        if (isDisabled) {
          return (
            <div
              key={item.key}
              title="Coming soon"
              aria-disabled="true"
              className={cn(
                baseClasses,
                'cursor-not-allowed text-(--brand-text-muted) opacity-45',
              )}
            >
              {content}
            </div>
          );
        }

        return (
          <Link
            key={item.key}
            href={href}
            onClick={onNavigate}
            aria-current={active ? 'page' : undefined}
            title={isUpcoming ? `${item.label} (preview)` : item.label}
            className={cn(
              baseClasses,
              active
                ? 'bg-(--brand-surface) text-(--brand-primary) shadow-[0_2px_10px_-2px_rgba(16,43,54,0.18)] ring-1 ring-(--brand-border)'
                : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary)',
              isUpcoming && !active && 'opacity-80',
            )}
          >
            {content}
          </Link>
        );
      })}
    </nav>
  );
}

export function DashboardSidebar() {
  // `[category]` is a single dynamic segment, never an array.
  const slug = useParams().category as string;
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentMode = searchParams.get('mode') ?? DEFAULT_ANALYTICS_MODE;
  const categoryName = slugToCategory(slug);

  const userMenu = session?.user ? (
    <UserMenu
      email={session.user.email || null}
      name={(session.user.user_metadata?.full_name as string) || null}
      image={undefined}
    />
  ) : null;

  return (
    <>
      {/* Desktop icon rail */}
      <aside
        className="sticky top-0 hidden h-screen w-24 shrink-0 flex-col border-r border-(--brand-border) bg-(--brand-bg) md:flex"
        aria-label="Dashboard navigation"
      >
        <Link
          href={ROUTES.DASHBOARD}
          title={categoryName}
          aria-label={`${categoryName} — back to dashboards`}
          className="flex h-16 shrink-0 items-center justify-center border-b border-(--brand-border) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
        >
          <Logo height={28} />
        </Link>

        <NavList slug={slug} pathname={pathname} currentMode={currentMode} />

        <div className="flex h-20 shrink-0 items-center justify-center border-t border-(--brand-border)">
          {userMenu}
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-(--brand-border) bg-(--brand-surface) px-4 md:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
        <Link href={ROUTES.DASHBOARD} aria-label={`${categoryName} — back to dashboards`}>
          <Logo height={26} />
        </Link>
        <div className="flex h-9 w-9 items-center justify-center">{userMenu}</div>
      </div>

      {/* Mobile off-canvas drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Dashboard navigation"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setMobileOpen(false);
          }}
        >
          <div
            className="absolute inset-0 bg-(--brand-text)/30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="absolute left-0 top-0 flex h-full w-28 flex-col border-r border-(--brand-border) bg-(--brand-bg) shadow-xl">
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-(--brand-border) px-2">
              <Logo height={24} />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation menu"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
            <NavList
              slug={slug}
              pathname={pathname}
              currentMode={currentMode}
              onNavigate={() => setMobileOpen(false)}
            />
            <div className="flex h-20 shrink-0 items-center justify-center border-t border-(--brand-border)">
              {userMenu}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
