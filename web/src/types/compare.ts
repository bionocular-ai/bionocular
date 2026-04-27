/**
 * Compare Treatments Table Types
 * Drives the side-by-side matrix view on the analytics page.
 */

export type CompareSortMode = 'most-complete' | 'alphabetical';
export type CompareGroup = 'efficacy' | 'safety';
export type CompareCellStatus = 'value' | 'NR' | 'NE';
export type CompareMode = 'efficacy' | 'safety' | 'all';

export interface CompareCell {
  treatmentName: string;
  metricKey: string;
  value: number | null;
  displayValue: string;
  status: CompareCellStatus;
  assessmentMethod?: string;
  unit: string;
}

export interface CompareRow {
  metricKey: string;
  label: string;
  description: string;
  unit: string;
  group: CompareGroup;
  subGroup?: string;
  cells: Record<string, CompareCell>;
  coverage: number;
}

export interface TreatmentMeta {
  modality: string | null;
  lineOfTreatment: string | null;
  stage: string | null;
  biomarker: string | null;
  nctId: string | null;
}

export interface CompareTableData {
  treatments: string[];
  efficacyRows: CompareRow[];
  safetyRows: CompareRow[];
  treatmentMeta: Record<string, TreatmentMeta>;
}

export interface CompareSelection {
  treatmentName: string;
  metricKey: string;
}

export const MAX_COMPARE_TREATMENTS = 5;
