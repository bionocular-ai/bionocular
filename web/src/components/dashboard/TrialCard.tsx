'use client';

import * as React from 'react';
import type { DashboardTrialCard as DashboardTrialCardType } from '@/lib/api';
import { User, Building2, FileText } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { extractTrialAcronym } from '@/lib/utils/trial-utils';

export type TrialCardDensity = 'compact' | 'responsive';

export interface TrialCardProps {
  trial: DashboardTrialCardType;
  className?: string;
  category?: string;
  /** 'compact' = fixed sizes (landscape columns). 'responsive' = container-query scaling (dashboard grid, drawer). */
  density?: TrialCardDensity;
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
  if (s === 'recruiting' || s === 'not yet recruiting' || s === 'active, not recruiting') return 'Open';
  if (s === 'completed' || s === 'terminated' || s === 'withdrawn') return 'Closed';
  if (s === 'suspended') return 'Suspended';
  if (s === 'enrolling by invitation') return 'Enrolling by invitation';
  if (s === 'not_yet_recruiting' || s === 'active_not_recruiting') return 'Open';
  if (s === 'enrolling_by_invitation') return 'Enrolling by invitation';
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
  return 'bg-slate-400 text-white';
}

function phaseTagVariant(phase: string): string {
  if (phase.startsWith('P3') || phase === 'P3') return 'bg-rose-500 text-white';
  if (phase.startsWith('P1/2') || phase.startsWith('P2/3')) return 'bg-purple-500 text-white';
  if (phase.startsWith('P1') || phase === 'P1') return 'bg-violet-500 text-white';
  if (phase.startsWith('P2') || phase === 'P2') return 'bg-orange-500 text-white';
  return 'bg-slate-400 text-white';
}

const STYLES = {
  compact: {
    root: '',
    body: 'px-3 pt-3 pb-2 gap-1',
    title: 'font-bold text-sm leading-tight tracking-tight',
    drug: 'text-xs text-slate-200 leading-snug font-medium line-clamp-1 wrap-break-word',
    sponsor: 'gap-1 text-[0.625rem] text-slate-400/90 pt-1.5 mt-auto',
    sponsorIcon: 'h-[10px] w-[10px]',
    footer: 'px-3 py-2',
    footerGroup: 'gap-1.5',
    enrollment: 'text-[0.625rem]',
    enrollmentIcon: 'h-[11px] w-[11px]',
    badge: 'rounded-sm px-1 py-0.5 text-[0.625rem] tracking-wide',
    resultsIcon: 'h-[9px] w-[9px]',
    resultsGap: 'gap-0.5',
    resultsLabel: 'inline',
  },
  responsive: {
    root: '@container/card',
    body: 'px-[clamp(0.5rem,2.4cqw,1.25rem)] pt-[clamp(0.25rem,2cqw,1.25rem)] pb-[clamp(0.25rem,2cqw,1.125rem)] gap-[clamp(0.125rem,1.6cqw,1rem)]',
    title: 'block shrink-0 font-semibold text-[clamp(0.75rem,3.6cqw,2rem)] leading-[1.2] @[14rem]/card:leading-[1.25]',
    drug: 'text-[clamp(0.625rem,2.8cqw,1.375rem)] text-slate-200 leading-tight @[14rem]/card:leading-snug font-medium line-clamp-1 @[14rem]/card:line-clamp-2 @[20rem]/card:line-clamp-3 wrap-break-word min-h-0',
    sponsor: 'gap-[clamp(0.25rem,1cqw,0.5rem)] text-[clamp(0.55rem,2cqw,0.9375rem)] pt-[clamp(0.125rem,1.6cqw,0.875rem)] @[16rem]/card:mt-auto',
    sponsorIcon: 'h-[clamp(0.625rem,2.2cqw,1rem)] w-[clamp(0.625rem,2.2cqw,1rem)]',
    footer: 'px-[clamp(0.5rem,2.4cqw,1.25rem)] py-[clamp(0.25rem,1.6cqw,0.875rem)]',
    footerGroup: 'gap-[clamp(0.25rem,1.1cqw,0.625rem)]',
    enrollment: 'text-[clamp(0.55rem,2.3cqw,0.9375rem)]',
    enrollmentIcon: 'h-[clamp(0.625rem,2.2cqw,1rem)] w-[clamp(0.625rem,2.2cqw,1rem)]',
    badge: 'rounded px-[clamp(0.25rem,1.1cqw,0.5rem)] py-[clamp(0.0625rem,0.5cqw,0.25rem)] text-[clamp(0.55rem,2.3cqw,0.9375rem)] tracking-wider',
    resultsIcon: 'h-[clamp(0.75rem,2.4cqw,1.125rem)] w-[clamp(0.75rem,2.4cqw,1.125rem)]',
    resultsGap: 'gap-0 @[14rem]/card:gap-1',
    resultsLabel: 'hidden @[14rem]/card:inline',
  },
} as const;

