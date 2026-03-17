'use client';

import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import Link from 'next/link';
import {
  Bar,
  BarChart as RechartsBarChart,
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

/** Recharts ReferenceLine label content props; viewBox may be Cartesian or Polar so we accept unknown and narrow when reading */
interface RechartsLabelContentProps {
  viewBox?: unknown;
  value?: React.ReactNode;
}

/** Wrap treatment name into multiple lines for dashboard (compact) X-axis. Max chars per line; prefer word boundaries. */
function wrapTreatmentName(text: string, maxCharsPerLine = 14): string[] {
  if (!text || !text.trim()) return [text || ''];
  const words = text.trim().split(/\s+/);
  if (words.length <= 1) {
    if (text.length <= maxCharsPerLine) return [text];
    return [text.slice(0, maxCharsPerLine), text.slice(maxCharsPerLine)].filter(Boolean);
  }
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxCharsPerLine) {
      current = next;
    } else {
      if (current) lines.push(current);
      current = word.length > maxCharsPerLine ? word.slice(0, maxCharsPerLine) : word;
      if (word.length > maxCharsPerLine && word.slice(maxCharsPerLine)) {
        lines.push(current);
        current = word.slice(maxCharsPerLine);
      }
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Custom X-axis tick for compact (dashboard) mode: multi-line treatment names. */
interface CompactXAxisTickProps {
  x?: number;
  y?: number;
  payload?: { value?: string; treatmentName?: string };
  fill?: string;
  fontSize?: number;
  fontWeight?: number;
}
function CompactXAxisTick({ x = 0, y = 0, payload, fill = COLORS.axis, fontSize = 10, fontWeight = 500 }: CompactXAxisTickProps) {
  const name = payload?.value ?? payload?.treatmentName ?? '';
  const lines = wrapTreatmentName(name, 12);
  const lineHeight = fontSize * 1.15;
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        textAnchor="middle"
        fill={fill}
        fontSize={fontSize}
        fontWeight={fontWeight}
        dominantBaseline="hanging"
      >
        {lines.map((line, i) => (
          <tspan key={i} x={0} dy={i === 0 ? 0 : lineHeight}>
            {line}
          </tspan>
        ))}
      </text>
    </g>
  );
}

// ============================================================================
// Custom Tooltip Component
// ============================================================================

function PinnedHeader({ unpinHint }: { unpinHint: string }) {
  return (
    <div className="mb-1.5 pb-1.5 border-b border-slate-600 flex items-center justify-between" style={{ animation: 'tooltipContentFadeIn 0.2s ease-out' }}>
      <span className="text-[9px] uppercase tracking-wider text-amber-400 font-medium flex items-center gap-1">
        <span className="text-amber-400" style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>📌</span> Pinned
      </span>
      <span className="text-[9px] text-slate-500">{unpinHint}</span>
    </div>
  );
}

interface CustomTooltipContentProps {
  tooltipData: TooltipData | null;
  metricLabel: string;
  metricUnit: string;
  isPinned?: boolean;
}

function CustomTooltipContent({ tooltipData, metricLabel, metricUnit, isPinned }: CustomTooltipContentProps) {
  if (!tooltipData) return null;

  const tooltipBaseClass = 'bg-slate-800 p-3 rounded-lg shadow-xl border border-slate-700 min-w-[260px] max-w-[340px] tooltip-enter';

  if (tooltipData.type === 'scatter') {
    const trial = tooltipData.data as ScatterPoint;
    const sourceValue = trial.publicationName || trial.abstractId;
    const isWebScrape = trial.abstractId?.startsWith('webscrape_');
    const hasSourceUrl = !!trial.sourceUrl;

    return (
      <div
        className={tooltipBaseClass}
        style={{
          animation: isPinned ? 'tooltipFadeIn 0.2s ease-out' : 'tooltipFadeIn 0.15s ease-out',
          pointerEvents: 'auto',
        }}
      >
        {isPinned && <PinnedHeader unpinHint="Click dot to unpin" />}
        <div className="mb-2 pb-2 border-b border-slate-700">
          <h4 className="font-bold text-white text-xs">{trial.treatmentName}</h4>
        </div>
        <div className="mb-2">
          <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0">{metricLabel}</p>
          <p className="text-base font-bold text-white tabular-nums">{trial.value.toFixed(1)}{metricUnit ? ` ${metricUnit}` : ''}</p>
        </div>
        <div className="pt-2 border-t border-slate-700 space-y-1">
          {trial.numberOfPatients != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-400">Patients</span>
              <span className="text-slate-200 font-medium">n={trial.numberOfPatients}</span>
            </div>
          )}
          {trial.nctNumber && (
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-400">NCT</span>
              <Link
                href={`/trial/nct/${trial.nctNumber}`}
                className="text-sky-400 font-mono hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-0.5"
                onClick={(e) => e.stopPropagation()}
                style={{ pointerEvents: 'auto' }}
              >
                <span>{trial.nctNumber}</span>
                <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            </div>
          )}
          {sourceValue && (
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-400">{trial.publicationName ? 'Publication' : 'Abstract ID'}</span>
              {isWebScrape && hasSourceUrl ? (
                <a
                  href={trial.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="text-[11px]">{sourceValue}</span>
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              ) : trial.abstractId ? (
                <Link
                  href={`/trial/abstract/${trial.abstractId}`}
                  className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="text-[11px]">{sourceValue}</span>
                  <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              ) : (
                <span className="text-slate-200 text-[11px]">{sourceValue}</span>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Bar tooltip – single parameter, same compact style as DivergingBarChart
  const treatment = tooltipData.data as HeadToHeadDataPoint;
  const firstTrial = treatment.trials[0];

  return (
    <div
      className={tooltipBaseClass}
      style={{
        animation: isPinned ? 'tooltipFadeIn 0.2s ease-out' : 'tooltipFadeIn 0.15s ease-out',
        pointerEvents: 'auto',
      }}
    >
      {isPinned && <PinnedHeader unpinHint="Click bar to unpin" />}
      <div className="mb-2 pb-2 border-b border-slate-700">
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-bold text-white text-xs">{treatment.treatmentName}</h4>
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider shrink-0 ${
              treatment.approvalStatus === 'Approved'
                ? 'bg-emerald-900/50 text-emerald-300'
                : treatment.approvalStatus === 'Investigational'
                ? 'bg-violet-900/50 text-violet-300'
                : 'bg-slate-700/50 text-slate-300'
            }`}
          >
            {treatment.approvalStatus === 'Approved' && '★ '}
            {treatment.approvalStatus}
          </span>
        </div>
      </div>
      <div className="mb-2">
        <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0">{metricLabel}</p>
        <p className="text-base font-bold text-white tabular-nums">{treatment.averageValue.toFixed(1)}{metricUnit ? ` ${metricUnit} avg` : ' avg'}</p>
      </div>
      <div className="pt-2 border-t border-slate-700 space-y-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-slate-400">Patients</span>
          <span className="text-slate-200 font-medium">{treatment.totalPatients > 0 ? `n=${treatment.totalPatients}` : '—'}</span>
        </div>
        {firstTrial?.nctNumber && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">NCT</span>
            <Link
              href={`/trial/nct/${firstTrial.nctNumber}`}
              className="text-sky-400 font-mono hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-0.5"
              onClick={(e) => e.stopPropagation()}
              style={{ pointerEvents: 'auto' }}
            >
              <span>{firstTrial.nctNumber}</span>
              <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        )}
        {(firstTrial?.publicationName || firstTrial?.abstractId) && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">{firstTrial.publicationName ? 'Publication' : 'Abstract ID'}</span>
            {(() => {
              const sourceValue = firstTrial.publicationName || firstTrial.abstractId;
              const isWebScrape = firstTrial.abstractId?.startsWith('webscrape_');
              const hasSourceUrl = !!firstTrial.sourceUrl;
              if (isWebScrape && hasSourceUrl) {
                return (
                  <a
                    href={firstTrial.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="text-[11px]">{sourceValue}</span>
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                );
              }
              if (firstTrial.abstractId) {
                return (
                  <Link
                    href={`/trial/abstract/${firstTrial.abstractId}`}
                    className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="text-[11px]">{sourceValue}</span>
                    <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                );
              }
              return <span className="text-slate-200 text-[11px]">{sourceValue}</span>;
            })()}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

interface BarChartProps {
  data: HeadToHeadDataPoint[];
  metric?: ChartMetric;
  title?: string;
  description?: string;
  height?: number;
  showLegend?: boolean;
  showReferenceLine?: boolean;
  referenceValue?: number;
  compact?: boolean;
  /** When false, container has no rounded corners (e.g. dashboard grid) */
  rounded?: boolean;
  /** When true (dashboard only), X-axis treatment names wrap to multiple lines. Ignored when compact is false. */
  wrapXAxisLabels?: boolean;
  /** Optional override for bottom margin (e.g. analytics fullscreen). */
  bottomMargin?: number;
  /** When false, tooltips (hover and pin) are disabled (e.g. dashboard snapshot) */
  showTooltip?: boolean;
}

export default function BarChart({
  data,
  metric = 'MEDIAN_OS',
  title,
  description,
  height = 500,
  showLegend = true,
  showReferenceLine = false,
  referenceValue,
  compact = false,
  rounded = true,
  wrapXAxisLabels = false,
  bottomMargin: bottomMarginProp,
  showTooltip = true,
}: BarChartProps) {
  // Ensure height is always a valid positive number (fixes SSR warnings)
  const chartHeight = Math.max(height || 500, 100);
  const [tooltipData, setTooltipData] = useState<TooltipData | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [pinnedDotId, setPinnedDotId] = useState<string | null>(null);
  const [containerDims, setContainerDims] = useState<{width: number; height: number}>({ width: 400, height: 300 });
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isHoveringRef = useRef(false);

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

  const chartContainerRef = useRef<HTMLDivElement>(null);

  const metricConfig = ALL_METRICS[metric];
  const metricLabel = metricConfig?.label || metric;
  const metricUnit = metricConfig?.unit || '';

  // Calculate total trials
  const totalTrials = useMemo(() => 
    data.reduce((sum: number, d: HeadToHeadDataPoint) => sum + d.trials.length, 0), 
    [data]
  );

  // Calculate overall median for reference line
  const overallMedian = useMemo(() => {
    if (referenceValue !== undefined) return referenceValue;
    const allValues = data.flatMap((d: HeadToHeadDataPoint) => d.trials.map((t: TrialDataPoint) => t.value));
    if (allValues.length === 0) return 0;
    const sorted = [...allValues].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
      ? sorted[mid]
      : (sorted[mid - 1] + sorted[mid]) / 2;
  }, [data, referenceValue]);

  // Calculate Y domain to include all individual values
  const yDomain = useMemo((): [number, number] => {
    const allValues = data.flatMap((d: HeadToHeadDataPoint) => [...d.trials.map((t: TrialDataPoint) => t.value), d.averageValue]);
    if (allValues.length === 0) return [0, 100];
    const maxValue = Math.max(...allValues);
    return [0, Math.ceil(maxValue * 1.15)];
  }, [data]);

  const margin = compact
    ? {
        top: 20,
        right: 6,
        bottom: bottomMarginProp ?? (wrapXAxisLabels ? 24 : 140),
        left: 6,
      }
    : {
        top: 20,
        right: showReferenceLine ? 14 : 30,
        bottom: bottomMarginProp ?? 130,
        left: 60,
      };

  // Median label on the right: white/chart background + subtle border, anchored to end of reference line
  const medianLabelRight = useMemo(() => {
    const label = `Median: ${overallMedian.toFixed(1)}`;
    const PADDING_X = 8;
    const PADDING_Y = 4;
    const FONT_SIZE = compact ? 10 : 11;
    const RIGHT_MARGIN = 4;
    const BG = compact ? '#ffffff' : '#1e293b';
    const BORDER = compact ? '#e2e8f0' : '#334155';
    const TEXT_FILL = compact ? '#64748b' : '#94a3b8';
    const RX = 4;

    function MedianLabelContent(props: RechartsLabelContentProps) {
      const vb = (props.viewBox ?? {}) as { x?: number; y?: number; width?: number };
      const chartRight = (vb.x ?? 0) + (vb.width ?? 0) - RIGHT_MARGIN;
      const y = vb.y ?? 0;
      const textWidth = label.length * (FONT_SIZE * 0.6);
      const boxWidth = textWidth + PADDING_X * 2;
      const boxHeight = FONT_SIZE + PADDING_Y * 2;
      const boxX = chartRight - boxWidth;
      const boxY = y - boxHeight / 2;
      return (
        <g style={{ pointerEvents: 'none' }}>
          <rect
            x={boxX}
            y={boxY}
            width={boxWidth}
            height={boxHeight}
            rx={RX}
            ry={RX}
            fill={BG}
            stroke={BORDER}
            strokeWidth={1}
          />
          <text
            x={chartRight - PADDING_X}
            y={y}
            textAnchor="end"
            dominantBaseline="middle"
            fill={TEXT_FILL}
            fontSize={FONT_SIZE}
            fontWeight={500}
          >
            {label}
          </text>
        </g>
      );
    }
    return MedianLabelContent;
  }, [overallMedian, compact]);

  // Consistent tooltip positioning - always follows the same pattern
  const calculateTooltipPosition = useCallback((clientX: number, clientY: number) => {
    const TOOLTIP_WIDTH = 420;
    const TOOLTIP_HEIGHT = 350;
    const OFFSET_X = 15; // Horizontal offset from cursor
    const OFFSET_Y = 10; // Vertical offset from cursor
    const EDGE_PADDING = 16;
    
    // Start with cursor offset (right and slightly below)
    let x = clientX + OFFSET_X;
    let y = clientY + OFFSET_Y;
    
    // Only adjust X if tooltip would go off right edge
    if (x + TOOLTIP_WIDTH > window.innerWidth - EDGE_PADDING) {
      // Flip to left side of cursor
      x = clientX - TOOLTIP_WIDTH - OFFSET_X;
    }
    
    // Ensure doesn't go off left edge
    if (x < EDGE_PADDING) {
      x = EDGE_PADDING;
    }
    
    // Only adjust Y if tooltip would go off bottom edge
    if (y + TOOLTIP_HEIGHT > window.innerHeight - EDGE_PADDING) {
      // Flip to above cursor
      y = clientY - TOOLTIP_HEIGHT - OFFSET_Y;
    }
    
    // Ensure doesn't go off top edge
    if (y < EDGE_PADDING) {
      y = EDGE_PADDING;
    }
    
    return { x, y };
  }, []);

  // Handle dot hover
  const handleDotMouseEnter = useCallback((point: ScatterPoint, event: React.MouseEvent) => {
    const dotId = `${point.treatmentName}-${point.studyId}-${point.value}`;
    
    // If hovering over the pinned dot, update tooltip position
    if (isPinned && pinnedDotId === dotId) {
      const position = calculateTooltipPosition(event.clientX, event.clientY);
      setTooltipData({
        type: 'scatter',
        data: point,
        x: position.x,
        y: position.y,
      });
      return;
    }
    
    // Don't change tooltip if another dot is pinned
    if (isPinned) return;
    
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
    isHoveringRef.current = true;
    const position = calculateTooltipPosition(event.clientX, event.clientY);
    setTooltipData({
      type: 'scatter',
      data: point,
      x: position.x,
      y: position.y,
    });
  }, [isPinned, pinnedDotId, calculateTooltipPosition]);

  const handleDotMouseLeave = useCallback((point?: ScatterPoint) => {
    // If leaving the pinned dot, hide the tooltip
    if (isPinned && point) {
      const dotId = `${point.treatmentName}-${point.studyId}-${point.value}`;
      if (pinnedDotId === dotId) {
        // Leaving pinned dot - keep tooltip but don't update position
        return;
      }
    }
    
    // Don't hide if something is pinned
    if (isPinned) return;
    
    isHoveringRef.current = false;
    scheduleHideTooltip();
  }, [isPinned, pinnedDotId, scheduleHideTooltip]);

  // Handle dot click - pin/unpin the tooltip
  const handleDotClick = useCallback((point: ScatterPoint, event: React.MouseEvent) => {
    if (!showTooltip) return;
    event.stopPropagation();
    event.preventDefault();
    
    const dotId = `${point.treatmentName}-${point.studyId}-${point.value}`;
    
    // If clicking the same pinned dot, unpin
    if (isPinned && pinnedDotId === dotId) {
      setIsPinned(false);
      setTooltipData(null);
      setPinnedDotId(null);
      return;
    }
    
    // Pin to this dot
    const position = calculateTooltipPosition(event.clientX, event.clientY);
    setPinnedDotId(dotId);
    setIsPinned(true);
    setTooltipData({
      type: 'scatter',
      data: point,
      x: position.x,
      y: position.y,
    });
  }, [showTooltip, isPinned, pinnedDotId, calculateTooltipPosition]);

  // Handle bar hover  
  const handleBarMouseEnter = useCallback((entry: HeadToHeadDataPoint, event: React.MouseEvent) => {
    if (!showTooltip || isPinned) return; // Don't change tooltip on hover if pinned or disabled
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
    }
    isHoveringRef.current = true;
    const position = calculateTooltipPosition(event.clientX, event.clientY);
    setTooltipData({
      type: 'bar',
      data: entry,
      x: position.x,
      y: position.y,
    });
  }, [showTooltip, isPinned, calculateTooltipPosition]);

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
    
    if (!payload || !background) return <Rectangle x={x} y={y} width={width} height={height} fill={fill} radius={0} />;
    
    const trials = payload.trials || [];
    const trialCount = trials.length;
    const centerX = x + width / 2;
    
    // Calculate y scale based on background (full chart height) vs bar height
    const chartAreaHeight = background.height;
    const chartAreaTop = background.y;
    const [yMin, yMax] = yDomain;
    
    const valueToY = (value: number) => {
      const range = yMax - yMin;
      if (range === 0) {
        // If all values are the same, center the dot
        return chartAreaTop + chartAreaHeight / 2;
      }
      const normalizedValue = (value - yMin) / range;
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
      
      const dotId = `${payload.treatmentName}-${trial.studyId}-${trial.value}`;
      const isPinnedDot = isPinned && pinnedDotId === dotId;
      
      return {
        ...trial,
        treatmentName: payload.treatmentName,
        dotX: centerX + xOffset,
        dotY: valueToY(trial.value),
        key: `dot-${index}`,
        dotId,
        isPinnedDot,
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
          radius={0}
        />
        {/* The dots */}
        {dots.map((dot) => {
          const isPinnedDot = dot.isPinnedDot;
          const dotRadius = isPinnedDot ? 9 : 7;
          const dotStrokeWidth = isPinnedDot ? 3 : 2;
          
          return (
            <g key={dot.key}>
              {/* Outer glow for pinned dot */}
              {isPinnedDot && (
                <>
                  <circle
                    cx={dot.dotX}
                    cy={dot.dotY}
                    r={16}
                    fill="#fbbf24"
                    opacity={0.2}
                    style={{ pointerEvents: 'none' }}
                  />
                  <circle
                    cx={dot.dotX}
                    cy={dot.dotY}
                    r={12}
                    fill="#fbbf24"
                    opacity={0.3}
                    style={{ pointerEvents: 'none' }}
                  />
                </>
              )}
              {/* Main dot - visual only */}
              <circle
                cx={dot.dotX}
                cy={dot.dotY}
                r={dotRadius}
                fill={isPinnedDot ? '#fbbf24' : colors.dot.fill}
                stroke={isPinnedDot ? '#f59e0b' : colors.dot.stroke}
                strokeWidth={dotStrokeWidth}
                style={{ 
                  transition: 'all 0.2s ease',
                  pointerEvents: 'none',
                }}
              />
              {/* Larger invisible clickable area */}
              <circle
                data-dot-id={dot.dotId}
                data-treatment={dot.treatmentName}
                cx={dot.dotX}
                cy={dot.dotY}
                r={15}
                fill="transparent"
                stroke="transparent"
                strokeWidth={20}
                style={{ 
                  cursor: 'pointer',
                  pointerEvents: 'all',
                }}
                onMouseEnter={(e) => {
                  handleDotMouseEnter(dot, e as unknown as React.MouseEvent);
                }}
                onMouseLeave={() => {
                  handleDotMouseLeave(dot);
                }}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                }}
                onMouseUp={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  const nativeEvent = e as unknown as React.MouseEvent;
                  handleDotClick(dot, nativeEvent);
                }}
              />
            </g>
          );
        })}
      </g>
    );
  }, [yDomain, colors.dot, handleDotMouseEnter, handleDotMouseLeave, handleDotClick, isPinned, pinnedDotId]);

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
        className={`w-full h-full bg-white border border-slate-200 overflow-hidden shadow-sm flex flex-col outline-none focus:outline-none ${rounded ? 'rounded-lg' : 'rounded-none'}`}
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
                <span className="text-[10px] text-slate-400 ml-1">(click to pin)</span>
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
          className="flex-1 bg-white relative outline-none [&_*]:outline-none [&_svg]:outline-none [&_svg_*]:outline-none min-h-0 min-w-0" 
          onMouseLeave={handleChartMouseLeave} 
          tabIndex={-1}
          style={{ WebkitTapHighlightColor: 'transparent' }}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <RechartsBarChart data={data} margin={margin}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={colors.grid}
              />
              <XAxis
                dataKey="treatmentName"
                tick={
                  wrapXAxisLabels ? (
                    <CompactXAxisTick fill={colors.axis} fontSize={10} fontWeight={500} />
                  ) : (
                    { fontSize: 10, fill: colors.axis, fontWeight: 500 }
                  )
                }
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                interval={0}
                angle={wrapXAxisLabels ? undefined : -45}
                textAnchor={wrapXAxisLabels ? undefined : 'end'}
                height={wrapXAxisLabels ? 48 : 80}
              />
              <YAxis
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                domain={yDomain}
                width={50}
                label={{
                  value: `${metricLabel} (${metricUnit})`,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              {showReferenceLine && (
                <ReferenceLine
                  y={overallMedian}
                  stroke="#94a3b8"
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                  segment={[
                    { x: 0, y: overallMedian },
                    { x: Math.max(0, data.length - 0.85), y: overallMedian },
                  ]}
                  label={{ content: medianLabelRight }}
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
                {data.map((entry: HeadToHeadDataPoint, index: number) => (
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
            </RechartsBarChart>
          </ResponsiveContainer>
          
          {/* Custom tooltip */}
          {showTooltip && tooltipData && (
            <div 
              className={`fixed z-[9999]`}
              style={{ 
                left: tooltipData.x,
                top: tooltipData.y,
                pointerEvents: 'auto',
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
              <span className="text-[10px] text-slate-500 ml-1">(click to pin)</span>
            </div>
          </div>
        )}

        <div 
          style={{ width: '100%', height: chartHeight, minWidth: 0, minHeight: 100, WebkitTapHighlightColor: 'transparent' }} 
          className="relative outline-none [&_*]:outline-none [&_svg]:outline-none [&_svg_*]:outline-none" 
          onMouseLeave={handleChartMouseLeave} 
          tabIndex={-1}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <RechartsBarChart data={data} margin={margin}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={colors.grid}
                strokeOpacity={0.3}
              />
              <XAxis
                dataKey="treatmentName"
                tick={{ fontSize: 10, fill: colors.axis, fontWeight: 500 }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                interval={0}
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                domain={yDomain}
                label={{
                  value: `${metricLabel} (${metricUnit})`,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              {showReferenceLine && (
                <ReferenceLine
                  y={overallMedian}
                  stroke="#94a3b8"
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                  segment={[
                    { x: 0, y: overallMedian },
                    { x: Math.max(0, data.length - 0.85), y: overallMedian },
                  ]}
                  label={{ content: medianLabelRight }}
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
                {data.map((entry: HeadToHeadDataPoint, index: number) => (
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
            </RechartsBarChart>
          </ResponsiveContainer>
          
          {/* Custom tooltip */}
          {showTooltip && tooltipData && (
            <div 
              className={`fixed z-[9999]`}
              style={{ 
                left: tooltipData.x,
                top: tooltipData.y,
                pointerEvents: 'auto',
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
                {data.filter((d: HeadToHeadDataPoint) => d.approvalStatus === 'Approved').length}
              </p>
              <p className="text-xs text-slate-400 uppercase tracking-wider">
                Approved
              </p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet-400 tabular-nums">
                {data.filter((d: HeadToHeadDataPoint) => d.approvalStatus === 'Investigational').length}
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
