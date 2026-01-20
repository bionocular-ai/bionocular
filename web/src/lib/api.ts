import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
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

  getLandscapeStats: async (): Promise<LandscapeStatsResponse> => {
    const response = await apiClient.get<LandscapeStatsResponse>('/api/landscape/stats');
    return response.data;
  },

  getTherapeuticIndex: async (skip = 0, limit = 100): Promise<TherapeuticIndexResponse> => {
    const response = await apiClient.get<TherapeuticIndexResponse>('/api/landscape/therapeutic-index', {
      params: { skip, limit },
    });
    return response.data;
  },

  getDiseaseLandscapeStats: async (category: string): Promise<DiseaseLandscapeStats> => {
    const response = await apiClient.get<DiseaseLandscapeStats>(`/api/landscape/disease-stats/${category}`);
    return response.data;
  },
};

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

export interface LandscapeStatsResponse {
  landscape: LandscapeStat[];
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

