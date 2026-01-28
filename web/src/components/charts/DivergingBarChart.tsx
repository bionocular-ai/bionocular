'use client';

import { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import {
  Bar,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  Legend,
  Rectangle,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { EfficacySafetyDataPoint } from '@/types/analytics';

// ============================================================================
// Types
// ============================================================================

interface DivergingBarChartProps {
  data: EfficacySafetyDataPoint[];
  title?: string;
  description?: string;
  height?: number;
  efficacyLabel?: string;
  safetyLabel?: string;
  compact?: boolean;
  efficacyParam?: string;
  safetyParam?: string;
}

// ============================================================================
// Color Palette
// ============================================================================

const COLORS = {
  efficacy: '#2563eb', // Vibrant blue for efficacy
  safety: '#dc2626', // Vibrant red for safety (adverse events)
  grid: '#cbd5e1', // More visible grid color
  axis: '#475569',
};

const DARK_COLORS = {
  efficacy: '#3b82f6', // Bright blue for dark mode
  safety: '#ef4444', // Bright red for dark mode
  grid: '#334155', // More visible grid color for dark mode
  axis: '#cbd5e1',
};

// ============================================================================
// Custom Tooltip
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    dataKey: string;
    color: string;
    payload: EfficacySafetyDataPoint;
  }>;
  label?: string;
  isPinned?: boolean;
  currentTrialIndex?: number;
  onTrialIndexChange?: (treatmentName: string, newIndex: number) => void;
  efficacyParam?: string;
  safetyParam?: string;
}

