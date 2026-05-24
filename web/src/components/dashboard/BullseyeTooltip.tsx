'use client';

import * as React from 'react';
import type { DrugDot } from '@/hooks/useBullseyeData';

interface BullseyeTooltipProps {
  drug: DrugDot;
  x: number;
  y: number;
}

export function BullseyeTooltip({ drug, x, y }: BullseyeTooltipProps) {
  return (
    <div
      className="pointer-events-none absolute z-50 rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-lg text-sm"
      style={{ left: x + 12, top: y - 8 }}
    >
      <p className="font-semibold text-slate-900 max-w-[180px] truncate">{drug.drug_name}</p>
      <p className="text-slate-500 text-xs mt-0.5">{drug.sponsor}</p>
      <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-600">
        <span className="font-medium text-sky-700">{drug.phase}</span>
        <span>{drug.trial_count} trial{drug.trial_count !== 1 ? 's' : ''}</span>
      </div>
    </div>
  );
}
