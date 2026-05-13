import { createClient } from './supabase/client';
import type { TrialDataFile } from '@/types/analytics';

export interface Trial {
  id: string;
  nct_id: string;
  title: string;
  phase: string;
  sponsor: string;
  status: string;
  abstract_id?: string;
  publication_name?: string;
  cancer_type?: string;
  year?: string | number;
  type?: 'abstract' | 'publication';
  source_url?: string; // For web-scraped trials
  arms?: Array<{
    arm_name: string;
    generic_name: string;
  }>;
  arm_name?: string;
  generic_name?: string;
  has_outcomes?: boolean;
}

export interface TrialsResponse {
  trials: Trial[];
  total: number;
  skip: number;
  limit: number;
}

export interface Document {
  id: string;
  original_filename: string;
  storage_path: string;
  type: string;
  upload_date: string;
  hash: string;
  status: string;
  metadata: Record<string, unknown>;
}

export function getDbCancerType(slug: string): string {
  const map: Record<string, string> = {
    'cutaneous-melanoma': 'Cutaneous Melanoma',
    'cutaneous-squamous-cell-carcinoma': 'Cutaneous Squamous Cell Carcinoma',
    'cutaneous-melanoma-with-brain-cns-metastasis': 'Cutaneous Melanoma with Brain/CNS Metastasis',
    'uveal-melanoma': 'Uveal Melanoma',
    'acral-melanoma': 'Acral Melanoma',
    'mucosal-melanoma': 'Mucosal Melanoma',
    'basal-cell-carcinoma': 'Basal Cell Carcinoma',
    'merkel-cell-carcinoma': 'Merkel Cell Carcinoma',
  };
  return map[slug] || slug;
}

import { normalizePhase, normalizeStatus } from './clinical-trials-enums';
export { PHASE_MAP, STATUS_MAP, normalizePhase, normalizeStatus } from './clinical-trials-enums';


