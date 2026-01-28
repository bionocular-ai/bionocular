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
  Legend,
  Cell,
  ReferenceLine,
  LabelList,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { BubbleChartDataPoint } from '@/types/analytics';

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
  // Current metric parameters for tooltip display
  efficacyParam?: string;
  safetyParam?: string;
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

const DARK_COLORS = {
  approved: '#34d399', // Lighter green
  investigational: '#a78bfa', // Lighter purple
  developmentStopped: '#f87171', // Lighter red
  unknown: '#94a3b8', // Lighter gray
  grid: '#334155',
  axis: '#94a3b8',
};

// ============================================================================
// Custom Label Component
// ============================================================================

interface CustomLabelProps {
  x?: number;
  y?: number;
  payload?: BubbleChartDataPoint & { x?: number; y?: number; z?: number; rawZ?: number };
  value?: string;
}

// CustomLabel component needs access to scaling function
// We'll pass it as a prop or use a context, but for now we'll calculate it inline
// Note: This is a simplified version - the actual scaling will be done by Recharts ZAxis
const CustomLabel = ({ x, y, payload, value }: CustomLabelProps) => {
  // Use value if provided, otherwise fall back to payload.treatmentName
  const labelText = value || payload?.treatmentName;
  
  if (!x || !y || !labelText) return null;
  
  // Calculate bubble radius based on z value (bubble size) if available
  // The z value is added during chartData transformation, so we need to access it from the extended payload
  // Recharts scales the bubble size automatically based on ZAxis range
  const extendedPayload = payload as (BubbleChartDataPoint & { z?: number; rawZ?: number }) | undefined;
  // Use rawZ if available (original value before log scaling), otherwise use z (transformed value)
  const rawZValue = extendedPayload?.rawZ ?? extendedPayload?.z;
  const transformedZ = extendedPayload?.z;
  
  // Estimate bubble radius based on the transformed z value
  // Recharts maps z values to bubble sizes in the range [20, 120] pixels (radius)
  // The relationship is approximately linear in the transformed space
  // For log-scaled values, the visual size will be proportional to the transformed value
  // We estimate: radius ≈ 20 + (z - zMin) / (zMax - zMin) * (120 - 20)
  // Since we don't have zMin/zMax here, we use a reasonable approximation
  let bubbleRadius = 10; // default
  if (transformedZ !== undefined && transformedZ > 0) {
    // Rough estimate: assume transformed z is in range [0, ~10] for log scale or [0, max] for linear
    // This is approximate but should work reasonably well for label positioning
    const estimatedRadius = Math.max(10, Math.min(60, transformedZ * 6 + 10));
    bubbleRadius = estimatedRadius;
  } else if (rawZValue !== undefined && rawZValue > 0) {
    // Fallback: estimate from raw value (less accurate but better than nothing)
    bubbleRadius = Math.max(10, Math.min(60, Math.sqrt(rawZValue) * 0.8));
  }
  
  // Position label below bubble by default, with spacing
  // Offset based on bubble radius plus some padding
  const verticalOffset = bubbleRadius + 12;
  const horizontalOffset = bubbleRadius + 8;
  
  // Determine label position - prefer below, but can be to the right if needed
  // For now, we'll position below the bubble
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
}

