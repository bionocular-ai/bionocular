'use client';

import * as React from 'react';
import type { DashboardTrialCard as DashboardTrialCardType } from '@/lib/api';
import { User, Building2, FileText } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { extractTrialAcronym } from '@/lib/utils/trial-utils';

export interface TrialCardProps {
  trial: DashboardTrialCardType;
  className?: string;
  category?: string;
}

function phaseToShort(phase: string): string {
  if (!phase) return '—';
  if (phase.includes('Early Phase 1')) return 'P0';
  if (phase.includes('Phase 1') && phase.includes('Phase 2')) return 'P1/2';
  if (phase.includes('Phase 2') && phase.includes('Phase 3')) return 'P2/3';
  if (phase.includes('Phase 1')) return 'P1';
  if (phase.includes('Phase 2')) return 'P2';
  if (phase.includes('Phase 3')) return 'P3';
  if (phase.includes('Phase 4')) return 'P4';
  return phase.slice(0, 6);
}

function statusDisplayLabel(status: string): string {
  const s = (status || '').toLowerCase().trim();
  // Map ClinicalTrials.gov normalized values → simplified 5-bucket labels
  if (s === 'recruiting' || s === 'not yet recruiting' || s === 'active, not recruiting') return 'Open';
  if (s === 'completed' || s === 'terminated' || s === 'withdrawn') return 'Closed';
  if (s === 'suspended') return 'Suspended';
  if (s === 'enrolling by invitation') return 'Enrolling by invitation';
  // Legacy raw API v2 enum values (in case normalizeStatus wasn't applied)
  if (s === 'recruiting' || s === 'not_yet_recruiting' || s === 'active_not_recruiting') return 'Open';
  if (s === 'completed' || s === 'terminated' || s === 'withdrawn') return 'Closed';
  if (s === 'suspended') return 'Suspended';
  if (s === 'enrolling_by_invitation') return 'Enrolling by invitation';
  // Already a simplified label
  if (s === 'open') return 'Open';
  if (s === 'closed') return 'Closed';
  return 'Unknown';
}

function studyStatusVariant(status: string): string {
  const label = statusDisplayLabel(status);
  if (label === 'Open') return 'bg-emerald-500 text-white';
  if (label === 'Closed') return 'bg-slate-500 text-white';
  if (label === 'Suspended') return 'bg-amber-500 text-white';
  if (label === 'Enrolling by invitation') return 'bg-cyan-500 text-white';
  return 'bg-slate-400 text-white'; // Unknown
}

function phaseTagVariant(phase: string): string {
  // Clean solid colors for minimalistic design
  if (phase.startsWith('P3') || phase === 'P3') return 'bg-rose-500 text-white';
  if (phase.startsWith('P1/2') || phase.startsWith('P2/3')) return 'bg-purple-500 text-white';
  if (phase.startsWith('P1') || phase === 'P1') return 'bg-violet-500 text-white';
  if (phase.startsWith('P2') || phase === 'P2') return 'bg-orange-500 text-white';
  return 'bg-slate-400 text-white';
}

