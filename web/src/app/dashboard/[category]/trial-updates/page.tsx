'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { trialsApi, type LatestTrialUpdateItem } from '@/lib/api';
import { Loader2, Zap, Lightbulb } from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { FilterChips } from '@/components/dashboard/FilterChips';
import { slugToCategory } from '@/lib/dashboard-constants';
import { cn } from '@/lib/utils';

type TimeWindow = '7' | '30' | '60' | '90';

const WINDOW_OPTIONS: { value: TimeWindow; label: string }[] = [
  { value: '7', label: '7d' },
  { value: '30', label: '30d' },
  { value: '60', label: '60d' },
  { value: '90', label: '90d' },
];

export default function TrialUpdatesPage() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const [timeRange, setTimeRange] = React.useState<TimeWindow>('90');

  const { data: landscapeStats } = useQuery({
    queryKey: ['disease-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const totalTrialsExamined = landscapeStats?.status?.["Overall Status"] ?? null;

  const days = Number(timeRange);
  const { data: updatesCount } = useQuery({
    queryKey: ['trial-updates-count', categorySlug, days],
    queryFn: () => trialsApi.getTrialUpdatesCount(categorySlug!, days),
    enabled: Boolean(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const { data: updatesData, isLoading, error, refetch } = useQuery({
    queryKey: ['latest-trial-updates', categorySlug, 200, days],
    queryFn: () => trialsApi.getLatestTrialUpdates(categorySlug, 200, days),
    enabled: Boolean(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const updates = updatesData?.trials ?? [];

  return (
    <div className="min-h-screen bg-(--brand-bg)">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          category={categoryName}
          title="Trial Updates"
          description="Newly registered trials and recent record changes, ordered by the most recent activity."
          right={
            <FilterChips
              label="WINDOW"
              options={WINDOW_OPTIONS}
              value={timeRange}
              onChange={setTimeRange}
            />
          }
        />

        {/* KPI summary */}
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-5 shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50">
                <Zap className="h-5 w-5 text-amber-500" aria-hidden />
              </div>
              <div className="min-w-0">
                <div
                  className="text-2xl font-bold leading-none tracking-tight text-(--brand-text)"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {updatesCount == null
                    ? <span className="text-(--brand-border)">—</span>
                    : updatesCount.new_records_added.toLocaleString()}
                </div>
                <span className="mt-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">
                  New Records
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-5 shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                <Lightbulb className="h-5 w-5 text-blue-500" aria-hidden />
              </div>
              <div className="min-w-0">
                <div
                  className="text-2xl font-bold leading-none tracking-tight text-(--brand-text)"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {updatesCount == null
                    ? <span className="text-(--brand-border)">—</span>
                    : updatesCount.updates.toLocaleString()}
                </div>
                <span className="mt-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">
                  Updates
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-(--brand-border) bg-(--brand-surface) p-5 shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-(--brand-accent-light)">
                <Zap className="h-5 w-5 text-(--brand-primary)" aria-hidden />
              </div>
              <div className="min-w-0">
                <div
                  className="text-2xl font-bold leading-none tracking-tight text-(--brand-text)"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {totalTrialsExamined == null
                    ? <span className="text-(--brand-border)">—</span>
                    : totalTrialsExamined.toLocaleString()}
                </div>
                <span className="mt-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">
                  Total Examined
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Updates table */}
        <div className="mt-6 overflow-hidden rounded-2xl border border-(--brand-border) bg-(--brand-surface) shadow-[0_1px_2px_rgba(16,43,54,0.04)]">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-10 w-10 animate-spin text-(--brand-text-muted)" aria-hidden />
              <p className="mt-4 text-sm text-(--brand-text-muted)">Loading trial updates…</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <p className="text-(--brand-text-muted)">Could not load trial updates. Please try again.</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : updates.length === 0 ? (
            <div className="p-12 text-center">
              <Zap className="mx-auto h-12 w-12 text-(--brand-border)" aria-hidden />
              <p className="mt-4 font-medium text-(--brand-text)">No trial updates yet</p>
              <p className="mt-1 text-sm text-(--brand-text-muted)">
                New records and updates for {categoryName} will appear here.
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-[110px_1fr_96px] items-center gap-4 border-b border-(--brand-border) bg-(--brand-bg) px-5 py-2.5">
                <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Date</span>
                <span className="min-w-0 text-[10px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Record</span>
                <span className="shrink-0 text-[10px] font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)">Type</span>
              </div>
              <ul className="divide-y divide-(--brand-border)">
                {updates.map((item: LatestTrialUpdateItem) => (
                  <li key={item.nct_id} className="group">
                    <Link
                      href={`/trial/nct/${item.nct_id}?category=${categorySlug}`}
                      className="grid grid-cols-[110px_1fr_96px] items-center gap-4 px-5 py-3.5 text-left transition-colors hover:bg-(--brand-accent-light)"
                    >
                      <span
                        className="shrink-0 text-xs font-medium text-(--brand-text-muted)"
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {item.date_iso
                          ? new Date(item.date_iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                          : 'Unknown'}
                      </span>
                      <div className="min-w-0">
                        <span className="line-clamp-1 text-sm font-semibold leading-snug text-(--brand-text) transition-colors group-hover:text-(--brand-primary)">
                          {item.title || item.nct_id}
                        </span>
                        <div className="mt-0.5 flex items-center gap-2">
                          {item.nct_id && (
                            <span
                              className="text-[10px] text-(--brand-text-muted)"
                              style={{ fontFamily: 'var(--font-mono)' }}
                            >
                              {item.nct_id}
                            </span>
                          )}
                          {item.sponsor_name && (
                            <>
                              <span className="text-[10px] text-(--brand-border)">·</span>
                              <span className="truncate text-[10px] text-(--brand-text-muted)">{item.sponsor_name}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={cn(
                          'h-1.5 w-1.5 shrink-0 rounded-full',
                          item.update_type === 'new' ? 'bg-amber-400' : 'bg-(--brand-primary)'
                        )} />
                        <span className={cn(
                          'text-xs font-medium',
                          item.update_type === 'new' ? 'text-amber-700' : 'text-(--brand-primary)'
                        )}>
                          {item.update_type === 'new' ? 'New' : 'Updated'}
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
