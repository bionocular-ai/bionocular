'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useSession } from 'next-auth/react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import {
  Bar,
  BarChart,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  Tooltip,
} from 'recharts';
import { UserMenu } from '@/components/user-menu';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';
import { Loader2, Calendar } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { DEFAULT_CANCER_TYPE_SLUG } from '@/lib/dashboard-constants';

const MIN_YEAR = 2023;
const MAX_YEAR = 2042;
const YEAR_RANGE = MAX_YEAR - MIN_YEAR;

/** Treatment timeline data: Final Study Completion. Professional palette: distinct, muted, report-ready. */
const TREATMENT_TIMELINES = [
  {
    treatment: 'IO102-IO103 + Pembrolizumab',
    startYear: 2023.5,
    endYear: 2028.5,
    color: '#1e40af', // deep blue
  },
  {
    treatment: 'Lifileucel + Pembrolizumab',
    startYear: 2026,
    endYear: 2030.5,
    color: '#0d9488', // teal
  },
  {
    treatment: 'OBX-115',
    startYear: 2024,
    endYear: 2028.5,
    color: '#5b21b6', // indigo
  },
  {
    treatment: 'EIK1001 + Pembrolizumab',
    startYear: 2025.5,
    endYear: 2040.5,
    color: '#b45309', // amber
  },
  {
    treatment: '[225Ac]Ac-A9-3408',
    startYear: 2026,
    endYear: 2028.5,
    color: '#0369a1', // sky
  },
] as const;

/** Chart data: _start = years from MIN_YEAR to bar start, _duration = bar length in years (for stacked horizontal bar). */
function buildChartData() {
  return TREATMENT_TIMELINES.map((t) => ({
    ...t,
    _start: t.startYear - MIN_YEAR,
    _duration: t.endYear - t.startYear,
  }));
}

function RegulatoryTimelineContent() {
  const { data: session } = useSession();
  const searchParams = useSearchParams();
  const params = useParams();
  const router = useRouter();

  const cancerTypeSlug =
    (params?.category as string) ||
    searchParams.get('cancer_type') ||
    DEFAULT_CANCER_TYPE_SLUG;

  const setCancerType = React.useCallback(
    (slug: string) => {
      router.push(`/dashboard/${slug}/regulatory-timeline`);
    },
    [router]
  );

  const chartData = React.useMemo(() => buildChartData(), []);

  return (
    <div className="flex flex-col h-screen w-full bg-slate-100 overflow-hidden">
      <header className="bg-white border-b border-slate-200 shrink-0 z-50">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 gap-3">
            <Link
              href="/"
              className="brand flex-shrink-0 hover:opacity-80 transition-opacity"
            >
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

      <main className="flex-1 flex flex-col min-h-0 overflow-y-auto overflow-x-hidden px-2 pt-2 pb-4 md:px-4 md:pt-4 md:pb-6 bg-slate-100 gap-4">
        <div className="w-full bg-white rounded-lg shadow shrink-0 overflow-visible">
          <DashboardGlobalHeader
            cancerTypeSlug={cancerTypeSlug}
            onCancerTypeChange={setCancerType}
          />
        </div>

        {/* Regulatory Timeline section — same layout pattern as Landscape */}
        <div className="w-full bg-white rounded-lg shadow min-h-0 min-w-0">
          <section className="bg-white min-h-0">
            <div className="px-4 sm:px-6 lg:px-8 pt-3 pb-2 flex flex-col min-h-0">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 shrink-0 mb-2">
                <div>
                  <h2 className="text-2xl font-medium tracking-wide text-sky-700">
                    Regulatory Timeline
                  </h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    Key regulatory milestones and approval pathway for this indication.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 py-2 shrink-0 border-y border-slate-100 bg-slate-50/50 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 mb-4">
                <div className="flex items-center gap-2 text-slate-600">
                  <Calendar className="h-4 w-4 text-slate-400" />
                  <span className="text-sm font-medium">Final Study Completion</span>
                </div>
              </div>

              {/* Clinical trial timelines — horizontal bar chart */}
              <div className="pb-6 min-h-[340px]">
                <h3 className="text-base font-semibold text-slate-700 mb-1">
                  Clinical Trial Timelines for Metastatic Melanoma (Final Study Completion)
                </h3>
                <p className="text-xs text-slate-500 mb-4">Hover a bar for start and end years.</p>
                <div className="w-full h-[300px] min-h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 12, right: 16, left: 12, bottom: 28 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#e2e8f0"
                        horizontal={false}
                        vertical={true}
                      />
                      <XAxis
                        type="number"
                        domain={[0, YEAR_RANGE]}
                        ticks={[0, 2, 4, 6, 8, 10, 12, 14, 16, 18]}
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        tickFormatter={(v) => String(MIN_YEAR + Math.round(v))}
                        axisLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
                        tickLine={{ stroke: '#cbd5e1' }}
                        label={{
                          value: 'Year',
                          position: 'insideBottom',
                          offset: -8,
                          fontSize: 12,
                          fontWeight: 500,
                          fill: '#64748b',
                        }}
                      />
                      <YAxis
                        type="category"
                        dataKey="treatment"
                        width={240}
                        tick={{ fontSize: 11, fill: '#334155', fontWeight: 500 }}
                        axisLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
                        tickLine={false}
                        reversed
                        label={{
                          value: 'Treatment',
                          angle: -90,
                          position: 'insideLeft',
                          fill: '#64748b',
                          fontSize: 12,
                        }}
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const p = payload[0]?.payload as (typeof chartData)[number];
                          if (!p) return null;
                          const duration = (p.endYear - p.startYear).toFixed(1);
                          return (
                            <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-lg ring-1 ring-slate-900/5">
                              <p className="font-semibold text-slate-800 text-sm">{p.treatment}</p>
                              <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                                <dt className="text-slate-500">Start</dt>
                                <dd className="tabular-nums text-slate-700">{p.startYear}</dd>
                                <dt className="text-slate-500">End</dt>
                                <dd className="tabular-nums text-slate-700">{p.endYear}</dd>
                                <dt className="text-slate-500">Duration</dt>
                                <dd className="tabular-nums text-slate-700">{duration} years</dd>
                              </dl>
                            </div>
                          );
                        }}
                      />
                      <Bar
                        dataKey="_start"
                        stackId="timeline"
                        fill="transparent"
                        barSize={28}
                        radius={0}
                        isAnimationActive={false}
                      />
                      <Bar
                        dataKey="_duration"
                        stackId="timeline"
                        barSize={28}
                        radius={0}
                        stroke="#1e293b"
                        strokeWidth={1}
                        isAnimationActive={true}
                        animationDuration={500}
                      >
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export default function RegulatoryTimelinePage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col min-h-screen w-full bg-white">
          <header className="bg-white border-b border-gray-200 h-14 sm:h-16" />
          <main className="flex-1 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </main>
        </div>
      }
    >
      <RegulatoryTimelineContent />
    </Suspense>
  );
}
