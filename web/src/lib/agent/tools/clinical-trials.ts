import { tool } from 'ai';
import { z } from 'zod';
import { fetchJson } from './fetch-with-retry';
import { normalizePhase, normalizeStatus } from '@/lib/clinical-trials-enums';

const CT_API = 'https://clinicaltrials.gov/api/v2/studies';

interface CtStudy {
  protocolSection?: {
    identificationModule?: { nctId?: string; briefTitle?: string };
    statusModule?: { overallStatus?: string };
    designModule?: { phases?: string[] };
    sponsorCollaboratorsModule?: { leadSponsor?: { name?: string } };
    conditionsModule?: { conditions?: string[] };
    armsInterventionsModule?: { interventions?: Array<{ name?: string; type?: string }> };
    eligibilityModule?: { eligibilityCriteria?: string };
  };
}

interface CtResponse {
  studies?: CtStudy[];
  totalCount?: number;
}

export const searchClinicalTrialsTool = tool({
  description:
    'Search ClinicalTrials.gov for live trial status, eligibility, sponsors. Use for: trial ' +
    'recruitment status, phase distribution by indication, competitor pipelines, eligibility ' +
    'criteria. Filters: condition (e.g. "melanoma"), intervention (drug name), phase, status.',
  inputSchema: z.object({
    condition: z.string().optional().describe('Disease/cancer type (e.g. "uveal melanoma")'),
    intervention: z.string().optional().describe('Drug or treatment name'),
    phase: z.enum(['EARLY_PHASE1', 'PHASE1', 'PHASE2', 'PHASE3', 'PHASE4', 'NA']).optional(),
    status: z.enum([
      'RECRUITING',
      'NOT_YET_RECRUITING',
      'ACTIVE_NOT_RECRUITING',
      'COMPLETED',
      'TERMINATED',
      'SUSPENDED',
      'WITHDRAWN',
      'ENROLLING_BY_INVITATION',
      'UNKNOWN',
    ]).optional(),
    pageSize: z.number().int().min(1).max(20).default(10),
  }),
  providerOptions: {
    anthropic: { cacheControl: { type: 'ephemeral' } },
  },
  execute: async ({ condition, intervention, phase, status, pageSize }) => {
    const params = new URLSearchParams({
      pageSize: String(pageSize),
      format: 'json',
      countTotal: 'true',
    });
    if (condition)    params.set('query.cond',  condition);
    if (intervention) params.set('query.intr',  intervention);
    if (phase)        params.set('filter.advanced', `AREA[Phase]${phase}`);
    if (status)       params.set('filter.overallStatus', status);

    const data = await fetchJson<CtResponse>(`${CT_API}?${params.toString()}`);

    const trials = (data.studies ?? []).map((s) => {
      const id  = s.protocolSection?.identificationModule;
      const st  = s.protocolSection?.statusModule;
      const dm  = s.protocolSection?.designModule;
      const sp  = s.protocolSection?.sponsorCollaboratorsModule;
      const cm  = s.protocolSection?.conditionsModule;
      const ai  = s.protocolSection?.armsInterventionsModule;
      const el  = s.protocolSection?.eligibilityModule;

      return {
        nctId:         id?.nctId ?? '',
        title:         id?.briefTitle ?? '',
        status:        normalizeStatus(st?.overallStatus ?? 'UNKNOWN'),
        phases:        (dm?.phases ?? []).map(normalizePhase),
        sponsor:       sp?.leadSponsor?.name ?? '',
        conditions:    cm?.conditions ?? [],
        interventions: (ai?.interventions ?? []).map((i) => ({
          name: i.name ?? '',
          type: i.type ?? '',
        })),
        eligibility:   el?.eligibilityCriteria?.slice(0, 600) ?? '',
      };
    });

    return {
      total: data.totalCount ?? trials.length,
      trials,
    };
  },
});
