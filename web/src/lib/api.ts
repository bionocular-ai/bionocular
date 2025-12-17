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
};

export interface AbstractData {
  abstract_id?: string;
  publication_id?: string;
  title?: string;
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

export const analyticsApi = {
  getData: async (): Promise<AnalyticsDataResponse> => {
    const response = await apiClient.get<AnalyticsDataResponse>('/api/analytics/data?limit=2000');
    return response.data;
  },
};

