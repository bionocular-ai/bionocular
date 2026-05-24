'use client';

import * as React from 'react';
import type { DashboardTrialCard } from '@/lib/api';
import type { GroupByOption } from '@/types/bullseye';
import { useBullseyeData, type DrugDot } from '@/hooks/useBullseyeData';
import { BullseyeChart } from '@/components/dashboard/BullseyeChart';
import { BullseyeTooltip } from '@/components/dashboard/BullseyeTooltip';
import { DrugTrialsDrawer } from '@/components/dashboard/DrugTrialsDrawer';

// 12-color categorical palette
const COLORS = [
  '#0d9488', '#7c3aed', '#ea580c', '#0284c7', '#16a34a',
  '#db2777', '#ca8a04', '#6d28d9', '#dc2626', '#0891b2',
  '#65a30d', '#9333ea',
];

interface BullseyeViewProps {
  trials: DashboardTrialCard[];
  groupBy: GroupByOption;
  cancerTypeSlug: string;
}

export function BullseyeView({ trials, groupBy, cancerTypeSlug }: BullseyeViewProps) {
  const { drugs, sponsors, legendValues, phaseRings } = useBullseyeData(trials, groupBy);

  const colorMap = React.useMemo(() => {
    const map = new Map<string, string>();
    legendValues.forEach((v, i) => map.set(v, COLORS[i % COLORS.length]!));
    return map;
  }, [legendValues]);

  const colorOf = React.useCallback((v: string) => colorMap.get(v) ?? '#94a3b8', [colorMap]);

  const [tooltip, setTooltip] = React.useState<{ drug: DrugDot; x: number; y: number } | null>(null);
  const [selectedDrug, setSelectedDrug] = React.useState<DrugDot | null>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const handleHover = React.useCallback((drug: DrugDot | null, absX: number, absY: number) => {
    if (!drug || !containerRef.current) { setTooltip(null); return; }
    const rect = containerRef.current.getBoundingClientRect();
    setTooltip({ drug, x: absX - rect.left, y: absY - rect.top });
  }, []);

  if (drugs.length === 0) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400 text-sm">
        No drugs match the current filters.
      </div>
    );
  }

  return (
    <div className="pb-4">
      {/* Chart — fills available width; sponsor labels are rendered inside the SVG */}
      <div ref={containerRef} className="relative w-full" style={{ minHeight: 520 }}>
        <BullseyeChart
          drugs={drugs}
          sponsors={sponsors}
          phaseRings={phaseRings}
          colorOf={colorOf}
          onHoverDrug={handleHover}
          onClickDrug={setSelectedDrug}
        />
        {tooltip && (
          <BullseyeTooltip drug={tooltip.drug} x={tooltip.x} y={tooltip.y} />
        )}
      </div>

      {/* Legend */}
      {legendValues.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 pt-3 justify-center">
          {legendValues.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100"
            >
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: colorOf(v) }}
              />
              {v}
            </span>
          ))}
        </div>
      )}

      {/* Drawer */}
      <DrugTrialsDrawer
        drug={selectedDrug}
        cancerTypeSlug={cancerTypeSlug}
        onClose={() => setSelectedDrug(null)}
      />
    </div>
  );
}
