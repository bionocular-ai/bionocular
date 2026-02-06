'use client';

import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import Link from 'next/link';
import {
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Cell,
  ReferenceLine,
  LabelList,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { BubbleChartDataPoint, EFFICACY_METRICS, SAFETY_METRICS } from '@/types/analytics';

// ============================================================================
// Types
// ============================================================================

interface BubbleChartProps {
  data: BubbleChartDataPoint[];
  title?: string;
  description?: string;
  height?: number;
  efficacyLabel?: string;
  safetyLabel?: string;
  compact?: boolean;
  // Safety axis is inverted (0% on right, 100% on left) - better safety = further right
  invertSafetyAxis?: boolean;
  // Z-axis parameter to determine bubble size
  zAxisParam?: string;
  // Axis configuration: 0-5 representing different X, Y, Z axis assignments
  // 0: X=Safety, Y=Efficacy, Z=ZParam (default)
  // 1: X=Efficacy, Y=Safety, Z=ZParam
  // 2: X=Safety, Y=ZParam, Z=Efficacy
  // 3: X=ZParam, Y=Safety, Z=Efficacy
  // 4: X=Efficacy, Y=ZParam, Z=Safety
  // 5: X=ZParam, Y=Efficacy, Z=Safety
  axisConfig?: number;
  efficacyParam?: string;
  safetyParam?: string;
  /** When set, both axes use the same metric type for labels (efficacy-efficacy or safety-safety) */
  axisMode?: 'efficacy-safety' | 'efficacy-efficacy' | 'safety-safety';
  /** When true (non-compact), chart fills parent height like DivergingBarChart */
  fillHeight?: boolean;
}

// ============================================================================
// Color Palette
// ============================================================================

// Extended color palette for different treatments
const TREATMENT_COLORS = [
  '#3b82f6', // Blue
  '#10b981', // Green
  '#f59e0b', // Amber
  '#ef4444', // Red
  '#8b5cf6', // Purple
  '#ec4899', // Pink
  '#06b6d4', // Cyan
  '#84cc16', // Lime
  '#f97316', // Orange
  '#6366f1', // Indigo
  '#14b8a6', // Teal
  '#a855f7', // Violet
  '#eab308', // Yellow
  '#22c55e', // Emerald
  '#f43f5e', // Rose
  '#0ea5e9', // Sky
  '#64748b', // Slate
  '#d946ef', // Fuchsia
  '#06b6d4', // Cyan
  '#22d3ee', // Light Cyan
];

const COLORS = {
  approved: '#10b981', // Green
  investigational: '#8b5cf6', // Purple
  developmentStopped: '#ef4444', // Red
  unknown: '#64748b', // Gray
  grid: '#e2e8f0',
  axis: '#64748b',
};

// Tooltip positioning: offset from anchor, flip when overflowing, clamp to safe viewport (with top inset for fixed header)
const TOOLTIP_WIDTH = 280; // Realistic tooltip width (min-w-[260px] + padding)
const TOOLTIP_HEIGHT = 220; // Realistic tooltip height for typical content
const TOOLTIP_OFFSET_X = 40; // Moderate offset to avoid covering bubbles
const TOOLTIP_OFFSET_Y = 15;  // Moderate offset to avoid covering bubbles
const TOOLTIP_EDGE_PADDING = 16;
const TOOLTIP_EDGE_PADDING_TOP = 72; // Reserve space for fixed app header so tooltip is never clipped

function getTooltipViewportBounds(): { top: number; left: number; right: number; bottom: number } {
  return {
    top: TOOLTIP_EDGE_PADDING_TOP,
    left: TOOLTIP_EDGE_PADDING,
    right: typeof window !== 'undefined' ? window.innerWidth - TOOLTIP_EDGE_PADDING : 800,
    bottom: typeof window !== 'undefined' ? window.innerHeight - TOOLTIP_EDGE_PADDING : 600,
  };
}

// Bubble radius range (px) – area proportional to value (Recharts maps domain [min,max] to area range)
// MIN_RADIUS is smaller (3px) for truly proportional sizing - smallest bubbles will be appropriately tiny
const MIN_RADIUS = 3;
const MAX_RADIUS = 60;

const Z_AXIS_MIN_AREA = Math.PI * Math.pow(MIN_RADIUS, 2);
const Z_AXIS_MAX_AREA = Math.PI * Math.pow(MAX_RADIUS, 2);

/**
 * Radius in px from linear area scale (matches Recharts: domain [min,max] -> area range, radius = sqrt(area/π)).
 * Ensures highest value maps to MAX_RADIUS and bubbles scale truly proportionally from near-zero to max.
 */
function radiusFromLinearArea(
  value: number,
  dataMin: number,
  dataMax: number
): number {
  // Only use MIN_RADIUS for zero or negative values
  if (value <= 0 || dataMax <= 0) return MIN_RADIUS;
  if (dataMax <= dataMin) return value >= dataMin ? MAX_RADIUS : MIN_RADIUS;
  // Proportional scaling: normalize value to [0, 1] range
  const t = (value - dataMin) / (dataMax - dataMin);
  const area = Z_AXIS_MIN_AREA + t * (Z_AXIS_MAX_AREA - Z_AXIS_MIN_AREA);
  const radius = Math.sqrt(Math.max(0, area) / Math.PI);
  // Cap at MAX_RADIUS but allow truly proportional small sizes (no MIN_RADIUS clamping for positive values)
  return Math.min(MAX_RADIUS, radius);
}

// ============================================================================
// Custom Label Component
// ============================================================================

interface CustomLabelProps {
  x?: number;
  y?: number;
  payload?: BubbleChartDataPoint & { x?: number; y?: number; z?: number; rawZ?: number };
  value?: string;
}

// CustomLabel uses radiusPx from payload (set by chartData) for positioning
const CustomLabel = ({ x, y, payload, value }: CustomLabelProps) => {
  const labelText = value || payload?.treatmentName;

  if (!x || !y || !labelText) return null;

  const extendedPayload = payload as (BubbleChartDataPoint & { z?: number; rawZ?: number; radiusPx?: number }) | undefined;
  const bubbleRadius = extendedPayload?.radiusPx ?? MIN_RADIUS;

  const verticalOffset = bubbleRadius + 12;
  const labelX = x;
  const labelY = y + verticalOffset;
  
  return (
    <g>
      {/* Optional: Add a subtle connecting line (dashed) from bubble to label */}
      <line
        x1={x}
        y1={y + bubbleRadius}
        x2={labelX}
        y2={labelY - 4}
        stroke="#666666"
        strokeWidth={0.5}
        strokeDasharray="2,2"
        opacity={0.4}
        pointerEvents="none"
      />
      {/* Label text - dark text for light background */}
      <text
        x={labelX}
        y={labelY}
        fill="#1e293b"
        fontSize={11}
        fontWeight={400}
        textAnchor="middle"
        style={{ 
          pointerEvents: 'none',
          userSelect: 'none',
          fontFamily: 'system-ui, -apple-system, sans-serif',
        }}
      >
        {labelText}
      </text>
    </g>
  );
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

// Get unit from metrics config
const getUnit = (param: string | undefined, metrics: typeof EFFICACY_METRICS | typeof SAFETY_METRICS): string => {
  if (!param) return '';
  const metric = metrics[param];
  return metric?.unit || '';
};

// Format axis label with unit
const formatAxisLabelWithUnit = (label: string, unit: string): string => {
  if (!unit) return label;
  return `${label} (${unit})`;
};

// ============================================================================
// Custom Tooltip
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: BubbleChartDataPoint;
    value: number;
  }>;
  isPinned?: boolean;
  currentTrialIndex?: number;
  onTrialIndexChange?: (treatmentName: string, newIndex: number) => void;
  efficacyParam?: string;
  safetyParam?: string;
  axisMode?: 'efficacy-safety' | 'efficacy-efficacy' | 'safety-safety';
}

