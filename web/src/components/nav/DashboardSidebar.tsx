'use client';

import { useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { useParams, usePathname, useSearchParams } from 'next/navigation';
import { Menu, PanelLeft, X } from 'lucide-react';
import { DASHBOARD_NAV_GROUPS } from '@/lib/dashboard-constants';
import type { DashboardNavItem } from '@/lib/dashboard-constants';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { dashboardRoute } from '@/lib/constants';
import { cn } from '@/lib/utils';

/** Default analytics mode used by the analytics page when no `?mode` is present. */
const DEFAULT_ANALYTICS_MODE = 'efficacy';

/**
 * How much of the rail is showing. `hover` keeps the collapsed footprint in the
 * layout and floats the labelled rail over the page while the pointer is on it.
 */
type SidebarMode = 'expanded' | 'collapsed' | 'hover';

const SIDEBAR_MODE_STORAGE_KEY = 'bionocular:sidebar-mode';

const SIDEBAR_MODE_OPTIONS: { value: SidebarMode; label: string }[] = [
  { value: 'expanded', label: 'Expanded' },
  { value: 'collapsed', label: 'Collapsed' },
  { value: 'hover', label: 'Expand on hover' },
];

function isSidebarMode(value: string | null): value is SidebarMode {
  return SIDEBAR_MODE_OPTIONS.some((option) => option.value === value);
}

/**
 * `localStorage` is the external store here, so the preference is read through
 * `useSyncExternalStore`: the server snapshot is the default, the client
 * snapshot is whatever was stored, and React reconciles the two without a
 * hydration mismatch. Writes notify this tab; the `storage` event covers others.
 */
const sidebarModeListeners = new Set<() => void>();

/**
 * Cached because `useSyncExternalStore` requires a snapshot that is stable
 * between changes, and because it keeps the chosen mode live even where writing
 * to storage throws.
 */
let cachedSidebarMode: SidebarMode | null = null;

function readStoredSidebarMode(): SidebarMode {
  try {
    const stored = window.localStorage.getItem(SIDEBAR_MODE_STORAGE_KEY);
    if (isSidebarMode(stored)) return stored;
  } catch {
    // Storage can be blocked (private mode, embedded contexts); the default stands.
  }
  return 'expanded';
}

function getSidebarMode(): SidebarMode {
  cachedSidebarMode ??= readStoredSidebarMode();
  return cachedSidebarMode;
}

function subscribeSidebarMode(onChange: () => void): () => void {
  // Another tab changed the preference: refresh the cache before React reads it.
  const onStorage = () => {
    cachedSidebarMode = readStoredSidebarMode();
    onChange();
  };
  sidebarModeListeners.add(onChange);
  window.addEventListener('storage', onStorage);
  return () => {
    sidebarModeListeners.delete(onChange);
    window.removeEventListener('storage', onStorage);
  };
}

function setSidebarMode(mode: SidebarMode): void {
  cachedSidebarMode = mode;
  try {
    window.localStorage.setItem(SIDEBAR_MODE_STORAGE_KEY, mode);
  } catch {
    // Preference lasts for this session only when storage is unavailable.
  }
  sidebarModeListeners.forEach((notify) => notify());
}

function useSidebarMode(): [SidebarMode, (mode: SidebarMode) => void] {
  const mode = useSyncExternalStore(
    subscribeSidebarMode,
    getSidebarMode,
    () => 'expanded' as const,
  );
  return [mode, setSidebarMode];
}

function isItemActive(
  item: DashboardNavItem,
  pathname: string,
  currentMode: string,
): boolean {
  if (!item.section) return false;
  if (!pathname.endsWith(`/${item.section}`)) return false;
  // Analytics items differ only by query.mode - disambiguate on the resolved mode.
  if (item.query?.mode) {
    return item.query.mode === currentMode;
  }
  return true;
}

/** Row geometry, shared by every item so the rail keeps one vertical rhythm. */
const ROW_BASE =
  'group/row relative mx-2 flex h-[34px] items-center gap-3 rounded-lg pr-3 pl-[11px] ' +
  'text-[13.5px] leading-none transition-colors duration-150';

/**
 * Labels are clipped by the rail's `overflow-hidden` rather than unmounted, so
 * the hover rail can reveal them in CSS without a re-render.
 */
function labelClasses(mode: SidebarMode): string {
  return cn(
    'min-w-0 flex-1 truncate text-left transition-opacity duration-150',
    mode === 'expanded'
      ? 'opacity-100'
      : mode === 'collapsed'
        ? 'opacity-0'
        : 'opacity-0 group-hover/rail:opacity-100',
  );
}

function NavItemLink({
  item,
  slug,
  pathname,
  currentMode,
  sidebarMode,
  onNavigate,
  isChild = false,
}: {
  item: DashboardNavItem;
  slug: string;
  pathname: string;
  currentMode: string;
  sidebarMode: SidebarMode;
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

  // Nesting shows as an indent plus a connector rule, and only while labels show -
  // a collapsed rail has no column to indent into. The indent is kept shallow so
  // the longest child label still clears the rail's inner width.
  const CONNECTOR =
    'before:absolute before:inset-y-0 before:left-[19px] before:w-px before:bg-(--brand-border) before:content-[""]';
  const indent =
    isChild &&
    (sidebarMode === 'expanded'
      ? cn('pl-[30px]', CONNECTOR)
      : sidebarMode === 'hover' &&
        cn('group-hover/rail:pl-[30px]', CONNECTOR, 'before:opacity-0 group-hover/rail:before:opacity-100'));

  const content = (
    <>
      <Icon
        className={cn(
          'size-[18px] shrink-0 transition-[stroke-width] duration-150',
          active && '[stroke-width:2.25]',
        )}
        aria-hidden
      />
      <span className={labelClasses(sidebarMode)}>{item.label}</span>
    </>
  );

  if (isDisabled) {
    return (
      <div
        title={`${item.label} - coming soon`}
        aria-disabled="true"
        className={cn(ROW_BASE, indent, 'cursor-not-allowed text-(--brand-text-muted)/70')}
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
      title={item.label}
      className={cn(
        ROW_BASE,
        indent,
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-(--brand-bg)',
        active
          ? 'bg-(--brand-primary) font-semibold text-white shadow-[0_1px_2px_rgba(16,43,54,0.12),0_8px_18px_-12px_rgba(16,43,54,0.85)]'
          : 'font-normal text-(--brand-text-muted) hover:bg-(--brand-accent-light) hover:text-(--brand-primary)',
        isUpcoming && !active && 'text-(--brand-text-muted)/70',
      )}
    >
      {content}
    </Link>
  );
}

function NavList({
  slug,
  pathname,
  currentMode,
  sidebarMode,
  onNavigate,
}: {
  slug: string;
  pathname: string;
  currentMode: string;
  sidebarMode: SidebarMode;
  onNavigate?: () => void;
}) {
  return (
    <nav
      className="flex flex-1 flex-col gap-px overflow-y-auto overflow-x-hidden py-2"
      aria-label="Dashboard sections"
    >
      {DASHBOARD_NAV_GROUPS.map((group, groupIndex) => (
        <div key={group[0].key} className="flex flex-col gap-px">
          {groupIndex > 0 && <div aria-hidden className="mx-4 my-2 h-px bg-(--brand-border)" />}
          {group.flatMap((item) => [
            <NavItemLink
              key={item.key}
              item={item}
              slug={slug}
              pathname={pathname}
              currentMode={currentMode}
              sidebarMode={sidebarMode}
              onNavigate={onNavigate}
            />,
            ...(item.children ?? []).map((child) => (
              <NavItemLink
                key={child.key}
                item={child}
                slug={slug}
                pathname={pathname}
                currentMode={currentMode}
                sidebarMode={sidebarMode}
                onNavigate={onNavigate}
                isChild
              />
            )),
          ])}
        </div>
      ))}
    </nav>
  );
}

function SidebarModeControl({
  mode,
  onModeChange,
}: {
  mode: SidebarMode;
  onModeChange: (mode: SidebarMode) => void;
}) {
  return (
    <div className="mt-auto px-2 py-2">
      <DropdownMenu>
        <DropdownMenuTrigger
          className={cn(
            ROW_BASE,
            'mx-0 w-full cursor-pointer text-(--brand-text-muted) transition-colors',
            'hover:bg-(--brand-accent-light) hover:text-(--brand-primary)',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-(--brand-bg)',
          )}
          aria-label="Sidebar control"
        >
          <PanelLeft className="size-[18px] shrink-0" aria-hidden />
          <span className={labelClasses(mode)}>Sidebar control</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="top"
          align="start"
          className="w-52 border-(--brand-border) text-(--brand-text)"
        >
          <DropdownMenuLabel className="px-3 py-1.5 text-xs font-medium text-(--brand-text-muted)">
            Sidebar control
          </DropdownMenuLabel>
          <DropdownMenuSeparator className="bg-(--brand-border)" />
          <DropdownMenuRadioGroup
            value={mode}
            onValueChange={(value) => onModeChange(value as SidebarMode)}
          >
            {SIDEBAR_MODE_OPTIONS.map((option) => (
              <DropdownMenuRadioItem
                key={option.value}
                value={option.value}
                className="cursor-pointer py-2 text-[13px] focus:bg-(--brand-accent-light) data-[state=checked]:font-semibold data-[state=checked]:text-(--brand-primary)"
              >
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export function DashboardSidebar() {
  // `[category]` is a single dynamic segment, never an array.
  const slug = useParams().category as string;
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarMode, setSidebarMode] = useSidebarMode();

  const currentMode = searchParams.get('mode') ?? DEFAULT_ANALYTICS_MODE;
  const isExpanded = sidebarMode === 'expanded';

  return (
    <>
      {/* Desktop rail - sits under the global top nav. The outer element reserves
          the layout width so `hover` mode can float the labelled rail over the
          page without shifting content. */}
      <div
        className={cn(
          // `position: sticky` opens a stacking context, so the rail's own
          // z-index is scoped inside this wrapper - the wrapper is what has to
          // out-rank the page's sticky table headers (z-10 to z-30) when the
          // hover rail expands over the content. Overlays at z-40 and above come
          // later in the DOM and still cover it.
          'sticky top-14 z-40 hidden h-[calc(100vh-3.5rem)] shrink-0 md:block',
          isExpanded ? 'w-64' : 'w-14',
        )}
      >
        <aside
          className={cn(
            'group/rail absolute inset-y-0 left-0 flex flex-col overflow-hidden',
            'border-r border-(--brand-border) bg-(--brand-bg) transition-[width,box-shadow] duration-200 ease-out',
            isExpanded ? 'w-64' : 'w-14',
            // Floating over the page, the rail is lit rather than scrimmed: a
            // near-invisible contact shadow holds the edge and a wide, low-alpha
            // ambient one carries the lift. Both are tinted with the brand teal
            // (#1B4F65) - a neutral black at this alpha greys the mint page
            // background into mud.
            sidebarMode === 'hover' &&
              cn(
                'hover:w-64 hover:bg-(--brand-surface)',
                'hover:shadow-[1px_0_2px_0_rgba(27,79,101,0.05),24px_0_32px_-16px_rgba(27,79,101,0.16)]',
              ),
          )}
        >
          <NavList
            slug={slug}
            pathname={pathname}
            currentMode={currentMode}
            sidebarMode={sidebarMode}
          />
          <SidebarModeControl mode={sidebarMode} onModeChange={setSidebarMode} />
        </aside>
      </div>

      {/* Mobile section-nav bar - sits under the global top nav */}
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

      {/* Mobile off-canvas drawer - always labelled; the mode control is desktop-only. */}
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
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-(--brand-border) bg-(--brand-bg) shadow-xl">
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
              sidebarMode="expanded"
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}
    </>
  );
}
