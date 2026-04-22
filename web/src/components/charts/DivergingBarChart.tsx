'use client';

import { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
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
import { EfficacySafetyDataPoint, EFFICACY_METRICS, SAFETY_METRICS } from '@/types/analytics';

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
  /** When true (e.g. fullscreen), chart fills container vertically like compact mode */
  fillHeight?: boolean;
  efficacyParam?: string;
  safetyParam?: string;
  /** When set, both axes use the same metric type for labels (efficacy-efficacy or safety-safety) */
  axisMode?: 'efficacy-safety' | 'efficacy-efficacy' | 'safety-safety';
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

// ============================================================================
// Helper Functions
// ============================================================================

// Get compact label from metrics config
const getCompactLabel = (param: string | undefined, metrics: typeof EFFICACY_METRICS | typeof SAFETY_METRICS, defaultLabel: string): string => {
  if (!param) return defaultLabel;
  const metric = metrics[param];
  return metric?.label || defaultLabel;
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
  axisMode?: 'efficacy-safety' | 'efficacy-efficacy' | 'safety-safety';
}

/** Payload shape for tooltip; may include optional fields from chart data */
type TooltipPayloadData = EfficacySafetyDataPoint & {
  safety?: number;
  safetyAbs?: number;
  sourceUrl?: string;
  biomarker?: string;
  notes?: string;
  developmentStatus?: string;
};

const CustomTooltip = ({ 
  active, 
  payload, 
  label, 
  isPinned,
  currentTrialIndex = 0,
  onTrialIndexChange,
  efficacyParam,
  safetyParam,
  axisMode,
}: CustomTooltipProps) => {
  const data = payload?.[0]?.payload as TooltipPayloadData | undefined;
  const allTrials = useMemo(() => data?.allTrials ?? [], [data?.allTrials]);

  const nctTrials = useMemo(() => {
    const grouped: Array<{ nctNumber: string; trialIndices: number[]; displayLabel: string }> = [];
    const idMap = new Map<string, number[]>();

    allTrials.forEach((trial, index) => {
      const id = trial.nctNumber || trial.abstractId || trial.publicationName || `Trial ${index + 1}`;
      if (!idMap.has(id)) {
        idMap.set(id, []);
      }
      idMap.get(id)!.push(index);
    });

    idMap.forEach((trialIndices, sourceId) => {
      trialIndices.forEach((trialIndex, idx) => {
        const displayLabel = trialIndices.length === 1
          ? sourceId
          : `${sourceId} data ${idx + 1}`;
        grouped.push({
          nctNumber: sourceId,
          trialIndices: [trialIndex],
          displayLabel,
        });
      });
    });

    return grouped;
  }, [allTrials]);

  if ((!active && !isPinned) || !payload || !payload.length) return null;

  const dataNonNull = data as TooltipPayloadData;
  const hasMultipleTrials = allTrials.length > 1;
  const currentTrial = allTrials[currentTrialIndex] || {
    efficacy: dataNonNull.efficacy,
    safety: dataNonNull.safety || 0,
    numberOfPatients: dataNonNull.numberOfPatients,
    year: undefined,
    nctNumber: undefined,
    abstractId: undefined,
    publicationName: undefined,
    citation: undefined,
    phase: undefined,
  };

  const efficacyMetrics = axisMode === 'safety-safety' ? SAFETY_METRICS : EFFICACY_METRICS;
  const safetyMetrics = axisMode === 'efficacy-efficacy' ? EFFICACY_METRICS : SAFETY_METRICS;
  const efficacyLabel = getCompactLabel(efficacyParam, efficacyMetrics, 'ORR');
  const safetyLabel = getCompactLabel(safetyParam, safetyMetrics, 'Grade 3+ TRAE');

  const handleNCTClick = (trialIndex: number) => {
    if (onTrialIndexChange) {
      onTrialIndexChange(dataNonNull.treatmentName, trialIndex);
    }
  };

  return (
    <div 
      className="bg-slate-800 p-3 rounded-lg shadow-xl border border-slate-700 min-w-[260px] max-w-[340px] tooltip-enter"
      style={{
        animation: isPinned ? 'tooltipFadeIn 0.2s ease-out' : 'tooltipFadeIn 0.15s ease-out',
        pointerEvents: 'auto',
      }}
    >
      {isPinned && (
        <div 
          className="mb-1.5 pb-1.5 border-b border-slate-600 flex items-center justify-between"
          style={{ animation: 'tooltipContentFadeIn 0.2s ease-out' }}
        >
          <span className="text-[9px] uppercase tracking-wider text-amber-400 font-medium flex items-center gap-1">
            <span className="text-amber-400" style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>📌</span> Pinned
          </span>
          <span className="text-[9px] text-slate-500">Click bar to unpin</span>
        </div>
      )}
      <div className="mb-2 pb-2 border-b border-slate-700">
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-bold text-white text-xs">{label || dataNonNull.treatmentName}</h4>
        </div>
        {dataNonNull.treatmentType && (
          <p className="text-[11px] text-slate-400 mt-0.5">{dataNonNull.treatmentType}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-2">
        <div>
          <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0">{efficacyLabel}</p>
          <p className="text-base font-bold text-white tabular-nums">{currentTrial.efficacy.toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0">{safetyLabel}</p>
          <p className="text-base font-bold text-white tabular-nums">{Math.abs(currentTrial.safety || 0).toFixed(1)}%</p>
        </div>
      </div>
      
      {hasMultipleTrials && (
        <div className="mb-2 pb-2 border-b border-slate-700">
          <label className="block text-[9px] uppercase tracking-wider text-slate-500 mb-1 font-medium">
            Trial
          </label>
          <select
            value={currentTrialIndex}
            onChange={(e) => {
              e.stopPropagation();
              const idx = Number(e.target.value);
              if (!Number.isNaN(idx)) handleNCTClick(idx);
            }}
            title={nctTrials.find((t) => t.trialIndices[0] === currentTrialIndex)?.displayLabel}
            className="w-full px-2 py-1.5 rounded text-xs font-mono bg-slate-700/80 text-slate-100 border border-slate-600 hover:border-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500/60 focus:border-sky-500/70 cursor-pointer transition-colors"
            style={{ pointerEvents: 'auto' }}
          >
            {nctTrials.map((nctTrial, idx) => (
              <option key={idx} value={nctTrial.trialIndices[0]}>
                {nctTrial.displayLabel}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="pt-2 border-t border-slate-700 space-y-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-slate-400">Patients</span>
          <span className="text-slate-200 font-medium">n={currentTrial.numberOfPatients || 0}</span>
        </div>
        {currentTrial.nctNumber && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">NCT</span>
            <Link
              href={`/trial/nct/${currentTrial.nctNumber}`}
              className="text-sky-400 font-mono hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              <span>{currentTrial.nctNumber}</span>
              <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        )}
        {(currentTrial.sourceType === 'webscrape' ? !!currentTrial.sourceUrl : !!(currentTrial.abstractId || currentTrial.publicationName)) && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">
              {currentTrial.sourceType === 'publication'
                ? 'Publication'
                : currentTrial.sourceType === 'webscrape'
                ? 'Web Source'
                : 'Abstract'}
            </span>
            {currentTrial.sourceType === 'webscrape' ? (
              <a
                href={currentTrial.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <span className="text-xs">{currentTrial.sourceUrl}</span>
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            ) : currentTrial.sourceType === 'publication' ? (
              <span className="text-slate-200 text-[11px]">{currentTrial.publicationName}</span>
            ) : (
              <Link
                href={`/trial/abstract/${currentTrial.abstractId}`}
                className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <span className="text-[11px]">{currentTrial.abstractId}</span>
                <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            )}
          </div>
        )}
        {dataNonNull.biomarker && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">Biomarker</span>
            <span className="text-slate-200 font-medium">{dataNonNull.biomarker}</span>
          </div>
        )}
        {dataNonNull.notes && (
          <div className="pt-1.5 border-t border-slate-700">
            <p className="text-[9px] text-slate-500 italic">{dataNonNull.notes}</p>
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
  fillHeight = false,
  efficacyParam,
  safetyParam,
  axisMode,
}: DivergingBarChartProps) {
  const chartHeight = Math.max(height || 400, 100);
  const LABEL_PLOT_GAP = 12; // gap between Y-axis labels and plot
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartAreaWidth, setChartAreaWidth] = useState(0);
  const [isPinned, setIsPinned] = useState(false);
  const [pinnedBarId, setPinnedBarId] = useState<string | null>(null);
  const [containerDims, setContainerDims] = useState<{width: number; height: number}>({ width: 400, height: 300 });
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

  // Update chart area dimensions when container size changes (must match ComposedChart: margin.left + yAxisWidth)
  const effectiveLeftMargin = LABEL_PLOT_GAP + 4 + 248 + LABEL_PLOT_GAP; // 248 = labelWidth (same for compact/fullscreen)
  useEffect(() => {
    const updateDimensions = () => {
      if (chartContainerRef.current) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        const leftMargin = effectiveLeftMargin;
        const rightMargin = compact ? 12 : 35;
        setChartAreaWidth(rect.width - leftMargin - rightMargin);
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [compact, effectiveLeftMargin]);

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

  // Calculate domain for X axis - dynamic to bar size, 0 centered, with nice tick intervals
  // Note: safety is already negative in chartData, efficacy is positive
  const xDomain = useMemo(() => {
    const allValues = chartData.flatMap((d) => [d.efficacy, d.safety]);
    if (allValues.length === 0) return [-60, 60];
    const absMax = Math.max(...allValues.map((v) => Math.abs(v)));
    // Small padding so bars don’t sit on the axis end (5%)
    const target = Math.max(absMax * 1.05, 2);
    // Nice step: 10 for small range, 20 for larger (matches reference -60 to 60)
    const step = target <= 30 ? 10 : 20;
    // Smallest nice value >= target so plot size fits the bars
    const roundedMax = Math.ceil(target / step) * step;
    const cappedMax = Math.min(Math.max(roundedMax, 20), 100);
    return [-cappedMax, cappedMax];
  }, [chartData]);
  
  // Calculate evenly spaced ticks with nice whole number intervals (10, 20, 30, etc.)
  const xAxisTicks = useMemo(() => {
    const [, max] = xDomain;
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

  // Average values for reference lines (left = safety avg, right = efficacy avg)
  const median = (arr: number[]) => {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
  };

  const { medianSafety, medianEfficacy } = useMemo(() => {
    if (chartData.length === 0) return { medianSafety: 0, medianEfficacy: 0 };
    return {
      medianSafety: median(chartData.map((d) => d.safety)),
      medianEfficacy: median(chartData.map((d) => d.efficacy)),
    };
  }, [chartData]);

  // Use light mode colors for both compact and fullscreen modes
  const colors = COLORS;
  // Same axis layout as compact: fixed label width + gap so full screen matches compact spacing.
  const labelWidth = 248; // same for compact and full screen so labels don't touch the plot
  const yAxisWidth = 4 + labelWidth + LABEL_PLOT_GAP; // axis band: labels in [4, 4+labelWidth], then gap
  const margin = compact
    ? { top: 16, right: 12, bottom: 50, left: LABEL_PLOT_GAP }
    : fillHeight
    ? { top: 20, right: 12, bottom: 40, left: LABEL_PLOT_GAP } // top room for median line labels
    : { top: 40, right: 35, bottom: 85, left: LABEL_PLOT_GAP };

  // Custom X-axis tick formatter to show absolute values
  const formatXAxisTick = (value: number) => {
    return `${Math.abs(value)}`;
  };

  const efficacyMetricsForAxis = axisMode === 'safety-safety' ? SAFETY_METRICS : EFFICACY_METRICS;
  const safetyMetricsForAxis = axisMode === 'efficacy-efficacy' ? EFFICACY_METRICS : SAFETY_METRICS;
  const dynamicEfficacyLabel = getCompactLabel(efficacyParam, efficacyMetricsForAxis, efficacyLabel || 'ORR');
  const dynamicSafetyLabel = getCompactLabel(safetyParam, safetyMetricsForAxis, safetyLabel || 'Grade 3+ AE');

  const getUnit = (param: string | undefined, metrics: typeof EFFICACY_METRICS | typeof SAFETY_METRICS): string => {
    if (!param) return '';
    const metric = metrics[param];
    return metric?.unit || '';
  };

  const efficacyUnit = getUnit(efficacyParam, efficacyMetricsForAxis);
  const safetyUnit = getUnit(safetyParam, safetyMetricsForAxis);

  const formatAxisLabel = (label: string, unit: string): string => {
    if (!unit) return label;
    return `${label} (${unit})`;
  };

  // Legend text: efficacy-efficacy => "Efficacy (metric)" for both; safety-safety => "Safety (metric)" for both
  const leftLegendText = axisMode === 'efficacy-efficacy' ? `Efficacy (${dynamicSafetyLabel})` : axisMode === 'safety-safety' ? `Safety (${dynamicEfficacyLabel})` : `Safety (${dynamicSafetyLabel})`;
  const rightLegendText = axisMode === 'efficacy-efficacy' ? `Efficacy (${dynamicEfficacyLabel})` : axisMode === 'safety-safety' ? `Safety (${dynamicSafetyLabel})` : `Efficacy (${dynamicEfficacyLabel})`;

  // Below-axis label: parameters only (e.g. "DCR (%) | ORR (%)"), no "Efficacy (...)" or "Safety (...)" wrapper
  const leftAxisPart = axisMode === 'efficacy-efficacy' ? formatAxisLabel(dynamicSafetyLabel, safetyUnit) : axisMode === 'safety-safety' ? formatAxisLabel(dynamicEfficacyLabel, efficacyUnit) : formatAxisLabel(dynamicSafetyLabel, safetyUnit);
  const rightAxisPart = axisMode === 'efficacy-efficacy' ? formatAxisLabel(dynamicEfficacyLabel, efficacyUnit) : axisMode === 'safety-safety' ? formatAxisLabel(dynamicSafetyLabel, safetyUnit) : formatAxisLabel(dynamicEfficacyLabel, efficacyUnit);
  const xAxisLabel = `${leftAxisPart} | ${rightAxisPart}`;

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

  /** Recharts Bar shape props for custom diverging bar */
  interface DivergingBarShapeProps {
    payload?: EfficacySafetyDataPoint;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    background?: { x?: number; width?: number };
  }

  const DivergingBarShape = useCallback((props: unknown) => {
    const { payload, y = 0, height = 0, background } = props as DivergingBarShapeProps;
    if (!payload) return <g />;

    const safety = payload.safety || 0; // Negative value
    const efficacy = payload.efficacy || 0; // Positive value
    const barId = payload.treatmentName;
    const isPinnedBar = isPinned && pinnedBarId === barId;
    
    // Recharts draws the shape in content coordinates (0 = left edge of plot). Use content width; left is always 0.
    const areaLeft = background?.x ?? 0;
    const areaWidth = background?.width ?? chartAreaWidth;
    
    if (!areaWidth || areaWidth === 0) {
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
            onMouseDown={(e: React.MouseEvent) => {
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseUp={(e: React.MouseEvent) => {
              e.stopPropagation();
              e.preventDefault();
              handleBarClick(data, e);
            }}
          />
        )}
        {/* Efficacy bar - extends right from 0 */}
        {efficacy > 0 && efficacyWidth > 0 && (
          <Rectangle
            x={efficacyX}
            y={y}
            width={efficacyWidth}
            height={height}
            fill={isPinnedBar ? '#fbbf24' : colors.efficacy}
            radius={0}
            style={{ cursor: 'pointer', pointerEvents: 'all' }}
            onMouseDown={(e: React.MouseEvent) => {
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseUp={(e: React.MouseEvent) => {
              e.stopPropagation();
              e.preventDefault();
              handleBarClick(data, e);
            }}
          />
        )}
      </g>
    );
  }, [xDomain, colors, chartAreaWidth, isPinned, pinnedBarId, handleBarClick]);

  // Custom Y-axis tick: position labels in axis band 0..yAxisWidth so no gap before plot (compact + fullscreen)
  const renderYAxisTick = useCallback(
    (props: { x: number; y: number; payload?: { value?: string }; width?: number }) => {
      const { y, payload } = props;
      const width = props.width ?? labelWidth;
      const text = payload?.value ?? '';
      return (
        <g transform={`translate(0,${y})`}>
          <foreignObject x={4} y={-14} width={width} height={44} style={{ overflow: 'hidden' }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 500,
                wordBreak: 'break-word',
                overflowWrap: 'break-word',
                lineHeight: 1.3,
                color: colors.axis,
                width: '100%',
                textAlign: 'right',
                paddingRight: 4,
              }}
            >
              {text}
            </div>
          </foreignObject>
        </g>
      );
    },
    [colors.axis, labelWidth]
  );

  // Early return: no data (after all hooks so hooks are never conditional)
  if (data.length === 0) {
    return (
      <Card className={`w-full bg-slate-900 border-slate-800 ${compact ? 'border-0 shadow-none' : ''}`}>
        <CardContent className={`flex items-center justify-center ${compact ? 'h-[200px]' : 'h-[400px]'}`}>
          <p className="text-slate-400">No data available</p>
        </CardContent>
      </Card>
    );
  }

  if (compact) {
    return (
      <div
        className="absolute inset-0 flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm"
        style={{ width: '100%', height: '100%', minHeight: 0, minWidth: 0 }}
      >
        {/* Legend outside chart (like BarChart) so plot can fill the rest of the container */}
        <div className="flex-shrink-0 flex items-center justify-center gap-6 px-2 py-1.5 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3" style={{ backgroundColor: colors.safety }} />
            <span className="text-xs" style={{ color: colors.axis }}>{leftLegendText}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3" style={{ backgroundColor: colors.efficacy }} />
            <span className="text-xs" style={{ color: colors.axis }}>{rightLegendText}</span>
          </div>
        </div>
        <div
          ref={chartContainerRef}
          className="flex-1 min-h-0 min-w-0"
          style={{ width: '100%', height: '100%' }}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ComposedChart
              data={chartData}
              layout="vertical"
              margin={margin}
              barCategoryGap="30%"
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
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <YAxis
                type="category"
                dataKey="name"
                interval={0}
                tick={renderYAxisTick}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                width={yAxisWidth}
              />
              <ReferenceLine x={0} stroke={colors.axis} strokeWidth={2.5} strokeOpacity={0.8} />
              <ReferenceLine
                x={medianSafety}
                stroke={colors.safety}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianSafety.toFixed(1)}`, position: 'top', fill: colors.safety, fontSize: 10, fontWeight: 600 }}
              />
              <ReferenceLine
                x={medianEfficacy}
                stroke={colors.efficacy}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianEfficacy.toFixed(1)}`, position: 'top', fill: colors.efficacy, fontSize: 10, fontWeight: 600 }}
              />
              <Tooltip 
                wrapperStyle={{ pointerEvents: 'auto' }}
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
                      axisMode={axisMode}
                    />;
                  }
                  return null;
                }}
              />
              <Bar 
                dataKey="efficacy" 
                shape={DivergingBarShape}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        
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

  // Full-screen fill layout: no header, chart fills container (like compact mode)
  if (fillHeight) {
    return (
      <div className="w-full h-full flex flex-col min-h-0 min-w-0 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        <div className="flex-shrink-0 flex items-center justify-center gap-6 px-2 py-1.5 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3" style={{ backgroundColor: colors.safety }} />
            <span className="text-xs" style={{ color: colors.axis }}>{leftLegendText}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3" style={{ backgroundColor: colors.efficacy }} />
            <span className="text-xs" style={{ color: colors.axis }}>{rightLegendText}</span>
          </div>
        </div>
        <div
          ref={chartContainerRef}
          className="flex-1 min-h-0 min-w-0"
          style={{ width: '100%', height: '100%' }}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ComposedChart
              data={chartData}
              layout="vertical"
              margin={margin}
              barCategoryGap="20%"
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
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <YAxis
                type="category"
                dataKey="name"
                interval={0}
                tick={renderYAxisTick}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                width={yAxisWidth}
              />
              <ReferenceLine x={0} stroke={colors.axis} strokeWidth={2.5} strokeOpacity={0.8} />
              <ReferenceLine
                x={medianSafety}
                stroke={colors.safety}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianSafety.toFixed(1)}`, position: 'top', fill: colors.safety, fontSize: 10, fontWeight: 600 }}
              />
              <ReferenceLine
                x={medianEfficacy}
                stroke={colors.efficacy}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianEfficacy.toFixed(1)}`, position: 'top', fill: colors.efficacy, fontSize: 10, fontWeight: 600 }}
              />
              <Tooltip 
                wrapperStyle={{ pointerEvents: 'auto' }}
                content={(props) => {
                  if (isPinned) return null;
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
                      axisMode={axisMode}
                    />;
                  }
                  return null;
                }}
              />
              <Bar 
                dataKey="efficacy" 
                shape={DivergingBarShape}
                background={{ fill: 'transparent' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
          {isPinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
            <div 
              className="fixed z-[9999]"
              style={{ left: tooltipData.x, top: tooltipData.y, pointerEvents: 'auto' }}
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
                axisMode={axisMode}
              />
            </div>
          )}
        </div>
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
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ComposedChart
              data={chartData}
              layout="vertical"
              margin={margin}
              barCategoryGap="30%"
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
                tick={{ fontSize: 13, fill: colors.axis, fontWeight: 500 }}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                tickFormatter={formatXAxisTick}
                label={{
                  value: xAxisLabel,
                  position: 'insideBottom',
                  offset: -5,
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <YAxis
                type="category"
                dataKey="name"
                interval={0}
                tick={renderYAxisTick}
                tickLine={{ stroke: colors.grid, strokeWidth: 1 }}
                axisLine={false}
                width={yAxisWidth}
              />
              <ReferenceLine x={0} stroke={colors.axis} strokeWidth={2.5} strokeOpacity={0.8} />
              <ReferenceLine
                x={medianSafety}
                stroke={colors.safety}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianSafety.toFixed(1)}`, position: 'top', fill: colors.safety, fontSize: 10, fontWeight: 600 }}
              />
              <ReferenceLine
                x={medianEfficacy}
                stroke={colors.efficacy}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.9}
                label={{ value: `Median ${medianEfficacy.toFixed(1)}`, position: 'top', fill: colors.efficacy, fontSize: 10, fontWeight: 600 }}
              />
              <Tooltip 
                wrapperStyle={{ pointerEvents: 'auto' }}
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
                      axisMode={axisMode}
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
                            {leftLegendText}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3" 
                            style={{ backgroundColor: colors.efficacy }}
                          />
                          <span className="text-xs" style={{ color: colors.axis }}>
                            {rightLegendText}
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
                currentTrialIndex={(() => {
                  const payloadData = tooltipData.payload?.[0]?.payload as EfficacySafetyDataPoint | undefined;
                  const treatmentName = payloadData?.treatmentName || '';
                  return trialIndices.get(treatmentName) || 0;
                })()}
                onTrialIndexChange={handleTrialIndexChange}
                efficacyParam={efficacyParam}
                safetyParam={safetyParam}
                axisMode={axisMode}
              />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