const CustomTooltip = ({ 
  active, 
  payload, 
  isPinned, 
  currentTrialIndex = 0,
  onTrialIndexChange,
  efficacyParam,
  safetyParam,
  axisMode,
}: CustomTooltipProps) => {
  const data = payload?.[0]?.payload as BubbleChartDataPoint | undefined;
  const allTrials = useMemo(() => data?.allTrials ?? [], [data?.allTrials]);

  // Group trials by NCT (or abstract id / pub id when no NCT) and create selectable list – must run unconditionally (hooks rule)
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

  const dataNonNull = data!;
  const hasMultipleTrials = allTrials.length > 1;
  const currentTrial = allTrials[currentTrialIndex] || {
    efficacy: dataNonNull.efficacy,
    safety: dataNonNull.safety,
    numberOfPatients: dataNonNull.numberOfPatients,
    year: dataNonNull.year,
    nctNumber: dataNonNull.nctNumber,
    abstractId: dataNonNull.abstractId,
    publicationName: dataNonNull.publicationName,
    citation: dataNonNull.citation,
    phase: dataNonNull.phase,
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
          <span className="text-[9px] text-slate-500">Click bubble to unpin</span>
        </div>
      )}
      <div className="mb-2 pb-2 border-b border-slate-700">
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-bold text-white text-xs">{dataNonNull.treatmentName}</h4>
          {dataNonNull.developmentStatus && (
            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider shrink-0 ${
                dataNonNull.developmentStatus === 'Approved'
                  ? 'bg-emerald-900/50 text-emerald-300'
                  : dataNonNull.developmentStatus === 'Development stopped'
                  ? 'bg-red-900/50 text-red-300'
                  : 'bg-violet-900/50 text-violet-300'
              }`}
            >
              {dataNonNull.developmentStatus === 'Approved' && '★ '}
              {dataNonNull.developmentStatus === 'Development stopped' && 'Ø '}
              {dataNonNull.developmentStatus}
            </span>
          )}
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
          <span className="text-slate-200 font-medium">n={currentTrial.numberOfPatients}</span>
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
        {(currentTrial.abstractId || currentTrial.publicationName) && (
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">
              {currentTrial.publicationName ? 'Publication' : 'Abstract ID'}
            </span>
            {(() => {
              const sourceValue = currentTrial.publicationName || currentTrial.abstractId;
              const isWebScrape = currentTrial.abstractId?.startsWith('webscrape_');
              const hasSourceUrl = !!dataNonNull.sourceUrl;
              if (isWebScrape && hasSourceUrl) {
                return (
                  <a
                    href={dataNonNull.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="text-xs">{sourceValue}</span>
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                );
              }
              if (currentTrial.abstractId) {
                return (
                  <Link
                    href={`/trial/abstract/${currentTrial.abstractId}`}
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

export default function BubbleChart({
  data,
  title = 'Safety vs Efficacy Comparison',
  description = 'Bubble size represents number of patients. Upper-right quadrant indicates better safety and efficacy.',
  height = 600,
  efficacyLabel = 'Efficacy (ORR %)',
  safetyLabel = 'Safety (Grade 3+ TRAE %)',
  compact = false,
  invertSafetyAxis = true, // Default: better safety (lower %) on the right
  zAxisParam = 'NUMBER_OF_PATIENTS', // Default to number of patients
  axisConfig = 0, // Default: X=Safety, Y=Efficacy, Z=ZParam
  efficacyParam,
  safetyParam,
  axisMode,
  fillHeight = false,
}: BubbleChartProps) {
  const chartHeight = Math.max(height || 600, 100);
  const [isPinned, setIsPinned] = useState(false);
  const [pinnedBubbleId, setPinnedBubbleId] = useState<string | null>(null);
  const [pinnedAxisConfig, setPinnedAxisConfig] = useState<number | null>(null);
  const [trialIndices, setTrialIndices] = useState<Map<string, number>>(new Map());
  const [containerDims, setContainerDims] = useState<{width: number; height: number}>({ width: 400, height: 300 });
  const [tooltipData, setTooltipData] = useState<{
    active: boolean;
    payload?: Array<{
      payload: BubbleChartDataPoint;
      value: number;
    }>;
    x?: number;
    y?: number;
  } | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const mousePositionRef = useRef<{ x: number; y: number } | null>(null);

  const handleTrialIndexChange = useCallback((treatmentName: string, newIndex: number) => {
    setTrialIndices(prev => {
      const next = new Map(prev);
      next.set(treatmentName, newIndex);
      return next;
    });
  }, []);

  const normalizedAxisConfig = Math.max(0, Math.min(5, Math.floor(axisConfig || 0)));
  const effectivePinned = isPinned && pinnedAxisConfig === normalizedAxisConfig;

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

  // Track mouse position globally for accurate tooltip positioning
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isPinned) {
        mousePositionRef.current = {
          x: e.clientX,
          y: e.clientY,
        };
      }
    };

    // Track mouse position globally to catch all movement
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [isPinned]);

  // Anchor in viewport coords → tooltip x,y. Flip when overflowing, clamp to safe bounds (top inset for fixed header).
  // Smart positioning: prefer right/bottom but flip to left/top if not enough space
  const calculateTooltipPosition = useCallback((anchorX: number, anchorY: number) => {
    const v = getTooltipViewportBounds();
    const W = TOOLTIP_WIDTH;
    const H = TOOLTIP_HEIGHT;
    const OX = TOOLTIP_OFFSET_X;
    const OY = TOOLTIP_OFFSET_Y;

    // Calculate available space in all directions
    const spaceRight = v.right - anchorX;
    const spaceLeft = anchorX - v.left;
    const spaceBottom = v.bottom - anchorY;
    const spaceTop = anchorY - v.top;

    // Choose horizontal position based on available space
    let x: number;
    if (spaceRight >= W + OX) {
      // Enough space on right
      x = anchorX + OX;
    } else if (spaceLeft >= W + OX) {
      // Not enough on right, try left
      x = anchorX - W - OX;
    } else {
      // Not enough space on either side, center it
      x = anchorX + OX;
    }
    x = Math.max(v.left, Math.min(x, v.right - W));

    // Choose vertical position based on available space
    let y: number;
    if (spaceBottom >= H + OY) {
      // Enough space below
      y = anchorY + OY;
    } else if (spaceTop >= H + OY) {
      // Not enough below, try above
      y = anchorY - H - OY;
    } else {
      // Not enough space above or below, position below
      y = anchorY + OY;
    }
    y = Math.max(v.top, Math.min(y, v.bottom - H));

    return { x, y };
  }, []);

  // Get tooltip position using actual mouse cursor position for accurate placement
  const getHoverTooltipViewportPosition = useCallback((
    // Intentionally unused - we use mousePositionRef.current instead
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _coordX: number | undefined,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _coordY: number | undefined
  ): { x: number; y: number } => {
    // Use the actual mouse cursor position if available
    if (mousePositionRef.current) {
      return calculateTooltipPosition(mousePositionRef.current.x, mousePositionRef.current.y);
    }
    
    // Fallback to a safe default position
    return calculateTooltipPosition(
      window.innerWidth / 2, 
      TOOLTIP_EDGE_PADDING_TOP + 100
    );
  }, [calculateTooltipPosition]);

  // Helper function to get Z-axis value based on zAxisParam
  const getZAxisValue = useCallback((item: BubbleChartDataPoint): number => {
    if (zAxisParam === 'NUMBER_OF_PATIENTS') {
      return item.numberOfPatients || 0;
    }
    if (item.zValue !== undefined && item.zValue !== null && !Number.isNaN(item.zValue)) {
      return item.zValue;
    }
    return 0;
  }, [zAxisParam]);

  // Helper function to determine which metric is on which axis
  const getAxisMetrics = useCallback((): { xMetric: 'efficacy' | 'safety' | 'zParam'; yMetric: 'efficacy' | 'safety' | 'zParam'; zMetric: 'efficacy' | 'safety' | 'zParam' } => {
    // Returns { xMetric, yMetric, zMetric } where each is 'efficacy', 'safety', or 'zParam'
    switch (normalizedAxisConfig) {
      case 0: return { xMetric: 'safety', yMetric: 'efficacy', zMetric: 'zParam' };
      case 1: return { xMetric: 'efficacy', yMetric: 'safety', zMetric: 'zParam' };
      case 2: return { xMetric: 'safety', yMetric: 'zParam', zMetric: 'efficacy' };
      case 3: return { xMetric: 'zParam', yMetric: 'safety', zMetric: 'efficacy' };
      case 4: return { xMetric: 'efficacy', yMetric: 'zParam', zMetric: 'safety' };
      case 5: return { xMetric: 'zParam', yMetric: 'efficacy', zMetric: 'safety' };
      default: return { xMetric: 'safety', yMetric: 'efficacy', zMetric: 'zParam' };
    }
  }, [normalizedAxisConfig]);

  // Fixed bubble radius range (px) for scaleSqrt and CustomLabel
  // Z-axis range as area so Recharts radius = sqrt(area/π). Highest value maps to MAX_RADIUS.
  const zAxisRange: [number, number] = useMemo(
    () => [Math.PI * Math.pow(MIN_RADIUS, 2), Math.PI * Math.pow(MAX_RADIUS, 2)],
    []
  );

  // Transform data: z = raw value (patient count etc.). Domain [min, max] so max maps to MAX_RADIUS.
  const { chartData, transformedZDomain } = useMemo(() => {
    if (!data || data.length === 0) {
      return { chartData: [] as Array<BubbleChartDataPoint & { x: number; y: number; z: number; rawZ: number; radiusPx?: number }>, transformedZDomain: [0, 1] as [number, number] };
    }

    type PointRow = {
      item: BubbleChartDataPoint;
      efficacy: number;
      safety: number;
      numberOfPatients: number;
      safetyValue: number;
      zValue: number;
      x: number;
      y: number;
      rawZValue: number;
    };

    const rows: PointRow[] = data.map((item) => {
      const currentIndex = trialIndices.get(item.treatmentName) ?? 0;
      const allTrials = item.allTrials || [];
      const currentTrial = allTrials[currentIndex];
      const efficacy = currentTrial?.efficacy ?? item.efficacy ?? 0;
      const safety = currentTrial?.safety ?? item.safety ?? 0;
      const numberOfPatients = currentTrial?.numberOfPatients ?? item.numberOfPatients ?? 0;
      const itemWithCurrentTrial = { ...item, efficacy, safety, numberOfPatients };
      const safetyValue = invertSafetyAxis ? 100 - safety : safety;
      const zValue = getZAxisValue(itemWithCurrentTrial);

      let x: number, y: number, rawZValue: number;
      switch (normalizedAxisConfig) {
        case 0:
          x = safetyValue;
          y = efficacy;
          rawZValue = Math.max(0, zValue);
          break;
        case 1:
          x = efficacy;
          y = safetyValue;
          rawZValue = Math.max(0, zValue);
          break;
        case 2:
          x = safetyValue;
          y = Math.max(0, zValue);
          rawZValue = efficacy;
          break;
        case 3:
          x = Math.max(0, zValue);
          y = safetyValue;
          rawZValue = efficacy;
          break;
        case 4:
          x = efficacy;
          y = Math.max(0, zValue);
          rawZValue = safetyValue;
          break;
        case 5:
          x = Math.max(0, zValue);
          y = efficacy;
          rawZValue = safetyValue;
          break;
        default:
          x = safetyValue;
          y = efficacy;
          rawZValue = Math.max(0, zValue);
      }
      return { item, efficacy, safety, numberOfPatients, safetyValue, zValue, x, y, rawZValue };
    });

    const rawZValues = rows.map((r) => r.rawZValue).filter((v) => v != null && !Number.isNaN(v) && isFinite(v));
    // Use 0 as dataMin for truly proportional bubble sizing (smallest values = smallest bubbles)
    const dataMin = 0;
    let dataMax = rawZValues.length === 0 ? 1 : Math.max(...rawZValues);
    if (dataMax <= 0) dataMax = 1;
    const domain: [number, number] = [dataMin, dataMax];

    const chartDataOut = rows.map((row) => {
      const { item, efficacy, safety, numberOfPatients, x, y, rawZValue } = row;
      const z = rawZValue;
      const radiusPx = radiusFromLinearArea(rawZValue, dataMin, dataMax);
      return {
        ...item,
        efficacy,
        safety,
        numberOfPatients,
        x,
        y,
        z,
        rawZ: rawZValue,
        radiusPx,
      };
    });

    return { chartData: chartDataOut, transformedZDomain: domain };
  }, [data, trialIndices, invertSafetyAxis, normalizedAxisConfig, getZAxisValue]);

  // Helper function to calculate domain for a given metric type
  const calculateDomainForMetric = useCallback((metricType: 'efficacy' | 'safety' | 'zParam', values: number[]): [number, number] => {
    if (values.length === 0) {
      // Default domains based on metric type
      if (metricType === 'efficacy') return [0, 60];
      if (metricType === 'safety') return [0, 100];
      if (metricType === 'zParam') return [0, 1000];
      return [0, 100];
    }
    
    const min = Math.min(...values);
    const max = Math.max(...values);
    
    // Handle edge case: all values are the same
    if (min === max) {
      const center = min;
      let range: number;
      if (metricType === 'efficacy') {
        range = Math.max(20, center * 0.2); // At least 20 or 20% of center
      } else if (metricType === 'safety') {
        range = Math.max(20, center * 0.2);
      } else { // zParam
        range = Math.max(100, center * 0.2);
      }
      const domainMin = Math.max(0, center - range);
      const domainMax = center + range;
      return [domainMin, domainMax];
    }
    
    const padding = Math.max((max - min) * 0.1, 1); // At least 1 unit padding
    const rawMin = Math.max(0, min - padding);
    let rawMax = max + padding;
    
    // For zParam, don't cap at 100
    if (metricType !== 'zParam') {
      rawMax = Math.min(100, rawMax);
    }
    
    // Round to nice whole numbers
    let roundedMin: number, roundedMax: number;
    if (metricType === 'zParam') {
      // For Z-axis values, use larger rounding intervals
      const interval = rawMax > 1000 ? 100 : rawMax > 100 ? 50 : 10;
      roundedMin = Math.floor(rawMin / interval) * interval;
      roundedMax = Math.ceil(rawMax / interval) * interval;
    } else {
      // For percentage values, round to 10s
      roundedMin = Math.floor(rawMin / 10) * 10;
      roundedMax = Math.ceil(rawMax / 10) * 10;
    }
    
    // Ensure we have a valid range
    if (roundedMin >= roundedMax) {
      const adjustment = metricType === 'zParam' ? 100 : 10;
      return [Math.max(0, roundedMin - adjustment), roundedMax + adjustment];
    }
    
    return [roundedMin, roundedMax];
  }, []);

  // Calculate domains with nice whole number boundaries
  // Handle edge cases: empty data, single value, all same values, etc.
  const xDomain = useMemo(() => {
    const values = chartData.map((d) => d.x).filter((v): v is number => v !== null && v !== undefined && !isNaN(v) && isFinite(v));
    const { xMetric } = getAxisMetrics();
    return calculateDomainForMetric(xMetric, values);
  }, [chartData, getAxisMetrics, calculateDomainForMetric]);

  const yDomain = useMemo(() => {
    const values = chartData.map((d) => d.y).filter((v): v is number => v !== null && v !== undefined && !isNaN(v) && isFinite(v));
    const { yMetric } = getAxisMetrics();
    return calculateDomainForMetric(yMetric, values);
  }, [chartData, getAxisMetrics, calculateDomainForMetric]);

  // Helper function to calculate ticks for an axis based on domain and metric type
  const calculateTicks = useCallback((domain: [number, number], metricType: 'efficacy' | 'safety' | 'zParam'): number[] => {
    const [min, max] = domain;
    const range = max - min;
    
    if (range <= 0) {
      return [min, max];
    }
    
    let tickInterval: number;
    
    if (metricType === 'zParam') {
      // For Z-axis values, use larger intervals
      if (range <= 100) {
        tickInterval = 20;
      } else if (range <= 500) {
        tickInterval = 100;
      } else if (range <= 1000) {
        tickInterval = 200;
      } else {
        tickInterval = 500;
      }
    } else {
      // For percentage values (efficacy, safety)
      if (range <= 30) {
        tickInterval = 10;
      } else if (range <= 60) {
        tickInterval = 20;
      } else {
        tickInterval = 20; // For up to 100
      }
    }
    
    const ticks: number[] = [];
    for (let i = min; i <= max; i += tickInterval) {
      ticks.push(i);
    }
    
    // Ensure max is included if not already
    if (ticks.length === 0 || ticks[ticks.length - 1] < max) {
      ticks.push(max);
    }
    
    // Remove duplicates and sort
    return Array.from(new Set(ticks)).sort((a, b) => a - b);
  }, []);

  // Calculate evenly spaced ticks with whole number intervals for X-axis
  const xAxisTicks = useMemo(() => {
    const { xMetric } = getAxisMetrics();
    return calculateTicks(xDomain, xMetric as 'efficacy' | 'safety' | 'zParam');
  }, [xDomain, getAxisMetrics, calculateTicks]);

  // Calculate evenly spaced ticks with whole number intervals for Y-axis
  const yAxisTicks = useMemo(() => {
    const { yMetric } = getAxisMetrics();
    return calculateTicks(yDomain, yMetric as 'efficacy' | 'safety' | 'zParam');
  }, [yDomain, getAxisMetrics, calculateTicks]);


  // Determine what metric is currently on the Z-axis (bubble size)

  // Calculate quadrant line positions
  // These are always at the midpoint of their respective domains
  const xMidpoint = useMemo(() => {
    const [min, max] = xDomain;
    if (min >= max) return min;
    return (min + max) / 2;
  }, [xDomain]);

  const yMidpoint = useMemo(() => {
    const [min, max] = yDomain;
    if (min >= max) return min;
    return (min + max) / 2;
  }, [yDomain]);

  // Use light mode colors for both compact and non-compact modes
  const colors = COLORS;
  // Padding so MAX_RADIUS (60px) bubbles are not clipped at chart edges
  const axisPadding = MAX_RADIUS + 15;
  const margin = compact
    ? { top: axisPadding, right: axisPadding, bottom: 60 + axisPadding, left: 60 + axisPadding }
    : { top: axisPadding, right: axisPadding, bottom: 80 + axisPadding, left: 80 + axisPadding };
  // Tighter margins when fillHeight so the plot occupies all area (like DivergingBarChart)
  const marginFillHeight = {
    top: MAX_RADIUS + 8,
    right: MAX_RADIUS + 8,
    bottom: 50,
    left: 70,
  };

  // Get readable label for Z-axis parameter - defined early so it can be used in other callbacks
  const getZAxisLabel = useCallback((param: string): string => {
    const labelMap: Record<string, string> = {
      'NUMBER_OF_PATIENTS': 'Number of patients',
      'HR_PFS': 'HR (PFS)',
      'HR_OS': 'HR (OS)',
      'HR_EFS': 'HR (EFS)',
      'HR_RFS': 'HR (RFS)',
      'HR_MFS': 'HR (MFS)',
    };
    return labelMap[param] || param;
  }, []);

  // Handle bubble click - pin/unpin the tooltip
  const handleBubbleClick = useCallback((data: BubbleChartDataPoint, event?: React.MouseEvent) => {
    const bubbleId = `${data.treatmentName}-${data.efficacy}-${data.safety}`;
    
    // If clicking the same pinned bubble, unpin
    if (isPinned && pinnedBubbleId === bubbleId) {
      setIsPinned(false);
      setTooltipData(null);
      setPinnedBubbleId(null);
      setPinnedAxisConfig(null);
      // Don't reset mousePositionRef - keep tracking for hover tooltips
      return;
    }
    
    // Pin to this bubble - use current mouse position or click event position
    let position: { x: number; y: number };
    
    if (mousePositionRef.current) {
      // Use the tracked mouse position
      position = calculateTooltipPosition(mousePositionRef.current.x, mousePositionRef.current.y);
    } else if (event) {
      // Fallback to click event position
      position = calculateTooltipPosition(event.clientX, event.clientY);
    } else {
      // Last resort: center of screen
      position = calculateTooltipPosition(window.innerWidth / 2, window.innerHeight / 2);
    }
    
    setPinnedBubbleId(bubbleId);
    setPinnedAxisConfig(normalizedAxisConfig);
    setIsPinned(true);
    setTooltipData({
      active: true,
      payload: [{
        payload: data,
        value: data.efficacy,
      }],
      x: position.x,
      y: position.y,
    });
  }, [isPinned, pinnedBubbleId, normalizedAxisConfig, calculateTooltipPosition]);

  // Get unique treatments and assign colors
  const treatmentColorMap = useMemo(() => {
    const uniqueTreatments = Array.from(new Set(data.map(item => item.treatmentName)));
    const map = new Map<string, string>();
    uniqueTreatments.forEach((treatment, index) => {
      map.set(treatment, TREATMENT_COLORS[index % TREATMENT_COLORS.length]);
    });
    return map;
  }, [data]);

  // Get color for each point based on treatment name
  const getColor = (item: BubbleChartDataPoint) => {
    return treatmentColorMap.get(item.treatmentName) || colors.unknown;
  };

  // Custom tick formatters - handle all axis configurations and inversion
  const formatXAxisTick = (value: number) => {
    const { xMetric } = getAxisMetrics();
    
    if (xMetric === 'safety' && invertSafetyAxis) {
      // Safety axis is inverted, show actual safety %
      return `${100 - value}`;
    }
    
    // For efficacy and zParam, no inversion needed
    // Format zParam values appropriately
    if (xMetric === 'zParam') {
      if (value >= 1000) {
        return `${(value / 1000).toFixed(1)}k`;
      }
      return `${Math.round(value)}`;
    }
    
    return `${value}`;
  };

  const formatYAxisTick = (value: number) => {
    const { yMetric } = getAxisMetrics();
    
    if (yMetric === 'safety' && invertSafetyAxis) {
      // Safety axis is inverted, show actual safety %
      return `${100 - value}`;
    }
    
    // For efficacy and zParam, no inversion needed
    // Format zParam values appropriately
    if (yMetric === 'zParam') {
      if (value >= 1000) {
        return `${(value / 1000).toFixed(1)}k`;
      }
      return `${Math.round(value)}`;
    }
    
    return `${value}`;
  };

  const efficacyMetricsForAxis = axisMode === 'safety-safety' ? SAFETY_METRICS : EFFICACY_METRICS;
  const safetyMetricsForAxis = axisMode === 'efficacy-efficacy' ? EFFICACY_METRICS : SAFETY_METRICS;
  const getAxisLabel = useCallback((metric: 'efficacy' | 'safety' | 'zParam'): string => {
    if (metric === 'efficacy') {
      const unit = getUnit(efficacyParam, efficacyMetricsForAxis);
      const label = getCompactLabel(efficacyParam, efficacyMetricsForAxis, efficacyLabel || 'ORR');
      return formatAxisLabelWithUnit(label, unit);
    }
    if (metric === 'safety') {
      const unit = getUnit(safetyParam, safetyMetricsForAxis);
      const label = getCompactLabel(safetyParam, safetyMetricsForAxis, safetyLabel || 'Grade 3+ TRAE');
      return formatAxisLabelWithUnit(label, unit);
    }
    if (metric === 'zParam') {
      return getZAxisLabel(zAxisParam);
    }
    return '';
  }, [efficacyParam, safetyParam, efficacyLabel, safetyLabel, zAxisParam, getZAxisLabel, efficacyMetricsForAxis, safetyMetricsForAxis]);

  const xAxisLabel = useMemo(() => {
    const { xMetric } = getAxisMetrics();
    return getAxisLabel(xMetric);
  }, [getAxisMetrics, getAxisLabel]);

  const yAxisLabel = useMemo(() => {
    const { yMetric } = getAxisMetrics();
    return getAxisLabel(yMetric);
  }, [getAxisMetrics, getAxisLabel]);

  if (data.length === 0) {
    return (
      <Card className={`w-full bg-slate-900 border-slate-800 outline-none focus:outline-none ${compact ? 'border-0 shadow-none' : ''}`}>
        <CardContent className={`flex items-center justify-center outline-none focus:outline-none ${compact ? 'h-[200px]' : 'h-[400px]'}`}>
          <p className="text-slate-400">No data available</p>
        </CardContent>
      </Card>
    );
  }

  if (compact) {
    return (
      <div 
        className="w-full h-full bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm outline-none focus:outline-none [&_svg]:outline-none [&_svg]:focus:outline-none [&_.recharts-wrapper]:outline-none [&_.recharts-wrapper]:focus:outline-none flex flex-col" 
        tabIndex={-1}
        onMouseDown={(e) => {
          const target = e.target as HTMLElement;
          const isInteractive = target.closest('select, button, input, a[href], [role="button"]');
          if (!isInteractive) {
            e.preventDefault();
            (e.currentTarget as HTMLElement).blur();
          }
        }}
        style={{ outline: 'none' }}
      >
        <div className="flex-1 min-h-0 relative" ref={chartContainerRef}>
        <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
          <ScatterChart margin={margin}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis
              type="number"
              dataKey="x"
              domain={xDomain}
              ticks={xAxisTicks}
              tick={{ fontSize: 12, fill: colors.axis }}
              tickLine={{ stroke: colors.grid }}
              axisLine={{ stroke: colors.grid }}
              tickFormatter={formatXAxisTick}
              label={{
                value: xAxisLabel,
                position: 'insideBottom',
                offset: -5,
                style: { textAnchor: 'middle', fill: colors.axis, fontSize: 12, fontWeight: 600 },
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={yDomain}
              ticks={yAxisTicks}
              tick={{ fontSize: 12, fill: colors.axis }}
              tickLine={{ stroke: colors.grid }}
              axisLine={{ stroke: colors.grid }}
              tickFormatter={formatYAxisTick}
              label={{
                value: yAxisLabel,
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fill: colors.axis, fontSize: 12, fontWeight: 600 },
              }}
            />
            <ZAxis 
              type="number" 
              dataKey="z" 
              range={zAxisRange} 
              domain={transformedZDomain}
              scale="auto"
            />
            <ReferenceLine 
              x={xMidpoint} 
              stroke={colors.axis} 
              strokeWidth={1.5} 
              strokeOpacity={0.5}
              strokeDasharray="3 3"
            />
            <ReferenceLine 
              y={yMidpoint} 
              stroke={colors.axis} 
              strokeWidth={1.5} 
              strokeOpacity={0.5}
              strokeDasharray="3 3"
            />
            <Tooltip 
              wrapperStyle={{ 
                visibility: 'hidden', // Hide Recharts default positioning
                pointerEvents: 'none',
              }}
              animationDuration={0}
              isAnimationActive={false}
              content={(props) => {
                if (effectivePinned) return null;
                if (props.active && props.payload && props.payload.length > 0) {
                  const viewportPos = getHoverTooltipViewportPosition(undefined, undefined);
                  const payloadData = props.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
                  const treatmentName = payloadData?.treatmentName || '';
                  const currentIndex = trialIndices.get(treatmentName) || 0;
                  return (
                    <div style={{ 
                      position: 'fixed', 
                      left: `${viewportPos.x}px`, 
                      top: `${viewportPos.y}px`, 
                      zIndex: 9999, 
                      pointerEvents: 'none',
                      visibility: 'visible',
                      willChange: 'transform',
                      transition: 'none',
                      opacity: 1,
                    }}>
                      <CustomTooltip
                        active={props.active}
                        payload={props.payload as CustomTooltipProps['payload']}
                        isPinned={false}
                        currentTrialIndex={currentIndex}
                        onTrialIndexChange={handleTrialIndexChange}
                        efficacyParam={efficacyParam}
                        safetyParam={safetyParam}
                        axisMode={axisMode}
                      />
                    </div>
                  );
                }
                return null;
              }}
              cursor={false}
            />
            <Scatter 
              name="Treatments" 
              data={chartData} 
              fill="#8884d8"
              fillOpacity={0.7}
              isAnimationActive={false}
              onClick={(entry: { payload?: BubbleChartDataPoint }, _index: number, event: React.MouseEvent) => {
                const payload = entry.payload;
                if (payload) handleBubbleClick(payload, event);
              }}
            >
              {chartData.map((entry, index) => {
                const bubbleId = `${entry.treatmentName}-${entry.efficacy}-${entry.safety}`;
                const isPinnedBubble = effectivePinned && pinnedBubbleId === bubbleId;
                const fillColor = isPinnedBubble ? '#fbbf24' : getColor(entry);
                return (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={fillColor}
                    fillOpacity={0.7}
                    style={{ pointerEvents: 'painted' }}
                  />
                );
              })}
              <LabelList 
                dataKey="treatmentName" 
                content={<CustomLabel />}
              />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
        
        {/* Custom pinned tooltip */}
        {effectivePinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
          <div 
            className="fixed z-[9999] tooltip-enter"
            style={{ 
              left: tooltipData.x,
              top: tooltipData.y,
              pointerEvents: 'auto',
              animation: 'tooltipFadeIn 0.2s ease-out',
            }}
          >
            <CustomTooltip 
              active={tooltipData.active}
              payload={tooltipData.payload}
              isPinned={effectivePinned}
              currentTrialIndex={(() => {
                const payloadData = tooltipData.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
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

  if (fillHeight) {
    return (
      <div className="w-full h-full flex flex-col min-h-0 min-w-0 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        {title ? (
          <div className="flex-shrink-0 px-4 pt-3 pb-1">
            <h3 className="text-xl font-bold text-slate-900">{title}</h3>
            {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
          </div>
        ) : null}
        <div
          ref={chartContainerRef}
          className="flex-1 min-h-0 min-w-0 outline-none focus:outline-none"
          style={{ width: '100%', height: '100%', outline: 'none' }}
          tabIndex={-1}
          onMouseDown={(e) => {
            const target = e.target as HTMLElement;
            const isInteractive = target.closest('select, button, input, a[href], [role="button"]');
            if (!isInteractive) {
              e.preventDefault();
              (e.currentTarget as HTMLElement).blur();
            }
          }}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ScatterChart margin={fillHeight ? marginFillHeight : margin}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} strokeOpacity={0.3} />
              <XAxis
                type="number"
                dataKey="x"
                domain={xDomain}
                ticks={xAxisTicks}
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatXAxisTick}
                label={{
                  value: xAxisLabel,
                  position: 'insideBottom',
                  offset: -5,
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                domain={yDomain}
                ticks={yAxisTicks}
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatYAxisTick}
                label={{
                  value: yAxisLabel,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <ZAxis
                type="number"
                dataKey="z"
                range={zAxisRange}
                domain={transformedZDomain}
                scale="auto"
              />
              <ReferenceLine x={xMidpoint} stroke={colors.axis} strokeWidth={1.5} strokeOpacity={0.5} strokeDasharray="3 3" />
              <ReferenceLine y={yMidpoint} stroke={colors.axis} strokeWidth={1.5} strokeOpacity={0.5} strokeDasharray="3 3" />
              <Tooltip
                wrapperStyle={{ 
                  visibility: 'hidden', // Hide Recharts default positioning
                  pointerEvents: 'none',
                }}
                animationDuration={0}
                isAnimationActive={false}
                content={(props) => {
                  if (effectivePinned) return null;
                  if (props.active && props.payload && props.payload.length > 0) {
                    const viewportPos = getHoverTooltipViewportPosition(undefined, undefined);
                    const payloadData = props.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
                    const treatmentName = payloadData?.treatmentName || '';
                    const currentIndex = trialIndices.get(treatmentName) || 0;
                    return (
                      <div style={{ 
                        position: 'fixed', 
                        left: `${viewportPos.x}px`, 
                        top: `${viewportPos.y}px`, 
                        zIndex: 9999, 
                      pointerEvents: 'none',
                      visibility: 'visible',
                      willChange: 'transform',
                      transition: 'none',
                      opacity: 1,
                      }}>
                        <CustomTooltip
                          active={props.active}
                          payload={props.payload as CustomTooltipProps['payload']}
                          isPinned={false}
                          currentTrialIndex={currentIndex}
                          onTrialIndexChange={handleTrialIndexChange}
                          efficacyParam={efficacyParam}
                          safetyParam={safetyParam}
                          axisMode={axisMode}
                        />
                      </div>
                    );
                  }
                  return null;
                }}
                cursor={false}
              />
              <Scatter
                name="Treatments"
                data={chartData}
                fill="#8884d8"
                fillOpacity={0.7}
                isAnimationActive={false}
                onClick={(point: { payload?: BubbleChartDataPoint }, _index: number, e: React.MouseEvent) => {
                  const payload = point.payload;
                  if (payload) handleBubbleClick(payload, e);
                }}
              >
                {chartData.map((entry, index) => {
                  const bubbleId = `${entry.treatmentName}-${entry.efficacy}-${entry.safety}`;
                  const isPinnedBubble = effectivePinned && pinnedBubbleId === bubbleId;
                  const fillColor = isPinnedBubble ? '#fbbf24' : getColor(entry);
                  return (
                    <Cell key={`cell-${index}`} fill={fillColor} fillOpacity={0.7} style={{ pointerEvents: 'painted' }} />
                  );
                })}
                <LabelList dataKey="treatmentName" content={<CustomLabel />} />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        {effectivePinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
          <div
            className="fixed z-[9999] tooltip-enter"
            style={{
              left: tooltipData.x,
              top: tooltipData.y,
              pointerEvents: 'auto',
              animation: 'tooltipFadeIn 0.2s ease-out',
            }}
          >
            <CustomTooltip
              active={tooltipData.active}
              payload={tooltipData.payload}
              isPinned={effectivePinned}
              currentTrialIndex={(() => {
                const payloadData = tooltipData.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
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
    );
  }

  return (
    <Card 
      className="w-full overflow-hidden bg-white border-slate-200 outline-none focus:outline-none [&_svg]:outline-none [&_svg]:focus:outline-none [&_.recharts-wrapper]:outline-none [&_.recharts-wrapper]:focus:outline-none" 
      tabIndex={-1}
      onMouseDown={(e) => {
        const target = e.target as HTMLElement;
        const isInteractive = target.closest('select, button, input, a[href], [role="button"]');
        if (!isInteractive) {
          e.preventDefault();
          (e.currentTarget as HTMLElement).blur();
        }
      }}
      style={{ outline: 'none' }}
    >
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-xl font-bold text-slate-900">{title}</CardTitle>
          {description && (
            <CardDescription className="mt-1 text-slate-600">{description}</CardDescription>
          )}
        </CardHeader>
      )}

      <CardContent 
        className={title ? "pt-4 outline-none focus:outline-none" : "p-0 outline-none focus:outline-none"} 
        tabIndex={-1}
        onMouseDown={(e) => {
          const target = e.target as HTMLElement;
          const isInteractive = target.closest('select, button, input, a[href], [role="button"]');
          if (!isInteractive) {
            e.preventDefault();
            (e.currentTarget as HTMLElement).blur();
          }
        }}
        style={{ outline: 'none' }}
      >

        <div 
          ref={chartContainerRef}
          style={{ width: '100%', height: chartHeight, minHeight: 100, outline: 'none' }} 
          className="outline-none focus:outline-none"
          tabIndex={-1}
          onMouseDown={(e) => {
            const target = e.target as HTMLElement;
            const isInteractive = target.closest('select, button, input, a[href], [role="button"]');
            if (!isInteractive) {
              e.preventDefault();
              (e.currentTarget as HTMLElement).blur();
            }
          }}
        >
          <ResponsiveContainer width={containerDims.width} height={containerDims.height}>
            <ScatterChart margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} strokeOpacity={0.3} />
              <XAxis
                type="number"
                dataKey="x"
                domain={xDomain}
                ticks={xAxisTicks}
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatXAxisTick}
                label={{
                  value: xAxisLabel,
                  position: 'insideBottom',
                  offset: -5,
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                domain={yDomain}
                ticks={yAxisTicks}
                tick={{ fontSize: 12, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatYAxisTick}
                label={{
                  value: yAxisLabel,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 13, fontWeight: 600 },
                }}
              />
              <ZAxis 
                type="number" 
                dataKey="z" 
                range={zAxisRange} 
                domain={transformedZDomain}
                scale="auto"
              />
              <ReferenceLine 
                x={xMidpoint} 
                stroke={colors.axis} 
                strokeWidth={1.5} 
                strokeOpacity={0.5}
                strokeDasharray="3 3"
              />
              <ReferenceLine 
                y={yMidpoint} 
                stroke={colors.axis} 
                strokeWidth={1.5} 
                strokeOpacity={0.5}
                strokeDasharray="3 3"
              />
              <Tooltip 
                wrapperStyle={{ 
                  visibility: 'hidden', // Hide Recharts default positioning
                  pointerEvents: 'none',
                }}
                animationDuration={0}
                isAnimationActive={false}
                content={(props) => {
                  if (effectivePinned) return null;
                  if (props.active && props.payload && props.payload.length > 0) {
                    const viewportPos = getHoverTooltipViewportPosition(undefined, undefined);
                    const payloadData = props.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
                    const treatmentName = payloadData?.treatmentName || '';
                    const currentIndex = trialIndices.get(treatmentName) || 0;
                    return (
                      <div style={{ 
                        position: 'fixed', 
                        left: `${viewportPos.x}px`, 
                        top: `${viewportPos.y}px`, 
                        zIndex: 9999, 
                      pointerEvents: 'none',
                      visibility: 'visible',
                      willChange: 'transform',
                      transition: 'none',
                      opacity: 1,
                      }}>
                        <CustomTooltip
                          active={props.active}
                          payload={props.payload as CustomTooltipProps['payload']}
                          isPinned={false}
                          currentTrialIndex={currentIndex}
                          onTrialIndexChange={handleTrialIndexChange}
                          efficacyParam={efficacyParam}
                          safetyParam={safetyParam}
                          axisMode={axisMode}
                        />
                      </div>
                    );
                  }
                  return null;
                }}
                cursor={false}
              />
              <Scatter
                name="Treatments" 
                data={chartData} 
                fill="#8884d8"
                fillOpacity={0.7}
                isAnimationActive={false}
                onClick={(point: { payload?: BubbleChartDataPoint }, _index: number, e: React.MouseEvent) => {
                  const payload = point.payload;
                  if (payload) handleBubbleClick(payload, e);
                }}
              >
                {chartData.map((entry, index) => {
                  const bubbleId = `${entry.treatmentName}-${entry.efficacy}-${entry.safety}`;
                  const isPinnedBubble = effectivePinned && pinnedBubbleId === bubbleId;
                  const fillColor = isPinnedBubble ? '#fbbf24' : getColor(entry);
                  return (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={fillColor}
                      fillOpacity={0.7}
                      style={{ pointerEvents: 'painted' }}
                    />
                  );
                })}
                <LabelList 
                  dataKey="treatmentName" 
                  content={<CustomLabel />}
                />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          
          {/* Custom pinned tooltip */}
          {effectivePinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
            <div 
              className="fixed z-[9999] tooltip-enter"
              style={{ 
                left: tooltipData.x,
                top: tooltipData.y,
                pointerEvents: 'auto',
                animation: 'tooltipFadeIn 0.2s ease-out',
              }}
            >
              <CustomTooltip 
                active={tooltipData.active}
                payload={tooltipData.payload}
                isPinned={effectivePinned}
                currentTrialIndex={(() => {
                  const payloadData = tooltipData.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
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
