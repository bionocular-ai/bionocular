import { useMemo } from 'react';
import type { DashboardTrialCard } from '@/lib/api';
import type { GroupByOption } from '@/types/bullseye';

export type PhaseRing = 'Phase 1' | 'Phase 2' | 'Phase 3' | 'Phase 4';

export interface DrugDot {
  drug_name: string;
  sponsor: string;
  phase: PhaseRing;
  trial_count: number;
  trials: DashboardTrialCard[];
  group_value: string;
}

const PHASE_ORDER: PhaseRing[] = ['Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];

const PHASE_RANK: Record<PhaseRing, number> = {
  'Phase 1': 1,
  'Phase 2': 2,
  'Phase 3': 3,
  'Phase 4': 4,
};

function phaseFromString(p: string): PhaseRing | null {
  if (p.includes('Phase 4')) return 'Phase 4';
  if (p.includes('Phase 3')) return 'Phase 3';
  if (p.includes('Phase 2')) return 'Phase 2';
  if (p.includes('Phase 1') || p.includes('Early Phase 1')) return 'Phase 1';
  return null;
}

function resolvePhase(phases: string[]): PhaseRing | null {
  let best: PhaseRing | null = null;
  for (const p of phases) {
    const ring = phaseFromString(p);
    if (!ring) continue;
    if (!best || PHASE_RANK[ring] > PHASE_RANK[best]) best = ring;
  }
  return best;
}

function getGroupValue(trial: DashboardTrialCard, groupBy: GroupByOption): string {
  switch (groupBy) {
    case 'modality': return (trial.modality ?? '').split(/[;,]/)[0]?.trim() || 'Other';
    case 'stage': return (trial.stage ?? '').split(/[;,]/)[0]?.trim() || 'Unspecified';
    case 'biomarker': return (trial.biomarker ?? '').split(/[;,]/)[0]?.trim() || 'Unspecified';
    case 'line_of_therapy': return (trial.line_of_therapy ?? '').split(/[;,]/)[0]?.trim() || 'Unspecified';
    case 'previous_treatment': return (trial.previous_treatment_criteria ?? '').split(/[;,]/)[0]?.trim() || 'Unspecified';
    default: return 'Other';
  }
}

export interface BullseyeData {
  drugs: DrugDot[];
  sponsors: string[];
  legendValues: string[];
  phaseRings: PhaseRing[];
}

const MAX_SPONSOR_SECTORS = 32;

export function useBullseyeData(
  trials: DashboardTrialCard[],
  groupBy: GroupByOption,
): BullseyeData {
  return useMemo(() => {
    const grouped = new Map<string, DashboardTrialCard[]>();
    for (const trial of trials) {
      const key = (trial.drug_name ?? trial.treatment_name ?? '').toLowerCase().trim();
      if (!key) continue;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(trial);
    }

    const drugs: DrugDot[] = [];
    for (const [, drugTrials] of grouped) {
      const phases = drugTrials.map((t) => t.phase ?? '');
      const phase = resolvePhase(phases);
      if (!phase) continue; // all "Not applicable" — skip

      const sponsor = drugTrials.find((t) => t.sponsor_name)?.sponsor_name ?? 'Unknown';
      const group_value = getGroupValue(drugTrials[0]!, groupBy);
      const display_name = drugTrials[0]!.drug_name ?? drugTrials[0]!.treatment_name ?? '';

      drugs.push({
        drug_name: display_name,
        sponsor,
        phase,
        trial_count: drugTrials.length,
        trials: drugTrials,
        group_value,
      });
    }

    // Count drugs per sponsor for top-N selection
    const drugCountBySponsor = new Map<string, number>();
    for (const d of drugs) {
      drugCountBySponsor.set(d.sponsor, (drugCountBySponsor.get(d.sponsor) ?? 0) + 1);
    }

    const allSponsors = Array.from(drugCountBySponsor.keys());
    let keptSponsors: Set<string>;
    let otherLabel: string | null = null;

    if (allSponsors.length > MAX_SPONSOR_SECTORS) {
      // Keep top (MAX-1) by drug count, alphabetical tiebreak; bucket rest
      const ranked = allSponsors.sort((a, b) => {
        const diff = (drugCountBySponsor.get(b) ?? 0) - (drugCountBySponsor.get(a) ?? 0);
        return diff !== 0 ? diff : a.localeCompare(b);
      });
      const top = ranked.slice(0, MAX_SPONSOR_SECTORS - 1);
      const rest = ranked.slice(MAX_SPONSOR_SECTORS - 1);
      keptSponsors = new Set(top);
      otherLabel = `Other (${rest.length})`;
      for (const d of drugs) {
        if (!keptSponsors.has(d.sponsor)) d.sponsor = otherLabel;
      }
    } else {
      keptSponsors = new Set(allSponsors);
    }

    const sponsors = Array.from(keptSponsors)
      .filter((s) => s !== 'Unknown')
      .sort((a, b) => a.localeCompare(b));
    if (keptSponsors.has('Unknown')) sponsors.push('Unknown');
    if (otherLabel) sponsors.push(otherLabel);

    const legendSet = new Set(drugs.map((d) => d.group_value));
    const legendValues = Array.from(legendSet).sort();

    return { drugs, sponsors, legendValues, phaseRings: PHASE_ORDER };
  }, [trials, groupBy]);
}
