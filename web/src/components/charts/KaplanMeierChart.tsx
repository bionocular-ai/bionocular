'use client';

import { Fragment, useMemo } from 'react';
import {
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  type TooltipContentProps,
} from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';
import type { KmCurveRow } from '@/lib/api';
import { formatArmName } from '@/lib/utils/arm-name';

// Series palette — mirrors the dashboard TREATMENT_COLORS ordering.
const CURVE_COLORS = [
  '#3b82f6', // blue
  '#15803d', // green
  '#f59e0b', // amber
  '#dc2626', // red
  '#7c3aed', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
];

const AXIS = '#64748b';
const GRID = '#e2e8f0';
const AXIS_TICK = { fontSize: 14, fill: AXIS };
const AXIS_TITLE = { fill: AXIS, fontSize: 16, fontWeight: 600 };

// Fixed time axis (months). Curves end at their own last coordinate; points
// beyond X_MAX are dropped.
const X_MAX = 30;
const X_TICKS = [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30];
const Y_TICKS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

/** One endpoint's curves, drawn in its own line style. */
export interface KmSeries {
  /** Endpoint code, e.g. "PFS". */
  endpoint: string;
  /** Reconstructed digitized-twin curves to plot - one line per arm. */
  curves: KmCurveRow[];
  /** Approximate HR shown in the plot's corner when exactly 2 arms are selected. */
  hr?: { value: number; cmpName: string; refName: string } | null;
}

interface KaplanMeierChartProps {
  /** Up to two endpoints sharing the axes; the second is drawn dashed. */
  series: KmSeries[];
}

// Line style per endpoint, by series position.
export const SERIES_DASH = [undefined, '6 4'];

/**
 * Series color per curve id, given each endpoint's curves. An arm keeps one
 * color across endpoints so its OS and PFS curves read as the same arm. The arm
 * is publication + arm name: comparison_label is usually a per-figure index that
 * differs between endpoints. Same-named arms within one endpoint (two cohorts)
 * pair up across endpoints in order.
 */
export function armColors(series: KmCurveRow[][]): Map<string, string> {
  const armIndex = new Map<string, number>();
  const colors = new Map<string, string>();
  for (const curves of series) {
    const seen = new Map<string, number>();
    for (const c of curves) {
      const name = `${c.publication_id}||${c.arm_name}`;
      const n = seen.get(name) ?? 0;
      seen.set(name, n + 1);
      const arm = `${name}||${n}`;
      if (!armIndex.has(arm)) armIndex.set(arm, armIndex.size);
      colors.set(c.id, CURVE_COLORS[armIndex.get(arm)! % CURVE_COLORS.length]);
    }
  }
  return colors;
}

/** A short sample of a curve's line, for keying an arm outside the plot. */
export function Swatch({ color, dash }: { color: string; dash?: string }) {
  return (
    <svg width="22" height="3" aria-hidden className="shrink-0">
      <line x1="0" y1="1.5" x2="22" y2="1.5" stroke={color} strokeWidth="2.5" strokeDasharray={dash} />
    </svg>
  );
}

/**
 * Reshape per-arm step points into a single wide series keyed by time.
 * For each arm we carry forward the last known survival value so the line is a
 * proper KM step function sampled at the union of all time points.
 */
function toWideSeries(curves: KmCurveRow[]): Array<Record<string, number | null>> {
  const times = new Set<number>();
  for (const c of curves) for (const p of c.twin_coords) if (p.time <= X_MAX) times.add(p.time);
  const sortedTimes = [...times].sort((a, b) => a - b);

  return sortedTimes.map((time) => {
    const row: Record<string, number | null> = { time };
    for (const c of curves) {
      const sorted = [...c.twin_coords].sort((a, b) => a.time - b.time);
      const lastTime = sorted.length ? sorted[sorted.length - 1].time : 0;
      let value: number | null = null;
      // Carry the step value forward, but stop at the arm's last coordinate so
      // the line ends where its data ends rather than running to the axis edge.
      for (const p of sorted) {
        if (p.time <= time) value = p.surv;
        else break;
      }
      row[c.id] = time <= lastTime ? value : null;
    }
    return row;
  });
}

/** Index of the last row where curve `id` has a value: where its line ends. */
export function lastIndex(data: Array<Record<string, number | null>>, id: string): number {
  return data.findLastIndex((row) => row[id] != null);
}

// The endpoint names its curve just past the line's end.
// ponytail: no collision avoidance; arms ending at the same time and survival overlap labels.
function endLabel(endpoint: string, last: number, color: string) {
  return function EndLabel({ x, y, index }: { x?: number | string; y?: number | string; index?: number }) {
    if (index !== last || x == null || y == null) return null;
    return (
      <text x={Number(x) + 6} y={Number(y)} dominantBaseline="central" fill={color} fontSize={14} fontWeight={600}>
        {endpoint}
      </text>
    );
  };
}

