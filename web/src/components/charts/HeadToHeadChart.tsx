'use client';

import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import {
  Bar,
  BarChart,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Rectangle,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { HeadToHeadDataPoint, TrialDataPoint, ALL_METRICS, ChartMetric } from '@/types/analytics';

// ============================================================================
// Types
// ============================================================================

interface ScatterPoint extends TrialDataPoint {
  treatmentName: string;
}

interface TooltipData {
  type: 'bar' | 'scatter';
  data: HeadToHeadDataPoint | ScatterPoint;
  x: number;
  y: number;
}

interface BarShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
  fillOpacity?: number;
  payload?: HeadToHeadDataPoint;
  background?: { height: number; y: number };
}

// ============================================================================
// Color Palette
// ============================================================================

const COLORS = {
  bar: {
    approved: '#3b82f6',
    investigational: '#8b5cf6',
    unknown: '#64748b',
  },
  dot: {
    fill: '#1f2937',
    stroke: '#9ca3af',
  },
  grid: '#e2e8f0',
  axis: '#64748b',
};

const DARK_COLORS = {
  bar: {
    approved: '#0ea5e9',
    investigational: '#8b5cf6',
    unknown: '#64748b',
  },
  dot: {
    fill: '#475569',
    stroke: '#e2e8f0',
  },
  grid: '#334155',
  axis: '#94a3b8',
};

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface CustomTooltipContentProps {
  tooltipData: TooltipData | null;
  metricLabel: string;
  metricUnit: string;
  isPinned?: boolean;
}