export const trialsApi = {
  getAll: async (skip = 0, limit = 100): Promise<TrialsResponse> => {
    const supabase = createClient();
    const { data, count } = await supabase.from('clinical_trials')
      .select('nct_id, brief_title, phases, lead_sponsor_name, overall_status', { count: 'exact' })
      .range(skip, skip + limit - 1);
    
    const trials: Trial[] = (data || []).map(d => ({
        id: d.nct_id,
        nct_id: d.nct_id,
        title: d.brief_title || d.nct_id,
        phase: Array.isArray(d.phases) ? d.phases.join(', ') : (d.phases || ''),
        sponsor: d.lead_sponsor_name || 'Unknown',
        status: d.overall_status || 'Unknown',
    }));
    return { trials, total: count || 0, skip, limit };
  },

  getById: async (id: string): Promise<Document> => {
    throw new Error(`Documents obsolete: ${id}`);
  },

  getByNctId: async (nctId: string, skip = 0, limit = 100): Promise<TrialsResponse> => {
    const trialDetail = await trialsApi.getTrialDetail(nctId);
    if (!trialDetail || !trialDetail.protocolSection) return { trials: [], total: 0, skip, limit };
    return { trials: [{
         id: nctId,
         nct_id: nctId,
         title: trialDetail.protocolSection.identificationModule?.briefTitle || nctId,
         phase: (trialDetail.protocolSection.designModule?.phases || []).join(', '),
         sponsor: trialDetail.protocolSection.sponsorCollaboratorsModule?.leadSponsor?.name || 'Unknown',
         status: trialDetail.protocolSection.statusModule?.overallStatus || 'Unknown',
    }], total: 1, skip, limit };
  },

  getByAbstractId: async (abstractId: string, category?: string | null): Promise<AbstractData> => {
    const supabase = createClient();
    const dbCancerType = category ? getDbCancerType(category) : null;
    const matchesCategory = (cancerTypes: unknown): boolean => {
      if (!dbCancerType) return false;
      if (Array.isArray(cancerTypes)) return (cancerTypes as unknown[]).includes(dbCancerType);
      if (typeof cancerTypes === 'string') return cancerTypes === dbCancerType;
      return false;
    };
    const CONTROL_ARM_RE = /investigator'?s?\s*choice|control|placebo|standard\s*of\s*care|comparator/i;
    const pickRow = (rows: Record<string, unknown>[]): Record<string, unknown> | null => {
      if (rows.length === 0) return null;
      const sorted = [...rows].sort((a, b) => {
        const aCat = matchesCategory(a.cancer_type) ? 1 : 0;
        const bCat = matchesCategory(b.cancer_type) ? 1 : 0;
        if (aCat !== bCat) return bCat - aCat;
        const aCtrl = typeof a.arm_name === 'string' && CONTROL_ARM_RE.test(a.arm_name) ? 1 : 0;
        const bCtrl = typeof b.arm_name === 'string' && CONTROL_ARM_RE.test(b.arm_name) ? 1 : 0;
        if (aCtrl !== bCtrl) return aCtrl - bCtrl;
        const aHas = typeof a.abstract_id === 'string' && a.abstract_id && a.abstract_id !== abstractId ? 1 : 0;
        const bHas = typeof b.abstract_id === 'string' && b.abstract_id && b.abstract_id !== abstractId ? 1 : 0;
        if (aHas !== bHas) return bHas - aHas;
        const ay = Number(a.published_year ?? 0);
        const by = Number(b.published_year ?? 0);
        return by - ay;
      });
      return sorted[0];
    };
    const { data: byAbstract } = await supabase
      .from('trial_outcomes')
      .select('*')
      .eq('abstract_id', abstractId)
      .limit(50);
    let data: Record<string, unknown> | null = pickRow((byAbstract as Record<string, unknown>[] | null) ?? []);

    // Fallback: abstractId may actually be a NCT id (links can substitute NCT
    // when a row's abstract_id is missing). Try looking up by nct_id and pick
    // the most recently published row.
    if (!data && /^NCT\d+/i.test(abstractId)) {
      const { data: byNct, error: nctErr } = await supabase
        .from('trial_outcomes')
        .select('*')
        .eq('nct_id', abstractId)
        .limit(50);
      if (nctErr) console.warn('getByAbstractId nct_id lookup error', nctErr);
      data = pickRow((byNct as Record<string, unknown>[] | null) ?? []);
    }

    // Final fallback: no trial_outcomes row at all. Still try to render a
    // summary card from clinical_trials + trial_landscape if abstractId is a NCT.
    if (!data) {
      if (/^NCT\d+/i.test(abstractId)) {
        const [{ data: trialRow }, { data: landscapeRows }] = await Promise.all([
          supabase
            .from('clinical_trials')
            .select('nct_id, brief_title, overall_status, phases, enrollment_count, lead_sponsor_name, lead_sponsor_class, conditions')
            .eq('nct_id', abstractId)
            .maybeSingle(),
          supabase
            .from('trial_landscape')
            .select('*')
            .eq('nct_id', abstractId),
        ]);
        return {
          abstract_id: abstractId,
          title: ((trialRow as ClinicalTrialFlat | null)?.brief_title as string) || '',
          outcome: null,
          trial: (trialRow as ClinicalTrialFlat | null) ?? null,
          landscape: ((landscapeRows as TrialLandscapeRow[] | null) ?? [])[0] ?? null,
        };
      }
      return { abstract_id: abstractId };
    }

    const outcome = data as unknown as TrialOutcomeRow;
    const nctId = (outcome.nct_id as string) || '';

    let trial: ClinicalTrialFlat | null = null;
    let landscape: TrialLandscapeRow | null = null;
    if (nctId) {
      const [{ data: trialRow }, { data: landscapeRows }] = await Promise.all([
        supabase
          .from('clinical_trials')
          .select('nct_id, brief_title, overall_status, phases, enrollment_count, lead_sponsor_name, lead_sponsor_class, conditions')
          .eq('nct_id', nctId)
          .maybeSingle(),
        supabase
          .from('trial_landscape')
          .select('*')
          .eq('nct_id', nctId),
      ]);
      trial = (trialRow as ClinicalTrialFlat | null) ?? null;
      const rows = (landscapeRows as TrialLandscapeRow[] | null) ?? [];
      const outcomeCancerTypes = Array.isArray(outcome.cancer_type) ? outcome.cancer_type as string[] : [];
      landscape =
        (dbCancerType ? rows.find(r => r.cancer_type === dbCancerType) : null) ??
        rows.find(r => outcomeCancerTypes.includes(r.cancer_type ?? '')) ??
        rows[0] ?? null;
    }

    // Always synthesise arm_results from the flat outcome columns so legacy
    // consumers (AbstractTimeline → extractKeyMetrics) keep working post-migration.
    const synthesisedRaw = outcomeRowToClinicalTrialRaw(data as Record<string, unknown>);
    const synthesisedArms = synthesisedRaw.arm_results as unknown as Record<string, ArmResult>;
    const existingArms =
      data.arm_results && typeof data.arm_results === 'object'
        ? (data.arm_results as unknown as Record<string, ArmResult>)
        : undefined;
    const armResults =
      existingArms && Object.keys(existingArms).length > 0 ? existingArms : synthesisedArms;

    return {
      abstract_id: (outcome.abstract_id as string) || abstractId,
      source_url: outcome.source as string | undefined,
      arm_results: armResults,
      title: (trial?.brief_title as string) || (outcome.trial_name as string) || '',
      outcome,
      trial,
      landscape,
    };
  },

  getLandscapeStats: async (cancerType?: string): Promise<LandscapeStatsResponse> => {
    const supabase = createClient();

    // Run count + data queries in parallel
    let countQ = supabase.from('trial_landscape').select('nct_id', { count: 'exact', head: true });
    let dataQ = supabase.from('trial_landscape').select('cancer_type');
    if (cancerType) {
      const dbType = getDbCancerType(cancerType);
      countQ = countQ.contains('cancer_type', [dbType]);
      dataQ = dataQ.contains('cancer_type', [dbType]);
    }

    const [{ count: exactCount }, { data: landscape }] = await Promise.all([countQ, dataQ]);

    const counts: Record<string, number> = {};
    landscape?.forEach(row => {
        if (!counts[row.cancer_type]) counts[row.cancer_type] = 0;
        counts[row.cancer_type]++;
    });

    const landscapeStats = Object.keys(counts).map(key => ({
        cancer_type: key,
        bubble_size: Math.log(counts[key] + 1) * 10,
        total_api_count: counts[key],
        extracted_count: counts[key]
    }));
    return { landscape: landscapeStats, selected_type_stats: { clinical_trials: exactCount || 0, pipeline_drugs: null, drug_targets: null, biomarkers: null } };
  },

  getTrialUpdatesCount: async (
    cancerType: string,
    days: number = 30
  ): Promise<TrialUpdatesCountResponse> => {
    const supabase = createClient();
    const since = new Date();
    since.setDate(since.getDate() - days);
    const sinceIso = since.toISOString().split('T')[0]; // YYYY-MM-DD
    const dbCancerType = getDbCancerType(cancerType);

    // Use actual ClinicalTrials.gov dates from the clinical_trials table:
    //   new_records_added → first_posted_date (trial first appeared on CT.gov)
    //   updates           → last_update_posted_date (trial data was last changed on CT.gov)
    // Both queries filter by cancer_type via trial_landscape join.
    const [newResult, updatedResult] = await Promise.all([
      supabase
        .from('clinical_trials')
        .select('nct_id', { count: 'exact', head: true })
        .contains('cancer_type', [dbCancerType])
        .gte('first_posted_date', sinceIso),
      supabase
        .from('clinical_trials')
        .select('nct_id', { count: 'exact', head: true })
        .contains('cancer_type', [dbCancerType])
        .gte('last_update_posted_date', sinceIso),
    ]);

    return {
      new_records_added: newResult.count || 0,
      updates: updatedResult.count || 0,
      window_end_iso: new Date().toISOString(),
      window_start_iso: since.toISOString(),
    };
  },

  getLatestTrialUpdates: async (
    cancerType: string,
    limit: number = 5,
    days?: number
  ): Promise<LatestTrialUpdatesResponse> => {
    const supabase = createClient();
    // Query clinical_trials directly to get actual ClinicalTrials.gov dates
    // rather than the Supabase bulk import timestamp (created_at)
    let query = supabase
      .from('clinical_trials')
      .select(`
        nct_id,
        brief_title,
        lead_sponsor_name,
        last_update_posted_date,
        first_posted_date
      `)
      .contains('cancer_type', [getDbCancerType(cancerType)]);

    if (days) {
      const since = new Date();
      since.setDate(since.getDate() - days);
      const sinceIso = since.toISOString().split('T')[0];
      query = query.gte('last_update_posted_date', sinceIso);
    }

    const { data, error } = await query
      .order('last_update_posted_date', { ascending: false, nullsFirst: false })
      .limit(limit);
      
    if (error) throw error;
    
    const trials = data.map(d => {
      // If the trial was just posted, first == last update date
      const isNew = d.first_posted_date && d.last_update_posted_date && d.first_posted_date === d.last_update_posted_date;
      
      return {
        nct_id: d.nct_id || '',
        title: d.brief_title || 'Unknown Title',
        sponsor_name: d.lead_sponsor_name || 'Unknown Sponsor',
        date_iso: d.last_update_posted_date || new Date().toISOString(),
        update_type: (isNew ? 'new' : 'updated') as 'new' | 'updated'
      };
    });
    
    return { trials };
  },

  getDashboardTrials: async (
    cancerType: string,
    filters: DashboardTrialsFilters = {}
  ): Promise<DashboardTrialsResponse> => {
    const supabase = createClient();
    const dbCancerType = getDbCancerType(cancerType);

    // Two-query path: fetch open + closed separately at DB level to guarantee ratio.
    const OPEN_RAW = ['RECRUITING', 'NOT_YET_RECRUITING', 'ACTIVE_NOT_RECRUITING'];
    const CLOSED_RAW = ['COMPLETED', 'TERMINATED', 'WITHDRAWN', 'SUSPENDED', 'ENROLLING_BY_INVITATION', 'UNKNOWN'];

    if (filters.open_fraction !== undefined && filters.limit !== undefined) {
      const wantOpen = Math.round(filters.limit * filters.open_fraction);
      const wantClosed = filters.limit - wantOpen;
      const biasSelect = '*, clinical_trials!inner(brief_title, phases, lead_sponsor_name, enrollment_count, overall_status, lead_sponsor_class)';

      const [{ data: openData, error: openErr }, { data: closedData, error: closedErr }] = await Promise.all([
        supabase.from('trial_landscape').select(biasSelect).contains('cancer_type', [dbCancerType]).in('clinical_trials.overall_status', OPEN_RAW).limit(wantOpen),
        supabase.from('trial_landscape').select(biasSelect).contains('cancer_type', [dbCancerType]).in('clinical_trials.overall_status', CLOSED_RAW).limit(wantClosed),
      ]);

      if (openErr || closedErr) {
        console.error('[getDashboardTrials] status-split error:', openErr || closedErr);
        return { trials: [], total: 0 };
      }

      const merged = [...(openData || []), ...(closedData || [])];
      const nctIds = merged.map((d: Record<string, unknown>) => d.nct_id).filter(Boolean);
      const { data: outcomesData } = await supabase.from('trial_outcomes').select('nct_id').in('nct_id', nctIds);
      const nctIdsWithOutcomes = new Set((outcomesData || []).map((o: { nct_id: string }) => o.nct_id));

      let biasTrials: DashboardTrialCard[] = merged.map((d: Record<string, unknown>) => {
        const ctEntry = Array.isArray(d.clinical_trials) ? (d.clinical_trials as Record<string, unknown>[])[0] : d.clinical_trials as Record<string, unknown>;
        const rawPhases = Array.isArray(ctEntry?.phases) ? ctEntry.phases as string[] : [];
        return {
          nct_id: (d.nct_id as string) || '',
          title: (ctEntry?.brief_title as string) || null,
          drug_name: (d.treatment_name as string) || null,
          sponsor_name: (ctEntry?.lead_sponsor_name as string) || null,
          enrollment_count: (ctEntry?.enrollment_count as number) || null,
          phase: rawPhases.map(normalizePhase).join(', ') || 'Unknown',
          study_status: normalizeStatus((ctEntry?.overall_status as string) || 'UNKNOWN'),
          sponsor_type: (ctEntry?.lead_sponsor_class as string) || 'Unknown',
          approval_group: 'Investigational',
          trial_name: (d.acronym as string) || null,
          modality: (d.modality as string) || null,
          treatment_name: (d.treatment_name as string) || null,
          stage: (d.stage as string) || null,
          biomarker: (d.biomarker as string) || null,
          line_of_therapy: (d.line_of_therapy as string) || null,
          previous_treatment_criteria: (d.previous_treatment_criteria as string) || null,
          has_outcomes: nctIdsWithOutcomes.has(d.nct_id as string),
        };
      });

      if (filters.sponsor_type && filters.sponsor_type.length > 0) {
        const wantsIndustry = filters.sponsor_type.some(s => s.toLowerCase() === 'industry');
        const wantsNonIndustry = filters.sponsor_type.some(s => s.toLowerCase() === 'non-industry');
        biasTrials = biasTrials.filter(t => {
          const isIndustry = (t.sponsor_type || '').toUpperCase() === 'INDUSTRY';
          if (wantsIndustry && wantsNonIndustry) return true;
          if (wantsIndustry) return isIndustry;
          if (wantsNonIndustry) return !isIndustry;
          return false;
        });
      }

      return { trials: biasTrials, total: biasTrials.length };
    }

    // Parallel: exact count (HEAD) + data rows — both share identical filters.
    let countQ = supabase.from('trial_landscape')
      .select('nct_id', { count: 'exact', head: true })
      .contains('cancer_type', [dbCancerType]);
    let dataQ = supabase.from('trial_landscape')
      .select('*, clinical_trials(brief_title, phases, lead_sponsor_name, enrollment_count, overall_status, lead_sponsor_class)')
      .contains('cancer_type', [dbCancerType]);

    if (filters.modality) {
      countQ = countQ.eq('modality', filters.modality);
      dataQ = dataQ.eq('modality', filters.modality);
    }

    const [{ count: exactCount, error: countErr }, { data, error }] = await Promise.all([countQ, dataQ]);

    if (error || countErr) {
      console.error('[getDashboardTrials] Supabase error:', error || countErr);
      return { trials: [], total: 0 };
    }
    if (!data || data.length === 0) return { trials: [], total: exactCount || 0 };

    // Separately fetch which nct_ids have outcomes (avoids FK dependency)
    const nctIds = data.map((d: Record<string, unknown>) => d.nct_id).filter(Boolean);
    const { data: outcomesData } = await supabase
      .from('trial_outcomes')
      .select('nct_id')
      .in('nct_id', nctIds);
    const nctIdsWithOutcomes = new Set((outcomesData || []).map((o: { nct_id: string }) => o.nct_id));

    let trials: DashboardTrialCard[] = data.map((d: Record<string, unknown>) => {
       const ctEntry = Array.isArray(d.clinical_trials) ? (d.clinical_trials as Record<string, unknown>[])[0] : d.clinical_trials as Record<string, unknown>;
       const rawPhases = Array.isArray(ctEntry?.phases) ? ctEntry.phases as string[] : [];
       const phases = rawPhases.map(normalizePhase);
       const hasOutcomes = nctIdsWithOutcomes.has(d.nct_id as string);

       return {
         nct_id: (d.nct_id as string) || '',
         title: (ctEntry?.brief_title as string) || null,
         drug_name: (d.treatment_name as string) || null,
         sponsor_name: (ctEntry?.lead_sponsor_name as string) || null,
         enrollment_count: (ctEntry?.enrollment_count as number) || null,
         phase: phases.join(', ') || 'Unknown',
         study_status: normalizeStatus((ctEntry?.overall_status as string) || 'UNKNOWN'),
         sponsor_type: (ctEntry?.lead_sponsor_class as string) || 'Unknown',
         approval_group: 'Investigational',
         trial_name: (d.acronym as string) || null,
         modality: (d.modality as string) || null,
         treatment_name: (d.treatment_name as string) || null,
         stage: (d.stage as string) || null,
         biomarker: (d.biomarker as string) || null,
         line_of_therapy: (d.line_of_therapy as string) || null,
         previous_treatment_criteria: (d.previous_treatment_criteria as string) || null,
         has_outcomes: hasOutcomes,
       };
    });

    // Client-side phase/sponsor filters (applied after fetch)
    if (filters.phase && filters.phase.length > 0) {
       trials = trials.filter(t => filters.phase!.some(p => t.phase.includes(p)));
    }
    if (filters.sponsor_type && filters.sponsor_type.length > 0) {
       const wantsIndustry = filters.sponsor_type.some(s => s.toLowerCase() === 'industry');
       const wantsNonIndustry = filters.sponsor_type.some(s => s.toLowerCase() === 'non-industry');
       trials = trials.filter(t => {
         const isIndustry = (t.sponsor_type || '').toUpperCase() === 'INDUSTRY';
         if (wantsIndustry && wantsNonIndustry) return true;
         if (wantsIndustry) return isIndustry;
         if (wantsNonIndustry) return !isIndustry;
         return false;
       });
    }

    // Use exactCount for total (accurate even when data rows are capped by PostgREST)
    // After client-side filters, total reflects filtered count from fetched rows.
    const hasClientFilter = (filters.phase?.length ?? 0) > 0 || (filters.sponsor_type?.length ?? 0) > 0;
    const total = hasClientFilter ? trials.length : (exactCount ?? trials.length);

    if (filters.skip !== undefined || filters.limit !== undefined) {
       trials = trials.slice(filters.skip || 0, (filters.skip || 0) + (filters.limit || 100));
    }

    return { trials, total };
  },

  getTherapeuticIndex: async (skip = 0, limit = 100): Promise<TherapeuticIndexResponse> => {
    const supabase = createClient();
    const { data, count } = await supabase.from('trial_landscape')
      .select('nct_id, clinical_trials(brief_title, phases, lead_sponsor_name, overall_status)', { count: 'exact' })
      .range(skip, skip + limit - 1);
    
    const trials: Trial[] = (data || []).map(d => {
       const ctEntry = Array.isArray(d.clinical_trials) ? d.clinical_trials[0] : d.clinical_trials;
       return {
         id: d.nct_id,
         nct_id: d.nct_id,
         title: ctEntry?.brief_title || d.nct_id,
         phase: Array.isArray(ctEntry?.phases) ? ctEntry.phases.join(', ') : (ctEntry?.phases || ''),
         sponsor: ctEntry?.lead_sponsor_name || 'Unknown',
         status: ctEntry?.overall_status || 'Unknown',
       };
    });
    return { trials, total: count || 0, skip, limit, has_more: (count || 0) > skip + limit - 1 };
  },

  getDiseaseLandscapeStats: async (
    category: string,
    opts?: { sponsor_type?: string }
  ): Promise<DiseaseLandscapeStats> => {
    const supabase = createClient();
    const dbCancerType = getDbCancerType(category);

    // Build a base filter factory so both queries share identical filters.
    // Non-Industry uses an OR clause so NULL lead_sponsor_class rows are kept
    // (Postgres `<>` returns NULL for NULL operand → would silently drop rows).
    const buildQuery = () => {
      let q = supabase.from('clinical_trials')
        .select('overall_status, phases, lead_sponsor_class')
        .contains('cancer_type', [dbCancerType]);
      if (opts?.sponsor_type) {
        const wantIndustry = opts.sponsor_type.toLowerCase() === 'industry';
        q = wantIndustry
          ? q.eq('lead_sponsor_class', 'INDUSTRY')
          : q.or('lead_sponsor_class.neq.INDUSTRY,lead_sponsor_class.is.null');
      }
      return q;
    };

    // Run two queries in parallel:
    // 1. HEAD-only count — PostgREST returns exact total in Content-Range, no rows transferred.
    // 2. Data query for phase/status/funder distributions (capped at PostgREST default ~1000,
    //    which is fine as a representative sample for percentage charts).

    const [countResult, dataResult] = await Promise.all([
      (() => {
        let q = supabase.from('clinical_trials')
          .select('nct_id', { count: 'exact', head: true })
          .contains('cancer_type', [dbCancerType]);
        if (opts?.sponsor_type) {
          const wantIndustry = opts.sponsor_type.toLowerCase() === 'industry';
          q = wantIndustry
            ? q.eq('lead_sponsor_class', 'INDUSTRY')
            : q.or('lead_sponsor_class.neq.INDUSTRY,lead_sponsor_class.is.null');
        }
        return q;
      })(),
      buildQuery(),
    ]);

    if (countResult.error) console.error('[getDiseaseLandscapeStats] count error:', countResult.error);
    if (dataResult.error) console.error('[getDiseaseLandscapeStats] data error:', dataResult.error);

    const exactTotal = countResult.count ?? dataResult.data?.length ?? 0;

    const stats: DiseaseLandscapeStats = {
      status: { 'Overall Status': exactTotal, 'Not yet recruiting': 0, 'Recruiting': 0, 'Active, not recruiting': 0, 'Completed': 0, 'Terminated': 0, 'Enrolling by invitation': 0, 'Suspended': 0, 'Withdrawn': 0, 'Unknown': 0 },
      phase: { 'Early Phase 1': 0, 'Phase 1': 0, 'Phase 2': 0, 'Phase 3': 0, 'Phase 4': 0, 'Not applicable': 0 },
      funder_type: { 'Industry': 0, 'Non-Industry': 0 },
      extracted_count: exactTotal,
    };

    dataResult.data?.forEach(d => {
       const rawStatus = (d.overall_status as string) || 'UNKNOWN';
       const pStatus = normalizeStatus(rawStatus);
       const phases = Array.isArray(d.phases) ? d.phases : [];
       const isIndustry = (d.lead_sponsor_class || '').toUpperCase() === 'INDUSTRY';

       if (stats.status[pStatus as keyof typeof stats.status] !== undefined) {
           stats.status[pStatus as keyof typeof stats.status]++;
       } else {
           stats.status['Unknown']++;
       }

       phases.forEach((p: string) => {
           const readable = normalizePhase(p);
           if (readable && stats.phase[readable as keyof typeof stats.phase] !== undefined) {
               stats.phase[readable as keyof typeof stats.phase]++;
           }
       });

       if (isIndustry) stats.funder_type['Industry']++;
       else stats.funder_type['Non-Industry']++;
    });
    return stats;
  },



  getLiveTicker: async (category: string): Promise<LiveTickerResponse> => {
    const supabase = createClient();
    const { data, error } = await supabase
      .from('news_feed')
      .select('title, date, url, nct_ids, has_efficacy, has_safety, efficacy_data, safety_data')
      .contains('cancer_type', [getDbCancerType(category)])
      .order('date', { ascending: false })
      .limit(100);

    if (error) throw error;

    const articles = (data ?? []).map(d => ({
      title: d.title as string,
      date: d.date as string,
      url: d.url as string,
      nct_ids: d.nct_ids as string[] | null,
      has_efficacy: d.has_efficacy as boolean | null,
      has_safety: d.has_safety as boolean | null,
      efficacy_data: d.efficacy_data as Record<string, Record<string, string>> | null,
      safety_data: d.safety_data as Record<string, Record<string, string>> | null,
    }));

    return { articles, results: [] };
  },

  /** Full trial detail from the flat clinical_trials columns (post-Supabase migration). */
  getTrialDetail: async (nctId: string): Promise<TrialDetailApiResponse> => {
    const supabase = createClient();
    const { data, error } = await supabase
      .from('clinical_trials')
      .select([
        'nct_id', 'brief_title', 'official_title',
        'overall_status', 'study_type', 'phases', 'enrollment_count',
        'lead_sponsor_name', 'lead_sponsor_class',
        'brief_summary', 'detailed_description', 'eligibility_criteria',
        'conditions', 'interventions', 'arm_groups',
        'primary_outcomes', 'secondary_outcomes', 'locations',
        'start_date', 'primary_completion_date', 'completion_date',
        'first_posted_date', 'last_update_posted_date',
        'minimum_age', 'maximum_age', 'sex',
      ].join(', '))
      .eq('nct_id', nctId)
      .single();

    if (error) throw error;
    if (!data) return {};

    // Reshape flat columns → TrialDetailApiResponse (protocolSection structure)
    // so TrialDetailView works without modification.
    const d = data as unknown as Record<string, unknown>;

    const toDateStruct = (date: unknown) =>
      date ? { date: date as string } : undefined;

    return {
      protocolSection: {
        identificationModule: {
          nctId: d.nct_id as string,
          briefTitle: d.brief_title as string,
        },
        conditionsModule: {
          conditions: (d.conditions as string[] | null) ?? [],
        },
        designModule: {
          studyType: d.study_type as string,
          phases: (d.phases as string[] | null) ?? [],
          enrollmentInfo: d.enrollment_count != null
            ? { count: d.enrollment_count as number }
            : undefined,
        },
        statusModule: {
          overallStatus: d.overall_status as string,
          startDateStruct: toDateStruct(d.start_date),
          primaryCompletionDateStruct: toDateStruct(d.primary_completion_date),
          completionDateStruct: toDateStruct(d.completion_date),
          studyFirstPostDateStruct: toDateStruct(d.first_posted_date),
          lastUpdatePostDateStruct: toDateStruct(d.last_update_posted_date),
        },
        sponsorCollaboratorsModule: {
          leadSponsor: {
            name: d.lead_sponsor_name as string,
            class: d.lead_sponsor_class as string,
          },
        },
        descriptionModule: {
          briefSummary: d.brief_summary as string,
          detailedDescription: d.detailed_description as string,
        },
        eligibilityModule: {
          eligibilityCriteria: d.eligibility_criteria as string,
          eligibilityInfo: {
            minimumAge: d.minimum_age as string,
            maximumAge: d.maximum_age as string,
            sex: d.sex as string,
          },
        },
        armsInterventionsModule: {
          interventions: (d.interventions as Array<{
            name?: string; type?: string; description?: string; otherNames?: string[];
          }> | null) ?? [],
          armGroups: (d.arm_groups as Array<{
            label?: string; type?: string; description?: string; interventionNames?: string[];
          }> | null) ?? [],
        },
        outcomesModule: {
          primaryOutcomes: (d.primary_outcomes as Array<{
            measure?: string; description?: string; timeFrame?: string;
          }> | null) ?? [],
          secondaryOutcomes: (d.secondary_outcomes as Array<{
            measure?: string; description?: string; timeFrame?: string;
          }> | null) ?? [],
        },
        contactsLocationsModule: {
          locations: (d.locations as Array<{
            facility?: string; city?: string; state?: string;
            zip?: string; country?: string; status?: string;
          }> | null) ?? [],
        },
      },
    } as TrialDetailApiResponse;
  },
};


