'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useParams } from 'next/navigation';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { trialsApi, type LatestTrialUpdateItem } from '@/lib/api';
import { ChevronRight, Zap } from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { slugToCategory } from '@/lib/dashboard-constants';
import { trialRoute } from '@/lib/constants';
import { dayLabel } from '@/lib/day-label';
import { cn } from '@/lib/utils';
import { useQueryParam } from '@/hooks/useQueryParam';

type TimeWindow = '7' | '30' | '60' | '90';
type Kind = 'all' | 'new' | 'updated';

const WINDOWS: readonly TimeWindow[] = ['7', '30', '60', '90'];
const KINDS: readonly Kind[] = ['all', 'new', 'updated'];
const isWindow = (v: string): v is TimeWindow => (WINDOWS as readonly string[]).includes(v);
const isKind = (v: string): v is Kind => (KINDS as readonly string[]).includes(v);

const WINDOW_OPTIONS: { value: TimeWindow; label: string }[] = [
  { value: '7', label: '7d' },
  { value: '30', label: '30d' },
  { value: '60', label: '60d' },
  { value: '90', label: '90d' },
];

// ponytail: counts come from the fetched list; past this many changes in one window
// they would undercount, so the page says so (a count query is the upgrade path).
const MAX_ROWS = 1000;

function UpdateRow({ item, categorySlug }: { item: LatestTrialUpdateItem; categorySlug: string }) {
  const isNew = item.update_type === 'new';
  return (
    <li>
      <Link
        href={trialRoute(item.nct_id, categorySlug)}
        className="group -mx-4 flex items-start gap-4 rounded-2xl px-4 py-4 transition-colors duration-100 hover:bg-(--brand-surface) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) active:bg-(--brand-accent-light)"
      >
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-[-0.005em] text-(--brand-text)">
            {item.title || item.nct_id}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-(--brand-text-muted)">
            {isNew && (
              <span
                className="rounded-full bg-(--brand-accent-light) px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-primary)"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                New
              </span>
            )}
            <span style={{ fontFamily: 'var(--font-mono)' }}>{item.nct_id}</span>
            {item.sponsor_name && (
              <>
                <span aria-hidden className="text-(--brand-border)">
                  ·
                </span>
                <span className="min-w-0 truncate">{item.sponsor_name}</span>
              </>
            )}
          </div>
        </div>
        <ChevronRight
          className="mt-0.5 h-4 w-4 shrink-0 text-(--brand-primary) opacity-0 transition-opacity duration-100 group-hover:opacity-100 group-focus-visible:opacity-100"
          aria-hidden
        />
      </Link>
    </li>
  );
}

