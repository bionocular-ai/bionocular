/**
 * Chart Data Transformers
 * Transforms raw clinical trial data into chart-ready formats
 */

import {
  ClinicalTrialRaw,
  TrialDataFile,
  HeadToHeadDataPoint,
  TrialDataPoint,
  ChartMetric,
  ApprovalStatus,
  ArmResult,
  AttributeValue,
} from '@/types/analytics';

// ============================================================================
// Approved Treatments Lookup (for approval status classification)
// ============================================================================

const APPROVED_TREATMENTS = new Set([
  'pembrolizumab',
  'nivolumab',
  'ipilimumab',
  'dabrafenib',
  'trametinib',
  'vemurafenib',
  'cobimetinib',
  'encorafenib',
  'binimetinib',
  'atezolizumab',
  'talimogene laherparepvec',
  't-vec',
  'lifileucel',
]);

// ============================================================================
// Attribute Key Mapping (abstracts use AttributeType.X, publications use lowercase)
// ============================================================================

/**
 * Get attribute value checking both uppercase (AttributeType.X) and lowercase (x) key formats
 * Publications use lowercase keys, abstracts use AttributeType.X format
 */
function getAttribute(attributes: Record<string, AttributeInput>, metricName: string): AttributeInput {
  // Try AttributeType.X format first (used by abstracts)
  const uppercaseKey = `AttributeType.${metricName}`;
  if (attributes[uppercaseKey] !== undefined) {
    return attributes[uppercaseKey];
  }
  
  // Try lowercase format (used by publications)
  const lowercaseKey = metricName.toLowerCase();
  if (attributes[lowercaseKey] !== undefined) {
    return attributes[lowercaseKey];
  }
  
  // Handle special aliases (e.g., ORR -> OBJECTIVE_RESPONSE_RATE)
  const ALIASES: Record<string, string[]> = {
    'ORR': ['OBJECTIVE_RESPONSE_RATE', 'objective_response_rate'],
    'PFS': ['MEDIAN_PFS', 'median_pfs'],
    'OS': ['MEDIAN_OS', 'median_os'],
    'DCR': ['DISEASE_CONTROL_RATE', 'disease_control_rate'],
    'DOR': ['MEDIAN_DOR', 'median_dor', 'DOR_RATE', 'dor_rate'],
    'CBR': ['CLINICAL_BENEFIT_RATE', 'clinical_benefit_rate'],
    'CR': ['COMPLETE_RESPONSE', 'complete_response'],
  };
  
  const aliases = ALIASES[metricName];
  if (aliases) {
    for (const alias of aliases) {
      const aliasUpperKey = `AttributeType.${alias}`;
      if (attributes[aliasUpperKey] !== undefined) {
        return attributes[aliasUpperKey];
      }
      if (attributes[alias] !== undefined) {
        return attributes[alias];
      }
    }
  }
  
  return undefined;
}

// ============================================================================
// Helper Functions
// ============================================================================

type AttributeInput = AttributeValue | string | number | boolean | null | undefined;

/**
 * Safely extract a numeric value from an attribute
 */
function extractNumericValue(attr: AttributeInput): number | null {
  if (attr === null || attr === undefined) return null;
  
  // Boolean - not numeric
  if (typeof attr === 'boolean') return null;
  
  // Direct number
  if (typeof attr === 'number') return attr;
  
  // String that might be a number
  if (typeof attr === 'string') {
    const parsed = parseFloat(attr);
    return isNaN(parsed) ? null : parsed;
  }
  
  // AttributeValue object
  if (typeof attr === 'object' && 'value' in attr) {
    const value = attr.value;
    if (value === null || value === 'Not found' || value === 'NR') return null;
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
      // Handle ranges like "12.5-15.3" by taking the first number
      const match = value.match(/[\d.]+/);
      if (match) {
        const parsed = parseFloat(match[0]);
        return isNaN(parsed) ? null : parsed;
      }
    }
  }
  
  return null;
}

/**
 * Safely extract a string value from an attribute
 */
function extractStringValue(attr: AttributeInput): string {
  if (attr === null || attr === undefined) return '';
  if (typeof attr === 'boolean') return attr ? 'true' : 'false';
  if (typeof attr === 'string') return attr;
  if (typeof attr === 'number') return String(attr);
  if (typeof attr === 'object' && 'value' in attr) {
    const value = attr.value;
    if (value === null || value === 'Not found') return '';
    return String(value);
  }
  return '';
}

/**
 * Normalize treatment name for grouping
 * - Sorts components in combination therapies alphabetically
 * - Normalizes separators and whitespace
 * - Handles common variations
 */
