import { createClient } from './supabase/client';

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

export const trialsApi = {
  getAll: async (skip = 0, limit = 100): Promise<TrialsResponse> => {
    const supabase = createClient();
    const { data, count } = await supabase.from('clinical_trials_cache').select('nct_id, api_response_json', { count: 'exact' }).range(skip, skip + limit - 1);
    
    const trials: Trial[] = (data || []).map(d => {
       const apiResp: any = d.api_response_json || {};
       const protocol = apiResp.protocolSection || {};
       return {
         id: d.nct_id,
         nct_id: d.nct_id,
         title: protocol.identificationModule?.briefTitle || d.nct_id,
         phase: (protocol.designModule?.phases || []).join(', '),
         sponsor: protocol.sponsorCollaboratorsModule?.leadSponsor?.name || 'Unknown',
         status: protocol.statusModule?.overallStatus || 'Unknown',
       };
    });
    return { trials, total: count || 0, skip, limit };
  },

  getById: async (id: string): Promise<Document> => {
    throw new Error("Documents obsolete");
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

  getByAbstractId: async (abstractId: string): Promise<AbstractData> => {
    const supabase = createClient();
    const { data } = await supabase.from('trial_outcomes').select('*').eq('abstract_id', abstractId).single();
    if (!data) return { abstract_id: abstractId };
    return { abstract_id: data.abstract_id, source_url: data.source, arm_results: data.arm_results as any, title: '' };
  },

  getLandscapeStats: async (cancerType?: string): Promise<LandscapeStatsResponse> => {
    const supabase = createClient();
    let query = supabase.from('trial_landscape').select('cancer_type');
    if (cancerType) query = query.eq('cancer_type', cancerType);
    
    const { data: landscape } = await query;
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
    return { landscape: landscapeStats, selected_type_stats: { clinical_trials: landscape?.length || 0, pipeline_drugs: null, drug_targets: null, biomarkers: null } };
  },

  getTrialUpdatesCount: async (
    cancerType: string,
    days: number = 30
  ): Promise<TrialUpdatesCountResponse> => {
    const supabase = createClient();
    const d = new Date();
    d.setDate(d.getDate() - days);
    
    const { count, error } = await supabase
      .from('trial_landscape')
      .select('*', { count: 'exact', head: true })
      .eq('cancer_type', cancerType)
      .gte('created_at', d.toISOString());
      
    if (error) throw error;
    
    return {
      new_records_added: count || 0,
      updates: count || 0,
      window_end_iso: new Date().toISOString(),
      window_start_iso: d.toISOString()
    };
  },

  getLatestTrialUpdates: async (
    cancerType: string,
    limit: number = 5
  ): Promise<LatestTrialUpdatesResponse> => {
    const supabase = createClient();
    // We fetch recent trial_landscape records and their clinical_trials data
    const { data, error } = await supabase
      .from('trial_landscape')
      .select(`
        nct_id,
        created_at,
        clinical_trials_cache (
          api_response_json
        )
      `)
      .eq('cancer_type', cancerType)
      .order('created_at', { ascending: false })
      .limit(limit);
      
    if (error) throw error;
    
    const trials = data.map(d => {
      // safely extract nested properties
      const ctEntry = Array.isArray(d.clinical_trials_cache) ? d.clinical_trials_cache[0] : d.clinical_trials_cache;
      const apiResp: any = ctEntry?.api_response_json || {};
      const protocol = apiResp.protocolSection || {};
      
      return {
        nct_id: d.nct_id || '',
        title: protocol.identificationModule?.briefTitle || 'Unknown Title',
        sponsor_name: protocol.sponsorCollaboratorsModule?.leadSponsor?.name || 'Unknown Sponsor',
        date_iso: d.created_at || new Date().toISOString(),
        update_type: 'updated' as const
      };
    });
    
    return { trials };
  },

  getDashboardTrials: async (
    cancerType: string,
    filters: DashboardTrialsFilters = {}
  ): Promise<DashboardTrialsResponse> => {
    const supabase = createClient();
    let query = supabase.from('v_clinical_trials_with_results')
      .select('*, clinical_trials(api_response_json)')
      .eq('cancer_type', cancerType);
      
    if (filters.modality) query = query.eq('modality', filters.modality);
    
    const { data } = await query;
    if (!data) return { trials: [], total: 0 };
    
    let trials: DashboardTrialCard[] = data.map(d => {
       const ctEntry = Array.isArray(d.clinical_trials) ? d.clinical_trials[0] : d.clinical_trials;
       const apiResp: any = ctEntry?.api_response_json || {};
       const protocol = apiResp.protocolSection || {};
       const phases = protocol.designModule?.phases || [];
       
       return {
         nct_id: d.nct_id || '',
         title: protocol.identificationModule?.briefTitle || null,
         drug_name: d.treatment_name || null,
         sponsor_name: protocol.sponsorCollaboratorsModule?.leadSponsor?.name || null,
         enrollment_count: protocol.designModule?.enrollmentInfo?.count || null,
         phase: phases.join(', ') || 'Unknown',
         study_status: protocol.statusModule?.overallStatus || 'Unknown',
         sponsor_type: protocol.sponsorCollaboratorsModule?.leadSponsor?.class || 'Unknown',
         approval_group: 'Investigational',
         modality: d.modality || null,
         treatment_name: d.treatment_name || null,
         stage: d.stage || null,
         biomarker: d.biomarker || null,
         line_of_therapy: d.line_of_therapy || null,
         previous_treatment_criteria: d.previous_treatment_criteria || null,
         has_outcomes: d.has_outcomes || false,
       };
    });
    
    if (filters.phase && filters.phase.length > 0) {
       trials = trials.filter(t => filters.phase!.some(p => t.phase.includes(p)));
    }
    if (filters.sponsor_type && filters.sponsor_type.length > 0) {
       trials = trials.filter(t => filters.sponsor_type!.includes(t.sponsor_type));
    }
    
    const total = trials.length;
    if (filters.skip !== undefined || filters.limit !== undefined) {
       trials = trials.slice(filters.skip || 0, (filters.skip || 0) + (filters.limit || 100));
    }
    
    return { trials, total };
  },

  getTherapeuticIndex: async (skip = 0, limit = 100): Promise<TherapeuticIndexResponse> => {
    const supabase = createClient();
    const { data, count } = await supabase.from('trial_landscape').select('nct_id, clinical_trials_cache(api_response_json)', { count: 'exact' }).range(skip, skip + limit - 1);
    
    const trials: Trial[] = (data || []).map(d => {
       const ctEntry = Array.isArray(d.clinical_trials_cache) ? d.clinical_trials_cache[0] : d.clinical_trials_cache;
       const apiResp: any = ctEntry?.api_response_json || {};
       const protocol = apiResp.protocolSection || {};
       return {
         id: d.nct_id,
         nct_id: d.nct_id,
         title: protocol.identificationModule?.briefTitle || d.nct_id,
         phase: (protocol.designModule?.phases || []).join(', '),
         sponsor: protocol.sponsorCollaboratorsModule?.leadSponsor?.name || 'Unknown',
         status: protocol.statusModule?.overallStatus || 'Unknown',
       };
    });
    return { trials, total: count || 0, skip, limit, has_more: (count || 0) > skip + limit - 1 };
  },

  getDiseaseLandscapeStats: async (
    category: string,
    opts?: { sponsor_type?: string }
  ): Promise<DiseaseLandscapeStats> => {
    const supabase = createClient();
    const { data } = await supabase.from('trial_landscape')
      .select('nct_id, clinical_trials_cache(api_response_json)')
      .eq('cancer_type', category);
      
    const stats: DiseaseLandscapeStats = {
      status: { 'Overall Status': 0, 'Not yet recruiting': 0, 'Recruiting': 0, 'Active, not recruiting': 0, 'Completed': 0, 'Terminated': 0, 'Enrolling by invitation': 0, 'Suspended': 0, 'Withdrawn': 0, 'Unknown': 0 },
      phase: { 'Early Phase 1': 0, 'Phase 1': 0, 'Phase 2': 0, 'Phase 3': 0, 'Phase 4': 0, 'Not applicable': 0 },
      funder_type: { 'Industry': 0, 'Non-Industry': 0 },
      extracted_count: data?.length || 0
    };
    
    data?.forEach(d => {
       const ctEntry = Array.isArray(d.clinical_trials) ? d.clinical_trials[0] : d.clinical_trials;
       const apiResp: any = ctEntry?.api_response_json || {};
       const protocol = apiResp.protocolSection || {};
       const pStatus = protocol.statusModule?.overallStatus || 'Unknown';
       const phases = protocol.designModule?.phases || [];
       const sClass = protocol.sponsorCollaboratorsModule?.leadSponsor?.class;
       
       stats.status['Overall Status']++;
       if (stats.status[pStatus as keyof typeof stats.status] !== undefined) {
           stats.status[pStatus as keyof typeof stats.status]++;
       } else {
           stats.status['Unknown']++;
       }
       
       phases.forEach((p: string) => {
           if (stats.phase[p as keyof typeof stats.phase] !== undefined) {
               stats.phase[p as keyof typeof stats.phase]++;
           }
       });
       
       if (sClass === 'INDUSTRY') stats.funder_type['Industry']++;
       else stats.funder_type['Non-Industry']++;
    });
    return stats;
  },

  getLiveTicker: async (category: string): Promise<LiveTickerResponse> => {
    const supabase = createClient();
    const { data, error } = await supabase
      .from('news_feed')
      .select('*')
      .eq('cancer_type', category)
      .limit(100);
      
    if (error) throw error;
    
    const articles = data.map(d => ({
      title: d.title,
      date: d.date,
      url: d.url,
      nct_id: d.nct_id
    }));
    
    return { articles, results: [] };
  },

  /** Full trial API data from clinical_trials_cache (ClinicalTrials.gov API v2 response). */
  getTrialDetail: async (nctId: string): Promise<TrialDetailApiResponse> => {
    const supabase = createClient();
    const { data, error } = await supabase
      .from('clinical_trials')
      .select('api_response_json')
      .eq('nct_number', nctId)
      .single();
      
    if (error) throw error;
    return (data?.api_response_json || {}) as TrialDetailApiResponse;
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
  [key: string]: unknown;
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
  nct_id?: string | null;
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

export const analyticsApi = {
  getData: async (filters: AnalyticsFilters = {}): Promise<AnalyticsDataResponse> => {
    const supabase = createClient();
    let query = supabase.from('trial_outcomes').select('*').limit(filters.limit || 200);
    if (filters.skip) query = query.range(filters.skip, filters.skip + (filters.limit || 200) - 1);
    
    if (filters.cancer_type && filters.cancer_type !== 'All') {
      query = query.contains('cancer_type', [filters.cancer_type]);
    }
    
    const { data } = await query;
    const trials = (data || []).map(d => ({
       id: d.id,
       nct_id: d.nct_id,
       source: d.source_name,
       arm_name: d.arm_name,
       orr: d.orr,
       median_pfs: d.median_pfs,
       median_os: d.median_os,
       grade_3_plus_ae_pct: d.grade_3_plus_ae_pct,
       num_patients: d.num_patients,
       is_nr: d.is_nr || []
    }));
    
    return {
       total_abstracts: trials.length,
       total_arms: trials.length,
       total_attributes_extracted: trials.length * 10, // heuristic
       average_confidence: 0.9,
       abstracts: trials as any // Re-mapping briefly to avoid breaking upstream consumers if any
    };
  },

  getSnapshot: async (cancer_type: string, resource_type = 'all', bubbleLimit = 8, barLimit = 8): Promise<SnapshotResponse> => {
    const supabase = createClient();
    // Query the flattened outcomes directly
    let query = supabase.from('trial_outcomes').select('arm_name, orr, grade_3_plus_trae_pct, num_patients');
    
    if (cancer_type && cancer_type !== 'All') {
      query = query.contains('cancer_type', [cancer_type]);
    }

    
    const { data } = await query.limit(500);
    
    const bubbles: Record<string, any> = {};
    const totalAbstracts = data?.length || 0;
    
    data?.forEach(row => {
      const name = row.arm_name || "Unknown";
      if (!bubbles[name]) {
        bubbles[name] = { 
          treatmentName: name, 
          approvalStatus: 'Investigational', 
          efficacy: 0, 
          safety: 0, 
          numberOfPatients: 0, 
          trialCount: 0, 
          effCount: 0, 
          safCount: 0 
        };
      }
      
      if (row.orr != null) {
        bubbles[name].efficacy += row.orr;
        bubbles[name].effCount++;
      }
      if (row.grade_3_plus_trae_pct != null) {
        bubbles[name].safety += row.grade_3_plus_trae_pct;
        bubbles[name].safCount++;
      }
      if (row.num_patients != null) {
        bubbles[name].numberOfPatients += row.num_patients;
      }
      bubbles[name].trialCount++;
    });
    
    const bubbleArray: SnapshotBubblePoint[] = Object.values(bubbles)
      .map((b: any) => ({
        treatmentName: b.treatmentName,
        approvalStatus: b.approvalStatus as 'Approved' | 'Investigational',
        efficacy: b.effCount > 0 ? b.efficacy / b.effCount : 0,
        safety: b.safCount > 0 ? b.safety / b.safCount : 0,
        numberOfPatients: b.numberOfPatients,
        trialCount: b.trialCount
      }))
      .filter(b => b.efficacy > 0)
      .sort((a, b) => b.efficacy - a.efficacy)
      .slice(0, bubbleLimit);
    
    const barArray: SnapshotBarPoint[] = bubbleArray.map(b => ({
      treatmentName: b.treatmentName,
      approvalStatus: b.approvalStatus,
      averageValue: b.efficacy,
      trialCount: b.trialCount
    }));
    
    return { bubble: bubbleArray, bar: barArray, totalAbstracts };
  },
};

/** Pre-aggregated bubble data point (ORR + TRAE) returned by /api/analytics/snapshot */
export interface SnapshotBubblePoint {
  treatmentName: string;
  approvalStatus: 'Approved' | 'Investigational';
  efficacy: number;       // avg ORR
  safety: number;         // avg Grade 3+ TRAE
  numberOfPatients: number | null;
  trialCount: number;
}

/** Pre-aggregated bar data point (ORR) returned by /api/analytics/snapshot */
export interface SnapshotBarPoint {
  treatmentName: string;
  approvalStatus: 'Approved' | 'Investigational';
  averageValue: number;   // avg ORR
  trialCount: number;
}

export interface SnapshotResponse {
  bubble: SnapshotBubblePoint[];
  bar: SnapshotBarPoint[];
  totalAbstracts: number;
}


