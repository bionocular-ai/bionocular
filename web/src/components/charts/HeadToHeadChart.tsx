'use client';

import { useMemo } from 'react';
import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Scatter,
  ComposedChart,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { HeadToHeadDataPoint, TrialDataPoint, EFFICACY_METRICS, EfficacyMetric } from '@/types/analytics';
import { flattenScatterData } from '@/lib/chart-transformers';

// ============================================================================
// Color Palette
// ============================================================================

const COLORS = {
  bar: {
    approved: '#0ea5e9',
    investigational: '#8b5cf6',
    unknown: '#64748b',
  },
  scatter: {
    high: '#10b981',
    medium: '#f59e0b',
    low: '#ef4444',
  },
  grid: '#334155',
  axis: '#94a3b8',
  tooltip: {
    bg: '#1e293b',
    border: '#334155',
    text: '#f1f5f9',
    muted: '#94a3b8',
  },
};

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: HeadToHeadDataPoint | (TrialDataPoint & { treatmentName: string });
    dataKey?: string;
  }>;
  metricLabel?: string;
  metricUnit: string;
}

function CustomTooltip({ active, payload, metricUnit }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0].payload;

  // Check if this is a scatter point (has studyId) or a bar (has treatmentName at root)
  if ('studyId' in data) {
    const trial = data as TrialDataPoint & { treatmentName: string };
    return (
      <div className="bg-slate-800 p-4 rounded-xl shadow-2xl border border-slate-700 min-w-[280px]">
        <div className="flex items-start justify-between gap-3 mb-3">
          <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-sky-900/50 text-sky-300 text-xs font-bold tracking-wide">
            {trial.studyId}
          </span>
          <span className="text-xs text-slate-400 font-medium">
            {trial.phase}
          </span>
        </div>
        
        <p className="text-sm text-slate-300 mb-3 font-medium">
          {trial.treatmentName}
        </p>
        
        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-3xl font-bold text-white tabular-nums">
            {trial.value.toFixed(1)}
          </span>
          <span className="text-sm text-slate-400">
            {metricUnit}
          </span>
        </div>

        <div className="pt-3 border-t border-slate-700 space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Citation</span>
            <span className="text-slate-200 font-medium">{trial.citation}</span>
          </div>
          {trial.nctNumber && (
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">NCT</span>
              <span className="text-sky-400 font-mono">{trial.nctNumber}</span>
            </div>
          )}
          {trial.numberOfPatients && (
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Patients</span>
              <span className="text-slate-200 font-medium">n={trial.numberOfPatients}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Bar tooltip
  const treatment = data as HeadToHeadDataPoint;
  return (
    <div className="bg-slate-800 p-4 rounded-xl shadow-2xl border border-slate-700 min-w-[260px]">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h4 className="font-bold text-white text-sm leading-tight max-w-[180px]">
          {treatment.treatmentName}
        </h4>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
          treatment.approvalStatus === 'Approved' 
            ? 'bg-emerald-900/50 text-emerald-300'
            : 'bg-violet-900/50 text-violet-300'
        }`}>
          {treatment.approvalStatus}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-3xl font-bold text-white tabular-nums">
          {treatment.averageValue.toFixed(1)}
        </span>
        <span className="text-sm text-slate-400">
          {metricUnit} avg
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-700">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Range</p>
          <p className="text-sm font-semibold text-slate-200 tabular-nums">
            {treatment.minValue.toFixed(1)} – {treatment.maxValue.toFixed(1)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Median</p>
          <p className="text-sm font-semibold text-slate-200 tabular-nums">
            {treatment.medianValue.toFixed(1)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Trials</p>
          <p className="text-sm font-semibold text-slate-200">
            {treatment.trialCount}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Patients</p>
          <p className="text-sm font-semibold text-slate-200">
            {treatment.totalPatients > 0 ? `n=${treatment.totalPatients}` : '—'}
          </p>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

interface HeadToHeadChartProps {
  data: HeadToHeadDataPoint[];
  metric?: EfficacyMetric;
  title?: string;
  description?: string;
  height?: number;
  showLegend?: boolean;
  showReferenceLine?: boolean;
  referenceValue?: number;
}

export default function HeadToHeadChart({
  data,
  metric = 'MEDIAN_OS',
  title,
  description,
  height = 500,
  showLegend = true,
  showReferenceLine = false,
  referenceValue,
}: HeadToHeadChartProps) {
  const metricConfig = EFFICACY_METRICS[metric];
  const metricLabel = metricConfig.label;
  const metricUnit = metricConfig.unit;

  // Flatten scatter data for overlay
  const scatterData = useMemo(() => flattenScatterData(data), [data]);

  // Calculate overall average for reference line
  const overallAverage = useMemo(() => {
    if (referenceValue !== undefined) return referenceValue;
    const allValues = data.flatMap(d => d.trials.map(t => t.value));
    return allValues.length > 0 
      ? allValues.reduce((a, b) => a + b, 0) / allValues.length 
      : 0;
  }, [data, referenceValue]);

  // Determine scatter point color based on value
  const getScatterColor = (value: number) => {
    const p75 = overallAverage * 1.25;
    const p25 = overallAverage * 0.75;
    if (value >= p75) return COLORS.scatter.high;
    if (value <= p25) return COLORS.scatter.low;
    return COLORS.scatter.medium;
  };

  if (data.length === 0) {
    return (
      <Card className="w-full bg-slate-900 border-slate-800">
        <CardContent className="flex items-center justify-center h-[400px]">
          <p className="text-slate-400">
            No data available for the selected filters
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full overflow-hidden bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-xl font-bold text-white">
              {title || 'Head-to-Head Efficacy Comparison'}
            </CardTitle>
            <CardDescription className="mt-1 text-slate-400">
              {description || `Comparing ${metricLabel} (${metricUnit}) across treatment arms. Bars show weighted averages; dots show individual trial results.`}
            </CardDescription>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: COLORS.bar.approved }} />
              <span className="text-slate-300">Approved</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: COLORS.bar.investigational }} />
              <span className="text-slate-300">Investigational</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {showLegend && (
          <div className="flex items-center justify-center gap-6 text-xs mb-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full border-2 border-slate-800" style={{ background: COLORS.scatter.high }} />
              <span className="text-slate-300">High response</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full border-2 border-slate-800" style={{ background: COLORS.scatter.medium }} />
              <span className="text-slate-300">Average</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full border-2 border-slate-800" style={{ background: COLORS.scatter.low }} />
              <span className="text-slate-300">Below average</span>
            </div>
          </div>
        )}

        <div style={{ width: '100%', height: height }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={data}
              margin={{ top: 20, right: 30, bottom: 100, left: 60 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={COLORS.grid}
                strokeOpacity={0.3}
              />

              <XAxis
                dataKey="treatmentName"
                type="category"
                tick={{ fontSize: 10, fill: COLORS.axis }}
                tickLine={{ stroke: COLORS.grid }}
                axisLine={{ stroke: COLORS.grid }}
                interval={0}
                angle={-45}
                textAnchor="end"
                height={100}
              />

              <YAxis
                type="number"
                tick={{ fontSize: 11, fill: COLORS.axis }}
                tickLine={{ stroke: COLORS.grid }}
                axisLine={{ stroke: COLORS.grid }}
                domain={[0, 'dataMax+10']}
                label={{
                  value: `${metricLabel} (${metricUnit})`,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: COLORS.axis, fontSize: 12 },
                }}
              />

              <Tooltip
                content={<CustomTooltip metricLabel={metricLabel} metricUnit={metricUnit} />}
                cursor={{ fill: 'rgba(148, 163, 184, 0.1)' }}
              />

              {showReferenceLine && (
                <ReferenceLine
                  y={overallAverage}
                  stroke="#94a3b8"
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                  label={{
                    value: `Avg: ${overallAverage.toFixed(1)}`,
                    position: 'right',
                    fill: '#94a3b8',
                    fontSize: 11,
                  }}
                />
              )}

              {/* Average Value Bars */}
              <Bar
                dataKey="averageValue"
                barSize={40}
                radius={[4, 4, 0, 0]}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.approvalStatus === 'Approved'
                        ? COLORS.bar.approved
                        : entry.approvalStatus === 'Investigational'
                        ? COLORS.bar.investigational
                        : COLORS.bar.unknown
                    }
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>

              {/* Individual Trial Scatter Points */}
              <Scatter
                data={scatterData}
                dataKey="value"
              >
                {scatterData.map((entry, index) => (
                  <Cell
                    key={`scatter-${index}`}
                    fill={getScatterColor(entry.value)}
                    stroke="#1e293b"
                    strokeWidth={2}
                  />
                ))}
              </Scatter>
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Summary Stats */}
        <div className="mt-6 pt-4 border-t border-slate-800">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-white tabular-nums">
                {data.length}
              </p>
              <p className="text-xs text-slate-400 uppercase tracking-wider">
                Treatments
              </p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-white tabular-nums">
                {scatterData.length}
              </p>
              <p className="text-xs text-slate-400 uppercase tracking-wider">
                Trial Results
              </p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-sky-400 tabular-nums">
                {data.filter(d => d.approvalStatus === 'Approved').length}
              </p>
              <p className="text-xs text-slate-400 uppercase tracking-wider">
                Approved
              </p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet-400 tabular-nums">
                {data.filter(d => d.approvalStatus === 'Investigational').length}
              </p>
              <p className="text-xs text-slate-400 uppercase tracking-wider">
                Investigational
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