/** Placeholder rows in the list's own layout, so nothing jumps when the trials arrive. */
function ListSkeleton() {
  const bar = 'rounded bg-(--brand-border)/60 motion-safe:animate-pulse';
  return (
    <div aria-busy="true" className="divide-y divide-(--brand-border)">
      <span className="sr-only" role="status">
        Loading trial updates…
      </span>
      {[3, 2].map((rows, g) => (
        <div key={g} aria-hidden className="grid grid-cols-1 gap-x-12 py-4 first:pt-0 md:grid-cols-[140px_minmax(0,1fr)]">
          <div className="pt-4">
            <div className={cn(bar, 'h-5 w-20')} />
            <div className={cn(bar, 'mt-2 h-3 w-24')} />
          </div>
          <div className="max-w-[880px]">
            {Array.from({ length: rows }, (_, i) => (
              <div key={i} className="py-4">
                <div className={cn(bar, 'h-4 w-10/12')} />
                <div className={cn(bar, 'mt-2.5 h-3 w-64')} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TrialUpdatesContent() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const [timeRange, setTimeRange] = useQueryParam('window', '90', isWindow);
  const [kind, setKind] = useQueryParam('show', 'all', isKind);

  const { data: landscapeStats } = useQuery({
    queryKey: ['disease-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    staleTime: 5 * 60 * 1000,
  });
  const totalTrials = landscapeStats?.status?.['Overall Status'] ?? null;

  const days = Number(timeRange);
  const { data: updatesData, isLoading, isPlaceholderData, error, refetch } = useQuery({
    queryKey: ['latest-trial-updates', categorySlug, MAX_ROWS, days],
    queryFn: () => trialsApi.getLatestTrialUpdates(categorySlug, MAX_ROWS, days),
    enabled: Boolean(categorySlug),
    staleTime: 5 * 60 * 1000,
    // Keep the current list on screen while another window loads, instead of blanking it.
    placeholderData: keepPreviousData,
  });

  const updates = React.useMemo(() => updatesData?.trials ?? [], [updatesData]);
  const newCount = updates.filter((u) => u.update_type === 'new').length;
  const counts: Record<Kind, number> = { all: updates.length, new: newCount, updated: updates.length - newCount };

  const kindOptions: { value: Kind; label: string; count: number }[] = [
    { value: 'all', label: 'All', count: counts.all },
    { value: 'new', label: 'New', count: counts.new },
    { value: 'updated', label: 'Updated', count: counts.updated },
  ];

  const daysGrouped = React.useMemo(() => {
    const byDay = new Map<string, LatestTrialUpdateItem[]>();
    for (const item of updates) {
      if (kind !== 'all' && item.update_type !== kind) continue;
      const key = item.date_iso.slice(0, 10);
      byDay.set(key, [...(byDay.get(key) ?? []), item]);
    }
    return [...byDay.entries()];
  }, [updates, kind]);

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={categoryName}
          title="Trial Updates"
          description="Newly registered trials and recent record changes, ordered by the most recent activity."
          right={<FilterChips label="WINDOW" options={WINDOW_OPTIONS} value={timeRange} onChange={setTimeRange} />}
        />

        {updatesData && (
          <div className="mt-8 flex flex-col items-start gap-3">
            <p className="text-[15px] leading-relaxed text-(--brand-text-muted) tabular-nums">
              <span className="font-semibold text-(--brand-text)">{counts.all.toLocaleString()}</span>
              {totalTrials != null && ` of ${totalTrials.toLocaleString()}`}{' '}
              trials changed in the last {days} days
              {counts.all >= MAX_ROWS && ' (showing the most recent ' + MAX_ROWS.toLocaleString() + ')'}
            </p>
            <FilterChips label="SHOW" options={kindOptions} value={kind} onChange={setKind} />
          </div>
        )}

        <div
          className={cn('mt-8 transition-opacity duration-150', isPlaceholderData && 'opacity-60')}
          aria-busy={isPlaceholderData || undefined}
        >
          {isLoading ? (
            <ListSkeleton />
          ) : error ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-8 text-center">
              <p className="text-(--brand-text-muted)">Could not load trial updates. Please try again.</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : daysGrouped.length === 0 ? (
            <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-12 text-center">
              <Zap className="mx-auto h-12 w-12 text-(--brand-border)" aria-hidden />
              <p className="mt-4 font-medium text-(--brand-text)">
                {updates.length === 0 ? 'No trial updates in this window' : `No ${kind} trials in this window`}
              </p>
              <p className="mt-1 text-sm text-(--brand-text-muted)">
                Try a longer window. New records and updates for {categoryName} appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-(--brand-border)">
              {daysGrouped.map(([date, items]) => {
                const { day, weekday } = dayLabel(date);
                return (
                  <section
                    key={date}
                    aria-label={`${weekday} ${day}`}
                    className="grid grid-cols-1 gap-x-12 py-4 first:pt-0 md:grid-cols-[140px_minmax(0,1fr)]"
                  >
                    <div className="pt-4 md:sticky md:top-20 md:self-start">
                      <p
                        className="text-[22px] font-semibold leading-none tracking-[-0.02em] text-(--brand-text)"
                        style={{ fontFamily: 'var(--font-display)' }}
                      >
                        {day}
                      </p>
                      <p className="mt-1.5 text-xs text-(--brand-text-muted)">{weekday}</p>
                      <p className="mt-2 text-xs text-(--brand-text-muted)">
                        <span className="font-medium text-(--brand-text)">{items.length}</span>{' '}
                        {items.length === 1 ? 'trial' : 'trials'}
                      </p>
                    </div>
                    <ul className="max-w-[880px]">
                      {items.map((item) => (
                        <UpdateRow key={item.nct_id} item={item} categorySlug={categorySlug} />
                      ))}
                    </ul>
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

export default function TrialUpdatesPage() {
  return (
    <Suspense fallback={null}>
      <TrialUpdatesContent />
    </Suspense>
  );
}
