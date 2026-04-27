'use client';

import * as React from 'react';
import { useSession } from "@/lib/supabase/hooks";
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserMenu } from '@/components/user-menu';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { Logo } from '@/components/Logo';
import Link from 'next/link';
import {
  Bar,
  BarChart as RechartsBarChart,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ArrowUpRight, Loader2, Bell, Send, Newspaper, Zap, Lightbulb, Maximize2 } from 'lucide-react';
import { trialsApi, analyticsApi, type LiveTickerArticle, type LiveTickerResult } from '@/lib/api';
import { cn } from '@/lib/utils';
import { PHASE_OPTIONS } from '@/lib/dashboard-constants';
import { TrialCard } from '@/components/dashboard/TrialCard';
import type { BubbleChartDataPoint, HeadToHeadDataPoint } from '@/types/analytics';
import BubbleChart from '@/components/charts/BubbleChart';
import BarChart from '@/components/charts/BarChart';

// Mapping of slugs to category names
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
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** Merkel Cell Carcinoma — Phase 2 & 3 trials (from ClinicalTrials.gov) */
const MCC_REGULATORY_TRIALS = [
  { label: 'Pembro (STAMP)', nct: 'NCT03712605', start: 2018.8, end: 2026.9, color: '#1d6fa4' },
  { label: 'Avelumab (I-MAT)', nct: 'NCT04291885', start: 2020.8, end: 2030.3, color: '#6a9e77' },
  { label: 'Vidutolimod + Cemipl.', nct: 'NCT04916002', start: 2021.5, end: 2024.8, color: '#d97141' },
  { label: 'Neoadjuv. PD-1', nct: 'NCT05496036', start: 2023.1, end: 2027.7, color: '#7059a6' },
  { label: 'Nivolumab + Relatlimab', nct: 'NCT06151236', start: 2024.2, end: 2034.3, color: '#b94040' },
];

// Reusable Module Wrapper with modern styling
function SnapshotModule({
  title,
  href,
  children,
  onNavigate,
  headerRight,
  hideNav = false,
  dark = false,
  flatDarkHeader = false,
  className = "",
}: {
  title: React.ReactNode;
  href?: string;
  children: React.ReactNode;
  onNavigate?: () => void;
  headerRight?: React.ReactNode;
  hideNav?: boolean;
  dark?: boolean;
  flatDarkHeader?: boolean;
  className?: string;
}) {
  const router = useRouter();

  const handleNav = () => {
    if (onNavigate) onNavigate();
    else if (href) router.push(href);
  };

  const headerBg = dark
    ? (flatDarkHeader ? "bg-transparent" : "bg-gradient-to-r from-white/10 to-transparent")
    : "bg-[var(--brand-bg)] border-b border-[var(--brand-border)]";

  return (
    <Card className={`flex flex-col overflow-hidden h-full bg-white border border-[var(--brand-border)] shadow-md ${className}`}>
      <CardHeader className={`flex flex-row items-center justify-between h-[clamp(38px,3.6vh,46px)] py-0 px-4 shrink-0 ${headerBg}`}>
        <CardTitle className={`text-[12px] font-bold tracking-[0.08em] uppercase flex items-center gap-2 min-w-0 truncate ${dark ? "text-slate-200" : "text-[var(--brand-text)]"}`}>
           <div className="w-1.5 h-3.5 shrink-0 bg-[var(--brand-primary)] rounded-full" />
           <span className="truncate">{title}</span>
        </CardTitle>
        {headerRight ?? (!hideNav && (href || onNavigate) && (
          <button
            type="button"
            onClick={handleNav}
            className={`p-1.5 rounded-full transition-all active:scale-95 ${dark ? "text-slate-400 hover:text-[var(--brand-accent)] hover:bg-white/10" : "text-[var(--brand-text-muted)] hover:text-[var(--brand-primary)] hover:bg-[var(--brand-accent-light)]"}`}
            aria-label={`Open ${title}`}
          >
            <ArrowUpRight className="h-4 w-4" />
          </button>
        ))}
      </CardHeader>
      <CardContent className="p-[clamp(12px,1.6vw,20px)] flex-1 flex flex-col min-h-0 overflow-hidden">
        {children}
      </CardContent>
    </Card>
  );
}

