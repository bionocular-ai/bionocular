'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { SyntheticEvent } from 'react';
import Link from 'next/link';
import { useParams, usePathname, useSearchParams } from 'next/navigation';
import { ChevronDown, Ellipsis, Menu, PanelLeft, X } from 'lucide-react';
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
  'text-sm leading-none transition-colors duration-150';

/** Hover is a faint neutral wash and press a deeper one; mint is kept for what is selected. */
const ROW_IDLE =
  'text-(--brand-text-muted) hover:bg-(--brand-text)/5 hover:text-(--brand-text) active:bg-(--brand-text)/10';

/**
 * The hover rail opens after a short dwell and closes after a short grace, so a
 * pointer crossing it on the way to the page doesn't throw it open. Keyboard
 * focus opens it at once.
 */
const HOVER_TIMING =
  'delay-300 group-hover/rail:delay-150 group-has-focus-visible/rail:delay-0';

/**
 * Labels are clipped by the rail's `overflow-hidden` rather than unmounted, so
 * the hover rail can reveal them in CSS without a re-render.
 */
function labelClasses(mode: SidebarMode): string {
  return cn(
    // Truncation clips at the line box, so the label needs room below the baseline for g, y and p.
    'min-w-0 flex-1 truncate text-left leading-normal transition-opacity duration-150',
    mode === 'expanded'
      ? 'opacity-100'
      : mode === 'collapsed'
        ? 'opacity-0'
        : cn('opacity-0 group-hover/rail:opacity-100 group-has-focus-visible/rail:opacity-100', HOVER_TIMING),
  );
}

