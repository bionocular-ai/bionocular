'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { DashboardGlobalHeader } from '@/components/dashboard/DashboardGlobalHeader';
import { Loader2 } from 'lucide-react';
import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { DashboardNavLink } from '@/components/nav/DashboardNavLink';
import { DEFAULT_CANCER_TYPE_SLUG } from '@/lib/dashboard-constants';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Trial {
  label: string;       // Multi-line label (name + NCT)
  nct: string;
  start: Date;
  end: Date;
  color: string;
}

// ─── Data ─────────────────────────────────────────────────────────────────────
/** Merkel Cell Carcinoma — Phase 2 & 3 trials (from ClinicalTrials.gov) */
const MCC_TRIALS: Trial[] = [
  {
    label: 'Pembrolizumab (STAMP)',
    nct: 'NCT03712605',
    start: new Date('2018-11-01'),
    end: new Date('2026-12-01'),
    color: '#1d6fa4',
  },
  {
    label: 'Avelumab (I-MAT)',
    nct: 'NCT04291885',
    start: new Date('2020-10-01'),
    end: new Date('2030-04-01'),
    color: '#6a9e77',
  },
  {
    label: 'Vidutolimod + Cemiplimab',
    nct: 'NCT04916002',
    start: new Date('2021-06-01'),
    end: new Date('2024-10-01'),
    color: '#d97141',
  },
  {
    label: 'Neoadjuvant PD-1 Blockade',
    nct: 'NCT05496036',
    start: new Date('2023-02-01'),
    end: new Date('2027-09-01'),
    color: '#7059a6',
  },
  {
    label: 'Nivolumab + Relatlimab',
    nct: 'NCT06151236',
    start: new Date('2024-03-01'),
    end: new Date('2034-04-01'),
    color: '#b94040',
  },
];

