'use client';

import * as React from 'react';
import type { SelectedTypeStats } from '@/lib/api';
import { cn } from '@/lib/utils';

export interface DashboardStatsProps {
  stats: SelectedTypeStats | null | undefined;
  className?: string;
}

const STAT_LABELS: { key: keyof SelectedTypeStats; label: string }[] = [
  { key: 'clinical_trials', label: 'Clinical Trials' },
  { key: 'pipeline_drugs', label: 'Pipeline Drugs' },
  { key: 'drug_targets', label: 'Drug Targets' },
  { key: 'biomarkers', label: 'Biomarkers' },
];

function formatValue(value: number | null | undefined): string {
  if (value == null) return '—';
  return String(value);
}

export function DashboardStats({ stats, className }: DashboardStatsProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-4 sm:gap-6 lg:gap-8 min-w-0', className)}>
      {STAT_LABELS.map(({ key, label }, index) => (
        <React.Fragment key={key}>
          {index > 0 && (
            <div
              className="w-px flex-shrink-0 bg-slate-200 self-stretch min-h-[2rem]"
              aria-hidden
            />
          )}
          <div className="flex flex-col min-w-0">
            <span className="text-2xl lg:text-3xl font-bold text-rose-500 tabular-nums leading-tight">
              {formatValue(stats?.[key] ?? null)}
            </span>
            <span className="text-sm text-slate-500 mt-0.5 font-medium">
              {label}
            </span>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}