type TooltipRow = { id: string; endpoint: string; arm: string; color: string; dash?: string };

/** Survival at the hovered month: one row per curve still running, in table order (OS arms, then PFS). */
function KmTooltip({ active, payload, label, rows }: TooltipContentProps<ValueType, NameType> & { rows: TooltipRow[] }) {
  if (!active || !payload?.length) return null;
  const value = new Map(payload.map((p) => [String(p.dataKey), p.value]));
  const shown = rows.filter((r) => value.get(r.id) != null);
  return (
    <div className="rounded-lg border border-(--brand-border) bg-(--brand-surface) px-3 py-2.5 text-xs shadow-[0_4px_16px_rgba(16,43,54,0.08)]">
      <div className="mb-1.5 font-medium tabular-nums text-(--brand-text-muted)">{Number(label).toFixed(1)} mo</div>
      <div className="grid grid-cols-[auto_auto_1fr_auto] items-center gap-x-2.5 gap-y-1.5">
        {shown.map((r) => (
          <Fragment key={r.id}>
            <span className="text-(--brand-text-muted)">{r.endpoint}</span>
            <Swatch color={r.color} dash={r.dash} />
            <span className="text-(--brand-text)">{r.arm}</span>
            <span className="pl-3 text-right font-semibold tabular-nums text-(--brand-text)">
              {Number(value.get(r.id)).toFixed(1)}%
            </span>
          </Fragment>
        ))}
      </div>
    </div>
  );
}

export default function KaplanMeierChart({ series }: KaplanMeierChartProps) {
  const curves = useMemo(() => series.flatMap((s) => s.curves), [series]);
  const data = useMemo(() => toWideSeries(curves), [curves]);
  const colors = useMemo(() => armColors(series.map((s) => s.curves)), [series]);
  const drawn = series.map((s, i) => ({ ...s, dash: SERIES_DASH[i] })).filter((s) => s.curves.length);
  const tooltipRows = drawn.flatMap((s) => s.curves.map((c) => ({
    id: c.id, endpoint: s.endpoint, arm: formatArmName(c.arm_name), color: colors.get(c.id)!, dash: s.dash,
  })));

  if (curves.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px] text-slate-400 text-sm">
        No curves selected
      </div>
    );
  }

  return (
    <div className="relative w-full">
      {/* Hazard ratios in the plot's top-right corner, where KM curves rarely run;
          above the plot on phones, where the corner is too small to hold them.
          ponytail: fixed corner; an arm holding near 100% late would run under the chips. */}
      {drawn.some((s) => s.hr) && (
        <div className="flex justify-center gap-2 pb-2 sm:absolute sm:right-[60px] sm:top-4 sm:z-10 sm:pb-0">
          {drawn.map((s) => s.hr && (
            <span
              key={s.endpoint}
              className="inline-flex items-baseline gap-1.5 rounded-full bg-(--brand-accent-light) px-2.5 py-1 text-[13px] text-(--brand-primary)"
            >
              <span className="font-medium tracking-wide">HR {s.endpoint}</span>
              <span className="font-semibold tabular-nums">
                {s.hr.value.toFixed(2)}
              </span>
            </span>
          ))}
        </div>
      )}
      {/* Taller on wider screens so the plot keeps a readable aspect (~2:1) and still fits a laptop screen. */}
      <div className="h-[460px] sm:h-[560px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 44, bottom: 32, left: 12 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis
          dataKey="time"
          type="number"
          domain={[0, X_MAX]}
          ticks={X_TICKS}
          allowDataOverflow
          tick={AXIS_TICK}
          tickLine={{ stroke: GRID }}
          axisLine={{ stroke: GRID }}
          label={{ value: 'Time (months)', position: 'insideBottom', offset: -16, style: AXIS_TITLE }}
        />
        <YAxis
          domain={[0, 100]}
          ticks={Y_TICKS}
          tick={AXIS_TICK}
          tickLine={{ stroke: GRID }}
          axisLine={{ stroke: GRID }}
          label={{
            value: 'Survival (%)',
            angle: -90,
            position: 'insideLeft',
            style: { ...AXIS_TITLE, textAnchor: 'middle' },
          }}
        />
        <Tooltip
          cursor={{ stroke: AXIS, strokeDasharray: '3 3' }}
          content={(props) => <KmTooltip {...props} rows={tooltipRows} />}
        />
        {drawn.flatMap((s) => s.curves.map((c) => (
          <Line
            key={c.id}
            type="stepAfter"
            dataKey={c.id}
            name={`${formatArmName(c.arm_name)} · ${s.endpoint}`}
            stroke={colors.get(c.id)}
            strokeDasharray={s.dash}
            strokeWidth={2.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
            label={endLabel(s.endpoint, lastIndex(data, c.id), colors.get(c.id)!)}
          />
        )))}
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
