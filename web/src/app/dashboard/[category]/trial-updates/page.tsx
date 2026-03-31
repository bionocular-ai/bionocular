'use client';

import * as React from 'react';
import { useSession } from "@/lib/supabase/hooks";
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { UserMenu } from '@/components/user-menu';
import { Button } from '@/components/ui/button';
import { trialsApi, type LatestTrialUpdateItem } from '@/lib/api';
import { Loader2, ChevronDown, Zap, Lightbulb, Maximize2 } from 'lucide-react';
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

  const [timeRange, setTimeRange] = React.useState<string>('30');

  const handleCancerTypeChange = React.useCallback(
    (slug: string) => {
      router.push(`/dashboard/${slug}/trial-updates`);
    },
    [router]
  );

  const { data: landscapeStats } = useQuery({
    queryKey: ['disease-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    staleTime: 5 * 60 * 1000,
  });

  const totalTrialsExamined = landscapeStats?.status?.["Overall Status"] ?? null;

  const days = parseInt(timeRange, 10) || 30;
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
      <header className="bg-white border-b border-slate-200 shrink-0 z-50">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 gap-3">
            <Link href="/" className="brand flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo height={32} />
              <span className="brand-text dashboard-brand-text">
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              <DashboardNavLink />
              {session?.user && (
                <UserMenu
                  email={session.user.email || null}
                  name={session.user.user_metadata?.full_name || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-2 pt-2 pb-0 md:px-4 md:pt-4 md:pb-0 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          <DashboardGlobalHeader
            cancerTypeSlug={categorySlug}
            onCancerTypeChange={handleCancerTypeChange}
          />
        </div>
        <div className="flex-1 flex flex-col min-h-0 min-w-0 w-full bg-white rounded-lg shadow overflow-hidden">
          <section className="flex-1 flex flex-col min-h-0 bg-white overflow-hidden">
            <div className="px-4 sm:px-6 lg:px-8 pt-4 pb-4 flex-1 flex flex-col min-h-0 overflow-hidden">
              {/* Top context + header row */}
              {totalTrialsExamined != null && (
                <p className="text-sm font-medium text-slate-500 mb-3">
                  Total Trials Examined: <span className="tabular-nums font-semibold text-slate-700">{totalTrialsExamined.toLocaleString()}</span>
                </p>
              )}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shrink-0 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-5 shrink-0 bg-blue-500 rounded-full" />
                  <h2 className="text-lg font-bold tracking-[0.12em] uppercase text-slate-700">Trial Updates</h2>
                </div>
                <div className="relative flex items-center gap-2">
                  <label htmlFor="trial-updates-time" className="text-sm font-medium text-slate-600">
                    Time range
                  </label>
                  <select
                    id="trial-updates-time"
                    aria-label="Time range"
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                    className="text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg pl-3 pr-8 py-2 appearance-none cursor-pointer hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  >
                    <option value="7">Past 7 Days</option>
                    <option value="30">Past 30 Days</option>
                    <option value="90">Past 90 Days</option>
                  </select>
                  <ChevronDown className="h-4 w-4 text-slate-500 pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2" aria-hidden />
                </div>
              </div>

              {/* KPI cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 shrink-0 mb-5">
                <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-amber-50 to-white p-4 shadow-sm">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-amber-100 p-2.5">
                      <Zap className="h-5 w-5 text-amber-600" aria-hidden />
                    </div>
                    <div className="min-w-0">
                      <p className="text-2xl font-bold tabular-nums text-slate-900">
                        {updatesCount ? updatesCount.new_records_added.toLocaleString() : '—'}
                      </p>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-0.5">New Records Added</p>
                      <p className="text-[11px] text-slate-400 mt-1">Past {days} days</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-sky-50 to-white p-4 shadow-sm">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-sky-100 p-2.5">
                      <Lightbulb className="h-5 w-5 text-sky-600" aria-hidden />
                    </div>
                    <div className="min-w-0">
                      <p className="text-2xl font-bold tabular-nums text-slate-900">
                        {updatesCount ? updatesCount.updates.toLocaleString() : '—'}
                      </p>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-0.5">Updates</p>
                      <p className="text-[11px] text-slate-400 mt-1">Past {days} days</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Updates table */}
              <div className="flex-1 min-h-0 overflow-auto border border-slate-200 rounded-xl">
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
                    <div className="sticky top-0 z-10 grid grid-cols-[90px_1fr_auto] items-center gap-4 px-4 py-3 bg-slate-50 border-b border-slate-200">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Date</span>
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest min-w-0">Record Name</span>
                      <div className="flex items-center justify-between gap-2 min-w-0">
                        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest shrink-0">Update</span>
                        <Link
                          href={`/dashboard/${categorySlug}`}
                          className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
                          aria-label="Open full dashboard"
                        >
                          <Maximize2 className="h-4 w-4" />
                        </Link>
                      </div>
                    </div>
                    <ul className="divide-y divide-slate-100">
                      {updates.map((item: LatestTrialUpdateItem) => (
                        <li key={item.nct_id} className="group">
                          <Link
                            href={`/trial/nct/${item.nct_id}?category=${categorySlug}`}
                            className="grid grid-cols-[90px_1fr_auto] items-start sm:items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
                          >
                            <span className="shrink-0 text-xs font-medium text-slate-500 tabular-nums pt-0.5 sm:pt-0">
                              {item.date_iso
                                ? new Date(item.date_iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                                : 'Unknown'}
                            </span>
                            <div className="min-w-0 py-1 sm:py-0">
                              <span className="text-sm font-medium text-blue-600 underline decoration-blue-600/40 underline-offset-2 group-hover:decoration-blue-600 line-clamp-2">
                                {item.title || item.nct_id}
                              </span>
                              {item.sponsor_name && (
                                <p className="text-xs text-slate-500 mt-0.5 truncate">{item.sponsor_name}</p>
                              )}
                            </div>
                            <span
                              className={cn(
                                'shrink-0 self-center inline-flex items-center rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider',
                                item.update_type === 'new'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-slate-100 text-slate-700'
                              )}
                            >
                              {item.update_type === 'new' ? 'New' : 'Updated'}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
