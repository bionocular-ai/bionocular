'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname, useSearchParams } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { DASHBOARD_NAV_ITEMS } from '@/lib/dashboard-constants';
import type { DashboardNavItem } from '@/lib/dashboard-constants';
import { dashboardRoute } from '@/lib/constants';
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

function NavItemLink({
  item,
  slug,
  pathname,
  currentMode,
  onNavigate,
  isChild = false,
}: {
  item: DashboardNavItem;
  slug: string;
  pathname: string;
  currentMode: string;
  onNavigate?: () => void;
  isChild?: boolean;
}) {
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
      <span className={cn('relative flex items-center justify-center', isChild ? 'h-6 w-6' : 'h-9 w-9')}>
        <Icon className={cn('shrink-0', isChild ? 'h-3.5 w-3.5' : 'h-5 w-5')} aria-hidden />
        {isUpcoming && item.section && !active && (
          <span
            aria-hidden
            className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-(--brand-accent) ring-2 ring-(--brand-surface)"
          />
        )}
      </span>
      <span
        className={cn(
          'text-center leading-tight',
          isChild ? 'text-[10px] font-medium tracking-tight' : 'text-[11px] font-medium tracking-tight',
        )}
      >
        {item.label}
      </span>
    </>
  );

  const baseClasses = cn(
    'group flex flex-col items-center text-center transition-all duration-200 ease-out',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 focus-visible:ring-offset-(--brand-surface)',
    isChild ? 'gap-0.5 rounded-md px-1 py-1.5' : 'gap-1 rounded-xl px-1.5 py-2.5',
  );

  if (isDisabled) {
    return (
      <div
        title="Coming soon"
        aria-disabled="true"
        className={cn(
          baseClasses,
          'cursor-not-allowed text-(--brand-text-muted) opacity-70',
        )}
      >
        {content}
      </div>
    );
  }

  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      title={isUpcoming ? `${item.label} (preview)` : item.label}
      className={cn(
        baseClasses,
        isChild
          ? active
            ? 'bg-(--brand-accent-light)/60 text-(--brand-primary) ring-1 ring-(--brand-accent)'
            : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light)/40 hover:text-(--brand-primary)'
          : active
            ? 'bg-(--brand-surface) text-(--brand-primary) shadow-[0_2px_10px_-2px_rgba(16,43,54,0.18)] ring-1 ring-(--brand-border)'
            : 'text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary)',
        isUpcoming && !active && 'opacity-80',
      )}
    >
      {content}
    </Link>
  );
}

function NavList({ slug, pathname, currentMode, onNavigate }: NavListProps) {
  return (
    <nav className="flex flex-1 flex-col items-stretch gap-1.5 overflow-y-auto px-2 py-3">
      {DASHBOARD_NAV_ITEMS.map((item) => (
        <div key={item.key} className="flex flex-col">
          <NavItemLink item={item} slug={slug} pathname={pathname} currentMode={currentMode} onNavigate={onNavigate} />
          {item.children?.map((child) => (
            <div key={child.key} className="flex flex-col items-center pl-2">
              <span aria-hidden className="h-2 w-px bg-(--brand-border)" />
              <div className="w-full">
                <NavItemLink item={child} slug={slug} pathname={pathname} currentMode={currentMode} onNavigate={onNavigate} isChild />
              </div>
            </div>
          ))}
        </div>
      ))}
    </nav>
  );
}

export function DashboardSidebar() {
  // `[category]` is a single dynamic segment, never an array.
  const slug = useParams().category as string;
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentMode = searchParams.get('mode') ?? DEFAULT_ANALYTICS_MODE;

  return (
    <>
      {/* Desktop icon rail — sits under the global top nav */}
      <aside
        className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-24 shrink-0 flex-col border-r border-(--brand-border) bg-(--brand-bg) md:flex"
        aria-label="Dashboard sections"
      >
        <NavList slug={slug} pathname={pathname} currentMode={currentMode} />
      </aside>

      {/* Mobile section-nav bar — sits under the global top nav */}
      <div className="fixed inset-x-0 top-14 z-30 flex h-12 items-center border-b border-(--brand-border) bg-(--brand-surface) px-4 md:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open section navigation"
          aria-expanded={mobileOpen}
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
        >
          <Menu className="h-5 w-5" aria-hidden />
          Sections
        </button>
      </div>

      {/* Mobile off-canvas drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Dashboard sections"
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
            <div className="flex h-12 shrink-0 items-center justify-end border-b border-(--brand-border) px-2">
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
          </aside>
        </div>
      )}
    </>
  );
}
