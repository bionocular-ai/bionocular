'use client';

import { useMemo, useState, useEffect, useRef } from 'react';
import {
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  Scatter,
  LabelList,
} from 'recharts';
import { Card, CardContent } from '@/components/ui/card';

// ============================================================================
// Types
// ============================================================================

export interface DumbbellDataPoint {
  treatmentName: string;
  /** First survival outcome (e.g. PFS months) */
  valueA: number;
  /** Second survival outcome (e.g. OS months) */
  valueB: number;
  /** Optional: used for bubble size (e.g. HR) */
  hr?: number;
}

interface DumbbellChartProps {
  data: DumbbellDataPoint[];
  /** Label for first series (e.g. "Time to Progression (PFS)") */
  labelA: string;
  /** Label for second series (e.g. "Total Survival (OS)") */
  labelB: string;
  /** X-axis label (e.g. "Survival Duration (Months)") */
  xAxisLabel?: string;
  /** Y-axis label (e.g. "Treatment") */
  yAxisLabel?: string;
  height?: number;
  compact?: boolean;
  /** Use HR for bubble size when true and hr is present in data */
  useHrForBubbleSize?: boolean;
}

const COLOR_A = '#3b82f6'; // Medium blue (PFS)
const COLOR_B = '#1e3a5f'; // Dark navy (OS)
const CONNECTOR_STROKE = '#94a3b8'; // Dumbbell connector line
const MIN_RADIUS = 6;
const MAX_RADIUS = 18;
const GRID_STROKE = '#e5e7eb'; // Uniform light gray for grid and axis lines (reference consistency)
const AXIS_STROKE = '#e2e8f0'; // Slightly visible axis border

// ============================================================================
// Custom scatter shape with optional size from hr
// ============================================================================

function DumbbellScatterShape(props: {
  cx?: number;
  cy?: number;
  payload?: DumbbellDataPoint;
  dataKey: string;
  fill: string;
  radiusScale?: (hr: number) => number;
}) {
  const { cx = 0, cy = 0, payload, fill, radiusScale } = props;
  const hr = payload?.hr;
  let r = 8;
  if (radiusScale && hr !== undefined && hr !== null && !Number.isNaN(hr) && hr > 0) {
    r = Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, radiusScale(hr)));
  }
  return <circle cx={cx} cy={cy} r={r} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

/** Props Recharts LabelList passes to content (dataKey we provide). value is RenderableText so we accept unknown. */
interface LabelListContentProps {
  x?: number | string;
  y?: number | string;
  value?: unknown;
  payload?: DumbbellDataPoint;
}

// Value label above each bubble (reference: "numerical value displayed directly above it, in a smaller font")
function ValueLabelAbove(props: LabelListContentProps & { dataKey: string }) {
  const { payload, dataKey } = props;
  const x = Number(props.x) || 0;
  const y = Number(props.y) || 0;
  const rawNum = props.value ?? (dataKey === 'valueA' ? payload?.valueA : payload?.valueB);
  const num = typeof rawNum === 'number' && !Number.isNaN(rawNum) ? rawNum : null;
  if (num == null) return null;
  const text = num.toFixed(1);
  return (
    <text x={x} y={y - 14} textAnchor="middle" fill="#475569" fontSize={10} fontWeight={500}>
      {text}
    </text>
  );
}

// ============================================================================
// Custom Tooltip
// ============================================================================

type DumbbellTooltipPayload = readonly { payload: DumbbellDataPoint; name: string; value: number }[] | undefined;

