'use client';

import * as React from 'react';
import { Suspense } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { trialsApi, LiveTickerArticle, LiveTickerResult } from '@/lib/api';
import { ArrowUpRight, Newspaper, Calendar, ChevronDown } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { slugToCategory } from '@/lib/dashboard-constants';
import { cn } from '@/lib/utils';
import { useQueryParam } from '@/hooks/useQueryParam';
import { NCT_ID_PATTERN, trialRoute } from '@/lib/constants';
import { dayLabel } from '@/lib/day-label';
import { cleanTitle, readoutMetrics, sourceOf, splitValue, type NewsMetric } from '@/lib/live-news';

type FeedFilter = 'latest' | 'efficacy';

const isFeedFilter = (v: string): v is FeedFilter => v === 'latest' || v === 'efficacy';
/** "" is all months; otherwise "YYYY-MM". */
const isMonthKey = (v: string): v is string => v === '' || /^\d{4}-\d{2}$/.test(v);

const FEED_FILTER_OPTIONS: { value: FeedFilter; label: string }[] = [
  { value: 'latest', label: 'Latest' },
  { value: 'efficacy', label: 'Efficacy & Safety' },
];

type FeedItemData = { type: 'result'; value: LiveTickerResult } | { type: 'article'; value: LiveTickerArticle };

/** Readout values shown before "All N values". */
const PREVIEW_METRICS = 4;