const CustomTooltip = ({ 
  active, 
  payload, 
  isPinned, 
  currentTrialIndex = 0,
  onTrialIndexChange,
  efficacyParam,
  safetyParam,
}: CustomTooltipProps) => {
  if ((!active && !isPinned) || !payload || !payload.length) return null;

  const data = payload[0].payload as BubbleChartDataPoint;
  const allTrials = data.allTrials || [];
  const hasMultipleTrials = allTrials.length > 1;
  const currentTrial = allTrials[currentTrialIndex] || {
    efficacy: data.efficacy,
    safety: data.safety,
    numberOfPatients: data.numberOfPatients,
    year: data.year,
    nctNumber: data.nctNumber,
    abstractId: data.abstractId,
    publicationName: data.publicationName,
    citation: data.citation,
    phase: data.phase,
  };

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
  const safetyLabel = safetyParam ? safetyParam.replace(/_/g, ' ') : 'Safety (Grade 3+ TRAE)';
  const isWebScrape = data.abstractId?.startsWith('webscrape_');
  const hasSourceUrl = !!data.sourceUrl;

  return (
    <div 
      className="bg-slate-800 p-4 rounded-xl shadow-2xl border border-slate-700 min-w-[320px] max-w-[420px] tooltip-enter"
      style={{
        animation: isPinned ? 'tooltipFadeIn 0.2s ease-out' : 'tooltipFadeIn 0.15s ease-out',
      }}
    >
      {isPinned && (
        <div 
          className="mb-2 pb-2 border-b border-slate-600 flex items-center justify-between"
          style={{ animation: 'tooltipContentFadeIn 0.2s ease-out' }}
        >
          <span className="text-[10px] uppercase tracking-wider text-amber-400 font-medium flex items-center gap-1">
            <span className="text-amber-400" style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>📌</span> Pinned
          </span>
          <span className="text-[10px] text-slate-500">Click bubble to unpin</span>
        </div>
      )}
      <div className="mb-3 pb-3 border-b border-slate-700">
        <h4 className="font-bold text-white text-sm mb-1">{data.treatmentName}</h4>
        {data.treatmentType && (
          <p className="text-xs text-slate-400">{data.treatmentType}</p>
        )}
      </div>

      {data.developmentStatus && (
        <div className="mb-3">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
              data.developmentStatus === 'Approved'
                ? 'bg-emerald-900/50 text-emerald-300'
                : data.developmentStatus === 'Development stopped'
                ? 'bg-red-900/50 text-red-300'
                : 'bg-violet-900/50 text-violet-300'
            }`}
          >
            {data.developmentStatus === 'Approved' && '★ '}
            {data.developmentStatus === 'Development stopped' && 'Ø '}
            {data.developmentStatus}
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{efficacyLabel}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevTrial}
              disabled={!hasMultipleTrials || currentTrialIndex === 0}
              className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
              style={{ pointerEvents: 'auto' }}
              title={hasMultipleTrials ? 'Previous trial' : 'Only one trial available'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <p className="text-lg font-bold text-white tabular-nums flex-1 text-center">{currentTrial.efficacy.toFixed(1)}%</p>
            <button
              onClick={handleNextTrial}
              disabled={!hasMultipleTrials || currentTrialIndex === allTrials.length - 1}
              className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
              style={{ pointerEvents: 'auto' }}
              title={hasMultipleTrials ? 'Next trial' : 'Only one trial available'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{safetyLabel}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevTrial}
              disabled={!hasMultipleTrials || currentTrialIndex === 0}
              className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
              style={{ pointerEvents: 'auto' }}
              title={hasMultipleTrials ? 'Previous trial' : 'Only one trial available'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <p className="text-lg font-bold text-white tabular-nums flex-1 text-center">{currentTrial.safety.toFixed(1)}%</p>
            <button
              onClick={handleNextTrial}
              disabled={!hasMultipleTrials || currentTrialIndex === allTrials.length - 1}
              className="text-slate-400 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors p-1 rounded hover:bg-slate-700"
              style={{ pointerEvents: 'auto' }}
              title={hasMultipleTrials ? 'Next trial' : 'Only one trial available'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      {hasMultipleTrials && (
        <div className="mb-3 text-center">
          <span className="text-[10px] text-slate-500">
            Trial {currentTrialIndex + 1} of {allTrials.length}
          </span>
        </div>
      )}

      <div className="pt-3 border-t border-slate-700 space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Patients</span>
          <span className="text-slate-200 font-medium">n={currentTrial.numberOfPatients}</span>
        </div>
        {currentTrial.phase && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Phase</span>
            <span className="text-slate-200 font-medium">{currentTrial.phase}</span>
          </div>
        )}
        {currentTrial.nctNumber && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">NCT</span>
            <Link
              href={`/trial/nct/${currentTrial.nctNumber}`}
              className="text-sky-400 font-mono hover:text-sky-300 hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              <span>{currentTrial.nctNumber}</span>
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        )}
        {(currentTrial.abstractId || currentTrial.publicationName) && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">
              {currentTrial.publicationName ? 'Publication' : 'Abstract ID'}
            </span>
            {(() => {
              const sourceValue = currentTrial.publicationName || currentTrial.abstractId;
              const isWebScrape = currentTrial.abstractId?.startsWith('webscrape_');
              const hasSourceUrl = !!data.sourceUrl;
              if (isWebScrape && hasSourceUrl) {
                return (
                  <a
                    href={data.sourceUrl}
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
                    <span className="text-xs">{sourceValue}</span>
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                );
              }
              return <span className="text-slate-200 text-xs">{sourceValue}</span>;
            })()}
          </div>
        )}
        {data.biomarker && (
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Biomarker</span>
            <span className="text-slate-200 font-medium">{data.biomarker}</span>
          </div>
        )}
        {data.notes && (
          <div className="pt-2 border-t border-slate-700">
            <p className="text-[10px] text-slate-500 italic">{data.notes}</p>
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
}: BubbleChartProps) {
  const chartHeight = Math.max(height || 600, 100);
  const [isPinned, setIsPinned] = useState(false);
  const [pinnedBubbleId, setPinnedBubbleId] = useState<string | null>(null);
  // Track current trial index per treatment for tooltip switching
  const [trialIndices, setTrialIndices] = useState<Map<string, number>>(new Map());

  const handleTrialIndexChange = useCallback((treatmentName: string, newIndex: number) => {
    setTrialIndices(prev => {
      const next = new Map(prev);
      next.set(treatmentName, newIndex);
      return next;
    });
  }, []);
  
  // Normalize axisConfig to valid range (0-5)
  const normalizedAxisConfig = Math.max(0, Math.min(5, Math.floor(axisConfig || 0)));
  
  // Unpin tooltip when axis configuration changes
  useEffect(() => {
    if (isPinned) {
      setIsPinned(false);
      setTooltipData(null);
      setPinnedBubbleId(null);
    }
  }, [normalizedAxisConfig]); // eslint-disable-line react-hooks/exhaustive-deps
  const [tooltipData, setTooltipData] = useState<{
    active: boolean;
    payload?: Array<{
      payload: BubbleChartDataPoint;
      value: number;
    }>;
    x?: number;
    y?: number;
  } | null>(null);
  const hoverTooltipPositionRef = useRef<{ x: number; y: number } | null>(null);

  // Track tooltip position from DOM when hovering
  useEffect(() => {
    if (isPinned) {
      hoverTooltipPositionRef.current = null;
      return;
    }
    
    const updateTooltipPosition = () => {
      const tooltipWrapper = document.querySelector('.recharts-tooltip-wrapper') as HTMLElement;
      if (tooltipWrapper && tooltipWrapper.style.display !== 'none' && tooltipWrapper.style.visibility !== 'hidden') {
        const rect = tooltipWrapper.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          hoverTooltipPositionRef.current = { x: rect.left, y: rect.top };
        }
      }
    };

    // Check tooltip position periodically when not pinned
    const intervalId = setInterval(updateTooltipPosition, 50);

    return () => {
      clearInterval(intervalId);
    };
  }, [isPinned]);

  // Calculate tooltip position
  const calculateTooltipPosition = useCallback((clientX: number, clientY: number) => {
    const TOOLTIP_WIDTH = 420;
    const TOOLTIP_HEIGHT = 400;
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

  // Helper function to get Z-axis value based on zAxisParam
  const getZAxisValue = useCallback((item: BubbleChartDataPoint): number => {
    if (zAxisParam === 'NUMBER_OF_PATIENTS') {
      return item.numberOfPatients || 0;
    }
    // Additional Z-axis parameters can be added here in the future
    // Example:
    // else if (zAxisParam === 'SOME_OTHER_PARAM') {
    //   return item.someOtherParam || 0;
    // }
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

  // Calculate bubble size range (Z-axis) - ensure it starts from 0 for proper scaling
  // Bubble size depends on which metric is on the Z-axis based on axis configuration
  const zDomain = useMemo(() => {
    const { zMetric } = getAxisMetrics();
    
    // Get values for the metric that's on the Z-axis (bubble size)
    let zAxisValues: number[] = [];
    
    if (zMetric === 'zParam') {
      // Z-axis is Z-parameter (e.g., number of patients)
      zAxisValues = data.map((item) => getZAxisValue(item)).filter((z): z is number => z !== null && z !== undefined && z > 0 && isFinite(z));
      if (zAxisValues.length === 0) return [0, 1000];
      const min = Math.min(...zAxisValues);
      const max = Math.max(...zAxisValues);
      // Add padding: 5% below min (but not below 0) and 10% above max
      const paddingMin = Math.max(0, min * 0.95);
      const paddingMax = max * 1.1;
      return [paddingMin, Math.ceil(paddingMax)];
    } else if (zMetric === 'efficacy') {
      // Z-axis is Efficacy
      zAxisValues = data.map((item) => item.efficacy ?? 0).filter((z): z is number => z !== null && z !== undefined && !isNaN(z) && isFinite(z) && z >= 0);
      if (zAxisValues.length === 0) return [0, 60];
      const min = Math.min(...zAxisValues);
      const max = Math.max(...zAxisValues);
      const paddingMin = Math.max(0, min * 0.95);
      const paddingMax = max * 1.1;
      return [paddingMin, Math.ceil(paddingMax)];
    } else if (zMetric === 'safety') {
      // Z-axis is Safety
      zAxisValues = data.map((item) => {
        const safety = item.safety ?? 0;
        return invertSafetyAxis ? 100 - safety : safety;
      }).filter((z): z is number => z !== null && z !== undefined && !isNaN(z) && isFinite(z) && z >= 0);
      if (zAxisValues.length === 0) return [0, 100];
      const min = Math.min(...zAxisValues);
      const max = Math.max(...zAxisValues);
      const paddingMin = Math.max(0, min * 0.95);
      const paddingMax = max * 1.1;
      return [paddingMin, Math.ceil(paddingMax)];
    }
    
    // Fallback
    return [0, 1000];
  }, [data, getAxisMetrics, getZAxisValue, invertSafetyAxis]);

  // Determine if we should use logarithmic scaling based on data range
  const useLogScale = useMemo(() => {
    const [min, max] = zDomain;
    const range = max - min;
    
    // Use logarithmic scaling if:
    // 1. Range is significant (more than 10% of max)
    // 2. Max is at least 2x min (or min is 0 and max > 0)
    // 3. Range spans at least 2 orders of magnitude (max/min > 10) or max > 100
    if (range <= 0 || min === max) return false;
    if (min === 0 && max > 0) return max > 10; // Handle zero minimum
    return (max / min > 2) && (range > max * 0.1 || max / min > 10 || max > 100);
  }, [zDomain]);

  // Calculate dynamic bubble size range based on zDomain values
  // Bubble sizes should scale proportionally with the actual data values
  // The range represents pixel radius, and Recharts maps z values (from domain) to this range
  const bubbleSizeRange = useMemo(() => {
    const [min, max] = zDomain;
    const range = max - min;
    
    // Base sizes - minimum and maximum bubble radii in pixels
    // These will be mapped proportionally to the z values in the domain
    const BASE_MIN_SIZE = 60;  // Minimum radius for smallest value
    const BASE_MAX_SIZE = 280; // Maximum radius for largest value
    
    // Scale the range based on the data spread
    // For wider ranges, use a larger pixel range to make differences more visible
    if (range <= 0 || min === max) {
      return {
        min: BASE_MIN_SIZE,
        max: BASE_MAX_SIZE,
      };
    }
    
    // Calculate scale factor based on data range
    // For patient counts: if range is large (e.g., 10-1000), use larger sizes
    // For percentages: if range is smaller (e.g., 20-80), use moderate sizes
    let scaleFactor = 1;
    if (max > 100) {
      // Large numbers (like patient counts) - use larger scale
      scaleFactor = Math.min(1.8, 1 + (range / max) * 0.8);
    } else {
      // Smaller numbers (like percentages) - use standard scale
      scaleFactor = 1.2;
    }
    
    return {
      min: BASE_MIN_SIZE,
      max: Math.round(BASE_MAX_SIZE * scaleFactor),
    };
  }, [zDomain]);

  // Helper function to transform z value for logarithmic scaling
  // Adds 1 to handle zero values (log(0) is undefined)
  const transformZValue = useCallback((zValue: number): number => {
    if (useLogScale) {
      // For logarithmic scaling, transform: log(z + 1)
      // This handles zero values and provides smooth scaling
      return Math.log(zValue + 1);
    }
    // For linear scaling, return as-is
    return zValue;
  }, [useLogScale]);

  // Calculate transformed zDomain for bubble sizing
  const transformedZDomain = useMemo(() => {
    const [min, max] = zDomain;
    if (useLogScale) {
      // Transform domain to log scale
      return [transformZValue(min), transformZValue(max)];
    }
    return [min, max];
  }, [zDomain, useLogScale, transformZValue]);

  // Transform data for scatter chart based on axis configuration
  // Transform data to use current trial values based on trialIndices
  // Safety axis is inverted: 0% (best) on right, 100% (worst) on left
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    
    return data.map((item) => {
      // Get the current trial index for this treatment (default to 0)
      const currentIndex = trialIndices.get(item.treatmentName) ?? 0;
      const allTrials = item.allTrials || [];
      
      // Use values from the current trial if available, otherwise use the original item values
      const currentTrial = allTrials[currentIndex];
      const efficacy = currentTrial?.efficacy ?? item.efficacy ?? 0;
      const safety = currentTrial?.safety ?? item.safety ?? 0;
      const numberOfPatients = currentTrial?.numberOfPatients ?? item.numberOfPatients ?? 0;
      
      // Create a modified item with current trial values for z-axis calculation
      const itemWithCurrentTrial = {
        ...item,
        efficacy,
        safety,
        numberOfPatients,
      };
      const safetyValue = invertSafetyAxis ? 100 - safety : safety;
      const zValue = getZAxisValue(itemWithCurrentTrial);
      
      // Map metrics to x, y, z based on axisConfig
      // Note: In Recharts, Z-axis is always bubble size
      // When zParam is on X or Y, we use a different metric for bubble size (z)
      // 0: X=Safety, Y=Efficacy, Z(bubble size)=ZParam
      // 1: X=Efficacy, Y=Safety, Z(bubble size)=ZParam
      // 2: X=Safety, Y=ZParam, Z(bubble size)=Efficacy (ZParam on Y, use Efficacy for size)
      // 3: X=ZParam, Y=Safety, Z(bubble size)=Efficacy (ZParam on X, use Efficacy for size)
      // 4: X=Efficacy, Y=ZParam, Z(bubble size)=Safety (ZParam on Y, use Safety for size)
      // 5: X=ZParam, Y=Efficacy, Z(bubble size)=Safety (ZParam on X, use Safety for size)
      
      let x: number, y: number;
      
      // Determine raw z value for bubble size
      let rawZValue: number;
      switch (normalizedAxisConfig) {
        case 0: // X=Safety, Y=Efficacy, Z(bubble size)=ZParam
          x = safetyValue;
          y = efficacy;
          rawZValue = Math.max(0, zValue);
          break;
        case 1: // X=Efficacy, Y=Safety, Z(bubble size)=ZParam
          x = efficacy;
          y = safetyValue;
          rawZValue = Math.max(0, zValue);
          break;
        case 2: // X=Safety, Y=ZParam, Z(bubble size)=Efficacy
          x = safetyValue;
          y = Math.max(0, zValue);
          rawZValue = efficacy; // Use efficacy for bubble size
          break;
        case 3: // X=ZParam, Y=Safety, Z(bubble size)=Efficacy
          x = Math.max(0, zValue);
          y = safetyValue;
          rawZValue = efficacy; // Use efficacy for bubble size
          break;
        case 4: // X=Efficacy, Y=ZParam, Z(bubble size)=Safety
          x = efficacy;
          y = Math.max(0, zValue);
          rawZValue = safetyValue; // Use safety for bubble size
          break;
        case 5: // X=ZParam, Y=Efficacy, Z(bubble size)=Safety
          x = Math.max(0, zValue);
          y = efficacy;
          rawZValue = safetyValue; // Use safety for bubble size
          break;
        default:
          // Fallback to default configuration
          x = safetyValue;
          y = efficacy;
          rawZValue = Math.max(0, zValue);
      }
      
      // Apply logarithmic scaling to z value if needed
      // Store both raw and transformed values for tooltip/label display
      const z = useLogScale ? transformZValue(rawZValue) : rawZValue;
      
      return {
        ...item,
        efficacy, // Update with current trial values
        safety,
        numberOfPatients,
        x,
        y,
        z,
        rawZ: rawZValue, // Store original z value for display in tooltips/labels
      };
    });
  }, [data, trialIndices, invertSafetyAxis, normalizedAxisConfig, getZAxisValue, useLogScale, transformZValue]);

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
    let rawMin = Math.max(0, min - padding);
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
  const getZAxisMetric = useCallback(() => {
    const { zMetric } = getAxisMetrics();
    return zMetric;
  }, [getAxisMetrics]);

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
  const margin = compact
    ? { top: 20, right: 30, bottom: 60, left: 60 }
    : { top: 20, right: 30, bottom: 80, left: 80 };

  // Get readable label for Z-axis parameter - defined early so it can be used in other callbacks
  const getZAxisLabel = useCallback((param: string): string => {
    const labelMap: Record<string, string> = {
      'NUMBER_OF_PATIENTS': 'Number of patients',
      // Additional mappings can be added here
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
      hoverTooltipPositionRef.current = null;
      return;
    }
    
    // Pin to this bubble - use hover position if available, otherwise calculate from click event
    // First try to get the current hover tooltip position from the DOM
    const tooltipWrapper = document.querySelector('.recharts-tooltip-wrapper') as HTMLElement;
    let position: { x: number; y: number };
    
    if (tooltipWrapper && tooltipWrapper.style.display !== 'none' && tooltipWrapper.style.visibility !== 'hidden') {
      const rect = tooltipWrapper.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        position = { x: rect.left, y: rect.top };
      } else {
        position = hoverTooltipPositionRef.current || (event ? calculateTooltipPosition(event.clientX, event.clientY) : { x: 0, y: 0 });
      }
    } else {
      position = hoverTooltipPositionRef.current || (event ? calculateTooltipPosition(event.clientX, event.clientY) : { x: 0, y: 0 });
    }
    
    setPinnedBubbleId(bubbleId);
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
  }, [isPinned, pinnedBubbleId, calculateTooltipPosition, tooltipData]);

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

  // Axis labels - based on axis configuration
  const getAxisLabel = useCallback((metric: 'efficacy' | 'safety' | 'zParam'): string => {
    if (metric === 'efficacy') {
      return efficacyLabel;
    }
    if (metric === 'safety') {
      return invertSafetyAxis
        ? `${safetyLabel} (0% = best safety, 100% = worst safety)`
        : safetyLabel;
    }
    if (metric === 'zParam') {
      return getZAxisLabel(zAxisParam);
    }
    return '';
  }, [efficacyLabel, safetyLabel, invertSafetyAxis, zAxisParam, getZAxisLabel]);

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
          e.preventDefault();
          (e.currentTarget as HTMLElement).blur();
        }}
        style={{ outline: 'none' }}
      >
        <div className="flex-1 min-h-0 relative">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={margin}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis
              type="number"
              dataKey="x"
              domain={xDomain}
              ticks={xAxisTicks}
              tick={{ fontSize: 10, fill: colors.axis }}
              tickLine={{ stroke: colors.grid }}
              axisLine={{ stroke: colors.grid }}
              tickFormatter={formatXAxisTick}
              label={{
                value: xAxisLabel,
                position: 'insideBottom',
                offset: -5,
                style: { textAnchor: 'middle', fill: colors.axis, fontSize: 10 },
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={yDomain}
              ticks={yAxisTicks}
              tick={{ fontSize: 10, fill: colors.axis }}
              tickLine={{ stroke: colors.grid }}
              axisLine={{ stroke: colors.grid }}
              tickFormatter={formatYAxisTick}
              label={{
                value: yAxisLabel,
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fill: colors.axis, fontSize: 10 },
              }}
            />
            <ZAxis 
              type="number" 
              dataKey="z" 
              range={[bubbleSizeRange.min, bubbleSizeRange.max]} 
              domain={transformedZDomain}
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
              content={(props) => {
                if (isPinned) return null; // Don't show Recharts tooltip when pinned
                if (props.active && props.payload && props.payload.length > 0) {
                  const payloadData = props.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
                  const treatmentName = payloadData?.treatmentName || '';
                  const currentIndex = trialIndices.get(treatmentName) || 0;
                  return <CustomTooltip 
                    active={props.active}
                    payload={props.payload as CustomTooltipProps['payload']}
                    isPinned={false}
                    currentTrialIndex={currentIndex}
                    onTrialIndexChange={handleTrialIndexChange}
                    efficacyParam={efficacyParam}
                    safetyParam={safetyParam}
                  />;
                }
                return null;
              }}
              cursor={{ strokeDasharray: '3 3' }} 
            />
            <Scatter 
              name="Treatments" 
              data={chartData} 
              fill="#8884d8"
              onClick={(data: any, index: number, e: any) => {
                const payload = data.payload as BubbleChartDataPoint;
                const event = e as React.MouseEvent;
                handleBubbleClick(payload, event);
              }}
            >
              {chartData.map((entry, index) => {
                const bubbleId = `${entry.treatmentName}-${entry.efficacy}-${entry.safety}`;
                const isPinnedBubble = isPinned && pinnedBubbleId === bubbleId;
                return (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={isPinnedBubble ? '#fbbf24' : getColor(entry)} 
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
        {isPinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
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
              isPinned={isPinned}
              currentTrialIndex={(() => {
                const payloadData = tooltipData.payload?.[0]?.payload as BubbleChartDataPoint | undefined;
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
      </div>
    );
  }

  return (
    <Card 
      className="w-full overflow-hidden bg-white border-slate-200 outline-none focus:outline-none [&_svg]:outline-none [&_svg]:focus:outline-none [&_.recharts-wrapper]:outline-none [&_.recharts-wrapper]:focus:outline-none" 
      tabIndex={-1}
      onMouseDown={(e) => {
        e.preventDefault();
        (e.currentTarget as HTMLElement).blur();
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
          e.preventDefault();
          (e.currentTarget as HTMLElement).blur();
        }}
        style={{ outline: 'none' }}
      >

        <div 
          style={{ width: '100%', height: chartHeight, minHeight: 100, outline: 'none' }} 
          className="outline-none focus:outline-none"
          tabIndex={-1}
          onMouseDown={(e) => {
            e.preventDefault();
            (e.currentTarget as HTMLElement).blur();
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} strokeOpacity={0.3} />
              <XAxis
                type="number"
                dataKey="x"
                domain={xDomain}
                ticks={xAxisTicks}
                tick={{ fontSize: 11, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatXAxisTick}
                label={{
                  value: xAxisLabel,
                  position: 'insideBottom',
                  offset: -5,
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 11 },
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                domain={yDomain}
                ticks={yAxisTicks}
                tick={{ fontSize: 11, fill: colors.axis }}
                tickLine={{ stroke: colors.grid }}
                axisLine={{ stroke: colors.grid }}
                tickFormatter={formatYAxisTick}
                label={{
                  value: yAxisLabel,
                  angle: -90,
                  position: 'insideLeft',
                  style: { textAnchor: 'middle', fill: colors.axis, fontSize: 12 },
                }}
              />
              <ZAxis 
              type="number" 
              dataKey="z" 
              range={[bubbleSizeRange.min, bubbleSizeRange.max]} 
              domain={transformedZDomain}
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
                content={(props) => {
                  if (isPinned) return null; // Don't show Recharts tooltip when pinned
                  if (props.active && props.payload && props.payload.length > 0) {
                    return <CustomTooltip 
                      active={props.active}
                      payload={props.payload as CustomTooltipProps['payload']}
                      isPinned={false} 
                    />;
                  }
                  return null;
                }}
                cursor={{ strokeDasharray: '3 3' }} 
              />
              <Scatter 
                name="Treatments" 
                data={chartData} 
                fill="#8884d8"
                onClick={(data: any, index: number, e: any) => {
                  const payload = data.payload as BubbleChartDataPoint;
                  const event = e as React.MouseEvent;
                  handleBubbleClick(payload, event);
                }}
              >
                {chartData.map((entry, index) => {
                  const bubbleId = `${entry.treatmentName}-${entry.efficacy}-${entry.safety}`;
                  const isPinnedBubble = isPinned && pinnedBubbleId === bubbleId;
                  return (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={isPinnedBubble ? '#fbbf24' : getColor(entry)} 
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
          {isPinned && tooltipData && tooltipData.x !== undefined && tooltipData.y !== undefined && (
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
                isPinned={isPinned}
              />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