const CustomTooltip = ({
  active,
  payload,
  labelA,
  labelB,
}: {
  active?: boolean;
  payload?: DumbbellTooltipPayload;
  labelA: string;
  labelB: string;
}) => {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]!.payload;
  return (
    <div className="bg-slate-800 text-white text-xs rounded-lg shadow-xl border border-slate-700 px-3 py-2 min-w-[180px]">
      <div className="font-semibold border-b border-slate-600 pb-1.5 mb-1.5">{p.treatmentName}</div>
      <div className="flex justify-between gap-4">
        <span className="text-slate-400">{labelA}</span>
        <span className="font-medium tabular-nums">{p.valueA.toFixed(1)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-slate-400">{labelB}</span>
        <span className="font-medium tabular-nums">{p.valueB.toFixed(1)}</span>
      </div>
      {p.hr != null && !Number.isNaN(p.hr) && (
        <div className="flex justify-between gap-4 mt-1 pt-1 border-t border-slate-600">
          <span className="text-slate-400">HR (bubble size)</span>
          <span className="font-medium tabular-nums">{p.hr.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Component
// ============================================================================

export default function DumbbellChart({
  data,
  labelA,
  labelB,
  xAxisLabel = 'Survival Duration (Months)',
  yAxisLabel = 'Treatment',
  height = 400,
  compact = false,
  useHrForBubbleSize = true,
}: DumbbellChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [containerDims, setContainerDims] = useState<{width: number; height: number}>({ width: 400, height: 300 });

  // Use ResizeObserver to track actual dimensions
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setContainerDims({ width, height });
        }
      }
    });

    observer.observe(chartContainerRef.current);
    return () => observer.disconnect();
  }, []);

  const { xDomain, xTicks } = useMemo(() => {
    const vals = data.flatMap((d) => [d.valueA, d.valueB]).filter((v) => typeof v === 'number' && !Number.isNaN(v));
    if (vals.length === 0) return { xDomain: [0, 24] as [number, number], xTicks: [0, 5, 10, 15, 20, 25] };
    const rawMin = Math.min(0, ...vals);
    const rawMax = Math.max(...vals);
    const range = rawMax - rawMin || 1;
    const padding = range * 0.08;
    const min = Math.floor(rawMin - padding);
    const max = Math.ceil(rawMax + padding);
    const span = max - min || 1;
    // Nice step based on span (reference: uniform intervals e.g. 5, 10, 15... or 0, 20, 40, 60, 80)
    const step = span <= 10 ? 2 : span <= 25 ? 5 : span <= 60 ? 10 : span <= 120 ? 20 : 30;
    // When data is non-negative, start at 0 so grid has a vertical line at origin (reference image)
    const domainMin = rawMin >= 0 ? 0 : Math.floor(min / step) * step;
    const domainMax = Math.ceil((rawMax + padding) / step) * step;
    const tickMax = Math.max(domainMax, max);
    const ticks: number[] = [];
    for (let t = domainMin; t <= tickMax; t += step) ticks.push(t);
    if (ticks.length === 0) ticks.push(domainMin, domainMax);
    // Keep all ticks so vertical grid line at origin (and every interval) is shown; uniform column width
    return { xDomain: [domainMin, Math.max(tickMax, domainMax)] as [number, number], xTicks: ticks };
  }, [data]);

  const radiusScale = useMemo(() => {
    if (!useHrForBubbleSize) return undefined;
    const hrs = data.map((d) => d.hr).filter((h): h is number => h != null && !Number.isNaN(h) && h > 0);
    if (hrs.length === 0) return undefined;
    const minHr = Math.min(...hrs);
    const maxHr = Math.max(...hrs);
    const range = maxHr - minHr || 1;
    return (hr: number) => MIN_RADIUS + ((hr - minHr) / range) * (MAX_RADIUS - MIN_RADIUS);
  }, [data, useHrForBubbleSize]);

  if (data.length === 0) {
    return (
      <Card className="w-full bg-slate-50 rounded-lg border border-slate-200 shadow-sm">
        <CardContent className={`flex items-center justify-center ${compact ? 'h-[200px]' : 'h-[300px]'}`}>
          <p className="text-slate-500 text-sm">No data available</p>
        </CardContent>
      </Card>
    );
  }

  const margin = compact ? { top: 28, right: 24, left: 16, bottom: 28 } : { top: 36, right: 32, left: 20, bottom: 32 };
  const tickFontSize = compact ? 10 : 11;

  const chartHeight = height || 400;

  return (
    <Card className={`w-full bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col min-h-0 ${compact ? 'h-full' : ''}`}>
      <CardContent className={`p-0 overflow-hidden rounded-lg flex flex-col min-h-0 ${compact ? 'h-full' : ''}`}>
        {/* Parameters with color above the plot */}
        <div className={`flex flex-wrap items-center justify-center gap-x-4 gap-y-1 flex-shrink-0 ${compact ? 'px-2 py-1.5' : 'px-3 py-2'} border-b border-slate-200 bg-slate-50/80`}>
          <span className="inline-flex items-center gap-1.5 text-slate-600" style={{ fontSize: compact ? 11 : 12 }}>
            <span className="inline-block w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLOR_A }} aria-hidden />
            <span className="font-medium">{labelA}</span>
          </span>
          <span className="text-slate-400 hidden sm:inline">|</span>
          <span className="inline-flex items-center gap-1.5 text-slate-600" style={{ fontSize: compact ? 11 : 12 }}>
            <span className="inline-block w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLOR_B }} aria-hidden />
            <span className="font-medium">{labelB}</span>
          </span>
          {useHrForBubbleSize && (
            <>
              <span className="text-slate-400 hidden sm:inline">|</span>
              <span className="text-slate-500" style={{ fontSize: compact ? 10 : 11 }}>
                Bubble size = HR
              </span>
            </>
          )}
        </div>
        <div ref={chartContainerRef} className="w-full min-h-0 flex-1" style={!compact ? { height: chartHeight, flex: 'none' } : undefined}>
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ComposedChart data={data} layout="vertical" margin={margin}>
              <CartesianGrid
                strokeDasharray="0"
                stroke={GRID_STROKE}
                strokeWidth={1}
                horizontal={true}
                vertical={true}
              />
              <XAxis
                type="number"
                domain={xDomain}
                ticks={xTicks}
                tick={{ fontSize: tickFontSize, fill: '#475569', fontWeight: 500 }}
                tickLine={{ stroke: GRID_STROKE, strokeWidth: 1 }}
                axisLine={{ stroke: AXIS_STROKE, strokeWidth: 1 }}
                label={
                  xAxisLabel
                    ? { value: xAxisLabel, position: 'insideBottom', offset: compact ? -8 : -12, style: { fontSize: tickFontSize, fill: '#64748b', fontWeight: 600 } }
                    : undefined
                }
              />
              <YAxis
                type="category"
                dataKey="treatmentName"
                width={compact ? 120 : 160}
                tick={{ fontSize: tickFontSize, fill: '#475569', fontWeight: 500 }}
                tickLine={{ stroke: GRID_STROKE, strokeWidth: 1 }}
                axisLine={{ stroke: AXIS_STROKE, strokeWidth: 1 }}
                interval={0}
                padding={{ top: 0, bottom: 0 }}
                label={compact ? undefined : { value: yAxisLabel, angle: -90, position: 'insideLeft', style: { fontSize: tickFontSize, fill: '#64748b', fontWeight: 600 } }}
              />
              <Tooltip
                content={({ active, payload }: { active?: boolean; payload?: DumbbellTooltipPayload }) => (
                  <CustomTooltip active={active} payload={payload} labelA={labelA} labelB={labelB} />
                )}
              />
              {/* Connecting line segments */}
              {data.map((row) => (
                <ReferenceLine
                  key={row.treatmentName}
                  segment={[{ x: row.valueA, y: row.treatmentName }, { x: row.valueB, y: row.treatmentName }]}
                  stroke={CONNECTOR_STROKE}
                  strokeWidth={2}
                  strokeDasharray="0"
                />
              ))}
              <Scatter
                dataKey="valueA"
                fill={COLOR_A}
                name={labelA}
                shape={(props: { cx?: number; cy?: number; payload?: DumbbellDataPoint }) => (
                  <DumbbellScatterShape
                    cx={props.cx}
                    cy={props.cy}
                    payload={props.payload}
                    dataKey="valueA"
                    fill={COLOR_A}
                    radiusScale={radiusScale}
                  />
                )}
              >
                <LabelList dataKey="valueA" content={(p: LabelListContentProps) => <ValueLabelAbove {...p} dataKey="valueA" />} />
              </Scatter>
              <Scatter
                dataKey="valueB"
                fill={COLOR_B}
                name={labelB}
                shape={(props: { cx?: number; cy?: number; payload?: DumbbellDataPoint }) => (
                  <DumbbellScatterShape
                    cx={props.cx}
                    cy={props.cy}
                    payload={props.payload}
                    dataKey="valueB"
                    fill={COLOR_B}
                    radiusScale={radiusScale}
                  />
                )}
              >
                <LabelList dataKey="valueB" content={(p: LabelListContentProps) => <ValueLabelAbove {...p} dataKey="valueB" />} />
              </Scatter>
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
