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

interface KaplanMeierChartProps {
  /** Reconstructed digitized-twin curves to plot — one line per arm. */
  curves: KmCurveRow[];
  /** Endpoint label for the Y-axis, e.g. "PFS". */
  endpoint: string;
  height?: number;
  /** Approximate HR shown below the legend when exactly 2 arms are selected. */
  hr?: { value: number; cmpName: string; refName: string } | null;
}

/** Series color for the arm at a given legend position. */
export function armColor(index: number): string {
  return CURVE_COLORS[index % CURVE_COLORS.length];
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

export default function KaplanMeierChart({ curves, endpoint, height = 460, hr }: KaplanMeierChartProps) {
  const data = useMemo(() => toWideSeries(curves), [curves]);

  if (curves.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px] text-slate-400 text-sm">
        No curves selected
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      {/* HTML legend overlay — kept out of Recharts so it doesn't reserve layout
          space and shrink the plot. Sits inside the plot at the top-right. */}
      <div
        className="absolute top-3 right-7 z-10 rounded-md border bg-white/90 px-2.5 py-1.5 text-xs"
        style={{ borderColor: GRID }}
      >
        {curves.map((c, i) => (
          <div key={c.id} className="flex items-center gap-2 py-0.5">
            <span className="inline-block h-0.5 w-4 rounded" style={{ background: armColor(i) }} />
            <span className="text-slate-700">{formatArmName(c.arm_name)}</span>
          </div>
        ))}
        {hr && (
          <div className="mt-1.5 border-t pt-1.5 flex items-center gap-2" style={{ borderColor: GRID }}>
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">HR</span>
            <span className="text-xs font-bold tabular-nums text-slate-900">{hr.value.toFixed(2)}</span>
          </div>
        )}
      </div>
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
            value: `${endpoint} (%)`,
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
        {curves.map((c, i) => (
          <Line
            key={c.id}
            type="stepAfter"
            dataKey={c.id}
            name={formatArmName(c.arm_name)}
            stroke={armColor(i)}
            strokeWidth={2.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