function MetricGrid({ metrics }: { metrics: NewsMetric[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      {metrics.map((m, i) => {
        const { main, note } = splitValue(m.value);
        // Numbers read in mono; prose values ("not reached") stay in the UI face.
        const numeric = /^[<>≤≥=~.\d-]/.test(main);
        return (
          <div key={i} className="min-w-0">
            {m.label && <dt className="text-xs leading-snug break-words text-(--brand-text-muted)">{m.label}</dt>}
            <dd className="mt-0.5 break-words">
              <span
                className={cn('font-medium leading-snug text-(--brand-text) tabular-nums', numeric ? 'text-[15px]' : 'text-sm')}
                style={numeric ? { fontFamily: 'var(--font-mono)' } : undefined}
              >
                {main}
              </span>
              {note && <span className="mt-0.5 block text-xs leading-snug text-(--brand-text-muted)">{note}</span>}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function FeedItem({ item, categorySlug, showTag }: { item: FeedItemData; categorySlug: string; showTag: boolean }) {
  const [open, setOpen] = React.useState(false);
  const restId = React.useId();
  const { value } = item;
  const source = sourceOf(value.url);
  const title = cleanTitle(value.title, source);
  const nct = value.nct_ids?.[0];
  const metrics = item.type === 'result' ? readoutMetrics(item.value) : null;
  const all = metrics ? [...metrics.efficacy, ...metrics.safety] : [];

  return (
    <article className="group relative -mx-4 rounded-2xl px-4 py-5 transition-colors duration-100 hover:bg-(--brand-surface) has-[>h3_a:active]:bg-(--brand-accent-light)">
      <div
        className="flex items-center gap-2.5 text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)"
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {source && <span>{source}</span>}
        {metrics && showTag && (
          <span className="rounded-full bg-(--brand-accent-light) px-2 py-0.5 text-(--brand-primary)">Efficacy &amp; Safety</span>
        )}
      </div>
      <h3 className="mt-2 text-[17px] font-semibold leading-snug tracking-[-0.01em] text-(--brand-text)">
        {/* The link stretches over the whole row; the values and their toggle sit above it. */}
        <a
          href={value.url}
          target="_blank"
          rel="noopener noreferrer"
          className="after:absolute after:inset-0 after:rounded-2xl focus:outline-none focus-visible:after:ring-2 focus-visible:after:ring-(--brand-primary)"
        >
          {title}
          {/* The no-break space keeps the arrow on the title's last line instead of wrapping alone. */}
          {'\u00A0'}
          <ArrowUpRight
            className="inline h-4 w-4 align-[-2px] text-(--brand-primary) opacity-0 transition-opacity duration-100 group-hover:opacity-100 group-has-[a:focus-visible]:opacity-100"
            aria-hidden
          />
        </a>
      </h3>
      {nct && NCT_ID_PATTERN.test(nct) && (
        <Link
          href={trialRoute(nct, categorySlug)}
          className="relative z-10 mt-0.5 -mb-1 inline-block rounded py-1 text-xs font-medium text-(--brand-primary) underline decoration-(--brand-border) underline-offset-[3px] transition-colors hover:decoration-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)"
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {nct}
        </Link>
      )}
      {all.length > 0 && (
        <div className="relative z-10 mt-4">
          <MetricGrid metrics={all.slice(0, PREVIEW_METRICS)} />
          {all.length > PREVIEW_METRICS && (
            <>
              {/* The toggle stays where it was pressed; the rest opens below it. */}
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-controls={restId}
                className="-my-1 mt-2 inline-flex items-center gap-1 rounded-md py-1 text-sm font-medium text-(--brand-primary) hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2"
              >
                {open ? 'Show fewer values' : `All ${all.length} values`}
                <ChevronDown
                  className={cn('h-4 w-4 transition-transform duration-300 motion-reduce:transition-none', open && 'rotate-180')}
                  aria-hidden
                />
              </button>
              <div
                id={restId}
                inert={!open}
                className={cn(
                  'grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none',
                  open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
                )}
              >
                <div className="overflow-hidden">
                  <div className="pt-4">
                    <MetricGrid metrics={all.slice(PREVIEW_METRICS)} />
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </article>
  );
}

/** Placeholder rows in the feed's own layout, so nothing jumps when the items arrive. */
function FeedSkeleton() {
  const bar = 'rounded bg-(--brand-border)/60 motion-safe:animate-pulse';
  return (
    <div aria-busy="true" className="divide-y divide-(--brand-border)">
      <span className="sr-only" role="status">
        Loading latest articles…
      </span>
      {[2, 1].map((rows, g) => (
        <div key={g} aria-hidden className="grid grid-cols-1 gap-x-12 py-4 first:pt-0 md:grid-cols-[140px_minmax(0,1fr)]">
          <div className="pt-5">
            <div className={cn(bar, 'h-5 w-20')} />
            <div className={cn(bar, 'mt-2 h-3 w-24')} />
          </div>
          <div className="max-w-[880px]">
            {Array.from({ length: rows }, (_, i) => (
              <div key={i} className="py-5">
                <div className={cn(bar, 'h-3 w-28')} />
                <div className={cn(bar, 'mt-3 h-4 w-11/12')} />
                <div className={cn(bar, 'mt-2 h-4 w-2/3')} />
                <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
                  {Array.from({ length: 4 }, (_, j) => (
                    <div key={j}>
                      <div className={cn(bar, 'h-3 w-20')} />
                      <div className={cn(bar, 'mt-2 h-4 w-14')} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function LiveTickerContent() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['live-ticker', categorySlug],
    queryFn: () => trialsApi.getLiveTicker(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const hasArticles = (data?.articles?.length ?? 0) > 0;
  const hasResults = (data?.results?.length ?? 0) > 0;
  const isEmpty = !hasArticles && !hasResults;

  const [feedFilter, setFeedFilter] = useQueryParam<FeedFilter>('view', 'latest', isFeedFilter);
  const efficacyOnly = feedFilter === 'efficacy';
  const [selectedMonthKey, setSelectedMonthKey] = useQueryParam('month', '', isMonthKey);
  /** Every item of the current view, newest first. */
  const viewItems = React.useMemo(() => {
    if (!data) return [];
    const resultUrls = new Set(data.results.map((r) => r.url));
    const results: FeedItemData[] = data.results.map((value) => ({ type: 'result' as const, value }));
    const articles: FeedItemData[] = data.articles
      .filter((a) => !resultUrls.has(a.url))
      .map((value) => ({ type: 'article' as const, value }));
    const items = efficacyOnly ? results : [...results, ...articles];
    return items.sort((a, b) => b.value.date.localeCompare(a.value.date));
  }, [data, efficacyOnly]);

  const getMonthKey = (d: string) => d.slice(0, 7);
  const formatMonthLabel = (key: string) =>
    new Date(`${key}-01T00:00:00Z`).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });

  const availableMonths = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of viewItems) {
      const key = getMonthKey(item.value.date);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([key, count]) => ({ key, label: formatMonthLabel(key), count }));
  }, [viewItems]);

  const displayedItems = React.useMemo(
    () => (selectedMonthKey ? viewItems.filter((item) => getMonthKey(item.value.date) === selectedMonthKey) : viewItems),
    [viewItems, selectedMonthKey],
  );

  const days = React.useMemo(() => {
    const byDay = new Map<string, FeedItemData[]>();
    for (const item of displayedItems) {
      const key = item.value.date.slice(0, 10);
      byDay.set(key, [...(byDay.get(key) ?? []), item]);
    }
    return [...byDay.entries()];
  }, [displayedItems]);

  const selectedMonth = availableMonths.find((m) => m.key === selectedMonthKey);
  const monthChoices = [{ key: '', label: 'All months', count: viewItems.length }, ...availableMonths];

  // The shared dropdown brings arrow keys, type-ahead, focus return and the grow-from-trigger motion.
  const monthFilter = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Filter by month"
          className="flex h-[42px] min-w-48 items-center justify-between gap-3 rounded-full border border-(--brand-border) bg-(--brand-surface) pl-3.5 pr-3 text-left text-sm text-(--brand-text) transition-colors hover:border-(--brand-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) data-[state=open]:border-(--brand-primary)"
        >
          <span className="flex items-center gap-2 truncate">
            <Calendar className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
            {selectedMonth ? selectedMonth.label : 'All months'}
            {data && (
              <span className="text-(--brand-text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
                {selectedMonth ? selectedMonth.count : viewItems.length}
              </span>
            )}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-(--brand-text-muted)" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={6} className="max-h-72 w-64 overflow-y-auto rounded-xl border-(--brand-border)">
        <DropdownMenuRadioGroup value={selectedMonthKey} onValueChange={setSelectedMonthKey}>
          {monthChoices.map((m) => (
            <DropdownMenuRadioItem
              key={m.key || 'all'}
              value={m.key}
              className="gap-3 rounded-md py-2 pr-3 text-(--brand-text-muted) focus:bg-(--brand-bg) focus:text-(--brand-text) data-[state=checked]:bg-(--brand-accent-light) data-[state=checked]:font-medium data-[state=checked]:text-(--brand-primary)"
            >
              <span className="min-w-0 flex-1">{m.label}</span>
              <span className="text-xs" style={{ fontFamily: 'var(--font-mono)' }}>
                {m.count}
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={categoryName}
          title="Live News"
          description="Latest news, press releases, and efficacy & safety readouts across the treatment landscape."
          right={
            <div className="flex flex-wrap items-center gap-3">
              {monthFilter}
              <FilterChips label="VIEW" options={FEED_FILTER_OPTIONS} value={feedFilter} onChange={setFeedFilter} />
            </div>
          }
        />

        <div className="mt-10">
          {isLoading ? (
            <FeedSkeleton />
          ) : error ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-12 text-center">
              <p className="text-(--brand-text-muted)">Could not load live ticker. Please try again.</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : isEmpty ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-16 text-center">
              <Newspaper className="mx-auto h-12 w-12 text-(--brand-border)" aria-hidden />
              <p className="mt-4 font-medium text-(--brand-text)">No updates yet</p>
              <p className="mt-1 text-sm text-(--brand-text-muted)">
                Latest articles and efficacy & safety highlights will appear here for {categoryName}.
              </p>
            </div>
          ) : displayedItems.length === 0 ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) py-10 text-center">
              <p className="text-sm text-(--brand-text-muted)">
                {efficacyOnly ? 'No efficacy & safety items for this period.' : 'No articles in this month.'}
              </p>
              <button
                type="button"
                onClick={() => setSelectedMonthKey('')}
                className="mt-3 rounded text-sm font-medium text-(--brand-primary) hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1"
              >
                Show all months
              </button>
            </div>
          ) : (
            <div className="divide-y divide-(--brand-border)">
              {days.map(([date, items]) => {
                const { day, weekday } = dayLabel(date);
                return (
                  <section
                    key={date}
                    aria-label={`${weekday} ${day}`}
                    className="grid grid-cols-1 gap-x-12 py-4 first:pt-0 md:grid-cols-[140px_minmax(0,1fr)]"
                  >
                    <div className="pt-5 md:sticky md:top-20 md:self-start">
                      <p
                        className="text-[22px] font-semibold leading-none tracking-[-0.02em] text-(--brand-text)"
                        style={{ fontFamily: 'var(--font-display)' }}
                      >
                        {day}
                      </p>
                      <p className="mt-1.5 text-xs text-(--brand-text-muted)">{weekday}</p>
                    </div>
                    <div className="max-w-[880px]">
                      {items.map((item, i) => (
                        <FeedItem
                          key={`${item.type}-${item.value.url}-${i}`}
                          item={item}
                          categorySlug={categorySlug}
                          showTag={!efficacyOnly}
                        />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LiveTickerPage() {
  return (
    <Suspense fallback={null}>
      <LiveTickerContent />
    </Suspense>
  );
}