function normalizeTreatmentName(name: string): string {
  if (!name) return 'Unknown';
  
  // Split by common combination separators
  const separatorRegex = /\s*[\+\/]\s*/;
  const parts = name.split(separatorRegex).map(p => p.trim()).filter(p => p.length > 0);
  
  // Sort parts alphabetically (case-insensitive) to normalize "A + B" and "B + A"
  parts.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  
  // Rejoin with consistent separator
  return parts.join(' + ');
}

/**
 * Determine approval status based on treatment name
 */
function getApprovalStatus(treatmentName: string): ApprovalStatus {
  const normalized = treatmentName.toLowerCase();
  
  // Check if any approved treatment is in the name
  for (const approved of APPROVED_TREATMENTS) {
    if (normalized.includes(approved)) {
      return 'Approved';
    }
  }
  
  // Check for combination therapies with approved drugs
  if (normalized.includes('+')) {
    const parts = normalized.split('+').map(p => p.trim());
    const hasApproved = parts.some(part => 
      Array.from(APPROVED_TREATMENTS).some(approved => part.includes(approved))
    );
    if (hasApproved) return 'Approved';
  }
  
  return 'Investigational';
}

/**
 * Build study ID from trial data
 */
function buildStudyId(trial: ClinicalTrialRaw, arm: ArmResult): string {
  const conference = extractStringValue(getAttribute(arm.attributes, 'CONFERENCE'));
  const year = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR'));
  const abstractNum = extractStringValue(getAttribute(arm.attributes, 'ABSTRACT_NUMBER'));
  
  if (trial.abstract_id) return trial.abstract_id;
  if (trial.publication_id) return trial.publication_id;
  if (conference && year && abstractNum) return `${conference}_${year}_${abstractNum}`;
  
  return `Study_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Calculate median of an array of numbers
 */
function calculateMedian(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ============================================================================
// Main Transformer Function
// ============================================================================

export interface TransformOptions {
  targetMetric?: ChartMetric;
  selectedTreatments?: string[];
  minTrialCount?: number;
  selectedPhases?: string[];
  yearRange?: [number, number];
}

/**
 * Transform raw clinical trial data into HeadToHead chart format
 */
export function transformHeadToHeadData(
  data: TrialDataFile | TrialDataFile[],
  options: TransformOptions = {}
): HeadToHeadDataPoint[] {
  const {
    targetMetric = 'MEDIAN_OS',
    selectedTreatments = [],
    minTrialCount = 1,
    selectedPhases = [],
    yearRange = [2000, 2030],
  } = options;

  // Normalize input to array
  const dataFiles = Array.isArray(data) ? data : [data];
  
  // Collect all trials
  const allTrials: ClinicalTrialRaw[] = [];
  for (const file of dataFiles) {
    if (file.abstracts) allTrials.push(...file.abstracts);
    if (file.publications) allTrials.push(...file.publications);
  }

  // Group data by treatment arm
  const grouped = new Map<string, {
    values: number[];
    patients: number[];
    trials: TrialDataPoint[];
  }>();

  for (const trial of allTrials) {
    for (const [, arm] of Object.entries(trial.arm_results)) {
      const rawTreatmentName = arm.arm_name;
      const treatmentName = normalizeTreatmentName(rawTreatmentName);
      
      // Skip if specific treatments are selected and this isn't one
      // Check both normalized and raw names for flexibility
      if (selectedTreatments.length > 0) {
        const normalizedSelected = selectedTreatments.map(normalizeTreatmentName);
        if (!normalizedSelected.includes(treatmentName) && !selectedTreatments.includes(rawTreatmentName)) {
          continue;
        }
      }

      // Extract metric value (check both uppercase and lowercase keys)
      const metricAttr = getAttribute(arm.attributes, targetMetric);
      const metricValue = extractNumericValue(metricAttr);
      if (metricValue === null) continue;

      // Filter by phase if specified
      const phase = extractStringValue(getAttribute(arm.attributes, 'CLINICAL_TRIAL_PHASE'));
      if (selectedPhases.length > 0 && phase && !selectedPhases.includes(phase)) {
        continue;
      }

      // Filter by year if specified
      const yearStr = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR'));
      const year = parseInt(yearStr, 10);
      if (!isNaN(year) && (year < yearRange[0] || year > yearRange[1])) {
        continue;
      }

      // Initialize group if needed (using normalized name)
      if (!grouped.has(treatmentName)) {
        grouped.set(treatmentName, { values: [], patients: [], trials: [] });
      }

      const group = grouped.get(treatmentName)!;
      group.values.push(metricValue);

      // Extract patient count
      const patientCount = extractNumericValue(getAttribute(arm.attributes, 'NUMBER_OF_PATIENTS'));
      if (patientCount !== null) {
        group.patients.push(patientCount);
      }

      // Build trial data point
      const studyId = buildStudyId(trial, arm);
      const nctNumber = extractStringValue(getAttribute(arm.attributes, 'NCT_NUMBER'));
      const conference = extractStringValue(getAttribute(arm.attributes, 'CONFERENCE'));
      const trialName = extractStringValue(getAttribute(arm.attributes, 'TRIAL_NAME'));
      
      // Get abstract ID or publication ID directly from trial object
      // This matches the logic in TrialDataTable.tsx
      const abstractId = trial.abstract_id || trial.publication_id || '';
      
      // Get publication name from attributes (for publications)
      const publicationNameAttr = extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_NAME'));
      
      group.trials.push({
        studyId,
        abstractId,
        publicationName: publicationNameAttr || '',
        trialName: trialName || '',
        value: metricValue,
        citation: `${conference} ${yearStr}`,
        phase: phase || 'Unknown',
        year: yearStr || 'Unknown',
        nctNumber,
        numberOfPatients: patientCount,
        sourceUrl: trial.source_url || '',
      });
    }
  }

  // Convert to HeadToHeadDataPoint array
  const result: HeadToHeadDataPoint[] = [];

  for (const [treatmentName, group] of grouped.entries()) {
    // Skip if below minimum trial count
    if (group.trials.length < minTrialCount) continue;

    const values = group.values;
    const sum = values.reduce((a, b) => a + b, 0);
    const totalPatients = group.patients.reduce((a, b) => a + b, 0);

    result.push({
      treatmentName,
      approvalStatus: getApprovalStatus(treatmentName),
      averageValue: sum / values.length,
      medianValue: calculateMedian(values),
      minValue: Math.min(...values),
      maxValue: Math.max(...values),
      trialCount: group.trials.length,
      totalPatients,
      trials: group.trials,
    });
  }

  // Sort by average value (highest first for survival metrics)
  result.sort((a, b) => b.averageValue - a.averageValue);

  return result;
}

// ============================================================================
// Utility Functions for Chart Components
// ============================================================================

/**
 * Get unique treatment names from data
 */
export function getUniqueTreatments(data: TrialDataFile | TrialDataFile[]): string[] {
  const dataFiles = Array.isArray(data) ? data : [data];
  const treatments = new Set<string>();

  for (const file of dataFiles) {
    const trials = [...(file.abstracts || []), ...(file.publications || [])];
    for (const trial of trials) {
      for (const arm of Object.values(trial.arm_results)) {
        if (arm.arm_name) treatments.add(arm.arm_name);
      }
    }
  }

  return Array.from(treatments).sort();
}

/**
 * Get unique phases from data
 */
export function getUniquePhases(data: TrialDataFile | TrialDataFile[]): string[] {
  const dataFiles = Array.isArray(data) ? data : [data];
  const phases = new Set<string>();

  for (const file of dataFiles) {
    const trials = [...(file.abstracts || []), ...(file.publications || [])];
    for (const trial of trials) {
      for (const arm of Object.values(trial.arm_results)) {
        const phase = extractStringValue(getAttribute(arm.attributes, 'CLINICAL_TRIAL_PHASE'));
        if (phase && phase !== 'Not found') phases.add(phase);
      }
    }
  }

  return Array.from(phases).sort();
}

/**
 * Get year range from data
 */
export function getYearRange(data: TrialDataFile | TrialDataFile[]): [number, number] {
  const dataFiles = Array.isArray(data) ? data : [data];
  let minYear = Infinity;
  let maxYear = -Infinity;

  for (const file of dataFiles) {
    const trials = [...(file.abstracts || []), ...(file.publications || [])];
    for (const trial of trials) {
      for (const arm of Object.values(trial.arm_results)) {
        const yearStr = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR'));
        const year = parseInt(yearStr, 10);
        if (!isNaN(year)) {
          minYear = Math.min(minYear, year);
          maxYear = Math.max(maxYear, year);
        }
      }
    }
  }

  return [
    minYear === Infinity ? 2015 : minYear,
    maxYear === -Infinity ? 2025 : maxYear,
  ];
}

/**
 * Flatten scatter data for Recharts
 * Maps individual trials to their treatment's x-axis position
 */
export function flattenScatterData(data: HeadToHeadDataPoint[]): (TrialDataPoint & { treatmentName: string })[] {
  return data.flatMap((group) =>
    group.trials.map((trial) => ({
      ...trial,
      treatmentName: group.treatmentName,
    }))
  );
}