const GANTT_BY_SLUG: Record<string, Trial[]> = {
  'merkel-cell-carcinoma': MCC_TRIALS,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

function yearFraction(d: Date): number {
  return d.getFullYear() + d.getMonth() / 12;
}

function durationYears(start: Date, end: Date): string {
  const months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
  const yr = Math.floor(months / 12);
  const mo = months % 12;
  return yr > 0 ? (mo > 0 ? `${yr}y ${mo}mo` : `${yr}y`) : `${mo}mo`;
}

// ─── Gantt Component ──────────────────────────────────────────────────────────
function GanttChart({ trials }: { trials: Trial[] }) {
  const LABEL_W = 220; // px reserved for Y-axis labels
  const BAR_H   = 28;
  const ROW_H   = 52;
  const PAD_TOP = 48; // space for x-axis ticks at top
  const PAD_BOT = 32;
  const CHART_H = PAD_TOP + trials.length * ROW_H + PAD_BOT;

  const [tooltip, setTooltip] = React.useState<{
    trial: Trial; x: number; y: number;
  } | null>(null);

  // Compute global min/max from trial dates
  const allYears = trials.flatMap(t => [yearFraction(t.start), yearFraction(t.end)]);
  const minYear = Math.floor(Math.min(...allYears)) - 0.25;
  const maxYear = Math.ceil(Math.max(...allYears))  + 0.5;
  const yearSpan = maxYear - minYear;

  function toX(year: number, chartW: number) {
    return ((year - minYear) / yearSpan) * chartW;
  }

  // Generate year ticks (every year from floor to ceil)
  const ticks: number[] = [];
  for (let y = Math.ceil(minYear); y <= Math.floor(maxYear); y++) ticks.push(y);

  const [containerW, setContainerW] = React.useState(800);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => {
      setContainerW(entries[0].contentRect.width);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const chartW = Math.max(containerW - LABEL_W - 32, 300);

  return (
    <div ref={containerRef} className="relative select-none font-sans" style={{ minHeight: CHART_H }}>
      {/* Date range labels */}
      <div style={{ marginLeft: LABEL_W }} className="flex justify-between px-0.5 pb-1">
        <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Trial Start Date</span>
        <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Est. Completion Date</span>
      </div>

      {/* Scrollable SVG */}
      <div style={{ marginLeft: LABEL_W }}>
        <svg width={chartW} height={CHART_H} style={{ overflow: 'visible' }}>
          {/* Vertical Grid Lines */}
          {ticks.map(y => {
            const x = toX(y, chartW);
            const isDecade = y % 5 === 0;
            return (
              <line
                key={y}
                x1={x} y1={0} x2={x} y2={CHART_H - 25}
                stroke={isDecade ? '#cbd5e1' : '#f1f5f9'}
                strokeWidth={isDecade ? 1.5 : 1}
              />
            );
          })}

          {/* Source label */}
          <text x={chartW} y={14} textAnchor="end" fontSize={10} fill="#94a3b8">
            Data from ClinicalTrials.gov
          </text>

          {/* Bars */}
          {trials.map((trial, i) => {
            const rowY = PAD_TOP + i * ROW_H;
            const barY = rowY + (ROW_H - BAR_H) / 2;
            const xStart = toX(yearFraction(trial.start), chartW);
            const xEnd   = toX(yearFraction(trial.end),   chartW);
            const barW   = Math.max(xEnd - xStart, 4);

            return (
              <g key={trial.nct}
                onMouseEnter={() => {
                  setTooltip({ trial, x: xEnd + LABEL_W + 8, y: barY });
                }}
                onMouseLeave={() => setTooltip(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Bar */}
                <rect
                  x={xStart} y={barY}
                  width={barW} height={BAR_H}
                  rx={3} fill={trial.color}
                  opacity={0.9}
                />
                {/* Diamond marker at completion */}
                <polygon
                  points={`${xEnd},${barY + BAR_H / 2 - 6} ${xEnd + 6},${barY + BAR_H / 2} ${xEnd},${barY + BAR_H / 2 + 6} ${xEnd - 6},${barY + BAR_H / 2}`}
                  fill="#94a3b8" stroke="#fff" strokeWidth={1}
                />
              </g>
            );
          })}
          {/* X-Axis Labels (Bottom) */}
          {ticks.map(y => {
            const x = toX(y, chartW);
            return (
              <text
                key={y}
                x={x} y={CHART_H - 8}
                textAnchor="middle"
                fontSize={11}
                fill="#94a3b8"
                fontWeight={500}
              >
                {y}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Y-axis labels (absolute positioned to the left) */}
      <div
        className="absolute top-0 left-0 flex flex-col"
        style={{ width: LABEL_W, paddingTop: PAD_TOP }}
      >
        {trials.map((trial) => (
          <div
            key={trial.nct}
            style={{ height: ROW_H }}
            className="flex flex-col justify-center pr-3"
          >
            <span className="text-[12px] font-semibold text-slate-700 leading-tight">{trial.label}</span>
            <span className="text-[10px] text-slate-400 leading-tight">({trial.nct})</span>
          </div>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-50 rounded-lg bg-white border border-slate-200 shadow-xl px-3 py-2.5 text-xs min-w-[180px]"
          style={{ left: Math.min(tooltip.x, containerW - 200), top: tooltip.y - 4 }}
        >
          <p className="font-semibold text-slate-800 mb-1.5">{tooltip.trial.label}</p>
          <p className="text-slate-500 text-[10px] mb-2">{tooltip.trial.nct}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            <dt className="text-slate-500">Start</dt>
            <dd className="text-slate-700 font-medium">{formatDate(tooltip.trial.start)}</dd>
            <dt className="text-slate-500">Est. Completion</dt>
            <dd className="text-slate-700 font-medium">{formatDate(tooltip.trial.end)}</dd>
            <dt className="text-slate-500">Duration</dt>
            <dd className="text-slate-700 font-medium">{durationYears(tooltip.trial.start, tooltip.trial.end)}</dd>
          </dl>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-3 mt-4 pl-1 flex-wrap">
        <div className="flex items-center gap-1.5">
          <div className="w-8 h-3 rounded-sm bg-slate-400 opacity-80" />
          <span className="text-[11px] text-slate-500">Trial duration</span>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width={14} height={14}>
            <polygon points="7,1 13,7 7,13 1,7" fill="#94a3b8" />
          </svg>
          <span className="text-[11px] text-slate-500">Estimated completion</span>
        </div>
      </div>
    </div>
  );
}

// ─── Page Content ──────────────────────────────────────────────────────────────
function RegulatoryTimelineContent() {
  const searchParams = useSearchParams();
  const params = useParams();
  const router = useRouter();

  const cancerTypeSlug =
    (params?.category as string) ||
    searchParams.get('cancer_type') ||
    DEFAULT_CANCER_TYPE_SLUG;

  const setCancerType = React.useCallback(
    (slug: string) => router.push(`/dashboard/${slug}/regulatory-timeline`),
    [router]
  );

  const trials = GANTT_BY_SLUG[cancerTypeSlug];

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
              <HomeNavLink />
              <DashboardNavLink />
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

        <div className="w-full bg-white rounded-lg shadow px-6 py-6">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-slate-800 tracking-tight">
              Clinical Trial Gantt Chart
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              Phase 2 &amp; 3 trials · Start and estimated completion dates · Hover for details
            </p>
          </div>

          {trials ? (
            <GanttChart trials={trials} />
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <p className="text-base font-medium">No timeline data available for this indication.</p>
              <p className="text-sm mt-1">Timeline data is currently available for Merkel Cell Carcinoma.</p>
            </div>
          )}
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
