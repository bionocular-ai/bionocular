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
  EfficacySafetyDataPoint,
  BubbleChartDataPoint,
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
 * Deduplicate trials by treatment name, keeping the most recent year.
 * If same year, prefer highest efficacy then lowest safety.
 */
function deduplicateTrialsByTreatment<T extends { treatmentName: string; year?: string; efficacy?: number; safety?: number }>(
  trials: T[]
): T[] {
  const treatmentMap = new Map<string, T>();

  for (const trial of trials) {
    const existing = treatmentMap.get(trial.treatmentName);
    if (!existing) {
      treatmentMap.set(trial.treatmentName, trial);
    } else {
      const existingYear = parseInt(existing.year || '0', 10);
      const currentYear = parseInt(trial.year || '0', 10);
      
      if (currentYear > existingYear) {
        treatmentMap.set(trial.treatmentName, trial);
      } else if (currentYear === existingYear) {
        // Same year - prefer higher efficacy, then lower safety
        const existingEfficacy = existing.efficacy ?? 0;
        const currentEfficacy = trial.efficacy ?? 0;
        const existingSafety = existing.safety ?? 0;
        const currentSafety = trial.safety ?? 0;
        
        if (currentEfficacy > existingEfficacy || 
            (currentEfficacy === existingEfficacy && currentSafety < existingSafety)) {
          treatmentMap.set(trial.treatmentName, trial);
        }
      }
    }
  }

  return Array.from(treatmentMap.values());
}

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

      // Filter by year if specified - abstracts use PUBLISHED_YEAR, publications use PUBLICATION_YEAR
      const yearStr = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'publication_year'));
      const year = parseInt(yearStr, 10);
      if (!isNaN(year) && (year < yearRange[0] || year > yearRange[1])) {
        continue;
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
      
      // Extract patient count
      const patientCount = extractNumericValue(getAttribute(arm.attributes, 'NUMBER_OF_PATIENTS'));

      // Initialize group if needed (using normalized name)
      if (!grouped.has(treatmentName)) {
        grouped.set(treatmentName, { values: [], patients: [], trials: [] });
      }

      const group = grouped.get(treatmentName)!;
      group.values.push(metricValue);

      if (patientCount !== null) {
        group.patients.push(patientCount);
      }
      
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

  // Deduplicate trials before aggregating
  for (const [, group] of grouped.entries()) {
    // Deduplicate trials by creating a map keyed by abstractId/year
    const trialMap = new Map<string, TrialDataPoint>();
    for (const trial of group.trials) {
      const key = `${trial.abstractId}_${trial.year}`;
      if (!trialMap.has(key)) {
        trialMap.set(key, trial);
      } else {
        // If same abstract/year, keep the one with better value (higher for efficacy metrics)
        const existing = trialMap.get(key)!;
        if (trial.value > existing.value) {
          trialMap.set(key, trial);
        }
      }
    }
    group.trials = Array.from(trialMap.values());
    
    // Sort trials by year (most recent first), then by value
    group.trials.sort((a, b) => {
      const yearA = parseInt(a.year || '0', 10);
      const yearB = parseInt(b.year || '0', 10);
      if (yearB !== yearA) return yearB - yearA;
      return b.value - a.value;
    });
    
    // Recalculate values and patients from deduplicated trials
    group.values = group.trials.map(t => t.value);
    group.patients = group.trials.map(t => t.numberOfPatients).filter((p): p is number => p !== null);
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

// ============================================================================
// Efficacy vs Safety Chart Transformers
// ============================================================================

export interface EfficacySafetyTransformOptions {
  efficacyMetric?: ChartMetric;
  safetyMetric?: ChartMetric;
  /** Z-axis metric for bubble size (e.g. NUMBER_OF_PATIENTS, HR_PFS). When set and not NUMBER_OF_PATIENTS, extracted into point.zValue */
  zMetric?: ChartMetric;
  selectedTreatments?: string[];
  minTrialCount?: number;
  selectedPhases?: string[];
  yearRange?: [number, number];
}

/**
 * Transform data for Diverging Bar Chart (Efficacy vs Safety)
 */
export function transformEfficacySafetyData(
  data: TrialDataFile | TrialDataFile[],
  options: EfficacySafetyTransformOptions = {}
): EfficacySafetyDataPoint[] {
  const {
    efficacyMetric = 'OBJECTIVE_RESPONSE_RATE',
    safetyMetric = 'GRADE_3_PLUS_AE',
    selectedTreatments = [],
    minTrialCount = 1,
    selectedPhases = [],
    yearRange = [2000, 2030],
  } = options;

  const dataFiles = Array.isArray(data) ? data : [data];
  const allTrials: ClinicalTrialRaw[] = [];
  for (const file of dataFiles) {
    if (file.abstracts) allTrials.push(...file.abstracts);
    if (file.publications) allTrials.push(...file.publications);
  }

  // Group by treatment - collect individual trials first
  const individualTrials: Array<{
    treatmentName: string;
    efficacy: number;
    safety: number;
    numberOfPatients?: number;
    year?: string;
    abstractId?: string;
    nctNumber?: string;
    publicationName?: string;
    citation?: string;
    phase?: string;
  }> = [];

  const grouped = new Map<string, {
    efficacyValues: number[];
    safetyValues: number[];
    patients: number[];
    trialCount: number;
  }>();

  for (const trial of allTrials) {
    for (const [, arm] of Object.entries(trial.arm_results)) {
      const treatmentName = normalizeTreatmentName(arm.arm_name);
      
      if (selectedTreatments.length > 0) {
        const normalizedSelected = selectedTreatments.map(normalizeTreatmentName);
        if (!normalizedSelected.includes(treatmentName) && !selectedTreatments.includes(arm.arm_name)) {
          continue;
        }
      }

      // Extract efficacy and safety values
      const efficacyAttr = getAttribute(arm.attributes, efficacyMetric);
      const safetyAttr = getAttribute(arm.attributes, safetyMetric);
      const efficacyValue = extractNumericValue(efficacyAttr);
      const safetyValue = extractNumericValue(safetyAttr);

      // Both metrics must be present
      if (efficacyValue === null || safetyValue === null) continue;

      // Filter by phase
      const phase = extractStringValue(getAttribute(arm.attributes, 'CLINICAL_TRIAL_PHASE'));
      if (selectedPhases.length > 0 && phase && !selectedPhases.includes(phase)) {
        continue;
      }

      // Filter by year - abstracts use PUBLISHED_YEAR, publications use PUBLICATION_YEAR
      const yearStr = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'publication_year'));
      const year = parseInt(yearStr, 10);
      if (!isNaN(year) && (year < yearRange[0] || year > yearRange[1])) {
        continue;
      }

      // Store individual trial data
      const abstractId = trial.abstract_id || trial.publication_id || '';
      const nctNumber = extractStringValue(getAttribute(arm.attributes, 'NCT_NUMBER'));
      const publicationName = extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_NAME'));
      const conference = extractStringValue(getAttribute(arm.attributes, 'CONFERENCE'));
      const patientCount = extractNumericValue(getAttribute(arm.attributes, 'NUMBER_OF_PATIENTS'));

      individualTrials.push({
        treatmentName,
        efficacy: efficacyValue,
        safety: safetyValue,
        numberOfPatients: patientCount || undefined,
        year: yearStr || undefined,
        abstractId: abstractId || undefined,
        nctNumber: nctNumber || undefined,
        publicationName: publicationName || undefined,
        citation: `${conference} ${yearStr}`,
        phase: phase || undefined,
      });

      if (!grouped.has(treatmentName)) {
        grouped.set(treatmentName, { efficacyValues: [], safetyValues: [], patients: [], trialCount: 0 });
      }

      const group = grouped.get(treatmentName)!;
      group.efficacyValues.push(efficacyValue);
      group.safetyValues.push(safetyValue);
      
      if (patientCount !== null) {
        group.patients.push(patientCount);
      }
      group.trialCount++;
    }
  }

  // Deduplicate individual trials by treatment before aggregating
  const deduplicatedTrials = deduplicateTrialsByTreatment(individualTrials);

  // Recalculate grouped data from deduplicated trials
  const deduplicatedGrouped = new Map<string, {
    efficacyValues: number[];
    safetyValues: number[];
    patients: number[];
    trialCount: number;
  }>();

  for (const trial of deduplicatedTrials) {
    if (!deduplicatedGrouped.has(trial.treatmentName)) {
      deduplicatedGrouped.set(trial.treatmentName, { efficacyValues: [], safetyValues: [], patients: [], trialCount: 0 });
    }
    const group = deduplicatedGrouped.get(trial.treatmentName)!;
    group.efficacyValues.push(trial.efficacy);
    group.safetyValues.push(trial.safety);
    if (trial.numberOfPatients !== undefined) {
      group.patients.push(trial.numberOfPatients);
    }
    group.trialCount++;
  }

  // Group all trials by treatment for tooltip switching
  const treatmentTrialsMap = new Map<string, typeof individualTrials>();
  for (const trial of individualTrials) {
    if (!treatmentTrialsMap.has(trial.treatmentName)) {
      treatmentTrialsMap.set(trial.treatmentName, []);
    }
    treatmentTrialsMap.get(trial.treatmentName)!.push(trial);
  }

  const result: EfficacySafetyDataPoint[] = [];

  for (const [treatmentName, group] of deduplicatedGrouped.entries()) {
    if (group.trialCount < minTrialCount) continue;

    const avgEfficacy = group.efficacyValues.reduce((a, b) => a + b, 0) / group.efficacyValues.length;
    const avgSafety = group.safetyValues.reduce((a, b) => a + b, 0) / group.safetyValues.length;
    const totalPatients = group.patients.reduce((a, b) => a + b, 0);

    // Get all trials for this treatment and sort by year
    const allTrials = treatmentTrialsMap.get(treatmentName) || [];
    allTrials.sort((a, b) => {
      const yearA = parseInt(a.year || '0', 10);
      const yearB = parseInt(b.year || '0', 10);
      if (yearB !== yearA) return yearB - yearA;
      if (b.efficacy !== a.efficacy) return b.efficacy - a.efficacy;
      return a.safety - b.safety;
    });

    result.push({
      treatmentName,
      approvalStatus: getApprovalStatus(treatmentName),
      efficacy: avgEfficacy,
      safety: avgSafety,
      numberOfPatients: totalPatients > 0 ? totalPatients : undefined,
      trialCount: group.trialCount,
      allTrials: allTrials,
      currentTrialIndex: 0,
    });
  }

  // Sort by efficacy (highest first)
  result.sort((a, b) => b.efficacy - a.efficacy);

  return result;
}

