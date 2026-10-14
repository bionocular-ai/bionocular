'use client';

import { useMemo } from 'react';
import {
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
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
  /** Approximate HR shown in the legend when exactly 2 arms are selected. */
  hr?: { value: number; cmpName: string; refName: string } | null;
}

interface KaplanMeierChartProps {
  /** Up to two endpoints sharing the axes; the second is drawn dashed. */
  series: KmSeries[];
  height?: number;
}

// Line style per endpoint, by series position.
const SERIES_DASH = [undefined, '6 4'];

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

function Swatch({ color, dash }: { color: string; dash?: string }) {
  return (
    <svg width="16" height="2" aria-hidden className="shrink-0">
      <line x1="0" y1="1" x2="16" y2="1" stroke={color} strokeWidth="2" strokeDasharray={dash} />
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

export default function KaplanMeierChart({ series, height = 460 }: KaplanMeierChartProps) {
  const curves = useMemo(() => series.flatMap((s) => s.curves), [series]);
  const data = useMemo(() => toWideSeries(curves), [curves]);
  const colors = useMemo(() => armColors(series.map((s) => s.curves)), [series]);
  const drawn = series.map((s, i) => ({ ...s, dash: SERIES_DASH[i] })).filter((s) => s.curves.length);

  if (curves.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px] text-slate-400 text-sm">
        No curves selected
      </div>
    );
  }

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 24, bottom: 28, left: 8 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis
          dataKey="time"
          type="number"
          domain={[0, X_MAX]}
          ticks={X_TICKS}
          allowDataOverflow
          tick={{ fontSize: 12, fill: AXIS }}
          tickLine={{ stroke: GRID }}
          axisLine={{ stroke: GRID }}
          label={{ value: 'Time (months)', position: 'insideBottom', offset: -12, fill: AXIS, fontSize: 12 }}
        />
        <YAxis
          domain={[0, 100]}
          ticks={Y_TICKS}
          tick={{ fontSize: 12, fill: AXIS }}
          tickLine={{ stroke: GRID }}
          axisLine={{ stroke: GRID }}
          label={{
            value: 'Survival (%)',
            angle: -90,
            position: 'insideLeft',
            style: { textAnchor: 'middle', fill: AXIS, fontSize: 12, fontWeight: 600 },
          }}
        />
        <Tooltip
          formatter={(value, name) => [
            value == null ? '—' : `${Number(value).toFixed(1)}%`,
            name,
          ]}
          labelFormatter={(t) => `${t} mo`}
          contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: GRID }}
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
          />
        )))}
        </LineChart>
      </ResponsiveContainer>
      {/* HTML legend under the plot, one column per endpoint. Kept out of the
          plot so it never covers a curve, however many arms are selected. */}
      <div className="mt-1 flex flex-wrap justify-center gap-x-12 gap-y-3 text-xs">
        {drawn.map((s) => (
          <div key={s.endpoint}>
            {drawn.length > 1 && (
              <div className="flex items-center gap-2 pb-0.5">
                <Swatch color={AXIS} dash={s.dash} />
                <span className="font-medium uppercase tracking-wide text-slate-400">{s.endpoint}</span>
              </div>
            )}
            {s.curves.map((c) => (
              <div key={c.id} className="flex items-center gap-2 py-0.5">
                <Swatch color={colors.get(c.id)!} dash={s.dash} />
                <span className="text-slate-700">{formatArmName(c.arm_name)}</span>
              </div>
            ))}
            {s.hr && (
              <div className="flex items-center gap-2 py-0.5">
                <span className="font-medium uppercase tracking-wide text-slate-400">HR</span>
                <span className="font-bold tabular-nums text-slate-900">{s.hr.value.toFixed(2)}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