function NavItemLink({
  item,
  slug,
  pathname,
  currentMode,
  sidebarMode,
  onNavigate,
}: {
  item: DashboardNavItem;
  slug: string;
  pathname: string;
  currentMode: string;
  sidebarMode: SidebarMode;
  onNavigate?: () => void;
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
      <Icon
        className={cn(
          'size-[18px] shrink-0 transition-[stroke-width] duration-150',
          active && '[stroke-width:2.25]',
        )}
        aria-hidden
      />
      <span className={labelClasses(sidebarMode)}>{item.label}</span>
      {isUpcoming && (
        // A neutral capsule in the label's own face, like a sidebar badge.
        <span
          className={cn(
            labelClasses(sidebarMode),
            '-ml-1.5 flex-none rounded-full bg-(--brand-text)/[0.06] px-[5px] py-px text-[11px] font-medium leading-4',
          )}
        >
          Soon
        </span>
      )}
    </>
  );

  if (isDisabled) {
    return (
      <div
        data-row
        data-tip={`${item.label} - coming soon`}
        aria-disabled="true"
        // The capsule brings its own padding, so the row's right edge tightens to keep the longest label whole.
        className={cn(ROW_BASE, 'cursor-not-allowed pr-2 text-(--brand-text-muted)')}
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
      data-row
      data-tip={item.label}
      className={cn(
        ROW_BASE,
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-(--brand-bg)',
        // A selection marks a place in the list; it sits flat, it doesn't float.
        active
          ? 'bg-(--brand-primary) font-semibold text-white active:bg-(--brand-primary-hover)'
          : cn('font-normal', ROW_IDLE),
      )}
    >
      {content}
    </Link>
  );
}

/** A parent with no page of its own: a disclosure row over its children, open by default. */
function NavGroup({
  item,
  slug,
  pathname,
  currentMode,
  sidebarMode,
  onNavigate,
}: {
  item: DashboardNavItem;
  slug: string;
  pathname: string;
  currentMode: string;
  sidebarMode: SidebarMode;
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(true);
  const Icon = item.icon;
  const children = item.children ?? [];
  const childActive = children.some((child) => isItemActive(child, pathname, currentMode));

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-row
        data-tip={item.label}
        className={cn(
          ROW_BASE,
          'cursor-pointer',
          ROW_IDLE,
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-(--brand-bg)',
          // Folded over the current page, the group stands in for the hidden active row.
          !open && childActive && 'font-semibold text-(--brand-primary)',
        )}
      >
        <Icon className="size-[18px] shrink-0" aria-hidden />
        <span className={labelClasses(sidebarMode)}>{item.label}</span>
        <ChevronDown
          className={cn(
            labelClasses(sidebarMode),
            'size-4 flex-none transition-transform duration-150',
            !open && '-rotate-90',
          )}
          aria-hidden
        />
      </button>
      {open && (
        // The connector rule runs down the parent icon's centre (row margin +
        // padding + half the icon) and the children sit right of it, so an
        // active pill never covers the line. Only while labels show - a
        // collapsed rail has no column to indent into.
        <div
          className={cn(
            'flex flex-col gap-px border-l border-transparent',
            sidebarMode === 'expanded' && 'ml-[27px] border-(--brand-border)',
            sidebarMode === 'hover' &&
              cn(
                'transition-[margin,border-color] duration-200 motion-reduce:transition-none',
                'group-hover/rail:ml-[27px] group-hover/rail:border-(--brand-border)',
                'group-has-focus-visible/rail:ml-[27px] group-has-focus-visible/rail:border-(--brand-border)',
                HOVER_TIMING,
              ),
          )}
        >
          {children.map((child) => (
            <NavItemLink
              key={child.key}
              item={child}
              slug={slug}
              pathname={pathname}
              currentMode={currentMode}
              sidebarMode={sidebarMode}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </>
  );
}

function NavList({
  slug,
  pathname,
  currentMode,
  sidebarMode,
  onNavigate,
  tipHandlers,
}: {
  slug: string;
  pathname: string;
  currentMode: string;
  sidebarMode: SidebarMode;
  onNavigate?: () => void;
  tipHandlers?: ReturnType<typeof useRailTip>['handlers'];
}) {
  return (
    <nav
      className="flex flex-1 flex-col gap-px overflow-y-auto overflow-x-hidden py-2"
      aria-label="Dashboard sections"
      {...tipHandlers}
    >
      {DASHBOARD_NAV_GROUPS.map((group, groupIndex) => (
        <div key={group[0].key} className="flex flex-col gap-px">
          {groupIndex > 0 && <div aria-hidden className="mx-4 my-2 h-px bg-(--brand-border)" />}
          {group.map((item) =>
            item.children && !item.section ? (
              <NavGroup
                key={item.key}
                item={item}
                slug={slug}
                pathname={pathname}
                currentMode={currentMode}
                sidebarMode={sidebarMode}
                onNavigate={onNavigate}
              />
            ) : (
              <NavItemLink
                key={item.key}
                item={item}
                slug={slug}
                pathname={pathname}
                currentMode={currentMode}
                sidebarMode={sidebarMode}
                onNavigate={onNavigate}
              />
            ),
          )}
        </div>
      ))}
    </nav>
  );
}

/** ⌘\ on macOS, Ctrl+\ elsewhere, as the toggle's tooltip and aria-keyshortcuts say. */
const TOGGLE_SHORTCUT = 'Meta+Backslash Control+Backslash';

/**
 * One click shows or hides the labels, the common case; the small menu beside
 * it holds every mode, "Expand on hover" included.
 */
function SidebarModeControl({
  mode,
  onModeChange,
}: {
  mode: SidebarMode;
  onModeChange: (mode: SidebarMode) => void;
}) {
  const toggleLabel = mode === 'expanded' ? 'Collapse sidebar' : 'Expand sidebar';
  return (
    <div className="mt-auto flex items-center gap-1 px-2 py-2">
      <button
        type="button"
        onClick={() => onModeChange(mode === 'expanded' ? 'collapsed' : 'expanded')}
        aria-keyshortcuts={TOGGLE_SHORTCUT}
        data-row
        data-tip={`${toggleLabel} (⌘\\)`}
        className={cn(
          ROW_BASE,
          'mx-0 min-w-0 flex-1 cursor-pointer',
          ROW_IDLE,
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2 focus-visible:ring-offset-(--brand-bg)',
        )}
      >
        <PanelLeft className="size-[18px] shrink-0" aria-hidden />
        <span className={labelClasses(mode)}>{toggleLabel}</span>
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Sidebar options"
          className={cn(
            labelClasses(mode),
            'flex size-[34px] flex-none cursor-pointer items-center justify-center rounded-lg',
            ROW_IDLE,
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)',
            // Hidden with the labels: there is no room for it beside a collapsed icon.
            mode === 'collapsed' && 'hidden',
          )}
        >
          <Ellipsis className="size-4" aria-hidden />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="top"
          align="start"
          className="w-52 border-(--brand-border) text-(--brand-text)"
        >
          <DropdownMenuLabel className="px-3 py-1.5 text-xs font-medium text-(--brand-text-muted)">
            Sidebar
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
                className="cursor-pointer py-2 text-[13px] focus:bg-(--brand-text)/5 data-[state=checked]:font-semibold data-[state=checked]:text-(--brand-primary)"
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

/**
 * Collapsed, the rail is icons only: each row's name shows beside it, after a
 * short dwell for the pointer and at once for keyboard focus. Fixed-positioned,
 * because the rail clips everything past its edge.
 */
function useRailTip(enabled: boolean) {
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const show = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setTip({ text: el.dataset.tip ?? '', x: r.right + 8, y: r.top + r.height / 2 });
  };
  const hide = () => {
    clearTimeout(timer.current);
    setTip(null);
  };
  const row = (e: SyntheticEvent) => (e.target as HTMLElement).closest<HTMLElement>('[data-tip]');
  const handlers = enabled
    ? {
        onPointerOver: (e: SyntheticEvent) => {
          const el = row(e);
          clearTimeout(timer.current);
          if (el) timer.current = setTimeout(() => show(el), 300);
          else setTip(null);
        },
        onPointerLeave: hide,
        onFocus: (e: SyntheticEvent) => {
          const el = row(e);
          if (el && el.matches(':focus-visible')) show(el);
        },
        onBlur: hide,
      }
    : {};
  const node =
    enabled && tip ? (
      <div
        role="tooltip"
        className="pointer-events-none fixed z-50 -translate-y-1/2 rounded-md bg-(--brand-text) px-2 py-1 text-xs font-medium whitespace-nowrap text-white shadow-md"
        style={{ left: tip.x, top: tip.y }}
      >
        {tip.text}
      </div>
    ) : null;
  return { handlers, node };
}

/** Every focusable control inside `root`, in tab order. */
function focusables(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')];
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
  const tip = useRailTip(sidebarMode === 'collapsed');

  // ⌘\ / Ctrl+\ shows or hides the labels from anywhere on the page.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '\\' || !(e.metaKey || e.ctrlKey)) return;
      e.preventDefault();
      setSidebarMode(getSidebarMode() === 'expanded' ? 'collapsed' : 'expanded');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setSidebarMode]);

  // The drawer is modal while open: focus moves in, the page behind stops
  // scrolling, and focus returns to "Sections" when it closes.
  const triggerRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!mobileOpen) return;
    const trigger = triggerRef.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    drawerRef.current?.querySelector<HTMLElement>('button')?.focus();
    return () => {
      document.body.style.overflow = overflow;
      trigger?.focus();
    };
  }, [mobileOpen]);

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
            'border-r border-(--brand-border) bg-(--brand-bg)',
            'transition-[width,box-shadow,background-color] duration-200 ease-out motion-reduce:transition-none',
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
                'has-focus-visible:w-64 has-focus-visible:bg-(--brand-surface)',
                'has-focus-visible:shadow-[1px_0_2px_0_rgba(27,79,101,0.05),24px_0_32px_-16px_rgba(27,79,101,0.16)]',
                'delay-300 hover:delay-150 has-focus-visible:delay-0',
              ),
          )}
        >
          <NavList
            slug={slug}
            pathname={pathname}
            currentMode={currentMode}
            sidebarMode={sidebarMode}
            tipHandlers={tip.handlers}
          />
          <div className="contents" {...tip.handlers}>
            <SidebarModeControl mode={sidebarMode} onModeChange={setSidebarMode} />
          </div>
        </aside>
        {tip.node}
      </div>

      {/* Mobile section-nav bar - sits under the global top nav */}
      <div className="fixed inset-x-0 top-14 z-30 flex h-12 items-center border-b border-(--brand-border) bg-(--brand-surface) px-4 md:hidden">
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open section navigation"
          aria-expanded={mobileOpen}
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-(--brand-text-muted) hover:bg-(--brand-text)/5 hover:text-(--brand-text) active:bg-(--brand-text)/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
        >
          <Menu className="h-5 w-5" aria-hidden />
          Sections
        </button>
      </div>

      {/* Mobile off-canvas drawer - always labelled; the mode control is desktop-only.
          It stays mounted so it can slide out along the path it came in by; closed,
          it is inert (out of the tab order and the accessibility tree). */}
      <div
        className={cn(
          'fixed inset-0 z-50 md:hidden',
          // Hidden only once the slide-out ends; opening shows it at once, so focus can land.
          !mobileOpen && 'invisible transition-[visibility] duration-300',
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Dashboard sections"
        inert={!mobileOpen}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setMobileOpen(false);
          if (e.key !== 'Tab' || !drawerRef.current) return;
          // Tab cycles inside the drawer while it is open.
          const items = focusables(drawerRef.current);
          const first = items[0];
          const last = items[items.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }}
      >
        <div
          className={cn(
            'absolute inset-0 bg-(--brand-text)/30 backdrop-blur-sm transition-opacity duration-300',
            mobileOpen ? 'opacity-100' : 'opacity-0',
          )}
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
        <aside
          ref={drawerRef}
          className={cn(
            'absolute left-0 top-0 flex h-full w-72 flex-col border-r border-(--brand-border) bg-(--brand-bg) shadow-xl',
            // Critically damped from the left edge, and back out the same way; a fade under reduced motion.
            'transition-[translate,opacity] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
            'motion-reduce:translate-x-0 motion-reduce:transition-opacity',
            mobileOpen ? 'translate-x-0 opacity-100' : '-translate-x-full motion-reduce:opacity-0',
            // Rows reach the 44 px touch minimum and body-size text here; the desktop rail keeps 34 px and 14 px.
            '[&_[data-row]]:h-11 [&_[data-row]]:text-[15px]',
          )}
        >
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-(--brand-border) pr-2 pl-5">
            <span className="text-sm font-semibold text-(--brand-text)">Sections</span>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation menu"
              className="flex size-11 items-center justify-center rounded-lg text-(--brand-text-muted) hover:bg-(--brand-text)/5 hover:text-(--brand-text) active:bg-(--brand-text)/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
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
    </>
  );
}