const BADGE_BASE = 'inline-flex items-center font-semibold uppercase leading-none';

export function TrialCard({ trial, className, category, density = 'responsive' }: TrialCardProps) {
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
  const s = STYLES[density];

  return (
    <div
      className={cn(
        s.root,
        'group relative rounded-lg overflow-hidden',
        'bg-[#1e3a5f]',
        'border border-[#2d4a6f]/80 hover:border-[#3d5f8f]',
        'shadow-sm transition-colors duration-150',
        'flex flex-col h-full min-h-0 min-w-0',
        className
      )}
    >
      {/* Body */}
      <Link
        href={href}
        className={cn('flex-1 flex flex-col min-w-0 min-h-0', s.body)}
      >
        <span
          className={cn(s.title, 'text-white truncate tabular-nums tracking-tight')}
          title={displayName !== trial.nct_id ? `${trial.nct_id} — ${displayName}` : trial.nct_id}
        >
          {displayName}
        </span>
        <span
          className={cn(s.drug, 'min-w-0')}
          title={(trial.treatment_name || trial.drug_name) || undefined}
        >
          {trial.treatment_name || trial.drug_name || '—'}
        </span>
        <div className={cn('flex items-center text-slate-400 min-w-0', s.sponsor)}>
          <Building2 className={cn(s.sponsorIcon, 'shrink-0 text-slate-500/80')} aria-hidden />
          <span className="truncate">{trial.sponsor_name || '—'}</span>
        </div>
      </Link>

      {/* Footer: enrollment, phase, status, results */}
      <div className={cn('border-t border-[#2d4a6f]/80 flex items-center justify-between gap-2 flex-nowrap shrink-0 overflow-hidden', s.footer)}>
        <div className={cn('flex items-center flex-nowrap min-w-0', s.footerGroup)}>
          <span className={cn('inline-flex items-center gap-1 text-slate-300 font-medium tabular-nums', s.enrollment)}>
            <User className={cn(s.enrollmentIcon, 'shrink-0 text-slate-500')} aria-hidden />
            {trial.enrollment_count != null ? trial.enrollment_count : '—'}
          </span>
          <span className={cn(BADGE_BASE, s.badge, phaseTagVariant(phaseShort))}>
            {phaseShort}
          </span>
          <span className={cn(BADGE_BASE, s.badge, studyStatusVariant(trial.study_status))}>
            {statusDisplayLabel(trial.study_status) || '—'}
          </span>
        </div>
        {hasOutcomes && (
          <Link
            href={href}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              BADGE_BASE,
              s.badge,
              s.resultsGap,
              'shrink-0 bg-sky-600/90 hover:bg-sky-500 text-white transition-colors duration-150'
            )}
            aria-label="View results"
          >
            <FileText className={s.resultsIcon} aria-hidden />
            <span className={s.resultsLabel}>Results</span>
          </Link>
        )}
      </div>
    </div>
  );
}
