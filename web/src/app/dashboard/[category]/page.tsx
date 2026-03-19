'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
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
import { ArrowUpRight, Loader2, Bell, Send, Newspaper, BarChart3, Clock, Activity, Zap, Lightbulb, ChevronDown, Maximize2 } from 'lucide-react';
import { trialsApi, analyticsApi, type LiveTickerArticle, type LiveTickerResult } from '@/lib/api';
import { PHASE_OPTIONS } from '@/lib/dashboard-constants';
import { TrialCard } from '@/components/dashboard/TrialCard';
import { transformBubbleChartData, transformHeadToHeadData } from '@/lib/chart-transformers';
import type { TrialDataFile, BubbleChartDataPoint, ChartMetric, HeadToHeadDataPoint } from '@/types/analytics';
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

/** Treatment timeline data for Regulatory Timeline (Final Study Completion). */
/** Professional palette: distinct, muted, report-ready. */
const REGULATORY_TIMELINE_DATA = [
  { treatment: 'IO102-IO103 + Pembro', startYear: 2023.5, endYear: 2028.5, color: '#1e40af' },
  { treatment: 'Lifileucel + Pembro', startYear: 2026, endYear: 2030.5, color: '#0d9488' },
  { treatment: 'OBX-115', startYear: 2024, endYear: 2028.5, color: '#5b21b6' },
  { treatment: 'EIK1001 + Pembro', startYear: 2025.5, endYear: 2040.5, color: '#b45309' },
  { treatment: '[225Ac]Ac-A9-3408', startYear: 2026, endYear: 2028.5, color: '#0369a1' },
].map((t) => ({
  ...t,
  _start: t.startYear - 2023,
  _duration: t.endYear - t.startYear,
}));