export function TrialCard({ trial, className, category }: TrialCardProps) {
  const phaseShort = phaseToShort(trial.phase);
  const trialAcronym = trial.trial_name?.trim();
  const acronym = (trialAcronym && trialAcronym.toLowerCase() !== 'unknown')
    ? trialAcronym
    : extractTrialAcronym(trial.title);
  const displayName = acronym ?? trial.nct_id;
  const href = category
    ? `/trial/nct/${trial.nct_id}?category=${category}`
    : `/trial/nct/${trial.nct_id}`;
  const hasOutcomes = !!trial.has_outcomes;

  return (
    <div
      className={cn(
        '@container/card group relative rounded-lg overflow-hidden',
        'bg-[#1e3a5f]',
        'border border-[#2d4a6f]/80',
        'shadow-sm',
        'flex flex-col h-full min-h-0 min-w-0',
        className
      )}
    >
      <Link
        href={href}
        className="flex-1 flex flex-col min-w-0 min-h-0 px-[clamp(0.5rem,2.4cqw,1.25rem)] pt-[clamp(0.5rem,2.4cqw,1.25rem)] pb-[clamp(0.375rem,1.8cqw,0.875rem)] gap-[clamp(0.25rem,1.4cqw,0.75rem)]"
      >
        <span
          className="font-semibold text-[clamp(0.75rem,3.6cqw,1.625rem)] text-white leading-[1.15] truncate block tabular-nums tracking-tight"
          title={displayName !== trial.nct_id ? `${trial.nct_id} — ${displayName}` : trial.nct_id}
        >
          {displayName}
        </span>
        <span
          className="text-[clamp(0.65rem,3cqw,1.25rem)] text-slate-200 leading-[1.3] font-medium line-clamp-2 @[20rem]/card:line-clamp-3 break-words min-w-0"
          title={(trial.treatment_name || trial.drug_name) || undefined}
        >
          {trial.treatment_name || trial.drug_name || '—'}
        </span>
        <div className="flex items-center gap-[clamp(0.25rem,1cqw,0.5rem)] text-[clamp(0.6rem,2.4cqw,1rem)] text-slate-400 mt-auto pt-[clamp(0.25rem,1cqw,0.5rem)] min-w-0">
          <Building2 className="h-[clamp(0.625rem,2.2cqw,1rem)] w-[clamp(0.625rem,2.2cqw,1rem)] flex-shrink-0 text-slate-500/80" aria-hidden />
          <span className="truncate">{trial.sponsor_name || '—'}</span>
        </div>
      </Link>

      {/* Footer: enrollment, phase, status; Results when applicable */}
      <div className="px-[clamp(0.5rem,2.4cqw,1.25rem)] py-[clamp(0.3rem,1.6cqw,0.75rem)] border-t border-[#2d4a6f]/80 flex items-center justify-between gap-2 flex-nowrap shrink-0 overflow-hidden">
        <div className="flex items-center gap-[clamp(0.25rem,1.1cqw,0.625rem)] flex-nowrap min-w-0">
          <span className="inline-flex items-center gap-1 text-[clamp(0.55rem,2.3cqw,0.9375rem)] text-slate-300 font-medium tabular-nums">
            <User className="h-[clamp(0.625rem,2.2cqw,1rem)] w-[clamp(0.625rem,2.2cqw,1rem)] flex-shrink-0 text-slate-500" aria-hidden />
            {trial.enrollment_count != null ? trial.enrollment_count : '—'}
          </span>
          <span
            className={cn(
              'inline-flex items-center rounded px-[clamp(0.25rem,1.1cqw,0.5rem)] py-[clamp(0.0625rem,0.5cqw,0.25rem)] text-[clamp(0.55rem,2.3cqw,0.9375rem)] font-semibold uppercase tracking-wider',
              phaseTagVariant(phaseShort)
            )}
          >
            {phaseShort}
          </span>
          <span
            className={cn(
              'inline-flex items-center rounded px-[clamp(0.25rem,1.1cqw,0.5rem)] py-[clamp(0.0625rem,0.5cqw,0.25rem)] text-[clamp(0.55rem,2.3cqw,0.9375rem)] font-semibold uppercase tracking-wider',
              studyStatusVariant(trial.study_status)
            )}
          >
            {statusDisplayLabel(trial.study_status) || '—'}
          </span>
        </div>
        {hasOutcomes && (
          <Link
            href={href}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              'inline-flex items-center gap-1 rounded px-[clamp(0.25rem,1.1cqw,0.5rem)] py-[clamp(0.0625rem,0.5cqw,0.25rem)] text-[clamp(0.55rem,2.3cqw,0.9375rem)] font-semibold uppercase tracking-wider flex-shrink-0',
              'bg-sky-600/90 hover:bg-sky-500 text-white transition-colors duration-150'
            )}
            aria-label="View results"
          >
            <FileText className="h-[clamp(0.625rem,2.2cqw,1rem)] w-[clamp(0.625rem,2.2cqw,1rem)]" aria-hidden />
            Results
          </Link>
        )}
      </div>
    </div>
  );
}
