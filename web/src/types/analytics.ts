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
  approval_status?: string; // Added by backend: "Approved", "Investigational", "Control", or "Unknown"
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
  // For web-scraped trials
  source_url?: string;
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

export type SourceType = 'abstract' | 'publication' | 'webscrape';

export interface TrialDataPoint {
  studyId: string;
  abstractId: string;
  publicationName: string;
  trialName: string;
  value: number;
  citation: string;
  phase: string;
  year: string;
  nctNumber: string;
  numberOfPatients: number | null;
  sourceUrl?: string;
  sourceType?: SourceType;
}

export interface HeadToHeadDataPoint {
  treatmentName: string;
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

export type EfficacyMetric = string; // Allow any efficacy metric string
export type SafetyMetric = string; // Allow any safety metric string
export type ChartMetric = string; // Allow any metric string

export interface MetricConfig {
  key: string;
  label: string;
  unit: string;
  description: string;
  lowerIsBetter?: boolean;
  subGroup?: string;
  integer?: boolean;
  pValue?: boolean;
}

// Efficacy metrics configuration - keys match backend AttributeType names
export const EFFICACY_METRICS: Record<string, MetricConfig> = {
  // Study metadata
  NUMBER_OF_PATIENTS: { key: 'NUMBER_OF_PATIENTS', label: 'N', unit: '', description: 'Number of patients enrolled', subGroup: 'Study', integer: true },

  // Survival Metrics - PFS
  MEDIAN_PFS: { key: 'MEDIAN_PFS', label: 'mPFS', unit: 'months', description: 'Median Progression-Free Survival', subGroup: 'PFS' },
  MEDIAN_FOLLOWUP_PFS: { key: 'MEDIAN_FOLLOWUP_PFS', label: 'PFS FU', unit: 'months', description: 'Median follow-up for measuring PFS', subGroup: 'PFS' },
  P_VALUE_PFS: { key: 'P_VALUE_PFS', label: 'p (PFS)', unit: '', description: 'p-value of median PFS', lowerIsBetter: true, pValue: true, subGroup: 'PFS' },
  HR_PFS: { key: 'HR_PFS', label: 'HR (PFS)', unit: '', description: 'Hazard Ratio for PFS', lowerIsBetter: true, subGroup: 'PFS' },

  // Survival Metrics - OS
  MEDIAN_OS: { key: 'MEDIAN_OS', label: 'mOS', unit: 'months', description: 'Median Overall Survival', subGroup: 'OS' },
  MEDIAN_FOLLOWUP_OS: { key: 'MEDIAN_FOLLOWUP_OS', label: 'OS FU', unit: 'months', description: 'Median follow-up for measuring OS', subGroup: 'OS' },
  P_VALUE_OS: { key: 'P_VALUE_OS', label: 'p (OS)', unit: '', description: 'p-value of OS', lowerIsBetter: true, pValue: true, subGroup: 'OS' },
  HR_OS: { key: 'HR_OS', label: 'HR (OS)', unit: '', description: 'Hazard Ratio for OS', lowerIsBetter: true, subGroup: 'OS' },

  // Response Metrics
  OBJECTIVE_RESPONSE_RATE: { key: 'OBJECTIVE_RESPONSE_RATE', label: 'ORR', unit: '%', description: 'Objective Response Rate', subGroup: 'Response' },
  COMPLETE_RESPONSE: { key: 'COMPLETE_RESPONSE', label: 'CR', unit: '%', description: 'Complete Response', subGroup: 'Response' },
  PATHOLOGICAL_COMPLETE_RESPONSE: { key: 'PATHOLOGICAL_COMPLETE_RESPONSE', label: 'pCR', unit: '%', description: 'Pathological Complete Response', subGroup: 'Response' },
  COMPLETE_METABOLIC_RESPONSE: { key: 'COMPLETE_METABOLIC_RESPONSE', label: 'CMR', unit: '%', description: 'Complete Metabolic Response', subGroup: 'Response' },
  DISEASE_CONTROL_RATE: { key: 'DISEASE_CONTROL_RATE', label: 'DCR', unit: '%', description: 'Disease Control Rate', subGroup: 'Response' },
  CLINICAL_BENEFIT_RATE: { key: 'CLINICAL_BENEFIT_RATE', label: 'CBR', unit: '%', description: 'Clinical Benefit Rate', subGroup: 'Response' },
  MEDIAN_DOR: { key: 'MEDIAN_DOR', label: 'mDOR', unit: 'months', description: 'Median Duration of Response', subGroup: 'Response' },
  DOR_RATE: { key: 'DOR_RATE', label: 'DOR', unit: '%', description: 'Duration of Response Rate', subGroup: 'Response' },

  // PFS Rate at various timepoints
  PFS_RATE_6M: { key: 'PFS_RATE_6M', label: 'PFS 6M', unit: '%', description: 'PFS rate at 6 months', subGroup: 'PFS' },
  PFS_RATE_9M: { key: 'PFS_RATE_9M', label: 'PFS 9M', unit: '%', description: 'PFS rate at 9 months', subGroup: 'PFS' },
  PFS_RATE_12M: { key: 'PFS_RATE_12M', label: 'PFS 12M', unit: '%', description: 'PFS rate at 12 months', subGroup: 'PFS' },
  PFS_RATE_18M: { key: 'PFS_RATE_18M', label: 'PFS 18M', unit: '%', description: 'PFS rate at 18 months', subGroup: 'PFS' },
  PFS_RATE_24M: { key: 'PFS_RATE_24M', label: 'PFS 24M', unit: '%', description: 'PFS rate at 24 months', subGroup: 'PFS' },
  PFS_RATE_36M: { key: 'PFS_RATE_36M', label: 'PFS 36M', unit: '%', description: 'PFS rate at 36 months', subGroup: 'PFS' },
  PFS_RATE_48M: { key: 'PFS_RATE_48M', label: 'PFS 48M', unit: '%', description: 'PFS rate at 48 months', subGroup: 'PFS' },

  // OS Rate at various timepoints
  OS_RATE_6M: { key: 'OS_RATE_6M', label: 'OS 6M', unit: '%', description: 'OS rate at 6 months', subGroup: 'OS' },
  OS_RATE_9M: { key: 'OS_RATE_9M', label: 'OS 9M', unit: '%', description: 'OS rate at 9 months', subGroup: 'OS' },
  OS_RATE_12M: { key: 'OS_RATE_12M', label: 'OS 12M', unit: '%', description: 'OS rate at 12 months', subGroup: 'OS' },
  OS_RATE_18M: { key: 'OS_RATE_18M', label: 'OS 18M', unit: '%', description: 'OS rate at 18 months', subGroup: 'OS' },
  OS_RATE_24M: { key: 'OS_RATE_24M', label: 'OS 24M', unit: '%', description: 'OS rate at 24 months', subGroup: 'OS' },
  OS_RATE_36M: { key: 'OS_RATE_36M', label: 'OS 36M', unit: '%', description: 'OS rate at 36 months', subGroup: 'OS' },
  OS_RATE_48M: { key: 'OS_RATE_48M', label: 'OS 48M', unit: '%', description: 'OS rate at 48 months', subGroup: 'OS' },

  // Other Survival Metrics
  EFS: { key: 'EFS', label: 'EFS', unit: 'months', description: 'Event-Free Survival', subGroup: 'EFS' },
  HR_EFS: { key: 'HR_EFS', label: 'HR (EFS)', unit: '', description: 'Hazard Ratio for EFS', lowerIsBetter: true, subGroup: 'EFS' },
  P_VALUE_EFS: { key: 'P_VALUE_EFS', label: 'p (EFS)', unit: '', description: 'p-value of EFS', lowerIsBetter: true, pValue: true, subGroup: 'EFS' },
  RFS: { key: 'RFS', label: 'RFS', unit: 'months', description: 'Recurrence-Free Survival', subGroup: 'RFS' },
  HR_RFS: { key: 'HR_RFS', label: 'HR (RFS)', unit: '', description: 'Hazard Ratio for RFS', lowerIsBetter: true, subGroup: 'RFS' },
  P_VALUE_RFS: { key: 'P_VALUE_RFS', label: 'p (RFS)', unit: '', description: 'p-value of RFS', lowerIsBetter: true, pValue: true, subGroup: 'RFS' },
  LENGTH_RFS: { key: 'LENGTH_RFS', label: 'RFS FU', unit: 'months', description: 'Length of measuring RFS', subGroup: 'RFS' },
  MFS: { key: 'MFS', label: 'MFS', unit: 'months', description: 'Metastasis-Free Survival', subGroup: 'MFS' },
  HR_MFS: { key: 'HR_MFS', label: 'HR (MFS)', unit: '', description: 'Hazard Ratio for MFS', lowerIsBetter: true, subGroup: 'MFS' },
  LENGTH_MFS: { key: 'LENGTH_MFS', label: 'MFS FU', unit: 'months', description: 'Length of measuring MFS', subGroup: 'MFS' },

  // Time Metrics
  TTR: { key: 'TTR', label: 'TTR', unit: 'months', description: 'Time to Response', subGroup: 'Time-to' },
  TTP: { key: 'TTP', label: 'TTP', unit: 'months', description: 'Time to Progression', subGroup: 'Time-to' },
  TTNT: { key: 'TTNT', label: 'TTNT', unit: 'months', description: 'Time to Next Treatment', subGroup: 'Time-to' },
  TTF: { key: 'TTF', label: 'TTF', unit: 'months', description: 'Time to Treatment Failure', subGroup: 'Time-to' },
};

// Safety metrics configuration - keys match backend AttributeType names
export const SAFETY_METRICS: Record<string, MetricConfig> = {
  // Study metadata
  NUMBER_OF_PATIENTS: { key: 'NUMBER_OF_PATIENTS', label: 'N', unit: '', description: 'Number of patients enrolled', subGroup: 'Study', integer: true },

  // General AE
  AE: { key: 'AE', label: 'AE', unit: '%', description: 'Adverse Events', lowerIsBetter: true, subGroup: 'AE' },
  GRADE_3_PLUS_AE: { key: 'GRADE_3_PLUS_AE', label: 'G3+ AE', unit: '%', description: 'Grade 3+ Adverse Events', lowerIsBetter: true, subGroup: 'AE' },
  AE_LEADING_TO_DISCONTINUATION: { key: 'AE_LEADING_TO_DISCONTINUATION', label: 'AE Disc', unit: '%', description: 'AE leading to discontinuation', lowerIsBetter: true, subGroup: 'AE' },
  SERIOUS_AE: { key: 'SERIOUS_AE', label: 'SAE', unit: '%', description: 'Serious Adverse Events', lowerIsBetter: true, subGroup: 'AE' },
  IMMUNE_RELATED_AE: { key: 'IMMUNE_RELATED_AE', label: 'irAE', unit: '%', description: 'Immune-related AE', lowerIsBetter: true, subGroup: 'AE' },
  SERIOUS_IMMUNE_RELATED_AE: { key: 'SERIOUS_IMMUNE_RELATED_AE', label: 'Serious irAE', unit: '%', description: 'Serious Immune-related AE', lowerIsBetter: true, subGroup: 'AE' },
  AE_LEADING_TO_DEATH: { key: 'AE_LEADING_TO_DEATH', label: 'AE Death', unit: '%', description: 'AE leading to death', lowerIsBetter: true, subGroup: 'AE' },

  // TEAE (Treatment-Emergent AE)
  TEAE: { key: 'TEAE', label: 'TEAE', unit: '%', description: 'Treatment-Emergent AE', lowerIsBetter: true, subGroup: 'TEAE' },
  GRADE_3_PLUS_TEAE: { key: 'GRADE_3_PLUS_TEAE', label: 'G3+ TEAE', unit: '%', description: 'Grade 3+ TEAE', lowerIsBetter: true, subGroup: 'TEAE' },
  GRADE_3_TEAE: { key: 'GRADE_3_TEAE', label: 'G3 TEAE', unit: '%', description: 'Grade 3 TEAE', lowerIsBetter: true, subGroup: 'TEAE' },
  GRADE_4_TEAE: { key: 'GRADE_4_TEAE', label: 'G4 TEAE', unit: '%', description: 'Grade 4 TEAE', lowerIsBetter: true, subGroup: 'TEAE' },
  GRADE_5_TEAE: { key: 'GRADE_5_TEAE', label: 'G5 TEAE', unit: '%', description: 'Grade 5 TEAE', lowerIsBetter: true, subGroup: 'TEAE' },
  TEAE_LEADING_TO_DISCONTINUATION: { key: 'TEAE_LEADING_TO_DISCONTINUATION', label: 'TEAE Disc', unit: '%', description: 'TEAE leading to discontinuation', lowerIsBetter: true, subGroup: 'TEAE' },
  TEAE_LEADING_TO_DEATH: { key: 'TEAE_LEADING_TO_DEATH', label: 'TEAE Death', unit: '%', description: 'TEAE leading to death', lowerIsBetter: true, subGroup: 'TEAE' },
  SERIOUS_TEAE: { key: 'SERIOUS_TEAE', label: 'STEAE', unit: '%', description: 'Serious TEAE', lowerIsBetter: true, subGroup: 'TEAE' },
  TEAE_IMMUNE_RELATED: { key: 'TEAE_IMMUNE_RELATED', label: 'TEAE irAE', unit: '%', description: 'TEAE Immune-related AE', lowerIsBetter: true, subGroup: 'TEAE' },

  // TRAE (Treatment-Related AE)
  TRAE: { key: 'TRAE', label: 'TRAE', unit: '%', description: 'Treatment-Related AE', lowerIsBetter: true, subGroup: 'TRAE' },
  GRADE_3_PLUS_TRAE: { key: 'GRADE_3_PLUS_TRAE', label: 'G3+ TRAE', unit: '%', description: 'Grade 3+ TRAE', lowerIsBetter: true, subGroup: 'TRAE' },
  GRADE_3_TRAE: { key: 'GRADE_3_TRAE', label: 'G3 TRAE', unit: '%', description: 'Grade 3 TRAE', lowerIsBetter: true, subGroup: 'TRAE' },
  GRADE_4_TRAE: { key: 'GRADE_4_TRAE', label: 'G4 TRAE', unit: '%', description: 'Grade 4 TRAE', lowerIsBetter: true, subGroup: 'TRAE' },
  GRADE_5_TRAE: { key: 'GRADE_5_TRAE', label: 'G5 TRAE', unit: '%', description: 'Grade 5 TRAE', lowerIsBetter: true, subGroup: 'TRAE' },
  TRAE_LEADING_TO_DISCONTINUATION: { key: 'TRAE_LEADING_TO_DISCONTINUATION', label: 'TRAE Disc', unit: '%', description: 'TRAE leading to discontinuation', lowerIsBetter: true, subGroup: 'TRAE' },
  TRAE_LEADING_TO_DEATH: { key: 'TRAE_LEADING_TO_DEATH', label: 'TRAE Death', unit: '%', description: 'TRAE leading to death', lowerIsBetter: true, subGroup: 'TRAE' },
  TRAE_IMMUNE_RELATED: { key: 'TRAE_IMMUNE_RELATED', label: 'TRAE irAE', unit: '%', description: 'TRAE Immune-related AE', lowerIsBetter: true, subGroup: 'TRAE' },
  SERIOUS_TRAE: { key: 'SERIOUS_TRAE', label: 'STRAE', unit: '%', description: 'Serious TRAE', lowerIsBetter: true, subGroup: 'TRAE' },

  // Specific AE Types
  CRS: { key: 'CRS', label: 'CRS', unit: '%', description: 'Cytokine Release Syndrome', lowerIsBetter: true, subGroup: 'Specific AE' },
  WBC_DECREASED: { key: 'WBC_DECREASED', label: 'WBC↓', unit: '%', description: 'White Blood Cell Decreased', lowerIsBetter: true, subGroup: 'Specific AE' },
  
  // Grade 3+ Specific AEs
  GRADE_3_PLUS_AE_CRS: { key: 'GRADE_3_PLUS_AE_CRS', label: 'G3+ CRS', unit: '%', description: 'Grade 3+ Cytokine Release Syndrome', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_THROMBOCYTOPENIA: { key: 'GRADE_3_PLUS_AE_THROMBOCYTOPENIA', label: 'G3+ Thrombocytopenia', unit: '%', description: 'Grade 3+ Thrombocytopenia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_NEUTROPENIA: { key: 'GRADE_3_PLUS_AE_NEUTROPENIA', label: 'G3+ Neutropenia', unit: '%', description: 'Grade 3+ Neutropenia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_LEUKOPENIA: { key: 'GRADE_3_PLUS_AE_LEUKOPENIA', label: 'G3+ Leukopenia', unit: '%', description: 'Grade 3+ Leukopenia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_NAUSEA: { key: 'GRADE_3_PLUS_AE_NAUSEA', label: 'G3+ Nausea', unit: '%', description: 'Grade 3+ Nausea', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_ANEMIA: { key: 'GRADE_3_PLUS_AE_ANEMIA', label: 'G3+ Anemia', unit: '%', description: 'Grade 3+ Anemia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_DIARRHEA: { key: 'GRADE_3_PLUS_AE_DIARRHEA', label: 'G3+ Diarrhea', unit: '%', description: 'Grade 3+ Diarrhea', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_COLITIS: { key: 'GRADE_3_PLUS_AE_COLITIS', label: 'G3+ Colitis', unit: '%', description: 'Grade 3+ Colitis', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_HYPERGLYCEMIA: { key: 'GRADE_3_PLUS_AE_HYPERGLYCEMIA', label: 'G3+ Hyperglycemia', unit: '%', description: 'Grade 3+ Hyperglycemia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED: { key: 'GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ Neutrophil↓', unit: '%', description: 'Grade 3+ Neutrophil Count Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_DYSPNEA: { key: 'GRADE_3_PLUS_AE_DYSPNEA', label: 'G3+ Dyspnea', unit: '%', description: 'Grade 3+ Dyspnea', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_PYREXIA: { key: 'GRADE_3_PLUS_AE_PYREXIA', label: 'G3+ Pyrexia', unit: '%', description: 'Grade 3+ Pyrexia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_BLEEDING: { key: 'GRADE_3_PLUS_AE_BLEEDING', label: 'G3+ Bleeding', unit: '%', description: 'Grade 3+ Bleeding', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_PRURITUS: { key: 'GRADE_3_PLUS_AE_PRURITUS', label: 'G3+ Pruritus', unit: '%', description: 'Grade 3+ Pruritus', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_RASH: { key: 'GRADE_3_PLUS_AE_RASH', label: 'G3+ Rash', unit: '%', description: 'Grade 3+ Rash', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_PNEUMONIA: { key: 'GRADE_3_PLUS_AE_PNEUMONIA', label: 'G3+ Pneumonia', unit: '%', description: 'Grade 3+ Pneumonia', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_THYROIDITIS: { key: 'GRADE_3_PLUS_AE_THYROIDITIS', label: 'G3+ Thyroiditis', unit: '%', description: 'Grade 3+ Thyroiditis', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_HYPOPHYSITIS: { key: 'GRADE_3_PLUS_AE_HYPOPHYSITIS', label: 'G3+ Hypophysitis', unit: '%', description: 'Grade 3+ Hypophysitis', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_HEPATITIS: { key: 'GRADE_3_PLUS_AE_HEPATITIS', label: 'G3+ Hepatitis', unit: '%', description: 'Grade 3+ Hepatitis', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_PNEUMONITIS: { key: 'GRADE_3_PLUS_AE_PNEUMONITIS', label: 'G3+ Pneumonitis', unit: '%', description: 'Grade 3+ Pneumonitis', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: { key: 'GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE', label: 'G3+ ALT', unit: '%', description: 'Grade 3+ Alanine Aminotransferase', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_WBC_DECREASED: { key: 'GRADE_3_PLUS_AE_WBC_DECREASED', label: 'G3+ WBC↓', unit: '%', description: 'Grade 3+ WBC Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  GRADE_3_PLUS_AE_IMMUNE_RELATED: { key: 'GRADE_3_PLUS_AE_IMMUNE_RELATED', label: 'G3+ irAE', unit: '%', description: 'Grade 3+ Immune-related AE', lowerIsBetter: true, subGroup: 'Grade 3+ AE' },
  
  // Grade 3+ TRAE Specific
  GRADE_3_PLUS_TRAE_IMMUNE_RELATED: { key: 'GRADE_3_PLUS_TRAE_IMMUNE_RELATED', label: 'G3+ TRAE irAE', unit: '%', description: 'Grade 3+ TRAE Immune-related AE', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_CRS: { key: 'GRADE_3_PLUS_TRAE_CRS', label: 'G3+ TRAE CRS', unit: '%', description: 'Grade 3+ TRAE CRS', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: { key: 'GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA', label: 'G3+ TRAE Thrombocytopenia', unit: '%', description: 'Grade 3+ TRAE Thrombocytopenia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_NEUTROPENIA: { key: 'GRADE_3_PLUS_TRAE_NEUTROPENIA', label: 'G3+ TRAE Neutropenia', unit: '%', description: 'Grade 3+ TRAE Neutropenia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_LEUKOPENIA: { key: 'GRADE_3_PLUS_TRAE_LEUKOPENIA', label: 'G3+ TRAE Leukopenia', unit: '%', description: 'Grade 3+ TRAE Leukopenia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_NAUSEA: { key: 'GRADE_3_PLUS_TRAE_NAUSEA', label: 'G3+ TRAE Nausea', unit: '%', description: 'Grade 3+ TRAE Nausea', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_ANEMIA: { key: 'GRADE_3_PLUS_TRAE_ANEMIA', label: 'G3+ TRAE Anemia', unit: '%', description: 'Grade 3+ TRAE Anemia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_DIARRHEA: { key: 'GRADE_3_PLUS_TRAE_DIARRHEA', label: 'G3+ TRAE Diarrhea', unit: '%', description: 'Grade 3+ TRAE Diarrhea', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_COLITIS: { key: 'GRADE_3_PLUS_TRAE_COLITIS', label: 'G3+ TRAE Colitis', unit: '%', description: 'Grade 3+ TRAE Colitis', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_HYPERGLYCEMIA: { key: 'GRADE_3_PLUS_TRAE_HYPERGLYCEMIA', label: 'G3+ TRAE Hyperglycemia', unit: '%', description: 'Grade 3+ TRAE Hyperglycemia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED: { key: 'GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ TRAE Neutrophil↓', unit: '%', description: 'Grade 3+ TRAE Neutrophil Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_DYSPNEA: { key: 'GRADE_3_PLUS_TRAE_DYSPNEA', label: 'G3+ TRAE Dyspnea', unit: '%', description: 'Grade 3+ TRAE Dyspnea', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_PYREXIA: { key: 'GRADE_3_PLUS_TRAE_PYREXIA', label: 'G3+ TRAE Pyrexia', unit: '%', description: 'Grade 3+ TRAE Pyrexia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_BLEEDING: { key: 'GRADE_3_PLUS_TRAE_BLEEDING', label: 'G3+ TRAE Bleeding', unit: '%', description: 'Grade 3+ TRAE Bleeding', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_PRURITUS: { key: 'GRADE_3_PLUS_TRAE_PRURITUS', label: 'G3+ TRAE Pruritus', unit: '%', description: 'Grade 3+ TRAE Pruritus', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_RASH: { key: 'GRADE_3_PLUS_TRAE_RASH', label: 'G3+ TRAE Rash', unit: '%', description: 'Grade 3+ TRAE Rash', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_PNEUMONIA: { key: 'GRADE_3_PLUS_TRAE_PNEUMONIA', label: 'G3+ TRAE Pneumonia', unit: '%', description: 'Grade 3+ TRAE Pneumonia', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_THYROIDITIS: { key: 'GRADE_3_PLUS_TRAE_THYROIDITIS', label: 'G3+ TRAE Thyroiditis', unit: '%', description: 'Grade 3+ TRAE Thyroiditis', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_HYPOPHYSITIS: { key: 'GRADE_3_PLUS_TRAE_HYPOPHYSITIS', label: 'G3+ TRAE Hypophysitis', unit: '%', description: 'Grade 3+ TRAE Hypophysitis', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_HEPATITIS: { key: 'GRADE_3_PLUS_TRAE_HEPATITIS', label: 'G3+ TRAE Hepatitis', unit: '%', description: 'Grade 3+ TRAE Hepatitis', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_PNEUMONITIS: { key: 'GRADE_3_PLUS_TRAE_PNEUMONITIS', label: 'G3+ TRAE Pneumonitis', unit: '%', description: 'Grade 3+ TRAE Pneumonitis', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: { key: 'GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE', label: 'G3+ TRAE ALT', unit: '%', description: 'Grade 3+ TRAE ALT', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  GRADE_3_PLUS_TRAE_WBC_DECREASED: { key: 'GRADE_3_PLUS_TRAE_WBC_DECREASED', label: 'G3+ TRAE WBC↓', unit: '%', description: 'Grade 3+ TRAE WBC Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ TRAE' },
  
  // Grade 3+ TEAE Specific
  GRADE_3_PLUS_TEAE_IMMUNE_RELATED: { key: 'GRADE_3_PLUS_TEAE_IMMUNE_RELATED', label: 'G3+ TEAE irAE', unit: '%', description: 'Grade 3+ TEAE Immune-related AE', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_CRS: { key: 'GRADE_3_PLUS_TEAE_CRS', label: 'G3+ TEAE CRS', unit: '%', description: 'Grade 3+ TEAE CRS', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: { key: 'GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA', label: 'G3+ TEAE Thrombocytopenia', unit: '%', description: 'Grade 3+ TEAE Thrombocytopenia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_NEUTROPENIA: { key: 'GRADE_3_PLUS_TEAE_NEUTROPENIA', label: 'G3+ TEAE Neutropenia', unit: '%', description: 'Grade 3+ TEAE Neutropenia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_LEUKOPENIA: { key: 'GRADE_3_PLUS_TEAE_LEUKOPENIA', label: 'G3+ TEAE Leukopenia', unit: '%', description: 'Grade 3+ TEAE Leukopenia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_NAUSEA: { key: 'GRADE_3_PLUS_TEAE_NAUSEA', label: 'G3+ TEAE Nausea', unit: '%', description: 'Grade 3+ TEAE Nausea', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_ANEMIA: { key: 'GRADE_3_PLUS_TEAE_ANEMIA', label: 'G3+ TEAE Anemia', unit: '%', description: 'Grade 3+ TEAE Anemia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_DIARRHEA: { key: 'GRADE_3_PLUS_TEAE_DIARRHEA', label: 'G3+ TEAE Diarrhea', unit: '%', description: 'Grade 3+ TEAE Diarrhea', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_COLITIS: { key: 'GRADE_3_PLUS_TEAE_COLITIS', label: 'G3+ TEAE Colitis', unit: '%', description: 'Grade 3+ TEAE Colitis', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_HYPERGLYCEMIA: { key: 'GRADE_3_PLUS_TEAE_HYPERGLYCEMIA', label: 'G3+ TEAE Hyperglycemia', unit: '%', description: 'Grade 3+ TEAE Hyperglycemia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED: { key: 'GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED', label: 'G3+ TEAE Neutrophil↓', unit: '%', description: 'Grade 3+ TEAE Neutrophil Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_DYSPNEA: { key: 'GRADE_3_PLUS_TEAE_DYSPNEA', label: 'G3+ TEAE Dyspnea', unit: '%', description: 'Grade 3+ TEAE Dyspnea', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_PYREXIA: { key: 'GRADE_3_PLUS_TEAE_PYREXIA', label: 'G3+ TEAE Pyrexia', unit: '%', description: 'Grade 3+ TEAE Pyrexia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_BLEEDING: { key: 'GRADE_3_PLUS_TEAE_BLEEDING', label: 'G3+ TEAE Bleeding', unit: '%', description: 'Grade 3+ TEAE Bleeding', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_PRURITUS: { key: 'GRADE_3_PLUS_TEAE_PRURITUS', label: 'G3+ TEAE Pruritus', unit: '%', description: 'Grade 3+ TEAE Pruritus', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_RASH: { key: 'GRADE_3_PLUS_TEAE_RASH', label: 'G3+ TEAE Rash', unit: '%', description: 'Grade 3+ TEAE Rash', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_PNEUMONIA: { key: 'GRADE_3_PLUS_TEAE_PNEUMONIA', label: 'G3+ TEAE Pneumonia', unit: '%', description: 'Grade 3+ TEAE Pneumonia', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_THYROIDITIS: { key: 'GRADE_3_PLUS_TEAE_THYROIDITIS', label: 'G3+ TEAE Thyroiditis', unit: '%', description: 'Grade 3+ TEAE Thyroiditis', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_HYPOPHYSITIS: { key: 'GRADE_3_PLUS_TEAE_HYPOPHYSITIS', label: 'G3+ TEAE Hypophysitis', unit: '%', description: 'Grade 3+ TEAE Hypophysitis', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_HEPATITIS: { key: 'GRADE_3_PLUS_TEAE_HEPATITIS', label: 'G3+ TEAE Hepatitis', unit: '%', description: 'Grade 3+ TEAE Hepatitis', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_PNEUMONITIS: { key: 'GRADE_3_PLUS_TEAE_PNEUMONITIS', label: 'G3+ TEAE Pneumonitis', unit: '%', description: 'Grade 3+ TEAE Pneumonitis', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: { key: 'GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE', label: 'G3+ TEAE ALT', unit: '%', description: 'Grade 3+ TEAE ALT', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
  GRADE_3_PLUS_TEAE_WBC_DECREASED: { key: 'GRADE_3_PLUS_TEAE_WBC_DECREASED', label: 'G3+ TEAE WBC↓', unit: '%', description: 'Grade 3+ TEAE WBC Decreased', lowerIsBetter: true, subGroup: 'Grade 3+ TEAE' },
};

export const ALL_METRICS: Record<string, MetricConfig> = {
  ...EFFICACY_METRICS,
  ...SAFETY_METRICS,
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

// ============================================================================
// Efficacy vs Safety Chart Types
// ============================================================================

export interface EfficacySafetyDataPoint {
  treatmentName: string;
  treatmentType?: string; // e.g., "Immunotherapy", "Chemo", "Targeted"
  efficacy: number; // ORR or other efficacy metric (%)
  safety: number; // Grade 3+ AE rate (%)
  numberOfPatients?: number;
  trialCount?: number;
  // Store all trials for this treatment (for tooltip switching)
  allTrials?: Array<{
    abstractId?: string;
    efficacy: number;
    safety: number;
    numberOfPatients?: number;
    year?: string;
    nctNumber?: string;
    publicationName?: string;
    citation?: string;
    phase?: string;
    sourceType?: SourceType;
    sourceUrl?: string;
  }>;
  currentTrialIndex?: number;
}

// ============================================================================
// Bubble Chart Types
// ============================================================================

export interface BubbleChartDataPoint {
  treatmentName: string;
  treatmentType?: string;
  efficacy: number; // ORR or other efficacy metric (%)
  safety: number; // Grade 3+ TRAE or AE rate (%)
  numberOfPatients: number; // Determines bubble size
  /** Z-axis value when Z is not NUMBER_OF_PATIENTS (e.g. HR_PFS, HR_OS) */
  zValue?: number;
  nctNumber?: string;
  abstractId?: string;
  publicationName?: string;
  citation?: string;
  phase?: string;
  year?: string;
  sourceUrl?: string;
  sourceType?: SourceType;
  // Additional metadata for tooltips
  notes?: string;
  biomarker?: string;
  // Store all trials for this treatment (for tooltip switching)
  allTrials?: Array<{
    abstractId?: string;
    efficacy: number;
    safety: number;
    numberOfPatients: number;
    year?: string;
    nctNumber?: string;
    publicationName?: string;
    citation?: string;
    phase?: string;
    sourceType?: SourceType;
    sourceUrl?: string;
  }>;
  currentTrialIndex?: number; // Index of currently displayed trial in allTrials array
}