/** ClinicalTrials.gov API v2 study response (protocolSection + resultsSection). */
export interface TrialDetailApiResponse {
  protocolSection?: {
    identificationModule?: { nctId?: string; briefTitle?: string; conditions?: string[] };
    /** Conditions (diseases) are under conditionsModule in API v2, not identificationModule. */
    conditionsModule?: { conditions?: string[] };
    designModule?: {
      phases?: string[];
      studyType?: string;
      enrollmentInfo?: { count?: number };
    };
    statusModule?: {
      overallStatus?: string;
      startDateStruct?: { date?: string };
      primaryCompletionDateStruct?: { date?: string };
      completionDateStruct?: { date?: string };
      studyFirstPostDateStruct?: { date?: string };
      lastUpdatePostDateStruct?: { date?: string };
    };
    sponsorCollaboratorsModule?: {
      leadSponsor?: { name?: string; class?: string };
    };
    armsInterventionsModule?: {
      interventions?: Array<{ name?: string; type?: string; description?: string; otherNames?: string[] }>;
      armGroups?: Array<{
        label?: string;
        type?: string;
        description?: string;
        interventionNames?: string[];
      }>;
    };
    descriptionModule?: { briefSummary?: string; detailedDescription?: string };
    eligibilityModule?: {
      eligibilityCriteria?: string;
      eligibilityInfo?: { minimumAge?: string; maximumAge?: string; sex?: string };
    };
    outcomesModule?: {
      primaryOutcomes?: Array<{ measure?: string; description?: string; timeFrame?: string }>;
      secondaryOutcomes?: Array<{ measure?: string; description?: string; timeFrame?: string }>;
    };
    contactsLocationsModule?: {
      locations?: Array<{
        facility?: string;
        city?: string;
        state?: string;
        zip?: string;
        country?: string;
        status?: string;
      }>;
    };
  };
  resultsSection?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface AbstractData {
  abstract_id?: string;
  publication_id?: string;
  title?: string;
  source_url?: string; // For web-scraped trials
  arm_results?: Record<string, ArmResult>;
  outcome?: TrialOutcomeRow | null;
  trial?: ClinicalTrialFlat | null;
  landscape?: TrialLandscapeRow | null;
  [key: string]: unknown;
}

/** Flat row from `trial_outcomes` (one record per arm/abstract). */
export type TrialOutcomeRow = Record<string, unknown> & {
  abstract_id?: string;
  nct_id?: string;
  arm_name?: string;
  source?: string;
  conference?: string;
  published_year?: string | number;
  publication_year?: string | number;
  trial_name?: string;
  phase?: string;
  cancer_type?: string[] | string;
  modality?: string;
  num_patients?: number;
  approval_status?: string;
};

/** Subset of `clinical_trials` columns used by the abstract page. */
export interface ClinicalTrialFlat {
  nct_id: string;
  brief_title: string | null;
  overall_status: string | null;
  phases: string[] | null;
  enrollment_count: number | null;
  lead_sponsor_name: string | null;
  lead_sponsor_class: string | null;
  conditions: string[] | null;
}

/** Subset of `trial_landscape` columns used by the abstract page. */
export interface TrialLandscapeRow {
  nct_id: string;
  cancer_type: string | null;
  modality: string | null;
  treatment_name: string | null;
  stage: string | null;
  biomarker: string | null;
  line_of_therapy: string | null;
  acronym: string | null;
}

export interface ArmResult {
  arm_id?: string;
  arm_name?: string;
  attributes?: Record<string, AttributeValue | string | number | boolean | null>;
  [key: string]: unknown;
}

export interface AttributeValue {
  value?: string | number | boolean | null;
  confidence?: number;
  source?: string;
  attribute_type?: string;
}

// Analytics types - matching the backend structure
export interface AnalyticsArmResult {
  arm_id: string;
  arm_name: string;
  total_attributes?: number;
  api_attributes?: number;
  abstract_attributes?: number;
  errors?: string[];
  warnings?: string[];
  attributes: Record<string, AttributeValue | string | number | boolean | null>;
}

export interface AnalyticsAbstract {
  abstract_id?: string;
  publication_id?: string;
  file?: string;
  total_arms: number;
  total_attributes_extracted: number;
  overall_confidence: number;
  processing_time_ms?: number;
  errors: string[];
  warnings: string[];
  arm_results: Record<string, AnalyticsArmResult>;
}

export interface AnalyticsDataResponse {
  total_abstracts: number;
  total_arms: number;
  total_attributes_extracted: number;
  average_confidence: number;
  abstracts: AnalyticsAbstract[];
}

export interface AnalyticsFilters {
  resource_type?: 'all' | 'conference' | 'publication';
  cancer_type?: string;
  therapy_type?: string;
  funding_type?: 'all' | 'industry' | 'non-industry';
  modality?: string;
  line_of_treatment?: string;
  has_metric?: string;
  skip?: number;
  limit?: number;
}

// Landscape statistics types
export interface LandscapeStat {
  cancer_type: string;
  bubble_size: number;
  total_api_count: number;
  extracted_count: number;
}

export interface SelectedTypeStats {
  clinical_trials: number | null;
  pipeline_drugs: number | null;
  drug_targets: number | null;
  biomarkers: number | null;
}

export interface LandscapeStatsResponse {
  landscape: LandscapeStat[];
  selected_type_stats?: SelectedTypeStats;
}

export interface TrialUpdatesCountResponse {
  new_records_added: number;
  updates: number;
  window_end_iso: string | null;
  window_start_iso: string | null;
}

export interface LatestTrialUpdateItem {
  nct_id: string;
  title: string;
  sponsor_name: string | null;
  date_iso: string;
  update_type: 'new' | 'updated';
}

export interface LatestTrialUpdatesResponse {
  trials: LatestTrialUpdateItem[];
}

export interface DashboardTrialCard {
  nct_id: string;
  title: string | null;
  drug_name: string | null;
  sponsor_name: string | null;
  enrollment_count: number | null;
  phase: string;
  study_status: string;
  sponsor_type: string;
  approval_group: string;
  abstract_id?: string | null;
  conference?: string | null;
  published_year?: string | null;
  /** Curated modality from trial_categorization (e.g. Small Molecule, Vaccine). */
  modality?: string | null;
  /** Curated treatment name from trial_categorization LLM extraction. */
  treatment_name?: string | null;
  trial_name?: string | null;
  /** Stage(s) from trial_categorization (e.g. "Stage III", "Stage IV"). */
  stage?: string | null;
  /** Biomarker(s) from trial_categorization. */
  biomarker?: string | null;
  /** Line of therapy from trial_categorization. */
  line_of_therapy?: string | null;
  /** Previous treatment criteria from trial_categorization. */
  previous_treatment_criteria?: string | null;
  /** Whether trial_outcomes records exist for this NCT. */
  has_outcomes?: boolean;
}

export interface DashboardTrialsResponse {
  trials: DashboardTrialCard[];
  total: number;
  /** When balance_by_modality was used, per-modality total counts (overall category size). */
  totals_by_modality?: Record<string, number>;
  /** When balance_by_group was used (stage/biomarker/line_of_therapy/previous_treatment), per-category total counts. */
  totals_by_group?: Record<string, number>;
}

export interface DashboardTrialsFilters {
  phase?: string[];
  has_abstracts?: boolean;
  status?: string[];
  sponsor_type?: string[];
  skip?: number;
  limit?: number;
  /** When true, backend returns up to per_group trials per modality (balanced columns). */
  balance_by_modality?: boolean;
  per_group?: number;
  /** Fetch one modality only (for "Load more"); backend returns trials and total for that modality. */
  modality?: string;
  modality_skip?: number;
  modality_limit?: number;
  /** Balance by category dimension (stage | biomarker | line_of_therapy | previous_treatment); top per_group per category. */
  balance_by_group?: string;
  /** Fetch one category only (for "Load more" in that column). */
  category_filter?: string;
  category_skip?: number;
  category_limit?: number;
  /** When set with limit, fetches open/closed trials in separate DB queries to guarantee the ratio. */
  open_fraction?: number;
}

export interface TherapeuticIndexResponse {
  trials: Trial[];
  total: number;
  skip: number;
  limit: number;
  has_more?: boolean;
}

export interface DiseaseLandscapeStats {
  status: {
    'Overall Status': number;
    'Not yet recruiting': number;
    'Recruiting': number;
    'Active, not recruiting': number;
    'Completed': number;
    'Terminated': number;
    'Enrolling by invitation': number;
    'Suspended': number;
    'Withdrawn': number;
    'Unknown': number;
  };
  phase: {
    'Early Phase 1': number;
    'Phase 1': number;
    'Phase 2': number;
    'Phase 3': number;
    'Phase 4': number;
    'Not applicable': number;
  };
  funder_type: {
    'Industry': number;
    'Non-Industry': number;
  };
  extracted_count?: number;
}

// Live ticker types
export interface LiveTickerArticle {
  title: string;
  date: string;
  url: string;
  nct_ids?: string[] | null;
  has_efficacy?: boolean | null;
  has_safety?: boolean | null;
  efficacy_data?: Record<string, Record<string, string>> | null;
  safety_data?: Record<string, Record<string, string>> | null;
}

export interface LiveTickerEfficacySafety {
  metric: string;
  value: string;
}

export interface LiveTickerResult extends LiveTickerArticle {
  efficacy_or_safety_data: LiveTickerEfficacySafety;
}

export interface LiveTickerResponse {
  articles: LiveTickerArticle[];
  results: LiveTickerResult[];
}

// ─── Column → AttributeType key mapping ────────────────────────────────────────
// Maps every flat column in trial_outcomes to its AttributeType.X key so that
// chart-transformers (which call getAttribute(attributes, 'OBJECTIVE_RESPONSE_RATE') etc.)
// find values without any JSON parsing.
export const OUTCOME_COL_TO_ATTR: Record<string, string> = {
  // Efficacy
  orr:                          'OBJECTIVE_RESPONSE_RATE',
  complete_response:            'COMPLETE_RESPONSE',
  disease_control_rate:         'DISEASE_CONTROL_RATE',
  clinical_benefit_rate:        'CLINICAL_BENEFIT_RATE',
  pathological_complete_response: 'PATHOLOGICAL_COMPLETE_RESPONSE',
  complete_metabolic_response:  'COMPLETE_METABOLIC_RESPONSE',
  median_pfs:                   'MEDIAN_PFS',
  median_os:                    'MEDIAN_OS',
  median_dor:                   'MEDIAN_DOR',
  dor_rate:                     'DOR_RATE',
  median_followup_pfs:          'MEDIAN_FOLLOWUP_PFS',
  median_followup_os:           'MEDIAN_FOLLOWUP_OS',
  hr_pfs:                       'HR_PFS',
  hr_os:                        'HR_OS',
  hr_efs:                       'HR_EFS',
  hr_rfs:                       'HR_RFS',
  hr_mfs:                       'HR_MFS',
  p_value_pfs:                  'P_VALUE_PFS',
  p_value_os:                   'P_VALUE_OS',
  p_value_efs:                  'P_VALUE_EFS',
  p_value_rfs:                  'P_VALUE_RFS',
  efs:                          'EFS',
  rfs:                          'RFS',
  length_rfs:                   'LENGTH_RFS',
  mfs:                          'MFS',
  length_mfs:                   'LENGTH_MFS',
  ttr:                          'TTR',
  ttp:                          'TTP',
  ttnt:                         'TTNT',
  ttf:                          'TTF',
  // PFS rates
  pfs_rate_6m:                  'PFS_RATE_6M',
  pfs_rate_9m:                  'PFS_RATE_9M',
  pfs_rate_12m:                 'PFS_RATE_12M',
  pfs_rate_18m:                 'PFS_RATE_18M',
  pfs_rate_24m:                 'PFS_RATE_24M',
  pfs_rate_36m:                 'PFS_RATE_36M',
  pfs_rate_48m:                 'PFS_RATE_48M',
  // OS rates
  os_rate_6m:                   'OS_RATE_6M',
  os_rate_9m:                   'OS_RATE_9M',
  os_rate_12m:                  'OS_RATE_12M',
  os_rate_18m:                  'OS_RATE_18M',
  os_rate_24m:                  'OS_RATE_24M',
  os_rate_36m:                  'OS_RATE_36M',
  os_rate_48m:                  'OS_RATE_48M',
  // Safety — AE
  ae_pct:                       'AE',
  grade_3_plus_ae_pct:          'GRADE_3_PLUS_AE',
  ae_leading_to_discontinuation:'AE_LEADING_TO_DISCONTINUATION',
  serious_ae:                   'SERIOUS_AE',
  immune_related_ae:            'IMMUNE_RELATED_AE',
  serious_immune_related_ae:    'SERIOUS_IMMUNE_RELATED_AE',
  ae_leading_to_death:          'AE_LEADING_TO_DEATH',
  // Safety — TEAE
  teae_pct:                     'TEAE',
  grade_3_plus_teae_pct:        'GRADE_3_PLUS_TEAE',
  grade_3_teae_pct:             'GRADE_3_TEAE',
  grade_4_teae_pct:             'GRADE_4_TEAE',
  grade_5_teae_pct:             'GRADE_5_TEAE',
  teae_leading_to_discontinuation: 'TEAE_LEADING_TO_DISCONTINUATION',
  teae_leading_to_death:        'TEAE_LEADING_TO_DEATH',
  serious_teae:                 'SERIOUS_TEAE',
  teae_immune_related:          'TEAE_IMMUNE_RELATED',
  // Safety — TRAE
  trae_pct:                     'TRAE',
  grade_3_plus_trae_pct:        'GRADE_3_PLUS_TRAE',
  grade_3_trae_pct:             'GRADE_3_TRAE',
  grade_4_trae_pct:             'GRADE_4_TRAE',
  grade_5_trae_pct:             'GRADE_5_TRAE',
  trae_leading_to_discontinuation: 'TRAE_LEADING_TO_DISCONTINUATION',
  trae_leading_to_death:        'TRAE_LEADING_TO_DEATH',
  trae_immune_related:          'TRAE_IMMUNE_RELATED',
  serious_trae:                 'SERIOUS_TRAE',
  // Patient / study metadata
  num_patients:                 'NUMBER_OF_PATIENTS',
  nct_id:                       'NCT_NUMBER',
  conference:                   'CONFERENCE',
  published_year:               'PUBLISHED_YEAR',
  publication_year:             'PUBLICATION_YEAR',
  trial_name:                   'TRIAL_NAME',
  source_name:                  'PUBLICATION_NAME',
  phase:                        'CLINICAL_TRIAL_PHASE',
  cancer_type:                  'CANCER_TYPE',
  approval_status:              'APPROVAL_STATUS',
};

/**
 * Convert a flat trial_outcomes row into the ClinicalTrialRaw structure that
 * chart-transformers expect (arm_results with attributes keyed as AttributeType.X).
 */
function outcomeRowToClinicalTrialRaw(d: Record<string, unknown>): import('@/types/analytics').ClinicalTrialRaw {
  // Build the attributes map: { 'AttributeType.OBJECTIVE_RESPONSE_RATE': <value>, … }
  const attributes: Record<string, number | string | null> = {};

  for (const [col, attrKey] of Object.entries(OUTCOME_COL_TO_ATTR)) {
    const val = d[col];
    if (val !== null && val !== undefined) {
      attributes[`AttributeType.${attrKey}`] = val as number | string;
    }
  }

  // Handle array columns (e.g. cancer_type is text[] in Supabase)
  if (Array.isArray(d.cancer_type) && d.cancer_type.length > 0) {
    attributes['AttributeType.CANCER_TYPE'] = d.cancer_type[0] as string;
  }

  const armId = String(d.id ?? d.nct_id ?? Math.random());
  const armName = String(d.arm_name ?? 'Unknown');

  return {
    abstract_id: d.abstract_id as string | undefined,
    total_arms: 1,
    total_attributes_extracted: Object.keys(attributes).length,
    overall_confidence: 0.9,
    errors: [],
    warnings: [],
    arm_results: {
      [armId]: {
        arm_id: armId,
        arm_name: armName,
        approval_status: d.approval_status as string | undefined,
        attributes,
      },
    },
  };
}

export const analyticsApi = {
  getData: async (filters: AnalyticsFilters = {}): Promise<TrialDataFile> => {
    const supabase = createClient();

    // Funding partition: Industry = trial_outcomes rows whose nct_id matches a
    // clinical_trials row with lead_sponsor_class='INDUSTRY'. Non-Industry =
    // strict complement (incl. NCTs missing from clinical_trials and NULL class).
    let allowedNctIds: string[] | null = null;
    let excludedNctIds: string[] | null = null;
    if (filters.funding_type === 'industry' || filters.funding_type === 'non-industry') {
      const { data: sponsorData, error: sponsorErr } = await supabase
        .from('clinical_trials')
        .select('nct_id')
        .eq('lead_sponsor_class', 'INDUSTRY')
        .limit(50000);
      if (sponsorErr) throw sponsorErr;
      const industryIds = (sponsorData || []).map(r => r.nct_id as string).filter(Boolean);
      if (filters.funding_type === 'industry') {
        if (industryIds.length === 0) {
          return { total_abstracts: 0, total_arms: 0, total_attributes_extracted: 0, average_confidence: 0.9, abstracts: [] };
        }
        allowedNctIds = industryIds;
      } else {
        excludedNctIds = industryIds;
      }
    }

    let query = supabase.from('trial_outcomes').select('*').limit(filters.limit || 200);
    if (filters.skip) query = query.range(filters.skip, filters.skip + (filters.limit || 200) - 1);

    if (filters.cancer_type && filters.cancer_type !== 'All') {
      query = query.contains('cancer_type', [getDbCancerType(filters.cancer_type)]);
    }
    if (filters.modality) {
      query = query.eq('modality', filters.modality);
    }
    if (filters.therapy_type && filters.therapy_type !== 'all') {
      query = query.eq('type_of_therapy', filters.therapy_type);
    }
    if (filters.resource_type === 'conference') {
      query = query.eq('source_type', 'abstract');
    } else if (filters.resource_type === 'publication') {
      query = query.eq('source_type', 'publication');
    }
    if (allowedNctIds) {
      query = query.in('nct_id', allowedNctIds);
    }
    if (excludedNctIds && excludedNctIds.length > 0) {
      query = query.not('nct_id', 'in', `(${excludedNctIds.join(',')})`);
    }

    const { data, error } = await query;
    if (error) throw error;

    // Map each flat row into ClinicalTrialRaw so chart-transformers can read
    // attribute values directly without any JSON parsing.
    const abstracts = (data || []).map(d => outcomeRowToClinicalTrialRaw(d as Record<string, unknown>));

    return {
      total_abstracts: abstracts.length,
      total_arms: abstracts.length,
      total_attributes_extracted: abstracts.reduce((s, a) => s + a.total_attributes_extracted, 0),
      average_confidence: 0.9,
      abstracts,
    };
  },

  getTreatmentMeta: async (
    cancerType: string,
  ): Promise<Array<{ treatmentName: string; modality: string | null; lineOfTreatment: string | null; stage: string | null; biomarker: string | null; nctId: string | null }>> => {
    const supabase = createClient();
    const dbCancerType = getDbCancerType(cancerType);
    const { data: outcomesData, error: outcomesError } = await supabase
      .from('trial_outcomes')
      .select('arm_name, nct_id, modality')
      .contains('cancer_type', [dbCancerType]);
    if (outcomesError) console.error('[getTreatmentMeta] trial_outcomes query failed:', outcomesError.message);

    const nctIds = [...new Set(
      (outcomesData || []).map((d: Record<string, unknown>) => d.nct_id as string).filter(Boolean)
    )];
    const landscapeByNct = new Map<string, { line_of_therapy: string | null; stage: string | null; biomarker: string | null }>();
    if (nctIds.length > 0) {
      const { data: landscapeData, error: landscapeError } = await supabase
        .from('trial_landscape')
        .select('nct_id, line_of_therapy, stage, biomarker')
        .in('nct_id', nctIds);
      if (landscapeError) console.error('[getTreatmentMeta] trial_landscape query failed:', landscapeError.message);
      for (const d of (landscapeData || []) as Record<string, unknown>[]) {
        landscapeByNct.set(d.nct_id as string, {
          line_of_therapy: (d.line_of_therapy as string) || null,
          stage: (d.stage as string) || null,
          biomarker: (d.biomarker as string) || null,
        });
      }
    }

    return (outcomesData || [])
      .filter((d: Record<string, unknown>) => d.arm_name)
      .map((d: Record<string, unknown>) => {
        const landscape = landscapeByNct.get(d.nct_id as string);
        return {
          treatmentName: d.arm_name as string,
          modality: (d.modality as string) || null,
          lineOfTreatment: landscape?.line_of_therapy ?? null,
          stage: landscape?.stage ?? null,
          biomarker: landscape?.biomarker ?? null,
          nctId: (d.nct_id as string) || null,
        };
      });
  },

  getSnapshot: async (cancer_type: string, resource_type = 'all', bubbleLimit = 8, barLimit = 8): Promise<SnapshotResponse> => {
    void resource_type; // reserved for future filtering; keep signature stable
    // Reuse the same data + transformer pipeline as the analytics page so bubble
    // positions are always identical to what the full page shows.
    const { transformBubbleChartData } = await import('@/lib/chart-transformers');

    const analyticsData = await analyticsApi.getData({
      cancer_type,
      limit: 500,
    });

    const totalAbstracts = analyticsData.total_abstracts || 0;

    // Same defaults as analytics page — ORR (Y) vs G3+ TRAE (X), bubble size = num patients
    const bubblePoints = transformBubbleChartData(analyticsData, {
      efficacyMetric: 'OBJECTIVE_RESPONSE_RATE',
      safetyMetric: 'GRADE_3_PLUS_TRAE',
      zMetric: 'NUMBER_OF_PATIENTS',
      minTrialCount: 1,
    });

    const bubbleArray: SnapshotBubblePoint[] = bubblePoints
      .slice(0, bubbleLimit)
      .map(p => ({
        treatmentName: p.treatmentName,
        efficacy: p.efficacy ?? 0,
        safety: p.safety ?? 0,
        numberOfPatients: p.numberOfPatients ?? null,
        trialCount: p.allTrials?.length ?? 1,
      }));

    // Bar uses same source, sorted by efficacy, independently sliced
    const barArray: SnapshotBarPoint[] = bubblePoints
      .filter(p => (p.efficacy ?? 0) > 0)
      .sort((a, b) => (b.efficacy ?? 0) - (a.efficacy ?? 0))
      .slice(0, barLimit)
      .map(p => ({
        treatmentName: p.treatmentName,
        averageValue: p.efficacy ?? 0,
        trialCount: p.allTrials?.length ?? 1,
      }));

    return { bubble: bubbleArray, bar: barArray, totalAbstracts };
  },


};

/** Pre-aggregated bubble data point (ORR + TRAE) returned by /api/analytics/snapshot */
export interface SnapshotBubblePoint {
  treatmentName: string;
  efficacy: number;       // avg ORR
  safety: number;         // avg Grade 3+ TRAE
  numberOfPatients: number | null;
  trialCount: number;
}

/** Pre-aggregated bar data point (ORR) returned by /api/analytics/snapshot */
export interface SnapshotBarPoint {
  treatmentName: string;
  averageValue: number;   // avg ORR
  trialCount: number;
}

export interface SnapshotResponse {
  bubble: SnapshotBubblePoint[];
  bar: SnapshotBarPoint[];
  totalAbstracts: number;
}