export default function CancerDashboardSnapshot() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  const [pipelineSponsor, setPipelineSponsor] = React.useState<'Industry' | 'Non-Industry'>('Industry');

  type TrialUpdatesWindow = 7 | 30 | 60 | 90;
  const [trialUpdatesDays, setTrialUpdatesDays] = React.useState<TrialUpdatesWindow>(60);

  // Fetch a snapshot of trial cards (same filter as landscape: Sponsor type = Industry)
  const { data: trialsData, isLoading: trialsLoading } = useQuery({
    queryKey: ['dashboard-snapshot-trials', categorySlug],
    queryFn: () =>
      trialsApi.getDashboardTrials(categorySlug, {
        limit: 9,
        open_fraction: 0.7,
        sponsor_type: ['Industry'],
      }),
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Fetch landscape stats (overall)
  const { data: landscapeStats, isLoading: statsLoading } = useQuery({
    queryKey: ['disease-stats', categorySlug],
    queryFn: () => trialsApi.getDiseaseLandscapeStats(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Pipeline Health: phase distribution for the currently-selected sponsor type
  const {
    data: pipelineStats,
    isLoading: pipelineStatsLoading,
    isError: pipelineStatsError,
  } = useQuery({
    queryKey: ['disease-stats', categorySlug, pipelineSponsor],
    queryFn: () =>
      trialsApi.getDiseaseLandscapeStats(categorySlug, {
        sponsor_type: pipelineSponsor,
      }),
    enabled: Boolean(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Fetch trial updates count (New Records Added + Updates in selected window, from ClinicalTrials.gov API dates)
  const { data: trialUpdatesCount, isFetching: trialUpdatesCountFetching } = useQuery({
    queryKey: ['trial-updates-count', categorySlug, trialUpdatesDays],
    queryFn: () => trialsApi.getTrialUpdatesCount(categorySlug, trialUpdatesDays),
    enabled: Boolean(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Fetch latest 5 trial updates (by date from ClinicalTrials.gov API) within selected window
  const {
    data: latestTrialUpdates,
    isLoading: latestUpdatesLoading,
    isFetching: latestUpdatesFetching,
  } = useQuery({
    queryKey: ['latest-trial-updates', categorySlug, 5, trialUpdatesDays],
    queryFn: () => trialsApi.getLatestTrialUpdates(categorySlug, 5, trialUpdatesDays),
    enabled: Boolean(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Fetch live ticker (Latest News)
  const { data: liveTickerData, isLoading: liveTickerLoading } = useQuery({
    queryKey: ['live-ticker', categorySlug],
    queryFn: () => trialsApi.getLiveTicker(categorySlug),
    refetchOnWindowFocus: false,
  });

  /** Derive Efficacy/Safety label from result's efficacy_or_safety_data for Latest News. */
  const getEfficacySafetyLabel = (result: LiveTickerResult): string | null => {
    const ed = result.efficacy_or_safety_data as
      | { metric?: string; efficacy_metrics?: unknown[]; safety_metrics?: unknown[] }
      | undefined;
    if (!ed) return null;
    const hasEfficacy = (ed.efficacy_metrics?.length ?? 0) > 0;
    const hasSafety = (ed.safety_metrics?.length ?? 0) > 0;
    if (hasEfficacy && hasSafety) return 'Efficacy & Safety';
    if (hasSafety) return 'Safety';
    if (hasEfficacy) return 'Efficacy';
    if (ed.metric && /safety|trae|toxicity|ae\b/i.test(ed.metric)) return 'Safety';
    if (ed.metric) return 'Efficacy';
    return null;
  };

  const latestNewsItems = React.useMemo(() => {
    if (!liveTickerData) return [];
    const resultUrls = new Set(liveTickerData.results.map((r) => r.url));
    const articlesOnly = liveTickerData.articles.filter((a) => !resultUrls.has(a.url));
    type Item = { type: 'result'; value: LiveTickerResult } | { type: 'article'; value: LiveTickerArticle };
    const parseDate = (d: string) => new Date(d).getTime();
    const byDateDesc = (a: Item, b: Item) => parseDate(b.value.date) - parseDate(a.value.date);
    const results: Item[] = liveTickerData.results.map((value) => ({ type: 'result' as const, value }));
    const articles: Item[] = articlesOnly.map((value) => ({ type: 'article' as const, value }));
    const combined = [...results, ...articles];
    combined.sort(byDateDesc);
    return combined.slice(0, 5);
  }, [liveTickerData]);

  const { data: snapshotData, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics-snapshot', categorySlug],
    // Pass the URL slug, not the display name — getDbCancerType() maps slugs to DB values.
    // e.g. 'cutaneous-melanoma' → 'Cutaneous Melanoma' (not 'Cutaneous/Metastatic Melanoma')
    queryFn: () => analyticsApi.getSnapshot(categorySlug, 'all', 5, 5),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // Map snapshot bubble data directly to BubbleChartDataPoint[]
  const efficacySafetyBubbleData = React.useMemo<BubbleChartDataPoint[]>(() => {
    if (!snapshotData?.bubble?.length) return [];
    return snapshotData.bubble.map((p) => ({
      treatmentName: p.treatmentName,
      efficacy: p.efficacy,
      safety: p.safety,
      numberOfPatients: p.numberOfPatients ?? 0,
      trialCount: p.trialCount,
    }));
  }, [snapshotData]);

  // Map snapshot bar data directly to HeadToHeadDataPoint[]
  const efficacySafetyBarData = React.useMemo<HeadToHeadDataPoint[]>(() => {
    if (!snapshotData?.bar?.length) return [];
    return snapshotData.bar.map((p) => ({
      treatmentName: p.treatmentName,
      averageValue: p.averageValue,
      medianValue: p.averageValue,
      minValue: p.averageValue,
      maxValue: p.averageValue,
      trialCount: p.trialCount,
      totalPatients: 0,
      trials: [],
    }));
  }, [snapshotData]);

  /** Pipeline Health: phase distribution. Use the sponsor-filtered query; only fall back to overall when on the Industry default and that query returns zero rows. */
  const pipelinePhaseBars = React.useMemo(() => {
    const pipelinePhase = pipelineStats?.phase;
    const landscapePhase = landscapeStats?.phase;

    const sponsorTotal = pipelinePhase
      ? Object.values(pipelinePhase).reduce((a, b) => a + b, 0)
      : 0;
    const hasValidSponsorStats = !pipelineStatsError && !pipelineStatsLoading && sponsorTotal > 0;
    const allowOverallFallback = pipelineSponsor === 'Industry';

    const phase = hasValidSponsorStats
      ? pipelinePhase
      : allowOverallFallback && !pipelineStatsLoading && landscapePhase
        ? landscapePhase
        : pipelinePhase;

    if (!phase) return [];
    const shortLabels: Record<string, string> = {
      'Early Phase 1': 'Early Phase 1',
      'Phase 1': 'Phase 1',
      'Phase 2': 'Phase 2',
      'Phase 3': 'Phase 3',
      'Phase 4': 'Phase 4',
      'Not applicable': 'N/A',
    };
    const maxCount = Math.max(1, ...PHASE_OPTIONS.map((p) => phase[p] ?? 0));
    const barAreaHeightPx = 80;
    const minBarPx = 8;
    return PHASE_OPTIONS.map((label) => {
      const count = phase[label] ?? 0;
      const heightPct = Math.round((count / maxCount) * 100);
      const heightPx = maxCount > 0 ? Math.max(Math.round((count / maxCount) * barAreaHeightPx), count > 0 ? minBarPx : 4) : minBarPx;
      return {
        label,
        shortLabel: shortLabels[label] ?? label,
        count,
        heightPct,
        heightPx,
      };
    });
  }, [pipelineStats?.phase, pipelineStatsError, pipelineStatsLoading, landscapeStats?.phase, pipelineSponsor]);

  const pipelineHealthSponsorActive =
    !pipelineStatsError &&
    Boolean(pipelineStats?.phase) &&
    Object.values(pipelineStats?.phase ?? {}).reduce((a, b) => a + b, 0) > 0;

  // Regulatory Timeline sizing state (avoid Recharts width/height -1 warnings)
  const regulatoryContainerRef = React.useRef<HTMLDivElement | null>(null);
  const regulatoryChartAreaRef = React.useRef<HTMLDivElement | null>(null);
  const [regulatoryReady, setRegulatoryReady] = React.useState(false);
  const [regulatoryDims, setRegulatoryDims] = React.useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });
  const [regulatoryChartW, setRegulatoryChartW] = React.useState(0);

  React.useEffect(() => {
    const node = regulatoryContainerRef.current;
    if (!node || typeof window === 'undefined') return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      const ok = rect.width > 0 && rect.height > 0;
      if (ok) setRegulatoryDims({ width: rect.width, height: rect.height });
      setRegulatoryReady(ok);

      const chartEl = regulatoryChartAreaRef.current;
      if (chartEl) {
        const chartRect = chartEl.getBoundingClientRect();
        if (chartRect.width > 0) setRegulatoryChartW(chartRect.width);
      }
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    const chartEl = regulatoryChartAreaRef.current;
    if (chartEl) ro.observe(chartEl);
    return () => ro.disconnect();
  }, []);

  // Pipeline Health sizing state
  const pipelineContainerRef = React.useRef<HTMLDivElement | null>(null);
  const [pipelineReady, setPipelineReady] = React.useState(false);
  const [pipelineDims, setPipelineDims] = React.useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });

  React.useEffect(() => {
    const node = pipelineContainerRef.current;
    if (!node || typeof window === 'undefined') return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      const ok = rect.width > 0 && rect.height > 0;
      if (ok) setPipelineDims({ width: rect.width, height: rect.height });
      setPipelineReady(ok);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="flex flex-col h-screen w-full bg-[var(--brand-bg)] overflow-hidden relative selection:bg-[var(--brand-accent-light)] selection:text-[var(--brand-primary)]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shrink-0 z-50 sticky top-0 shadow-sm">
        <div className="w-full px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24">
          <div className="flex items-center justify-between h-14 sm:h-16 gap-3">
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
                  name={(session.user.user_metadata?.full_name as string) || null}
                  image={undefined}
                />
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Page Title Context */}
      <div className="px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24 py-6 sm:py-8 shrink-0 flex flex-col items-center justify-center z-10 relative text-center">
        <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-[var(--brand-text)] tracking-tight flex flex-wrap items-center justify-center gap-2 sm:gap-3">
          {categoryName} <span style={{ color: 'var(--brand-primary)' }}>bi<span className="brand-o">o</span>nocular</span>
        </h1>
      </div>

      {/* Main Grid: 1 col below 768px, 2 cols 768–1023px (Left|Middle, then Right), 3 cols 1024px+.
          Use min-h-0 + overflow so columns are constrained to viewport and scroll independently. */}
      <main className="flex-1 min-h-0 flex flex-col px-10 sm:px-12 lg:px-16 xl:px-20 2xl:px-24 pb-8 sm:pb-10 z-10 relative">
        <div className="flex-1 min-h-0 w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4 sm:gap-5 lg:gap-6 items-stretch overflow-hidden">

          {/* LEFT COLUMN: Data/Abstract, News, Alerts */}
          <div className="lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-hidden">
            <div className="flex flex-col gap-0 flex-1 min-h-0">
              {landscapeStats?.status?.["Overall Status"] != null && (
                <div className="shrink-0 px-4 py-2.5 bg-slate-50 border border-slate-200 border-b-slate-200 rounded-t-lg flex items-center justify-center">
                  <span className="text-sm font-semibold text-slate-700">
                    Total Trials Examined: <span className="tabular-nums text-slate-900">{(landscapeStats.status["Overall Status"]).toLocaleString()}</span>
                  </span>
                </div>
              )}
              <div className="flex-1 min-h-0">
              <SnapshotModule
                title="Trial Updates"
                className="rounded-t-none"
                href={`/dashboard/${categorySlug}/trial-updates`}
                headerRight={
                  <div role="tablist" aria-label="Time range" className="inline-flex items-center gap-0.5 p-0.5 bg-slate-100 border border-slate-200 rounded-lg">
                    {([7, 30, 60, 90] as const).map((d) => {
                      const active = trialUpdatesDays === d;
                      return (
                        <button
                          key={d}
                          type="button"
                          role="tab"
                          aria-selected={active}
                          onClick={() => setTrialUpdatesDays(d)}
                          className={cn(
                            'text-[10px] font-bold tracking-widest px-2 py-1 rounded uppercase transition-colors',
                            active
                              ? 'bg-white text-[var(--brand-primary)] shadow-sm'
                              : 'text-slate-500 hover:text-slate-700',
                          )}
                        >
                          {d}D
                        </button>
                      );
                    })}
                  </div>
                }
              >
                <div className="flex flex-col h-full gap-2 min-h-0 -mt-1 -mx-1">
                  {/* Summary cards */}
                  <div className={cn('flex w-full gap-2 shrink-0 transition-opacity', trialUpdatesCountFetching && 'opacity-60')}>
                    <div className="flex-1 flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg py-1.5 px-2 min-w-0">
                      <div className="flex-shrink-0 w-6 h-6 rounded-md bg-amber-50 flex items-center justify-center">
                        <Zap className="h-3 w-3 text-amber-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-bold text-slate-800 tabular-nums">
                          {trialUpdatesCount == null ? <Loader2 className="h-4 w-4 animate-spin text-blue-400" /> : (trialUpdatesCount.new_records_added.toLocaleString() ?? "0")}
                        </div>
                        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">New Records Added</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">Past {trialUpdatesDays} days</div>
                      </div>
                    </div>
                    <div className="flex-1 flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg py-1.5 px-2 min-w-0">
                      <div className="flex-shrink-0 w-6 h-6 rounded-md bg-blue-50 flex items-center justify-center">
                        <Lightbulb className="h-3 w-3 text-blue-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-bold text-slate-800 tabular-nums">
                          {trialUpdatesCount == null ? <Loader2 className="h-4 w-4 animate-spin text-blue-400" /> : (trialUpdatesCount.updates.toLocaleString() ?? "0")}
                        </div>
                        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Updates</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">Past {trialUpdatesDays} days</div>
                      </div>
                    </div>
                  </div>

                  {/* Data table: 4 columns so "Update Message" and icon have space; label and values align in col 3 */}
                  <div className="flex-1 flex flex-col min-h-0 border border-slate-200 rounded-xl overflow-hidden bg-white -mb-2">
                    <div className="grid grid-cols-[5rem_1fr_minmax(5rem,auto)_2.25rem] gap-2 px-3 py-2.5 bg-slate-100 border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-600 shrink-0 items-center">
                      <span>Date</span>
                      <span>Record Name</span>
                      <span className="min-w-0 block pl-3">Update Message</span>
                      <span className="w-9 flex justify-end">
                        <Link href={`/dashboard/${categorySlug}/trial-updates`} className="p-1 rounded hover:bg-slate-200 text-slate-500" aria-label="Full view"><Maximize2 className="h-3.5 w-3" /></Link>
                      </span>
                    </div>
                    <div className={cn('flex-1 min-h-0 overflow-hidden transition-opacity', latestUpdatesFetching && !latestUpdatesLoading && 'opacity-60')}>
                      {latestUpdatesLoading ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                        </div>
                      ) : !latestTrialUpdates?.trials?.length ? (
                        <div className="py-6 text-center text-sm text-slate-500">No trial updates in the past {trialUpdatesDays} days</div>
                      ) : (
                        latestTrialUpdates.trials.slice(0, 5).map((trial, idx) => (
                          <div
                            key={trial.nct_id}
                            className={`grid grid-cols-[5rem_1fr_minmax(5rem,auto)_2.25rem] gap-2 px-3 py-2.5 border-b border-slate-100 text-xs items-center ${idx % 2 === 0 ? "bg-white" : "bg-slate-50/80"}`}
                          >
                            <span className="text-slate-500 font-medium">
                              {trial.date_iso
                                ? new Date(trial.date_iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                                : '—'}
                            </span>
                            <div className="min-w-0">
                              <Link
                                href={`/trial/nct/${trial.nct_id}?category=${categorySlug}`}
                                className="font-medium text-blue-600 hover:text-blue-800 hover:underline line-clamp-2"
                              >
                                {trial.title || trial.nct_id}
                              </Link>
                              <div className="text-[10px] text-slate-500 mt-0.5 line-clamp-2">
                                {trial.sponsor_name || "Unknown Sponsor"}
                              </div>
                            </div>
                            <span className="text-slate-700 min-w-0 block pl-3">
                              {trial.update_type === "new" ? "New trial added." : "Updated."}
                            </span>
                            <span className="w-9" aria-hidden />
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </SnapshotModule>
              </div>
            </div>

            <div className="flex-1 min-h-0">
              <SnapshotModule title="Latest News" href={`/dashboard/${categorySlug}/live-ticker`}>
                <div className="space-y-2 pt-1 -mx-2 -mt-3 -mb-2">
                  {liveTickerLoading && (
                    <div className="flex items-center justify-center py-6">
                      <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                    </div>
                  )}
                  {!liveTickerLoading && latestNewsItems.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-6 text-center text-slate-500">
                      <Newspaper className="h-8 w-8 text-slate-300 mb-2" />
                      <p className="text-xs font-medium">No live ticker items yet</p>
                      <p className="text-[10px] text-slate-400 mt-1">Results and articles will appear here.</p>
                    </div>
                  )}
                  {!liveTickerLoading && latestNewsItems.map((item, i) => {
                    const { title, date, url, nct_id } = item.value;
                    const efficacySafetyLabel = item.type === 'result' ? getEfficacySafetyLabel(item.value) : null;
                    const dateLabel = (() => {
                      try {
                        const d = new Date(date);
                        const now = new Date();
                        const diffMs = now.getTime() - d.getTime();
                        const diffDays = Math.floor(diffMs / (24 * 60 * 60 * 1000));
                        if (diffDays === 0) return 'Today';
                        if (diffDays === 1) return 'Yesterday';
                        if (diffDays < 7) return `${diffDays}d ago`;
                        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
                      } catch {
                        return date;
                      }
                    })();
                    return (
                      <a
                        key={`${url}-${i}`}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex gap-3 items-center group p-2.5 rounded-xl hover:bg-white hover:shadow-sm border border-transparent hover:border-slate-100 transition-all duration-200"
                      >
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-sky-600 shrink-0 flex items-center justify-center text-white shadow-inner relative overflow-hidden">
                          <Newspaper className="h-4 w-4 relative z-10" />
                        </div>
                        <div className="flex flex-col gap-1 min-w-0 flex-1">
                          <span className="text-xs font-semibold text-slate-700 line-clamp-2 leading-relaxed group-hover:text-blue-700 transition-colors">{title}</span>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] text-slate-400 font-medium">{dateLabel}</span>
                            {nct_id && (
                              <>
                                <span className="w-1 h-1 rounded-full bg-slate-300" />
                                <span className="text-[10px] text-slate-500 font-mono">{nct_id}</span>
                              </>
                            )}
                            {efficacySafetyLabel && (
                              <>
                                <span className="w-1 h-1 rounded-full bg-slate-300" />
                                <span className="text-[10px] font-medium text-slate-600">{efficacySafetyLabel}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </a>
                    );
                  })}
                </div>
              </SnapshotModule>
            </div>

            <div className="h-[clamp(160px,20vh,230px)] shrink-0">
              <SnapshotModule title="Alerts">
                <div className="flex flex-col items-center justify-center h-full text-center px-4 gap-3 text-slate-500">
                  <div className="h-12 w-12 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center mb-1">
                    <Bell className="h-5 w-5 text-slate-300" />
                  </div>
                  <p className="text-sm font-medium text-slate-600">No recent alerts</p>
                  <p className="text-xs text-slate-400 max-w-[220px] leading-relaxed hidden xl:block">Stay updated on clinical changes by creating a saved search or watchlist.</p>
                  <button className="mt-2 text-[10px] font-bold tracking-wide uppercase px-4 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 hover:border-blue-300 hover:text-blue-700 transition-all shadow-sm">Setup Alert</button>
                </div>
              </SnapshotModule>
            </div>
          </div>

          {/* MIDDLE COLUMN: Trial Cards, Results */}
          <div className="lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-hidden">
            <div className="flex-1 flex flex-col min-h-0">
              <SnapshotModule title="Trial Landscape" href={`/dashboard/${categorySlug}/landscape`}>
                <div className="flex flex-col gap-3 h-full min-h-0">
                  {trialsLoading && (
                    <div className="flex items-center justify-center flex-1">
                      <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2 min-h-0 flex-1 overflow-hidden">
                    {(trialsData?.trials ?? []).map((trial) => (
                      <TrialCard
                        key={trial.nct_id}
                        trial={trial}
                        category={categorySlug}
                        className="min-w-0 min-h-[110px]"
                      />
                    ))}
                  </div>
                </div>
              </SnapshotModule>
            </div>

            <div className="flex-1 min-h-0">
              <SnapshotModule title="Trial Efficacy / Safety" href={`/dashboard/${categorySlug}/analytics`}>
                <div className="flex flex-col h-full min-h-0 flex-1 -m-5">
                  {analyticsLoading && (
                    <div className="flex items-center justify-center flex-1 min-h-[110px]">
                      <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    </div>
                  )}
                  {!analyticsLoading && !snapshotData && (
                    <div className="flex flex-col items-center justify-center flex-1 min-h-[110px] text-center px-4">
                      <p className="text-sm text-slate-500">No efficacy & safety data yet</p>
                      <p className="text-xs text-slate-400 mt-1">View analytics for more.</p>
                    </div>
                  )}
                  {!analyticsLoading && snapshotData && (
                    <div className="flex flex-col gap-0 h-full min-h-0 flex-1">
                      {/* Bubble: Efficacy vs Safety (top, half) */}
                      <div
                        className="min-h-0 flex-1 flex flex-col min-w-0"
                        style={{ minHeight: 'clamp(90px,10vh,110px)' }}
                      >
                        {efficacySafetyBubbleData.length > 0 ? (
                          <BubbleChart
                            data={efficacySafetyBubbleData}
                            height={110}
                            compact={true}
                            fillHeight={false}
                            isCompact={true}
                            efficacyLabel="ORR %"
                            safetyLabel="G3+ TRAE %"
                            efficacyParam="OBJECTIVE_RESPONSE_RATE"
                            safetyParam="GRADE_3_PLUS_TRAE"
                            axisConfig={0}
                            axisMode="efficacy-safety"
                            rounded={false}
                            showTooltip={false}
                          />
                        ) : (
                          <div className="flex items-center justify-center h-[110px] text-[10px] text-slate-400">No bubble data</div>
                        )}
                      </div>
                      {/* Simple bar: ORR by treatment (bottom, half) */}
                      <div
                        className="min-h-0 flex-1 flex flex-col min-w-0"
                        style={{ minHeight: 'clamp(90px,10vh,110px)' }}
                      >
                        {efficacySafetyBarData.length > 0 ? (
                          <BarChart
                            data={efficacySafetyBarData}
                            metric="OBJECTIVE_RESPONSE_RATE"
                            title=""
                            description=""
                            height={110}
                            showReferenceLine={false}
                            showLegend={false}
                            compact={true}
                            rounded={false}
                            wrapXAxisLabels={true}
                            showTooltip={false}
                          />
                        ) : (
                          <div className="flex items-center justify-center h-[110px] text-[10px] text-slate-400">No bar data</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </SnapshotModule>
            </div>
          </div>

          {/* RIGHT COLUMN: Pipeline, Regulatory, AI — full width on md when 2-col */}
          <div className="md:col-span-2 lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-hidden">
            <div className="flex-1 min-h-0">
              <SnapshotModule
                title="Pipeline Health"
                href={`/dashboard/${categorySlug}/landscape?sponsor_type=${pipelineSponsor}`}
              >
                <style>{`.pipeline-module .lucide-arrow-up-right { color: #64748b; } .pipeline-module button:hover .lucide-arrow-up-right { color: #2563eb; } .pipeline-module button:hover { background-color: rgba(37,99,235,0.08); } .pipeline-module *:focus { outline: none; }`}</style>
                <div className="h-full flex flex-col relative pipeline-module min-h-0">
                  <div className="flex w-full justify-between items-center mb-3 relative z-10 pt-1">
                    <div className="text-[var(--brand-text-muted)] text-xs font-medium">
                    {pipelineHealthSponsorActive
                      ? pipelineSponsor === 'Industry'
                        ? 'Trials by phase (Industry-sponsored)'
                        : 'Trials by phase (Non-Industry)'
                      : 'Trials by phase'}
                  </div>
                    <div className="flex gap-2">
                      {(['Industry', 'Non-Industry'] as const).map((s) => {
                        const active = pipelineSponsor === s;
                        return (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setPipelineSponsor(s)}
                            aria-pressed={active}
                            className={cn(
                              'border border-[var(--brand-border)] text-[9px] font-bold tracking-widest px-2 py-1 rounded uppercase transition-colors',
                              active
                                ? 'bg-[var(--brand-accent-light)] text-[var(--brand-primary)] shadow-sm'
                                : 'bg-transparent text-[var(--brand-text-muted)] hover:bg-[var(--brand-accent-light)]/50',
                            )}
                          >
                            {s}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex-1 min-h-[90px] w-full z-10" ref={pipelineContainerRef}>
                    {(() => {
                      const showLoading = (statsLoading && pipelineStatsLoading) || pipelinePhaseBars.length === 0;
                      if (showLoading) {
                        return <div className="flex items-center justify-center text-[10px] text-slate-400 h-full">Loading…</div>;
                      }
                      const chartData = pipelinePhaseBars.map((bar) => ({
                        label: bar.shortLabel,
                        fullLabel: bar.label,
                        count: bar.count,
                        href: `/dashboard/${categorySlug}/landscape?${new URLSearchParams({ sponsor_type: pipelineSponsor, phase: bar.label }).toString()}`,
                        isNa: bar.label === 'Not applicable',
                      }));
                      const maxCount = Math.max(...chartData.map((d) => d.count), 1);
                      const yMaxRaw = Math.ceil(maxCount * 1.15);
                      // Pick 4–6 equal divisions based on data so tick labels are consistent
                      // with "2 more lines" of horizontal grid/ticks.
                      // Enforce "even whole numbers" for ticks (step is an even integer).
                      const nCandidates = [6, 5, 4] as const;
                      let bestN = 4;
                      let bestStep = 2;
                      let bestDiff = Number.POSITIVE_INFINITY;
                      let bestTickMax = yMaxRaw;

                      // Special-case tiny domains so we still get clean even ticks.
                      if (yMaxRaw <= 2) {
                        bestN = 1;
                        bestStep = 2;
                        bestTickMax = 2;
                      } else {
                        for (const n of nCandidates) {
                          if (yMaxRaw < n) continue;
                          const stepRaw = Math.floor(yMaxRaw / n);
                          // Largest even integer <= stepRaw (so tickMax stays close and avoids decimals).
                          const stepEven = stepRaw % 2 === 0 ? stepRaw : stepRaw - (stepRaw % 2);
                          if (stepEven < 2) continue; // keep ticks strictly even: 0,2,4...
                          const tickMax = stepEven * n;
                          const diff = Math.abs(yMaxRaw - tickMax);
                          if (diff < bestDiff || (diff === bestDiff && n > bestN)) {
                            bestDiff = diff;
                            bestN = n;
                            bestStep = stepEven;
                            bestTickMax = tickMax;
                          }
                        }
                      }

                      const yTicks = Array.from({ length: bestN + 1 }, (_, i) => i * bestStep);
                      if (!pipelineReady) return null;
                      return (
                        <ResponsiveContainer
                          width={pipelineDims.width || '100%'}
                          height={pipelineDims.height || 150}
                          minWidth={0}
                          minHeight={90}
                        >
                          <RechartsBarChart
                            data={chartData}
                            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                            barCategoryGap="25%"
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 9, fill: '#64748b', fontWeight: 700 }}
                              axisLine={{ stroke: '#e2e8f0' }}
                              tickLine={false}
                              interval={0}
                            />
                            <YAxis
                              domain={[0, bestTickMax]}
                              ticks={yTicks}
                              tick={{ fontSize: 9, fill: '#64748b' }}
                              axisLine={false}
                              tickLine={false}
                              width={28}
                              allowDecimals={false}
                            />
                            <Bar
                              dataKey="count"
                              radius={[4, 4, 0, 0]}
                              isAnimationActive={true}
                              cursor="pointer"
                              onClick={(entry) => {
                                if (entry?.href) router.push(entry.href);
                              }}
                            >
                              {chartData.map((entry, i) => (
                                <Cell
                                  key={i}
                                  fill={entry.isNa ? 'var(--brand-border)' : 'var(--brand-primary)'}
                                  fillOpacity={entry.isNa ? 0.5 : 1}
                                />
                              ))}
                            </Bar>
                          </RechartsBarChart>
                        </ResponsiveContainer>
                      );
                    })()}
                  </div>
                </div>
              </SnapshotModule>
            </div>

            <div className="flex-1 min-h-0">
              <SnapshotModule
                title="Regulatory Timeline"
                href={`/dashboard/${categorySlug}/regulatory-timeline`}
                hideNav
              >
                <div className="flex flex-col h-full min-h-0 -m-5 -mb-8 mt-1 pb-0">
                  <div className="flex px-5 pt-1.5 pb-0.5">
                    <div style={{ width: '105px' }} aria-hidden />
                    <div className="flex-1 relative ml-1 h-4">
                      <span
                        className="absolute top-0 text-[10px] font-semibold text-[var(--brand-text-muted)] tracking-wide"
                        style={{ left: 12 }}
                      >
                        Trial Start Date
                      </span>
                      <span
                        className="absolute top-0 text-[10px] font-semibold text-[var(--brand-text-muted)] tracking-wide"
                        style={{ right: 12 }}
                      >
                        Est. Completion Date
                      </span>
                    </div>
                  </div>
                  <div
                    className="flex-1 min-h-[120px] px-2"
                    ref={regulatoryContainerRef}
                  >
                    {regulatoryReady && (categorySlug === 'merkel-cell-carcinoma' ? (
                      <div className="w-full h-full flex flex-row">
                        {/* Y-Axis Labels */}
                        <div className="flex flex-col justify-between py-1 pr-2 pl-2" style={{ width: '105px', height: regulatoryDims.height - 20 }}>
                          {MCC_REGULATORY_TRIALS.map((trial) => (
                            <div key={trial.nct} className="py-0.5">
                              <div className="text-[9px] font-semibold text-slate-700 leading-tight break-words">
                                {trial.label}
                              </div>
                              <div className="text-[8px] text-slate-400 leading-tight font-mono">
                                {trial.nct}
                              </div>
                            </div>
                          ))}
                        </div>
                        
                        {/* Chart Area */}
                        <div ref={regulatoryChartAreaRef} className="flex-1 relative ml-1">
                          {(() => {
                            const domainStart = 2018;
                            const domainEnd = 2034;
                            const domainSpan = domainEnd - domainStart;
                            const padX = 12; // keep end labels centered without clipping
                            const chartW = Math.max(regulatoryChartW || 0, 0);
                            const innerW = Math.max(chartW - padX * 2, 1);
                            const toX = (year: number) => padX + ((year - domainStart) / domainSpan) * innerW;
                            const tickYears = [2018, 2022, 2026, 2030, 2034] as const;
                            const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max);
                            const formatYearFrac = (yf: number) => {
                              const year = Math.floor(yf);
                              const monthIndex = clamp(Math.round((yf - year) * 12), 0, 11);
                              const d = new Date(Date.UTC(year, monthIndex, 1));
                              return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
                            };

                            return (
                              <svg width={chartW || '100%'} height={regulatoryDims.height} style={{ overflow: 'visible' }}>
                            {/* Grid lines */}
                            {tickYears.map((year) => {
                              const x = toX(year);
                              return (
                                <line
                                  key={year}
                                  x1={x}
                                  y1={0}
                                  x2={x}
                                  y2={regulatoryDims.height - 22}
                                  stroke="#e2e8f0"
                                  strokeWidth={1.25}
                                />
                              );
                            })}

                            {/* X-axis baseline */}
                            <line
                              x1={Math.max(padX - 10, 0)}
                              y1={regulatoryDims.height - 22}
                              x2={padX + innerW + 10}
                              y2={regulatoryDims.height - 22}
                              stroke="#e2e8f0"
                              strokeWidth={1.25}
                            />
                            
                            {MCC_REGULATORY_TRIALS.map((trial, i) => {
                              const rowH = (regulatoryDims.height - 22) / MCC_REGULATORY_TRIALS.length;
                              const barH = 10;
                              const y = i * rowH + (rowH - barH) / 2;
                              const xStart = toX(trial.start);
                              const xEnd = toX(trial.end);
                              const barW = Math.max(xEnd - xStart, 4);
                              const labelY = Math.max(y - 3, 8);
                              
                              return (
                                <g key={trial.nct}>
                                  {/* Start/Completion labels */}
                                  <text
                                    x={clamp(xStart, padX, padX + innerW)}
                                    y={labelY}
                                    textAnchor="start"
                                    fontSize="7"
                                    fill="#64748b"
                                    fontWeight="600"
                                  >
                                    {formatYearFrac(trial.start)}
                                  </text>
                                  <text
                                    x={clamp(xEnd, padX, padX + innerW)}
                                    y={labelY}
                                    textAnchor="end"
                                    fontSize="7"
                                    fill="#64748b"
                                    fontWeight="600"
                                  >
                                    {formatYearFrac(trial.end)}
                                  </text>
                                  <rect x={xStart} y={y} width={barW} height={barH} rx={1.5} fill={trial.color} opacity={0.8} />
                                  <polygon
                                    points={`${xEnd},${y + barH / 2 - 3.5} ${xEnd + 3.5},${y + barH / 2} ${xEnd},${y + barH / 2 + 3.5} ${xEnd - 3.5},${y + barH / 2}`}
                                    fill="#94a3b8" stroke="#fff" strokeWidth={0.5}
                                  />
                                </g>
                              );
                            })}
                            
                            {/* X-Axis Labels */}
                            {tickYears.map((year) => {
                              const x = toX(year);
                              return (
                                <text
                                  key={year}
                                  x={x}
                                  y={regulatoryDims.height - 8}
                                  textAnchor="middle"
                                  fontSize="9"
                                  fill="#64748b"
                                  fontWeight="600"
                                >
                                  {year}
                                </text>
                              );
                            })}
                              </svg>
                            );
                          })()}
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-full text-[10px] text-slate-400">
                        No timeline data available
                      </div>
                    ))}
                  </div>
                </div>
              </SnapshotModule>
            </div>

            <div className="h-[clamp(160px,20vh,230px)] shrink-0">
              <SnapshotModule
                title={
                  <>
                    {categoryName} AI Agent <span className="text-slate-400">(Upcoming)</span>
                  </>
                }
              >
                <div className="h-full flex flex-col justify-end relative overflow-hidden mt-1">
                  <div className="flex items-stretch bg-[var(--brand-bg)] border border-[var(--brand-border)] rounded-lg p-2 pl-3 min-h-[5rem] focus-within:ring-2 focus-within:ring-[var(--brand-primary)]/30 focus-within:border-[var(--brand-primary)]/50 transition-all z-10">
                    <textarea
                      rows={2}
                      className="bg-transparent flex-1 outline-none text-[var(--brand-text)] text-sm placeholder:text-[var(--brand-text-muted)] font-medium resize-none py-1.5"
                      placeholder="Ask Bionocular AI Agent..."
                    />
                    <button className="h-9 w-9 self-end rounded-md bg-[var(--brand-primary)] flex items-center justify-center text-white ml-2 hover:bg-[var(--brand-primary-hover)] hover:shadow-md transition-all active:scale-95 shrink-0">
                      <Send className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="text-center mt-2 text-[9px] font-medium text-[var(--brand-text-muted)] uppercase tracking-wider">
                    Validate insights with primary sources
                  </div>
                </div>
              </SnapshotModule>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
