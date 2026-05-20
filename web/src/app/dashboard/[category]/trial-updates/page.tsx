'use client';

import * as React from 'react';
import { useSession } from "@/lib/supabase/hooks";
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { UserMenu } from '@/components/user-menu';
import { Button } from '@/components/ui/button';
import { trialsApi, type LatestTrialUpdateItem } from '@/lib/api';
import { Loader2, Zap, Lightbulb } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';
import { cn } from '@/lib/utils';

const CATEGORY_SLUG_MAP: Record<string, string> = {
  'cutaneous-melanoma': 'Cutaneous/Metastatic Melanoma',
  'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous Melanoma with Brain/CNS Metastasis',
  'uveal-melanoma': 'Uveal Melanoma',
  'mucosal-melanoma': 'Mucosal Melanoma',
  'acral-melanoma': 'Acral Melanoma',
  'basal-cell-carcinoma': 'Basal Cell Carcinoma',
  'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
};

function slugToCategory(slug: string): string {
  return CATEGORY_SLUG_MAP[slug] || slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export default function TrialUpdatesPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const handleCancerTypeChange = React.useCallback(
    (slug: string) => { router.push(`/dashboard/${slug}/trial-updates`); },
    [router]
  );

  type TimeWindow = 7 | 30 | 60 | 90;
  const [timeRange, setTimeRange] = React.useState<TimeWindow>(90);

const { data: landscapeStats } = useQuery({
    queryKey: ['disease-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const totalTrialsExamined = landscapeStats?.status?.["Overall Status"] ?? null;

  const days = timeRange;
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
    <div className="flex flex-col h-screen w-full bg-slate-100 overflow-hidden">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="w-full px-8">
          <div className="flex items-center justify-between h-14 gap-4">
            <div className="flex items-center gap-4">
              <Link href="/" className="brand flex-shrink-0">
                <Logo height={32} />
                <span className="brand-text text-lg">bi<span className="brand-o">o</span>nocular</span>
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <DashboardNavLink />
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={(session.user.user_metadata?.full_name as string) || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-y-auto overflow-x-hidden px-2 pt-2 pb-4 md:px-4 md:pt-4 md:pb-6 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          <DashboardGlobalHeader
            cancerTypeSlug={categorySlug}
            onCancerTypeChange={handleCancerTypeChange}
          />
        </div>

        <div className="w-full bg-white rounded-lg shadow min-h-0 min-w-0">
          {/* Module header — title + time range tabs */}
          <div className="px-4 sm:px-6 lg:px-8 pt-3 pb-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 shrink-0">
            <h2 className="text-2xl font-medium tracking-wide text-sky-700">Trial Updates</h2>
            <div role="tablist" aria-label="Time range" className="inline-flex items-center gap-0.5 p-0.5 bg-slate-100 border border-slate-200 rounded-lg shrink-0">
              {([7, 30, 60, 90] as const).map((d) => {
                const active = timeRange === d;
                return (
                  <button
                    key={d}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setTimeRange(d)}
                    className={cn(
                      'text-[10px] font-bold tracking-widest px-2 py-1 rounded uppercase transition-colors',
                      active
                        ? 'bg-white text-(--brand-primary) shadow-sm'
                        : 'text-slate-500 hover:text-slate-700',
                    )}
                  >
                    {d}D
                  </button>
                );
              })}
            </div>
          </div>

          {/* KPI row */}
          {totalTrialsExamined != null && (
            <div className="flex items-center justify-center px-4 py-3 border-b border-(--brand-border)">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                Total Examined:{' '}
                <span className="text-base font-bold text-slate-800 tabular-nums">{totalTrialsExamined.toLocaleString()}</span>
              </span>
            </div>
          )}
          <div className="flex divide-x divide-(--brand-border) border-b border-(--brand-border) shrink-0">
            <div className="flex-1 flex flex-row items-center justify-center px-5 py-3 gap-3 min-w-0">
              <div className="rounded-xl bg-amber-50 p-2.5 shrink-0 flex items-center justify-center">
                <Zap className="h-5 w-5 text-amber-500" />
              </div>
              <div className="flex flex-col min-w-0">
                <div className="text-3xl font-extrabold tabular-nums text-slate-900 leading-none tracking-tight">
                  {updatesCount == null
                    ? <span className="text-slate-200">—</span>
                    : updatesCount.new_records_added.toLocaleString()}
                </div>
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.12em] mt-1">New Records</span>
              </div>
            </div>
            <div className="flex-1 flex flex-row items-center justify-center px-5 py-3 gap-3 min-w-0">
              <div className="rounded-xl bg-blue-50 p-2.5 shrink-0 flex items-center justify-center">
                <Lightbulb className="h-5 w-5 text-blue-500" />
              </div>
              <div className="flex flex-col min-w-0">
                <div className="text-3xl font-extrabold tabular-nums text-slate-900 leading-none tracking-tight">
                  {updatesCount == null
                    ? <span className="text-slate-200">—</span>
                    : updatesCount.updates.toLocaleString()}
                </div>
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.12em] mt-1">Updates</span>
              </div>
            </div>
          </div>

          {/* Updates table */}
          <div className="flex-1 min-h-0 overflow-auto">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="h-10 w-10 animate-spin text-slate-400" aria-hidden />
                <p className="mt-4 text-sm text-slate-500">Loading trial updates…</p>
              </div>
            ) : error ? (
              <div className="p-8 text-center">
                <p className="text-slate-600">Could not load trial updates. Please try again.</p>
                <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : updates.length === 0 ? (
              <div className="p-12 text-center">
                <Zap className="mx-auto h-12 w-12 text-slate-300" aria-hidden />
                <p className="mt-4 font-medium text-slate-600">No trial updates yet</p>
                <p className="mt-1 text-sm text-slate-500">
                  New records and updates for {categoryName} will appear here.
                </p>
              </div>
            ) : (
              <>
                <div className="sticky top-0 z-10 grid grid-cols-[96px_1fr_88px] items-center gap-4 px-4 pr-8 py-2.5 bg-(--brand-bg) border-b border-(--brand-border)">
                  <span className="text-[10px] font-bold text-(--brand-text-muted) uppercase tracking-widest">Date</span>
                  <span className="text-[10px] font-bold text-(--brand-text-muted) uppercase tracking-widest min-w-0">Record</span>
                  <span className="text-[10px] font-bold text-(--brand-text-muted) uppercase tracking-widest shrink-0">Type</span>
                </div>
                <ul className="divide-y divide-(--brand-border)">
                  {updates.map((item: LatestTrialUpdateItem) => (
                    <li key={item.nct_id} className="group">
                      <Link
                        href={`/trial/nct/${item.nct_id}?category=${categorySlug}`}
                        className="grid grid-cols-[96px_1fr_88px] items-center gap-4 px-4 pr-8 py-3 hover:bg-(--brand-accent-light) transition-colors text-left"
                      >
                        <span className="shrink-0 text-xs font-medium text-(--brand-text-muted) tabular-nums">
                          {item.date_iso
                            ? new Date(item.date_iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                            : 'Unknown'}
                        </span>
                        <div className="min-w-0">
                          <span className="text-sm font-semibold text-(--brand-text) group-hover:text-(--brand-primary) transition-colors line-clamp-1 leading-snug">
                            {item.title || item.nct_id}
                          </span>
                          <div className="flex items-center gap-2 mt-0.5">
                            {item.nct_id && (
                              <span className="text-[10px] font-mono text-(--brand-text-muted)">{item.nct_id}</span>
                            )}
                            {item.sponsor_name && (
                              <>
                                <span className="text-slate-200 text-[10px]">·</span>
                                <span className="text-[10px] text-(--brand-text-muted) truncate">{item.sponsor_name}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={cn(
                            'w-1.5 h-1.5 rounded-full shrink-0 -ml-3',
                            item.update_type === 'new' ? 'bg-amber-400' : 'bg-sky-400'
                          )} />
                          <span className={cn(
                            'text-xs font-medium',
                            item.update_type === 'new' ? 'text-amber-700' : 'text-sky-700'
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
      </main>
    </div>
  );
}
