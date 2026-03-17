import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60s - dashboard-trials can be slow on cold start / large result sets
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.code === 'ECONNABORTED' && error.message?.includes('timeout')) {
      throw new Error(
        `Backend request timed out. The server may be starting or under load. Please try again in a moment.`
      );
    }
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
      throw new Error(
        `Cannot connect to backend API at ${API_BASE_URL}. Please ensure the server is running.`
      );
    }
    if (error.response) {
      // Server responded with error status
      const message =
        (error.response.data as { detail?: string })?.detail ||
        error.message ||
        'An error occurred';
      throw new Error(message);
    }
    throw error;
  }
);

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
    const response = await apiClient.get<TrialsResponse>('/api/trials', {
      params: { skip, limit },
    });
    return response.data;
  },

  getById: async (id: string): Promise<Document> => {
    const response = await apiClient.get<Document>(`/api/trials/${id}`);
    return response.data;
  },

  getByNctId: async (nctId: string, skip = 0, limit = 100): Promise<TrialsResponse> => {
    const response = await apiClient.get<TrialsResponse>(`/api/trials/nct/${nctId}`, {
      params: { skip, limit },
    });
    return response.data;
  },

  getByAbstractId: async (abstractId: string): Promise<AbstractData> => {
    const response = await apiClient.get<AbstractData>(`/api/trials/abstract/${abstractId}`);
    return response.data;
  },

  getLandscapeStats: async (cancerType?: string): Promise<LandscapeStatsResponse> => {
    const response = await apiClient.get<LandscapeStatsResponse>('/api/landscape/stats', {
      params: cancerType ? { cancer_type: cancerType } : undefined,
    });
    return response.data;
  },

  getTrialUpdatesCount: async (
    cancerType: string,
    days: number = 30
  ): Promise<TrialUpdatesCountResponse> => {
    const response = await apiClient.get<TrialUpdatesCountResponse>(
      '/api/landscape/trial-updates-count',
      { params: { cancer_type: cancerType, days } }
    );
    return response.data;
  },

  getLatestTrialUpdates: async (
    cancerType: string,
    limit: number = 5
  ): Promise<LatestTrialUpdatesResponse> => {
    const response = await apiClient.get<LatestTrialUpdatesResponse>(
      '/api/landscape/latest-trial-updates',
      { params: { cancer_type: cancerType, limit } }
    );
    return response.data;
  },

  getDashboardTrials: async (
    cancerType: string,
    filters: DashboardTrialsFilters = {}
  ): Promise<DashboardTrialsResponse> => {
    const params: Record<string, string | number | boolean> = {};
    if (filters.phase?.length) {
      params.phase = filters.phase.join(',');
    }
    if (filters.has_abstracts === true) params.has_abstracts = true;
    if (filters.status?.length) params.status = filters.status.join(',');
    if (filters.sponsor_type?.length) params.sponsor_type = filters.sponsor_type.join(',');
    if (filters.skip != null) params.skip = filters.skip;
    if (filters.limit != null) params.limit = filters.limit;
    if (filters.balance_by_modality === true) params.balance_by_modality = true;
    if (filters.per_group != null) params.per_group = filters.per_group;
    if (filters.modality != null) params.modality = filters.modality;
    if (filters.modality_skip != null) params.modality_skip = filters.modality_skip;
    if (filters.modality_limit != null) params.modality_limit = filters.modality_limit;
    if (filters.balance_by_group != null) params.balance_by_group = filters.balance_by_group;
    if (filters.category_filter != null) params.category_filter = filters.category_filter;
    if (filters.category_skip != null) params.category_skip = filters.category_skip;
    if (filters.category_limit != null) params.category_limit = filters.category_limit;
    const response = await apiClient.get<DashboardTrialsResponse>(
      '/api/landscape/dashboard-trials',
      { params: { cancer_type: cancerType, ...params } }
    );
    return response.data;
  },

  getTherapeuticIndex: async (skip = 0, limit = 100): Promise<TherapeuticIndexResponse> => {
    const response = await apiClient.get<TherapeuticIndexResponse>('/api/landscape/therapeutic-index', {
      params: { skip, limit },
    });
    return response.data;
  },

  getDiseaseLandscapeStats: async (
    category: string,
    opts?: { sponsor_type?: string }
  ): Promise<DiseaseLandscapeStats> => {
    const params = new URLSearchParams();
    if (opts?.sponsor_type) params.set('sponsor_type', opts.sponsor_type);
    const qs = params.toString();
    const url = `/api/landscape/disease-stats/${category}${qs ? `?${qs}` : ''}`;
    const response = await apiClient.get<DiseaseLandscapeStats>(url);
    return response.data;
  },

  getLiveTicker: async (category: string): Promise<LiveTickerResponse> => {
    const response = await apiClient.get<LiveTickerResponse>(`/api/landscape/live-ticker/${category}`);
    return response.data;
  },

  /** Full trial API data from clinical_trials_cache (ClinicalTrials.gov API v2 response). */
  getTrialDetail: async (nctId: string): Promise<TrialDetailApiResponse> => {
    const response = await apiClient.get<TrialDetailApiResponse>(`/api/landscape/trial/${nctId}`);
    return response.data;
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
    const params = new URLSearchParams();

    if (filters.skip !== undefined) {
      params.append('skip', filters.skip.toString());
    }
    if (filters.limit !== undefined) {
      params.append('limit', filters.limit.toString());
    } else {
      params.append('limit', '2000'); // Default limit
    }
    if (filters.resource_type && filters.resource_type !== 'all') {
      params.append('resource_type', filters.resource_type);
    }
    if (filters.cancer_type) {
      params.append('cancer_type', filters.cancer_type);
    }
    if (filters.therapy_type && filters.therapy_type !== 'all') {
      params.append('therapy_type', filters.therapy_type);
    }
    if (filters.funding_type && filters.funding_type !== 'all') {
      params.append('funding_type', filters.funding_type);
    }
    if (filters.line_of_treatment && filters.line_of_treatment !== 'all') {
      params.append('line_of_treatment', filters.line_of_treatment);
    }
    if (filters.has_metric) {
      params.append('has_metric', filters.has_metric);
    }

    const response = await apiClient.get<AnalyticsDataResponse>(`/api/analytics/data?${params.toString()}`);
    return response.data;
  },
};