const CustomTooltip = ({ 
  active, 
  payload, 
  label, 
  isPinned,
  currentTrialIndex = 0,
  onTrialIndexChange,
  efficacyParam,
  safetyParam,
}: CustomTooltipProps) => {
  if ((!active && !isPinned) || !payload || !payload.length) return null;

  const data = payload[0].payload as EfficacySafetyDataPoint & { safety: number; safetyAbs: number };
  const allTrials = data.allTrials || [];
  const hasMultipleTrials = allTrials.length > 1;
  const currentTrial = allTrials[currentTrialIndex] || {
    efficacy: data.efficacy,
    safety: data.safety || 0,
    numberOfPatients: data.numberOfPatients,
    year: undefined,
    nctNumber: undefined,
    abstractId: undefined,
    publicationName: undefined,
    citation: undefined,
    phase: undefined,
  };
  
  // Get values directly from the current trial
  const efficacy = currentTrial.efficacy || 0;
  const safety = Math.abs(currentTrial.safety || 0);

  const handlePrevTrial = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (currentTrialIndex > 0 && onTrialIndexChange) {
      onTrialIndexChange(data.treatmentName, currentTrialIndex - 1);
    }
  };

  const handleNextTrial = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (currentTrialIndex < allTrials.length - 1 && onTrialIndexChange) {
      onTrialIndexChange(data.treatmentName, currentTrialIndex + 1);
    }
  };

  // Get metric labels
  const efficacyLabel = efficacyParam ? efficacyParam.replace(/_/g, ' ') : 'Efficacy (ORR)';
  const safetyLabel = safetyParam ? safetyParam.replace(/_/g, ' ') : 'Safety (Grade 3+ AE)';

  return (
    <div className="bg-slate-800 p-4 rounded-xl shadow-2xl border border-slate-700 min-w-[260px]">
      {isPinned && (
        <div className="mb-2 pb-2 border-b border-slate-600 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-amber-400 font-medium flex items-center gap-1">
            <span className="text-amber-400">📌</span> Pinned
          </span>
          <span className="text-[10px] text-slate-500">Click bar to unpin</span>
        </div>
      )}
      <h4 className="font-bold text-white text-sm mb-3">{label || data.treatmentName}</h4>
      {data.treatmentType && (
        <p className="text-xs text-slate-400 mb-3">{data.treatmentType}</p>
      )}
      <div className="space-y-2">
        {efficacy > 0 && (
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded" style={{ background: COLORS.efficacy }} />
              <span className="text-sm text-slate-300">{efficacyLabel}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevTrial}
                disabled={!hasMultipleTrials || currentTrialIndex === 0}
                className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
                style={{ pointerEvents: 'auto' }}
                title={hasMultipleTrials ? 'Previous trial' : 'Only one trial available'}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <span className="text-sm font-bold text-white tabular-nums min-w-[50px] text-center">
                {efficacy.toFixed(1)}%
              </span>
              <button
                onClick={handleNextTrial}
                disabled={!hasMultipleTrials || currentTrialIndex === allTrials.length - 1}
                className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
                style={{ pointerEvents: 'auto' }}
                title={hasMultipleTrials ? 'Next trial' : 'Only one trial available'}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
        {safety > 0 && (
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded" style={{ background: COLORS.safety }} />
              <span className="text-sm text-slate-300">{safetyLabel}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevTrial}
                disabled={!hasMultipleTrials || currentTrialIndex === 0}
                className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
                style={{ pointerEvents: 'auto' }}
                title={hasMultipleTrials ? 'Previous trial' : 'Only one trial available'}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <span className="text-sm font-bold text-white tabular-nums min-w-[50px] text-center">
                {safety.toFixed(1)}%
              </span>
              <button
                onClick={handleNextTrial}
                disabled={!hasMultipleTrials || currentTrialIndex === allTrials.length - 1}
                className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
                style={{ pointerEvents: 'auto' }}
                title={hasMultipleTrials ? 'Next trial' : 'Only one trial available'}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
      {hasMultipleTrials && (
        <div className="mt-2 text-center">
          <span className="text-[10px] text-slate-500">
            Trial {currentTrialIndex + 1} of {allTrials.length}
          </span>
        </div>
      )}
      <div className="mt-3 pt-3 border-t border-slate-700 space-y-1.5">
        {currentTrial.numberOfPatients && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Patients</span>
            <span className="text-slate-200 font-medium">n={currentTrial.numberOfPatients}</span>
          </div>
        )}
        {data.trialCount && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Trials</span>
            <span className="text-slate-200 font-medium">{data.trialCount}</span>
          </div>
        )}
        {data.approvalStatus && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Status</span>
            <span className={`font-medium ${
              data.approvalStatus === 'Approved' 
                ? 'text-emerald-300' 
                : data.approvalStatus === 'Investigational'
                ? 'text-violet-300'
                : 'text-slate-300'
            }`}>
              {data.approvalStatus}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export default function DivergingBarChart({
  data,
  title = 'Drug Efficacy vs Safety Profile Comparison',
  description = 'Positive efficacy scores contrast with adverse event rates',
  height = 400,
  efficacyLabel = 'ORR (%)',
  safetyLabel = 'Grade 3+ AE rate (%)',
  compact = false,
  efficacyParam,
  safetyParam,
}: DivergingBarChartProps) {
  const chartHeight = Math.max(height || 400, 100);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartAreaWidth, setChartAreaWidth] = useState(0);
  const [chartAreaLeft, setChartAreaLeft] = useState(0);
  const [isPinned, setIsPinned] = useState(false);
  const [pinnedBarId, setPinnedBarId] = useState<string | null>(null);
  // Track current trial index per treatment for tooltip switching
  const [trialIndices, setTrialIndices] = useState<Map<string, number>>(new Map());

  const handleTrialIndexChange = useCallback((treatmentName: string, newIndex: number) => {
    setTrialIndices(prev => {
      const next = new Map(prev);
      next.set(treatmentName, newIndex);
      return next;
    });
  }, []);
  const [tooltipData, setTooltipData] = useState<{
    active: boolean;
    payload?: Array<{
      name: string;
      value: number;
      dataKey: string;
      color: string;
      payload: EfficacySafetyDataPoint;
    }>;
    label?: string;
    x?: number;
    y?: number;
  } | null>(null);

  // Calculate tooltip position
  const calculateTooltipPosition = useCallback((clientX: number, clientY: number) => {
    const TOOLTIP_WIDTH = 300;
    const TOOLTIP_HEIGHT = 200;
    const OFFSET_X = 15;
    const OFFSET_Y = 10;
    const EDGE_PADDING = 16;
    
    let x = clientX + OFFSET_X;
    let y = clientY + OFFSET_Y;
    
    if (x + TOOLTIP_WIDTH > window.innerWidth - EDGE_PADDING) {
      x = clientX - TOOLTIP_WIDTH - OFFSET_X;
    }
    
    if (x < EDGE_PADDING) {
      x = EDGE_PADDING;
    }
    
    if (y + TOOLTIP_HEIGHT > window.innerHeight - EDGE_PADDING) {
      y = clientY - TOOLTIP_HEIGHT - OFFSET_Y;
    }
    
    if (y < EDGE_PADDING) {
      y = EDGE_PADDING;
    }
    
    return { x, y };
  }, []);

  // Update chart area dimensions when container size changes
  useEffect(() => {
    const updateDimensions = () => {
      if (chartContainerRef.current) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        // Account for margins
        const leftMargin = compact ? 130 : 160;
        const rightMargin = 35;
        setChartAreaWidth(rect.width - leftMargin - rightMargin);
        setChartAreaLeft(leftMargin);
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [compact]);

  // Transform data for diverging chart
  // Safety values need to be negative to extend left, efficacy positive to extend right
  // Both bars will start from 0 and extend in opposite directions
  const chartData = useMemo(() => {
    return data.map((item) => {
      // Get the current trial index for this treatment (default to 0)
      const currentIndex = trialIndices.get(item.treatmentName) ?? 0;
      const allTrials = item.allTrials || [];
      
      // Use values from the current trial if available, otherwise use the original item values
      const currentTrial = allTrials[currentIndex];
      const efficacy = currentTrial?.efficacy ?? item.efficacy ?? 0;
      const safety = currentTrial?.safety ?? item.safety ?? 0;
      
      return {
        ...item,
        name: item.treatmentName,
        efficacy, // Positive, extends right from 0
        safety: -safety, // Negative, extends left from 0
        safetyAbs: Math.abs(safety), // Absolute value for display
      };
    });
  }, [data, trialIndices]);

  // Calculate domain for X axis - ensure 0 is always in the center with evenly spaced ticks
  // The range will be divisible by the number of intervals to get whole number ticks
  // Note: safety is already negative in chartData, efficacy is positive
  const xDomain = useMemo(() => {
    const allValues = chartData.flatMap((d) => [d.efficacy, d.safety]);
    if (allValues.length === 0) return [-60, 60];
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const absMax = Math.max(Math.abs(min), Math.abs(max));
    const padding = absMax * 0.1;
    
    // We want 7 ticks (6 intervals), so the range should be divisible by 6
    // Round up to the nearest number that's divisible by 6 and gives nice intervals
    const tickCount = 7;
    const intervalCount = tickCount - 1; // 6 intervals
    
    // Start with a base rounded value
    const baseMax = Math.ceil((absMax + padding) / 10) * 10;
    
    // Find the smallest multiple of intervalCount that's >= baseMax
    // This ensures the range is divisible by intervalCount for whole number intervals
    const roundedMax = Math.ceil(baseMax / intervalCount) * intervalCount;
    
    // Cap at 100 since efficacy and safety are percentages and can't exceed 100%
    const cappedMax = Math.min(roundedMax, 100);
    
    // Ensure symmetric domain around 0, capped at 100
    return [-cappedMax, cappedMax];
  }, [chartData]);
  
  // Calculate evenly spaced ticks with nice whole number intervals (10, 20, 30, etc.)
  const xAxisTicks = useMemo(() => {
    const [min, max] = xDomain;
    const absMax = Math.abs(max);
    
    // Determine a nice interval based on the max value
    // For values up to 60, use interval of 20 (0, 20, 40, 60)
    // For values up to 100, use interval of 20 (0, 20, 40, 60, 80, 100)
    // For smaller ranges, use interval of 10 (0, 10, 20, 30, ...)
    let tickInterval = 20;
    if (absMax <= 30) {
      tickInterval = 10;
    } else if (absMax <= 60) {
      tickInterval = 20;
    } else {
      tickInterval = 20; // For up to 100
    }
    
    // Generate ticks from -max to +max with the interval
    const ticks: number[] = [];
    for (let i = -absMax; i <= absMax; i += tickInterval) {
      ticks.push(i);
    }
    
    // Ensure 0 is always included
    if (!ticks.includes(0)) {
      ticks.push(0);
      ticks.sort((a, b) => a - b);
    }
    
    return ticks;
  }, [xDomain]);

  // Use light mode colors for both compact and fullscreen modes
  const colors = COLORS;
  const margin = compact
    ? { top: 25, right: 35, bottom: 65, left: 130 }
    : { top: 25, right: 35, bottom: 85, left: 160 };

  if (data.length === 0) {
    return (
      <Card className={`w-full bg-slate-900 border-slate-800 ${compact ? 'border-0 shadow-none' : ''}`}>
        <CardContent className={`flex items-center justify-center ${compact ? 'h-[200px]' : 'h-[400px]'}`}>
          <p className="text-slate-400">No data available</p>
        </CardContent>
      </Card>
    );
  }

  // Custom X-axis tick formatter to show absolute values
  const formatXAxisTick = (value: number) => {
    return `${Math.abs(value)}`;
  };

  // Custom X-axis label
  const xAxisLabel = `${safetyLabel} | ${efficacyLabel}`;

  // Handle bar hover - we'll use Recharts tooltip for hover, only handle clicks for pinning

  // Handle bar click - pin/unpin the tooltip
  const handleBarClick = useCallback((data: EfficacySafetyDataPoint, event?: React.MouseEvent) => {
    if (event) {
      event.stopPropagation();
      event.preventDefault();
    }
    
    const barId = data.treatmentName;
    
    // If clicking the same pinned bar, unpin
    if (isPinned && pinnedBarId === barId) {
      setIsPinned(false);
      setTooltipData(null);
      setPinnedBarId(null);
      return;
    }
    
    // Pin to this bar - calculate position from click event or use existing position
    const position = event 
      ? calculateTooltipPosition(event.clientX, event.clientY)
      : tooltipData 
        ? { x: tooltipData.x || 0, y: tooltipData.y || 0 }
        : { x: 0, y: 0 };
    
    setPinnedBarId(barId);
    setIsPinned(true);
    setTooltipData({
      active: true,
      payload: [{
        name: 'efficacy',
        value: data.efficacy,
        dataKey: 'efficacy',
        color: colors.efficacy,
        payload: data,
      }],
      label: data.treatmentName,
      x: position.x,
      y: position.y,
    });
  }, [isPinned, pinnedBarId, colors, calculateTooltipPosition, tooltipData]);

  // Custom shape for diverging bars - both bars start from center (0) and extend in opposite directions
  // For horizontal bar charts (layout="vertical"), Recharts provides:
  // - x: X position (horizontal, where the bar starts for positive values)
  // - y: Y position (vertical, category position)
  // - width: bar width (horizontal, for the data value)
  // - height: bar height (vertical)
  // - background: chart area dimensions (if available)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const DivergingBarShape = useCallback((props: any) => {
    const { payload, x, y, width, height, background } = props;
    if (!payload) return <g />;

    const safety = payload.safety || 0; // Negative value
    const efficacy = payload.efficacy || 0; // Positive value
    const barId = payload.treatmentName;
    const isPinnedBar = isPinned && pinnedBarId === barId;
    
    // Try to get chart area dimensions from background prop first
    let areaWidth = background?.width;
    let areaLeft = background?.x;
    
    // If background not available, use state values
    if (!areaWidth || areaWidth === 0) {
      areaWidth = chartAreaWidth;
      areaLeft = chartAreaLeft;
    }
    
    // If still no dimensions, we can't render properly
    if (!areaWidth || areaWidth === 0 || areaLeft === undefined) {
      return <g />;
    }
    
    // Calculate where x=0 is in the chart area
    const [minDomain, maxDomain] = xDomain;
    const domainRange = maxDomain - minDomain;
    const zeroPosition = areaLeft + ((0 - minDomain) / domainRange) * areaWidth;
    
    // Calculate bar widths based on domain
    const safetyWidth = Math.abs(safety) * (areaWidth / domainRange);
    const efficacyWidth = efficacy * (areaWidth / domainRange);
    
    // Position bars from center (zeroPosition)
    // Safety extends left (negative), efficacy extends right (positive)
    const safetyX = zeroPosition - safetyWidth;
    const efficacyX = zeroPosition;

    const data = payload as EfficacySafetyDataPoint;
    
    return (
      <g>
        {/* Safety bar - extends left from 0 */}
        {safety < 0 && safetyWidth > 0 && (
          <Rectangle
            x={safetyX}
            y={y} // y is the vertical (category) position
            width={safetyWidth}
            height={height}
            fill={isPinnedBar ? '#fbbf24' : colors.safety}
            radius={0}
            style={{ cursor: 'pointer', pointerEvents: 'all' }}
            onMouseDown={(e: any) => {
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseUp={(e: any) => {
              e.stopPropagation();
              e.preventDefault();
              const nativeEvent = e as unknown as React.MouseEvent;
              handleBarClick(data, nativeEvent);
            }}
          />
        )}
        {/* Efficacy bar - extends right from 0 */}
        {efficacy > 0 && efficacyWidth > 0 && (
          <Rectangle
            x={efficacyX}
            y={y} // y is the vertical (category) position
            width={efficacyWidth}
            height={height}
            fill={isPinnedBar ? '#fbbf24' : colors.efficacy}
            radius={0}
            style={{ cursor: 'pointer', pointerEvents: 'all' }}
            onMouseDown={(e: any) => {
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseUp={(e: any) => {
              e.stopPropagation();
              e.preventDefault();
              const nativeEvent = e as unknown as React.MouseEvent;
              handleBarClick(data, nativeEvent);
            }}
          />
        )}
      </g>
    );
  }, [xDomain, colors, chartAreaWidth, chartAreaLeft, isPinned, pinnedBarId, handleBarClick]);

  if (compact) {
    return (
      <div ref={chartContainerRef} className="w-full h-full bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            layout="vertical"
            margin={margin}
            barCategoryGap="25%"
          >
            <CartesianGrid 
              strokeDasharray="0" 
              stroke={colors.grid} 
              strokeWidth={1}
              strokeOpacity={0.5}
              vertical={true}
              horizontal={true}
            />
            <XAxis
              type="number"
              domain={xDomain}
              ticks={xAxisTicks}
              tick={{ fontSize: 11, fill: colors.axis, fontWeight: 500 }}
              tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
              axisLine={false}
              tickFormatter={formatXAxisTick}
              label={{
                value: xAxisLabel,
                position: 'insideBottom',
                offset: -5,
                style: { textAnchor: 'middle', fill: colors.axis, fontSize: 11, fontWeight: 600 },
              }}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11, fill: colors.axis, fontWeight: 500 }}
              tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
              axisLine={false}
              width={130}
            />
            <ReferenceLine x={0} stroke={colors.axis} strokeWidth={2.5} strokeOpacity={0.8} />
            <Tooltip 
              content={(props) => {
                if (isPinned) return null; // Don't show Recharts tooltip when pinned
                if (props.active && props.payload && props.payload.length > 0) {
                  const payloadData = props.payload?.[0]?.payload as EfficacySafetyDataPoint | undefined;
                  const treatmentName = payloadData?.treatmentName || '';
                  const currentIndex = trialIndices.get(treatmentName) || 0;
                  return <CustomTooltip 
                    active={props.active}
                    payload={props.payload as CustomTooltipProps['payload']}
                    label={props.label?.toString()}
                    isPinned={false}
                    currentTrialIndex={currentIndex}
                    onTrialIndexChange={handleTrialIndexChange}
                    efficacyParam={efficacyParam}
                    safetyParam={safetyParam}
                  />;
                }
                return null;
              }}
            />
            <Legend
              verticalAlign="top"
              wrapperStyle={{ paddingBottom: '12px' }}
              iconType="square"
              iconSize={12}
              content={({ payload }) => (
                <div className="flex items-center justify-center gap-6">
                  {payload && payload.length > 0 && (
                    <>
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3" 
                          style={{ backgroundColor: colors.safety }}
                        />
                        <span className="text-xs" style={{ color: colors.axis }}>
                          Safety (Grade 3+ AE)
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3" 
                          style={{ backgroundColor: colors.efficacy }}
                        />
                        <span className="text-xs" style={{ color: colors.axis }}>
                          Efficacy (ORR)
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}
            />
            <Bar 
              dataKey="efficacy" 
              shape={DivergingBarShape}
            />
          </ComposedChart>
        </ResponsiveContainer>
        
        {/* Custom pinned tooltip */}
        {isPinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
          <div 
            className="fixed z-[9999]"
            style={{ 
              left: tooltipData.x,
              top: tooltipData.y,
              pointerEvents: 'auto',
            }}
          >
            <CustomTooltip 
              active={tooltipData.active}
              payload={tooltipData.payload}
              label={tooltipData.label}
              isPinned={isPinned}
              currentTrialIndex={(() => {
                const payloadData = tooltipData.payload?.[0]?.payload as EfficacySafetyDataPoint | undefined;
                const treatmentName = payloadData?.treatmentName || '';
                return trialIndices.get(treatmentName) || 0;
              })()}
              onTrialIndexChange={handleTrialIndexChange}
              efficacyParam={efficacyParam}
              safetyParam={safetyParam}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <Card className="w-full overflow-hidden bg-white border-slate-200">
      <CardHeader className="pb-2">
        <CardTitle className="text-xl font-bold text-slate-900">{title}</CardTitle>
        <CardDescription className="mt-1 text-slate-600">{description}</CardDescription>
      </CardHeader>

      <CardContent className="pt-4">
        <div ref={chartContainerRef} style={{ width: '100%', height: chartHeight, minHeight: 100 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              layout="vertical"
              margin={margin}
              barCategoryGap="25%"
            >
              <CartesianGrid 
                strokeDasharray="0" 
                stroke={colors.grid} 
                strokeWidth={1}
                strokeOpacity={0.5}
                vertical={true}
                horizontal={true}
              />
              <XAxis
                type="number"
                domain={xDomain}
                ticks={xAxisTicks}
                tick={{ fontSize: 12, fill: colors.axis, fontWeight: 500 }}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                tickFormatter={formatXAxisTick}
                label={{
                  value: xAxisLabel,
                  position: 'insideBottom',
                  offset: -5,
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 12, fontWeight: 600 },
                }}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 12, fill: colors.axis, fontWeight: 500 }}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                width={160}
              />
              <ReferenceLine x={0} stroke={colors.axis} strokeWidth={2.5} strokeOpacity={0.8} />
              <Tooltip 
                content={(props) => {
                  if (isPinned) return null; // Don't show Recharts tooltip when pinned
                  if (props.active && props.payload && props.payload.length > 0) {
                    return <CustomTooltip 
                      active={props.active}
                      payload={props.payload as CustomTooltipProps['payload']}
                      label={props.label?.toString()}
                      isPinned={false} 
                    />;
                  }
                  return null;
                }}
              />
              <Legend
                verticalAlign="top"
                wrapperStyle={{ paddingBottom: '12px' }}
                iconType="square"
                iconSize={12}
                content={({ payload }) => (
                  <div className="flex items-center justify-center gap-6">
                    {payload && payload.length > 0 && (
                      <>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3" 
                            style={{ backgroundColor: colors.efficacy }}
                          />
                          <span className="text-xs" style={{ color: colors.axis }}>
                            Efficacy (ORR)
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3" 
                            style={{ backgroundColor: colors.safety }}
                          />
                          <span className="text-xs" style={{ color: colors.axis }}>
                            Safety (Grade 3+ AE)
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                )}
              />
              <Bar 
                dataKey="efficacy" 
                shape={DivergingBarShape}
                background={{ fill: 'transparent' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
          
          {/* Custom pinned tooltip */}
          {isPinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
            <div 
              className="fixed z-[9999]"
              style={{ 
                left: tooltipData.x,
                top: tooltipData.y,
                pointerEvents: 'auto',
              }}
            >
              <CustomTooltip 
                active={tooltipData.active}
                payload={tooltipData.payload}
                label={tooltipData.label}
                isPinned={isPinned}
              />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
