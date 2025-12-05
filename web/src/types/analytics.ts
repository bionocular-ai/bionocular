/**
 * Analytics Types for Clinical Trial Data Visualization
 * Used by chart components for Head-to-Head comparisons and efficacy analysis
 */

// ============================================================================
// Raw Data Types (matching the deployed JSON structure)
// ============================================================================

export interface AttributeValue {
  value: string | number | boolean | null;
  confidence: number;
  source: string;
  source_chunks?: string[];
  validation_status?: string;
  validation_errors?: string[];
  extracted_at?: string;
  context_chunks?: number;
}

export interface ArmAttributes {
  [key: string]: AttributeValue | string | number | boolean | null | undefined;
}

export interface ArmResult {
  arm_id: string;
  arm_name: string;
  total_attributes?: number;
  api_attributes?: number;
  abstract_attributes?: number;
  errors?: string[];
  warnings?: string[];
  attributes: ArmAttributes;
}

export interface ClinicalTrialRaw {
  // For abstracts
  abstract_id?: string;
  // For publications
  publication_id?: string;
  file?: string;
  // Common fields
  total_arms: number;
  total_attributes_extracted: number;
  overall_confidence: number;
  processing_time_ms?: number;
  errors: string[];
  warnings: string[];
  arm_results: Record<string, ArmResult>;
}

export interface TrialDataFile {
  total_abstracts?: number;
  total_publications?: number;
  total_arms: number;
  total_attributes_extracted: number;
  average_confidence: number;
  total_processing_time_ms?: number;
  abstracts?: ClinicalTrialRaw[];
  publications?: ClinicalTrialRaw[];
}

// ============================================================================
// Transformed Data Types (for chart components)
// ============================================================================

export type ApprovalStatus = 'Approved' | 'Investigational' | 'Unknown';

export interface TrialDataPoint {
  studyId: string;
  value: number;
  citation: string;
  phase: string;
  year: string;
  nctNumber: string;
  numberOfPatients: number | null;
}

export interface HeadToHeadDataPoint {
  treatmentName: string;
  approvalStatus: ApprovalStatus;
  averageValue: number;
  medianValue: number;
  minValue: number;
  maxValue: number;
  trialCount: number;
  totalPatients: number;
  // Individual trial dots for scatter overlay
  trials: TrialDataPoint[];
}

// ============================================================================
// Chart Configuration Types
// ============================================================================

export type EfficacyMetric = 
  | 'MEDIAN_PFS' 
  | 'MEDIAN_OS' 
  | 'HR_PFS' 
  | 'HR_OS';

export interface MetricConfig {
  key: EfficacyMetric;
  label: string;
  unit: string;
  description: string;
  lowerIsBetter?: boolean; // For HR metrics
}

export const EFFICACY_METRICS: Record<EfficacyMetric, MetricConfig> = {
  MEDIAN_PFS: {
    key: 'MEDIAN_PFS',
    label: 'Median PFS',
    unit: 'months',
    description: 'Median Progression-Free Survival',
  },
  MEDIAN_OS: {
    key: 'MEDIAN_OS',
    label: 'Median OS',
    unit: 'months',
    description: 'Median Overall Survival',
  },
  HR_PFS: {
    key: 'HR_PFS',
    label: 'HR (PFS)',
    unit: '',
    description: 'Hazard Ratio for Progression-Free Survival',
    lowerIsBetter: true,
  },
  HR_OS: {
    key: 'HR_OS',
    label: 'HR (OS)',
    unit: '',
    description: 'Hazard Ratio for Overall Survival',
    lowerIsBetter: true,
  },
};

// ============================================================================
// Filter Types
// ============================================================================

export interface ChartFilters {
  selectedTreatments: string[];
  selectedMetric: EfficacyMetric;
  minTrialCount: number;
  selectedPhases: string[];
  yearRange: [number, number];
}

export const DEFAULT_CHART_FILTERS: ChartFilters = {
  selectedTreatments: [],
  selectedMetric: 'MEDIAN_OS',
  minTrialCount: 1,
  selectedPhases: [],
  yearRange: [2015, 2025],
};