// Reusable Module Wrapper with modern styling
function SnapshotModule({ title, href, children, onNavigate, headerRight, dark = false, flatDarkHeader = false, className = "" }: { title: string; href?: string; children: React.ReactNode; onNavigate?: () => void; headerRight?: React.ReactNode; dark?: boolean; flatDarkHeader?: boolean; className?: string }) {
  const router = useRouter();

  const handleNav = () => {
    if (onNavigate) onNavigate();
    else if (href) router.push(href);
  };

  const headerBg = dark
    ? (flatDarkHeader ? "bg-transparent" : "bg-gradient-to-r from-white/10 to-transparent")
    : "bg-[var(--brand-bg)] border-b border-[var(--brand-border)]";

  return (
    <Card className={`flex flex-col overflow-hidden h-full bg-white border border-[var(--brand-border)] shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300 ${className}`}>
      <CardHeader className={`flex flex-row items-center justify-between h-[52px] py-0 px-5 shrink-0 ${headerBg}`}>
        <CardTitle className={`text-[13px] font-bold tracking-[0.1em] uppercase flex items-center gap-2 min-w-0 truncate ${dark ? "text-slate-200" : "text-[var(--brand-text)]"}`}>
           <div className="w-1.5 h-4 shrink-0 bg-[var(--brand-primary)] rounded-full" />
           <span className="truncate">{title}</span>
        </CardTitle>
        {headerRight ?? ((href || onNavigate) && (
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
      <CardContent className="p-5 flex-1 flex flex-col min-h-0 overflow-y-auto">
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

  // Fetch a snapshot of trial cards (same filter as landscape: Sponsor type = Industry)
  const { data: trialsData, isLoading: trialsLoading } = useQuery({
    queryKey: ['dashboard-snapshot-trials', categorySlug],
    queryFn: () =>
      trialsApi.getDashboardTrials(categorySlug, {
        limit: 9,
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

  // Pipeline Health: phase distribution for Industry-sponsored trials only (matches landscape filter)
  const {
    data: pipelineStats,
    isLoading: pipelineStatsLoading,
    isError: pipelineStatsError,
  } = useQuery({
    queryKey: ['disease-stats', categorySlug, 'Industry'],
    queryFn: () =>
      trialsApi.getDiseaseLandscapeStats(categorySlug, {
        sponsor_type: 'Industry',
      }),
    enabled: Boolean(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Fetch trial updates count (New Records Added + Updates in past 30 days, from ClinicalTrials.gov API dates)
  const { data: trialUpdatesCount } = useQuery({
    queryKey: ['trial-updates-count', categorySlug, 30],
    queryFn: () => trialsApi.getTrialUpdatesCount(categorySlug, 30),
    enabled: Boolean(categorySlug),
    refetchOnWindowFocus: false,
  });

  // Fetch latest 5 trial updates (by date from ClinicalTrials.gov API)
  const { data: latestTrialUpdates, isLoading: latestUpdatesLoading } = useQuery({
    queryKey: ['latest-trial-updates', categorySlug, 5],
    queryFn: () => trialsApi.getLatestTrialUpdates(categorySlug, 5),
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

  const { data: analyticsData, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics-data', categorySlug, categoryName],
    queryFn: () => analyticsApi.getData({ cancer_type: categoryName, limit: 500 }),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const trialData = React.useMemo<TrialDataFile | null>(() => {
    if (!analyticsData?.abstracts) return null;
    const allTrials: TrialDataFile['abstracts'] = (analyticsData.abstracts as unknown as TrialDataFile['abstracts']) || [];
    return {
      total_abstracts: analyticsData.total_abstracts,
      total_arms: analyticsData.total_arms,
      total_attributes_extracted: analyticsData.total_attributes_extracted,
      average_confidence: analyticsData.average_confidence,
      abstracts: allTrials,
    };
  }, [analyticsData]);

  const efficacySafetyBubbleData = React.useMemo<BubbleChartDataPoint[]>(() => {
    if (!trialData) return [];
    const points = transformBubbleChartData(trialData, {
      efficacyMetric: 'OBJECTIVE_RESPONSE_RATE',
      safetyMetric: 'GRADE_3_PLUS_TRAE',
      minTrialCount: 1,
    });
    if (points.length === 0) return [];

    // Take the first 5 treatments in the natural data order.
    const slice = points.slice(0, 5).filter(Boolean);
    if (slice.length >= 3) return slice;

    // Fallback: not enough data in that range — use a spread across the dataset
    if (points.length <= 5) return points;
    const start = Math.max(2, Math.floor(points.length * 0.2));
    const step = Math.max(1, Math.floor((points.length - start) / 5));
    return Array.from({ length: 5 }, (_, i) => points[Math.min(start + i * step, points.length - 1)]).filter(Boolean);
  }, [trialData]);

  const efficacySafetyBarData = React.useMemo<HeadToHeadDataPoint[]>(() => {
    if (!trialData) return [];
    const data = transformHeadToHeadData(trialData, {
      targetMetric: 'OBJECTIVE_RESPONSE_RATE' as ChartMetric,
      minTrialCount: 1,
    });
    data.sort((a, b) => b.averageValue - a.averageValue);
    // Use treatments 7–12 by ORR so bar chart shows a different set from the top-ranked ones
    return data.slice(6, 12);
  }, [trialData]);

  /** Pipeline Health: phase distribution. Prefer Industry-only; fallback to overall when Industry stats are all zero or unavailable. */
  const pipelinePhaseBars = React.useMemo(() => {
    const pipelinePhase = pipelineStats?.phase;
    const landscapePhase = landscapeStats?.phase;

    // Industry stats are considered valid only if they have non-zero data
    const industryTotal = pipelinePhase
      ? Object.values(pipelinePhase).reduce((a, b) => a + b, 0)
      : 0;
    const hasValidIndustryStats = !pipelineStatsError && !pipelineStatsLoading && industryTotal > 0;

    const phase = hasValidIndustryStats
      ? pipelinePhase
      : !pipelineStatsLoading && landscapePhase
        ? landscapePhase
        : undefined;

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
  }, [pipelineStats?.phase, pipelineStatsError, pipelineStatsLoading, landscapeStats?.phase]);

  const pipelineHealthIsIndustryOnly =
    !pipelineStatsError &&
    Boolean(pipelineStats?.phase) &&
    Object.values(pipelineStats?.phase ?? {}).reduce((a, b) => a + b, 0) > 0;

  // Regulatory Timeline sizing state (avoid Recharts width/height -1 warnings)
  const regulatoryContainerRef = React.useRef<HTMLDivElement | null>(null);
  const [regulatoryReady, setRegulatoryReady] = React.useState(false);
  const [regulatoryDims, setRegulatoryDims] = React.useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });

  React.useEffect(() => {
    const node = regulatoryContainerRef.current;
    if (!node || typeof window === 'undefined') return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      const ok = rect.width > 0 && rect.height > 0;
      if (ok) setRegulatoryDims({ width: rect.width, height: rect.height });
      setRegulatoryReady(ok);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
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
                  name={session.user.name || null}
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
          <div className="lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-y-auto overflow-x-hidden custom-scrollbar">
            <div className="flex flex-col gap-0 flex-1 min-h-[160px]">
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
                  <div className="relative flex items-center">
                    <select
                      aria-label="Time range"
                      className="text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg pl-2.5 pr-7 py-1.5 appearance-none cursor-pointer hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 uppercase tracking-wider"
                      defaultValue="30"
                    >
                      <option value="7">Past 7 Days</option>
                      <option value="30">Past 30 Days</option>
                      <option value="90">Past 90 Days</option>
                    </select>
                    <ChevronDown className="h-3.5 w-3.5 text-slate-500 pointer-events-none absolute right-2 top-1/2 -translate-y-1/2" aria-hidden />
                  </div>
                }
              >
                <div className="flex flex-col h-full gap-2 min-h-0 -mt-2 -mx-2">
                  {/* Summary cards */}
                  <div className="flex w-full gap-2 shrink-0">
                    <div className="flex-1 flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg py-2 px-2.5 min-w-0">
                      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center">
                        <Zap className="h-3.5 w-3.5 text-amber-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-base font-bold text-slate-800 tabular-nums">
                          {trialUpdatesCount == null ? <Loader2 className="h-4 w-4 animate-spin text-blue-400" /> : (trialUpdatesCount.new_records_added.toLocaleString() ?? "0")}
                        </div>
                        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">New Records Added</div>
                        <div className="text-[8px] text-slate-400 mt-0.5">Past 30 days</div>
                      </div>
                    </div>
                    <div className="flex-1 flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg py-2 px-2.5 min-w-0">
                      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-blue-50 flex items-center justify-center">
                        <Lightbulb className="h-3.5 w-3.5 text-blue-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-base font-bold text-slate-800 tabular-nums">
                          {trialUpdatesCount == null ? <Loader2 className="h-4 w-4 animate-spin text-blue-400" /> : (trialUpdatesCount.updates.toLocaleString() ?? "0")}
                        </div>
                        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Updates</div>
                        <div className="text-[8px] text-slate-400 mt-0.5">Past 30 days</div>
                      </div>
                    </div>
                  </div>

                  {/* Data table: 4 columns so "Update Message" and icon have space; label and values align in col 3 */}
                  <div className="flex-1 flex flex-col min-h-0 border border-slate-200 rounded-xl overflow-hidden bg-white -mb-4">
                    <div className="grid grid-cols-[5rem_1fr_minmax(5rem,auto)_2.25rem] gap-2 px-3 py-2.5 bg-slate-100 border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-600 shrink-0 items-center">
                      <span>Date</span>
                      <span>Record Name</span>
                      <span className="min-w-0 block pl-3">Update Message</span>
                      <span className="w-9 flex justify-end">
                        <Link href={`/dashboard/${categorySlug}/trial-updates`} className="p-1 rounded hover:bg-slate-200 text-slate-500" aria-label="Full view"><Maximize2 className="h-3.5 w-3" /></Link>
                      </span>
                    </div>
                    <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar">
                      {latestUpdatesLoading ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                        </div>
                      ) : !latestTrialUpdates?.trials?.length ? (
                        <div className="py-6 text-center text-sm text-slate-500">No trial updates</div>
                      ) : (
                        latestTrialUpdates.trials.slice(0, 5).map((trial, idx) => (
                          <div
                            key={trial.nct_id}
                            className={`grid grid-cols-[5rem_1fr_minmax(5rem,auto)_2.25rem] gap-2 px-3 py-2.5 border-b border-slate-100 text-xs items-center ${idx % 2 === 0 ? "bg-white" : "bg-slate-50/80"}`}
                          >
                            <span className="text-slate-500 font-medium">{trial.date_iso}</span>
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

            <div className="flex-1 min-h-[160px]">
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

            <div className="h-56 shrink-0">
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
          <div className="lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-y-auto overflow-x-hidden custom-scrollbar">
            <div className="flex-1 flex flex-col min-h-[220px]">
              <SnapshotModule title="Trial Landscape" href={`/dashboard/${categorySlug}/landscape`}>
                <div className="flex flex-col gap-3 h-full min-h-0">
                  {trialsLoading && (
                    <div className="flex items-center justify-center flex-1">
                      <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2 min-h-0 flex-1 overflow-y-auto custom-scrollbar">
                    {trialsData?.trials.slice(0, 9).map((trial) => (
                      <TrialCard
                        key={trial.nct_id}
                        trial={trial}
                        category={categorySlug}
                        className="min-w-0 min-h-[120px]"
                      />
                    ))}
                  </div>
                </div>
              </SnapshotModule>
            </div>

            <div className="flex-1 min-h-[220px]">
              <SnapshotModule title="Trial Efficacy / Safety" href={`/dashboard/${categorySlug}/analytics`}>
                <div className="flex flex-col h-full min-h-0 flex-1 -m-5">
                  {analyticsLoading && (
                    <div className="flex items-center justify-center flex-1 min-h-[200px]">
                      <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    </div>
                  )}
                  {!analyticsLoading && !trialData && (
                    <div className="flex flex-col items-center justify-center flex-1 min-h-[200px] text-center px-4">
                      <p className="text-sm text-slate-500">No efficacy & safety data yet</p>
                      <p className="text-xs text-slate-400 mt-1">View analytics for more.</p>
                    </div>
                  )}
                  {!analyticsLoading && trialData && (
                    <div className="flex flex-col gap-0 h-full min-h-0 flex-1">
                      {/* Bubble: Efficacy vs Safety (top, half) */}
                      <div className="min-h-0 flex-1 flex flex-col min-w-0" style={{ minHeight: 140 }}>
                        {efficacySafetyBubbleData.length > 0 ? (
                          <BubbleChart
                            data={efficacySafetyBubbleData}
                            height={140}
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
                          <div className="flex items-center justify-center h-[140px] text-[10px] text-slate-400">No bubble data</div>
                        )}
                      </div>
                      {/* Simple bar: ORR by treatment (bottom, half) */}
                      <div className="min-h-0 flex-1 flex flex-col min-w-0" style={{ minHeight: 140 }}>
                        {efficacySafetyBarData.length > 0 ? (
                          <BarChart
                            data={efficacySafetyBarData}
                            metric="OBJECTIVE_RESPONSE_RATE"
                            title=""
                            description=""
                            height={140}
                            showReferenceLine={false}
                            showLegend={false}
                            compact={true}
                            rounded={false}
                            wrapXAxisLabels={true}
                            showTooltip={false}
                          />
                        ) : (
                          <div className="flex items-center justify-center h-[140px] text-[10px] text-slate-400">No bar data</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </SnapshotModule>
            </div>
          </div>

          {/* RIGHT COLUMN: Pipeline, Regulatory, AI — full width on md when 2-col */}
          <div className="md:col-span-2 lg:col-span-4 flex flex-col gap-4 sm:gap-5 min-h-0 overflow-y-auto overflow-x-hidden custom-scrollbar">
            <div className="flex-1 min-h-[200px]">
              <SnapshotModule
                title="Pipeline Health"
                href={`/dashboard/${categorySlug}/landscape?sponsor_type=Industry`}
              >
                <style>{`.pipeline-module .lucide-arrow-up-right { color: #64748b; } .pipeline-module button:hover .lucide-arrow-up-right { color: #2563eb; } .pipeline-module button:hover { background-color: rgba(37,99,235,0.08); } .pipeline-module *:focus { outline: none; }`}</style>
                <div className="h-full flex flex-col relative pipeline-module min-h-0">
                  <div className="flex w-full justify-between items-center mb-3 relative z-10 pt-1">
                    <div className="text-[var(--brand-text-muted)] text-xs font-medium">
                    {pipelineHealthIsIndustryOnly
                      ? 'Trials by phase (Industry-sponsored)'
                      : 'Trials by phase'}
                  </div>
                    <div className="flex gap-2">
                      <span className="bg-[var(--brand-accent-light)] border border-[var(--brand-border)] text-[9px] font-bold tracking-widest px-2 py-1 rounded text-[var(--brand-primary)] uppercase shadow-sm">Industry</span>
                      <span className="bg-transparent border border-[var(--brand-border)] text-[9px] font-bold tracking-widest px-2 py-1 rounded text-[var(--brand-text-muted)] uppercase">Non-Industry</span>
                    </div>
                  </div>
                  <div className="flex-1 min-h-[120px] w-full z-10" ref={pipelineContainerRef}>
                    {(() => {
                      const showLoading = (statsLoading && pipelineStatsLoading) || pipelinePhaseBars.length === 0;
                      if (showLoading) {
                        return <div className="flex items-center justify-center text-[10px] text-slate-400 h-full">Loading…</div>;
                      }
                      const chartData = pipelinePhaseBars.map((bar) => ({
                        label: bar.shortLabel,
                        fullLabel: bar.label,
                        count: bar.count,
                        href: `/dashboard/${categorySlug}/landscape?${new URLSearchParams({ sponsor_type: 'Industry', phase: bar.label }).toString()}`,
                        isNa: bar.label === 'Not applicable',
                      }));
                      const maxCount = Math.max(...chartData.map((d) => d.count), 1);
                      const yMax = Math.ceil(maxCount * 1.15);
                      if (!pipelineReady) return null;
                      return (
                        <ResponsiveContainer
                          width={pipelineDims.width || '100%'}
                          height={pipelineDims.height || 180}
                          minWidth={0}
                          minHeight={120}
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
                              domain={[0, yMax]}
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

            <div className="flex-1 min-h-[200px]">
              <SnapshotModule title="Regulatory Timeline" href={`/dashboard/${categorySlug}/regulatory-timeline`}>
                <div className="flex flex-col h-full min-h-0 -m-5 -mb-8 mt-1 pb-0">
                  <p className="text-[11px] font-semibold text-[var(--brand-text-muted)] uppercase tracking-wider px-5 pt-1.5 pb-0.5">Final Study Completion</p>
                  <div
                    className="flex-1 min-h-[160px] px-2"
                    ref={regulatoryContainerRef}
                  >
                    {regulatoryReady ? (
                      <ResponsiveContainer
                        width={regulatoryDims.width || '100%'}
                        height={regulatoryDims.height || 160}
                        minWidth={0}
                        minHeight={160}
                      >
                        <RechartsBarChart
                          data={REGULATORY_TIMELINE_DATA}
                          layout="vertical"
                          margin={{ top: 4, right: 8, left: 4, bottom: 20 }}
                        >
                          <CartesianGrid
                            strokeDasharray="2 2"
                            stroke="#e2e8f0"
                            horizontal={false}
                            vertical={true}
                          />
                          <XAxis
                            type="number"
                            domain={[0, 19]}
                            ticks={[0, 4, 8, 12, 16]}
                            tick={{ fontSize: 9, fill: '#64748b' }}
                            tickFormatter={(v) => String(2023 + Math.round(v))}
                            axisLine={{ stroke: '#94a3b8' }}
                            tickLine={{ stroke: '#cbd5e1' }}
                          />
                          <YAxis
                            type="category"
                            dataKey="treatment"
                            width={108}
                            tick={{ fontSize: 9, fill: '#334155', fontWeight: 500 }}
                            axisLine={{ stroke: '#94a3b8' }}
                            tickLine={false}
                            reversed
                          />
                          <Bar dataKey="_start" stackId="rt" fill="transparent" barSize={16} isAnimationActive={false} />
                          <Bar dataKey="_duration" stackId="rt" barSize={16} radius={0} stroke="#1e293b" strokeWidth={0.5} isAnimationActive={true}>
                            {REGULATORY_TIMELINE_DATA.map((entry, i) => (
                              <Cell key={i} fill={entry.color} />
                            ))}
                          </Bar>
                        </RechartsBarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-[10px] text-slate-400">
                        Loading chart…
                      </div>
                    )}
                  </div>
                </div>
              </SnapshotModule>
            </div>

            <div className="h-56 shrink-0">
              <SnapshotModule title={`${categoryName} AI`}>
                <div className="h-full flex flex-col justify-end relative overflow-hidden mt-1">
                  <div className="flex items-stretch bg-[var(--brand-bg)] border border-[var(--brand-border)] rounded-lg p-2 pl-3 min-h-[4.5rem] focus-within:ring-2 focus-within:ring-[var(--brand-primary)]/30 focus-within:border-[var(--brand-primary)]/50 transition-all z-10">
                    <textarea
                      rows={3}
                      className="bg-transparent flex-1 outline-none text-[var(--brand-text)] text-sm placeholder:text-[var(--brand-text-muted)] font-medium resize-none py-1.5"
                      placeholder="Ask Bionocular AI..."
                    />
                    <button className="h-9 w-9 self-end rounded-md bg-[var(--brand-primary)] flex items-center justify-center text-white ml-2 hover:bg-[var(--brand-primary-hover)] hover:shadow-md transition-all active:scale-95 shrink-0">
                      <Send className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="text-center mt-2.5 text-[9px] font-medium text-[var(--brand-text-muted)] uppercase tracking-wider">
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