function CustomTooltipContent({ tooltipData, metricUnit, isPinned }: CustomTooltipContentProps) {
  if (!tooltipData) return null;

  if (tooltipData.type === 'scatter') {
    const trial = tooltipData.data as ScatterPoint;
    const isPublication = !!trial.publicationName;
    const sourceLabel = isPublication ? 'Publication' : 'Abstract/Publication ID';
    const sourceValue = isPublication ? trial.publicationName : trial.abstractId;

    return (
      <div className="bg-slate-800 p-4 rounded-xl shadow-2xl border border-slate-700 min-w-[320px] max-w-[420px]">
        {isPinned && (
          <div className="mb-2 pb-2 border-b border-slate-600 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-amber-400 font-medium">📌 Pinned</span>
            <span className="text-[10px] text-slate-500">Click elsewhere to dismiss</span>
          </div>
        )}
        {sourceValue && (
          <div className="mb-3 pb-3 border-b border-slate-700">
            <span className="text-[10px] uppercase tracking-wider text-slate-500 block mb-1">{sourceLabel}</span>
            <span className={`text-sm font-bold leading-tight block ${isPublication ? 'text-emerald-300' : 'text-sky-300'}`}>
              {sourceValue}
            </span>
          </div>
        )}
        
        {trial.trialName && (
          <div className="mb-3">
            <span className="text-[10px] uppercase tracking-wider text-slate-500 block mb-0.5">Trial Name</span>
            <span className="text-sm font-semibold text-violet-300">{trial.trialName}</span>
          </div>
        )}
        
        <div className="flex items-start justify-between gap-3 mb-3 pb-3 border-b border-slate-700">
          <p className="text-sm text-slate-200 font-medium leading-tight">
            {trial.treatmentName}
          </p>
          <span className="text-xs text-slate-400 font-medium shrink-0">
            {trial.phase}
          </span>
        </div>
        
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
  const treatment = tooltipData.data as HeadToHeadDataPoint;
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
  metric?: ChartMetric;
  title?: string;
  description?: string;
  height?: number;
  showLegend?: boolean;
  showReferenceLine?: boolean;
  referenceValue?: number;
  compact?: boolean;
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
  compact = false,
}: HeadToHeadChartProps) {
  const [tooltipData, setTooltipData] = useState<TooltipData | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isHoveringRef = useRef(false);

  // Clear tooltip after a delay if not hovering and not pinned
  const scheduleHideTooltip = useCallback(() => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
    hideTimeoutRef.current = setTimeout(() => {
      if (!isHoveringRef.current && !isPinned) {
        setTooltipData(null);
      }
    }, 100);
  }, [isPinned]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
      }
    };
  }, []);

  // Track the pinned dot's ID to allow clicking the same dot to unpin
  const pinnedDotIdRef = useRef<string | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const metricConfig = ALL_METRICS[metric];
  const metricLabel = metricConfig?.label || metric;
  const metricUnit = metricConfig?.unit || '';

  // Calculate total trials
  const totalTrials = useMemo(() => 
    data.reduce((sum, d) => sum + d.trials.length, 0), 
    [data]
  );

  // Calculate overall average for reference line
  const overallAverage = useMemo(() => {
    if (referenceValue !== undefined) return referenceValue;
    const allValues = data.flatMap(d => d.trials.map(t => t.value));
    return allValues.length > 0 
      ? allValues.reduce((a, b) => a + b, 0) / allValues.length 
      : 0;
  }, [data, referenceValue]);

  // Calculate Y domain to include all individual values
  const yDomain = useMemo((): [number, number] => {
    const allValues = data.flatMap(d => [...d.trials.map(t => t.value), d.averageValue]);
    if (allValues.length === 0) return [0, 100];
    const maxValue = Math.max(...allValues);
    return [0, Math.ceil(maxValue * 1.15)];
  }, [data]);

  const margin = compact
    ? { top: 20, right: 30, bottom: 80, left: 55 }
    : { top: 20, right: 30, bottom: 100, left: 60 };

  // Handle dot hover
  const handleDotMouseEnter = useCallback((point: ScatterPoint, event: React.MouseEvent) => {
    if (isPinned) return; // Don't change tooltip on hover if pinned
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
    isHoveringRef.current = true;
    setTooltipData({
      type: 'scatter',
      data: point,
      x: event.clientX,
      y: event.clientY,
    });
  }, [isPinned]);

  const handleDotMouseLeave = useCallback(() => {
    if (isPinned) return; // Don't hide if pinned
    isHoveringRef.current = false;
    scheduleHideTooltip();
  }, [isPinned, scheduleHideTooltip]);

  // Handle dot click - pin/unpin the tooltip
  const handleDotClick = useCallback((point: ScatterPoint, event: React.MouseEvent) => {
    event.stopPropagation();
    event.preventDefault();
    
    const dotId = `${point.treatmentName}-${point.studyId}-${point.value}`;
    
    // If clicking the same pinned dot, unpin
    if (isPinned && pinnedDotIdRef.current === dotId) {
      setIsPinned(false);
      setTooltipData(null);
      pinnedDotIdRef.current = null;
      return;
    }
    
    // Pin to this dot
    pinnedDotIdRef.current = dotId;
    setIsPinned(true);
    setTooltipData({
      type: 'scatter',
      data: point,
      x: event.clientX,
      y: event.clientY,
    });
  }, [isPinned]);
  
  // Handle click outside chart to unpin
  const handleChartContainerClick = useCallback((_e: React.MouseEvent) => {
    // Only unpin if clicking outside a dot (dots have their own handler with stopPropagation)
    if (isPinned) {
      setIsPinned(false);
      setTooltipData(null);
      pinnedDotIdRef.current = null;
    }
  }, [isPinned]);

  // Handle bar hover  
  const handleBarMouseEnter = useCallback((entry: HeadToHeadDataPoint, event: React.MouseEvent) => {
    if (isPinned) return; // Don't change tooltip on hover if pinned
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
    isHoveringRef.current = true;
    setTooltipData({
      type: 'bar',
      data: entry,
      x: event.clientX,
      y: event.clientY,
    });
  }, [isPinned]);

  const handleBarMouseLeave = useCallback(() => {
    if (isPinned) return; // Don't hide if pinned
    isHoveringRef.current = false;
    scheduleHideTooltip();
  }, [isPinned, scheduleHideTooltip]);

  // Handle chart container mouse leave - immediate hide unless pinned
  const handleChartMouseLeave = useCallback(() => {
    if (isPinned) return; // Don't hide if pinned
    isHoveringRef.current = false;
    setTooltipData(null);
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
  }, [isPinned]);

  const colors = compact ? COLORS : DARK_COLORS;

  // Custom bar shape that renders both the bar and dots
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const CustomBarShape = useCallback((props: any) => {
    const { x = 0, y = 0, width = 0, height = 0, fill, fillOpacity, payload, background } = props as BarShapeProps;
    
    if (!payload || !background) return <Rectangle x={x} y={y} width={width} height={height} fill={fill} radius={[4, 4, 0, 0]} />;
    
    const trials = payload.trials || [];
    const trialCount = trials.length;
    const centerX = x + width / 2;
    
    // Calculate y scale based on background (full chart height) vs bar height
    const chartAreaHeight = background.height;
    const chartAreaTop = background.y;
    const [yMin, yMax] = yDomain;
    
    const valueToY = (value: number) => {
      const normalizedValue = (value - yMin) / (yMax - yMin);
      return chartAreaTop + chartAreaHeight * (1 - normalizedValue);
    };

    // Calculate dot positions
    const dots = trials.map((trial, index) => {
      let xOffset = 0;
      if (trialCount > 1) {
        const maxSpread = Math.min(width * 0.8, 40);
        const spacing = maxSpread / Math.max(trialCount - 1, 1);
        xOffset = (index - (trialCount - 1) / 2) * spacing;
      }
      
      return {
        ...trial,
        treatmentName: payload.treatmentName,
        dotX: centerX + xOffset,
        dotY: valueToY(trial.value),
        key: `dot-${index}`,
      };
    });

    return (
      <g>
        {/* The bar */}
        <Rectangle
          x={x}
          y={y}
          width={width}
          height={height}
          fill={fill}
          fillOpacity={fillOpacity}
          radius={[4, 4, 0, 0]}
        />
        {/* The dots */}
        {dots.map((dot) => (
          <circle
            key={dot.key}
            cx={dot.dotX}
            cy={dot.dotY}
            r={7}
            fill={colors.dot.fill}
            stroke={colors.dot.stroke}
            strokeWidth={2}
            style={{ cursor: 'pointer' }}
            onMouseEnter={(e) => handleDotMouseEnter(dot, e as unknown as React.MouseEvent)}
            onMouseLeave={handleDotMouseLeave}
            onClick={(e) => handleDotClick(dot, e as unknown as React.MouseEvent)}
          />
        ))}
      </g>
    );
  }, [yDomain, colors.dot, handleDotMouseEnter, handleDotMouseLeave, handleDotClick]);

  if (data.length === 0) {
    return (
      <Card className={`w-full bg-slate-900 border-slate-800 ${compact ? 'border-0 shadow-none' : ''}`}>
        <CardContent className={`flex items-center justify-center ${compact ? 'h-[200px]' : 'h-[400px]'}`}>
          <p className="text-slate-400">
            No data available for the selected filters
          </p>
        </CardContent>
      </Card>
    );
  }

  // Compact mode
  if (compact) {
    return (
      <div 
        ref={chartContainerRef}
        className="w-full h-full bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm flex flex-col outline-none focus:outline-none"
        onClick={handleChartContainerClick}
        tabIndex={-1}
      >
        {showLegend && (
          <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-200 flex-shrink-0">
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ background: colors.bar.approved }} />
                <span className="text-slate-600 font-medium">Approved</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ background: colors.bar.investigational }} />
                <span className="text-slate-600 font-medium">Investigational</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div 
                  className="w-3 h-3 rounded-full" 
                  style={{ background: colors.dot.fill, border: `2px solid ${colors.dot.stroke}` }} 
                />
                <span className="text-slate-600 font-medium">Individual trials</span>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{data.length}</span> treatments
              <span className="text-slate-300">•</span>
              <span className="font-medium text-slate-700">{totalTrials}</span> trials
            </div>
          </div>
        )}
        
        <div 
          className="flex-1 bg-white relative outline-none [&_*]:outline-none [&_svg]:outline-none [&_svg_*]:outline-none" 
          onMouseLeave={handleChartMouseLeave} 
          tabIndex={-1}
          style={{ WebkitTapHighlightColor: 'transparent' }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={margin}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={colors.grid}
              />
              <XAxis
                dataKey="treatmentName"
                tick={{ fontSize: 10, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                interval={0}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis
                tick={{ fontSize: 11, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                domain={yDomain}
                width={50}
                label={{
                  value: `${metricLabel} (${metricUnit})`,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 11, fontWeight: 500 },
                }}
              />
              {showReferenceLine && (
                <ReferenceLine
                  y={overallAverage}
                  stroke="#94a3b8"
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                  label={{
                    value: `Avg: ${overallAverage.toFixed(1)}`,
                    position: 'right',
                    fill: '#64748b',
                    fontSize: 10,
                    fontWeight: 500,
                  }}
                />
              )}
              <Bar 
                dataKey="averageValue" 
                shape={CustomBarShape}
                background={{ fill: 'transparent' }}
                onMouseEnter={(_, index, e) => {
                  if (data[index]) handleBarMouseEnter(data[index], e as unknown as React.MouseEvent);
                }}
                onMouseLeave={handleBarMouseLeave}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.approvalStatus === 'Approved'
                        ? colors.bar.approved
                        : entry.approvalStatus === 'Investigational'
                        ? colors.bar.investigational
                        : colors.bar.unknown
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          
          {/* Custom tooltip */}
          {tooltipData && (
            <div 
              className={`fixed z-[9999] ${isPinned ? 'pointer-events-auto' : 'pointer-events-none'}`}
              style={{ 
                left: Math.min(tooltipData.x + 15, window.innerWidth - 450),
                top: Math.max(tooltipData.y - 20, 10),
              }}
            >
              <CustomTooltipContent 
                tooltipData={tooltipData} 
                metricLabel={metricLabel} 
                metricUnit={metricUnit}
                isPinned={isPinned}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  // Full mode (dark theme)
  return (
    <Card 
      ref={chartContainerRef as React.RefObject<HTMLDivElement>}
      className="w-full overflow-hidden bg-slate-900 border-slate-800 outline-none focus:outline-none"
      onClick={handleChartContainerClick}
      tabIndex={-1}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-xl font-bold text-white">
              {title || 'Head-to-Head Efficacy Comparison'}
            </CardTitle>
            <CardDescription className="mt-1 text-slate-400">
              {description || `Comparing ${metricLabel} (${metricUnit}) across treatment arms. Bars show averages; dots show individual trial results.`}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {showLegend && (
          <div className="flex items-center justify-center gap-6 text-xs mb-4">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded" style={{ background: colors.bar.approved }} />
              <span className="text-slate-300">Approved</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded" style={{ background: colors.bar.investigational }} />
              <span className="text-slate-300">Investigational</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ background: colors.dot.fill, border: `2px solid ${colors.dot.stroke}` }} 
              />
              <span className="text-slate-300">Individual trials</span>
            </div>
          </div>
        )}

        <div 
          style={{ width: '100%', height: height, WebkitTapHighlightColor: 'transparent' }} 
          className="relative outline-none [&_*]:outline-none [&_svg]:outline-none [&_svg_*]:outline-none" 
          onMouseLeave={handleChartMouseLeave} 
          tabIndex={-1}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={margin}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={colors.grid}
                strokeOpacity={0.3}
              />
              <XAxis
                dataKey="treatmentName"
                tick={{ fontSize: 10, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                interval={0}
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis
                tick={{ fontSize: 11, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                domain={yDomain}
                label={{
                  value: `${metricLabel} (${metricUnit})`,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 12 },
                }}
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
              <Bar 
                dataKey="averageValue" 
                shape={CustomBarShape}
                background={{ fill: 'transparent' }}
                onMouseEnter={(_, index, e) => {
                  if (data[index]) handleBarMouseEnter(data[index], e as unknown as React.MouseEvent);
                }}
                onMouseLeave={handleBarMouseLeave}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.approvalStatus === 'Approved'
                        ? colors.bar.approved
                        : entry.approvalStatus === 'Investigational'
                        ? colors.bar.investigational
                        : colors.bar.unknown
                    }
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          
          {/* Custom tooltip */}
          {tooltipData && (
            <div 
              className={`fixed z-[9999] ${isPinned ? 'pointer-events-auto' : 'pointer-events-none'}`}
              style={{ 
                left: Math.min(tooltipData.x + 15, window.innerWidth - 450),
                top: Math.max(tooltipData.y - 20, 10),
              }}
            >
              <CustomTooltipContent 
                tooltipData={tooltipData} 
                metricLabel={metricLabel} 
                metricUnit={metricUnit}
                isPinned={isPinned}
              />
            </div>
          )}
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
                {totalTrials}
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