/**
 * Transform data for Bubble Chart (Safety vs Efficacy)
 */
export function transformBubbleChartData(
  data: TrialDataFile | TrialDataFile[],
  options: EfficacySafetyTransformOptions = {}
): BubbleChartDataPoint[] {
  const {
    efficacyMetric = 'OBJECTIVE_RESPONSE_RATE',
    safetyMetric = 'GRADE_3_PLUS_TRAE',
    zMetric,
    selectedTreatments = [],
    minTrialCount = 1,
    selectedPhases = [],
    yearRange = [2000, 2030],
  } = options;

  const dataFiles = Array.isArray(data) ? data : [data];
  const allTrials: ClinicalTrialRaw[] = [];
  for (const file of dataFiles) {
    if (file.abstracts) allTrials.push(...file.abstracts);
    if (file.publications) allTrials.push(...file.publications);
  }

  const result: BubbleChartDataPoint[] = [];

  for (const trial of allTrials) {
    for (const [, arm] of Object.entries(trial.arm_results)) {
      const treatmentName = normalizeTreatmentName(arm.arm_name);
      
      if (selectedTreatments.length > 0) {
        const normalizedSelected = selectedTreatments.map(normalizeTreatmentName);
        if (!normalizedSelected.includes(treatmentName) && !selectedTreatments.includes(arm.arm_name)) {
          continue;
        }
      }

      // Extract metrics
      const efficacyAttr = getAttribute(arm.attributes, efficacyMetric);
      const safetyAttr = getAttribute(arm.attributes, safetyMetric);
      const efficacyValue = extractNumericValue(efficacyAttr);
      const safetyValue = extractNumericValue(safetyAttr);

      if (efficacyValue === null || safetyValue === null) continue;

      // Filter by phase
      const phase = extractStringValue(getAttribute(arm.attributes, 'CLINICAL_TRIAL_PHASE'));
      if (selectedPhases.length > 0 && phase && !selectedPhases.includes(phase)) {
        continue;
      }

      // Filter by year - abstracts use PUBLISHED_YEAR, publications use PUBLICATION_YEAR
      const yearStr = extractStringValue(getAttribute(arm.attributes, 'PUBLISHED_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_YEAR')) ||
                     extractStringValue(getAttribute(arm.attributes, 'publication_year'));
      const year = parseInt(yearStr, 10);
      if (!isNaN(year) && (year < yearRange[0] || year > yearRange[1])) {
        continue;
      }

      const patientCount = extractNumericValue(getAttribute(arm.attributes, 'NUMBER_OF_PATIENTS')) || 0;
      const nctNumber = extractStringValue(getAttribute(arm.attributes, 'NCT_NUMBER'));
      const abstractId = trial.abstract_id || trial.publication_id || '';
      const publicationName = extractStringValue(getAttribute(arm.attributes, 'PUBLICATION_NAME'));
      const conference = extractStringValue(getAttribute(arm.attributes, 'CONFERENCE'));
      const zValue = zMetric && zMetric !== 'NUMBER_OF_PATIENTS'
        ? (extractNumericValue(getAttribute(arm.attributes, zMetric)) ?? undefined)
        : undefined;

      result.push({
        treatmentName,
        approvalStatus: getApprovalStatus(treatmentName),
        developmentStatus: getApprovalStatus(treatmentName) === 'Approved' ? 'Approved' : 'Investigational',
        efficacy: efficacyValue,
        safety: safetyValue,
        numberOfPatients: patientCount,
        ...(zValue !== undefined && zValue !== null && !Number.isNaN(zValue) ? { zValue } : {}),
        nctNumber: nctNumber || undefined,
        abstractId: abstractId || undefined,
        publicationName: publicationName || undefined,
        citation: `${conference} ${yearStr}`,
        phase: phase || undefined,
        year: yearStr || undefined,
        sourceUrl: trial.source_url || undefined,
      });
    }
  }

  // Group all data points by treatment to collect all trials
  const treatmentTrialsMap = new Map<string, BubbleChartDataPoint[]>();
  for (const point of result) {
    if (!treatmentTrialsMap.has(point.treatmentName)) {
      treatmentTrialsMap.set(point.treatmentName, []);
    }
    treatmentTrialsMap.get(point.treatmentName)!.push(point);
  }

  // Deduplicate to get the most recent trial for display
  const deduplicatedResult = deduplicateTrialsByTreatment(result);

  // Attach allTrials array to each deduplicated point
  for (const point of deduplicatedResult) {
    const allTrials = treatmentTrialsMap.get(point.treatmentName) || [];
    // Sort by year (most recent first)
    allTrials.sort((a, b) => {
      const yearA = parseInt(a.year || '0', 10);
      const yearB = parseInt(b.year || '0', 10);
      if (yearB !== yearA) return yearB - yearA;
      // Same year - prefer higher efficacy, then lower safety
      if (b.efficacy !== a.efficacy) return b.efficacy - a.efficacy;
      return a.safety - b.safety;
    });
    point.allTrials = allTrials.map(trial => ({
      abstractId: trial.abstractId,
      efficacy: trial.efficacy,
      safety: trial.safety,
      numberOfPatients: trial.numberOfPatients,
      year: trial.year,
      nctNumber: trial.nctNumber,
      publicationName: trial.publicationName,
      citation: trial.citation,
      phase: trial.phase,
    }));
    point.currentTrialIndex = 0; // Most recent trial
  }

  // Filter by minimum trial count per treatment
  const treatmentCounts = new Map<string, number>();
  for (const point of deduplicatedResult) {
    treatmentCounts.set(point.treatmentName, (treatmentCounts.get(point.treatmentName) || 0) + 1);
  }

  return deduplicatedResult.filter((point) => (treatmentCounts.get(point.treatmentName) || 0) >= minTrialCount);
}

