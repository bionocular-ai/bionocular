import { Document, type DashboardTrialCard } from '@/lib/api';

const OPEN_STUDY_STATUSES = new Set([
  'open',
  'not yet recruiting',
  'recruiting',
  'active, not recruiting',
]);

export function isOpenStudyStatus(status: string | null | undefined): boolean {
  return OPEN_STUDY_STATUSES.has((status ?? '').trim().toLowerCase());
}

export function selectTrialsWithOpenBias(
  trials: DashboardTrialCard[],
  count: number,
  openFraction = 0.7
): DashboardTrialCard[] {
  const open = trials.filter((t) => isOpenStudyStatus(t.study_status));
  const closed = trials.filter((t) => !isOpenStudyStatus(t.study_status));
  const wantOpen = Math.min(Math.round(count * openFraction), open.length);
  const wantClosed = Math.min(count - wantOpen, closed.length);
  const actualOpen = Math.min(open.length, count - wantClosed);
  return [...open.slice(0, actualOpen), ...closed.slice(0, wantClosed)];
}

const CANCER_ABBREVS = new Set([
  'NSCLC', 'SCLC', 'BC', 'MBC', 'ABC', 'CRC', 'MCRC', 'HCC', 'RCC', 'MRCC',
  'AML', 'CLL', 'CML', 'NHL', 'MM', 'MDS', 'DLBCL', 'FL', 'MCL', 'GBM',
  'TNBC', 'ER+', 'HR+', 'HER2+', 'HER2-', 'PD-L1', 'EGFR', 'ALK', 'KRAS',
  'BRAF', 'MEK', 'IO', 'TKI', 'VEGF', 'CTDNA', 'TMB', 'MSI', 'DMMR',
  'PMMR', 'MSS', 'MSI-H', 'TMB-H', 'ER', 'PR', 'OS', 'PFS', 'ORR', 'DOR',
  'DCR', 'CBR', 'TTP', 'EFS', 'RFS', 'DFS', 'TTR', 'CR', 'SD', 'PD', 'NE',
  'BCC', 'SCC', 'NPC', 'BTC', 'OC', 'EC', 'GC', 'GEJ', 'ESCC', 'PDAC',
  'NET', 'NEC', 'MCC', 'GIST', 'PNET', 'LGG', 'HGG', 'IDH',
  'ASCO', 'ESMO', 'AACR', 'WHO', 'ECOG', 'R/R', 'R/M', 'UC', 'UBC',
]);

/**
 * Extract a trial acronym/name from the end of a brief title.
 * Titles often append the trial name in parentheses or brackets, e.g.:
 *   "A Phase 3 Study of Pembrolizumab in TNBC (KEYNOTE-522)"
 * Returns null if no bracket is found or the candidate looks like a cancer/biomarker abbreviation.
 */
export function extractTrialAcronym(title: string | null): string | null {
  if (!title) return null;
  const match = title.match(/[\[(]\s*([^\])]+?)\s*[\])]\s*$/);
  if (!match) return null;
  const candidate = match[1].trim();
  if (CANCER_ABBREVS.has(candidate.toUpperCase())) return null;
  if (candidate.length <= 2) return null;
  // Digit or hyphen → almost certainly a trial code (KEYNOTE-522, IMpower110)
  if (/[\d-]/.test(candidate)) return candidate;
  // Mixed-case word → proper noun trial name (CheckMate, Destiny)
  if (candidate.length > 3 && candidate !== candidate.toUpperCase() && candidate !== candidate.toLowerCase()) return candidate;
  // All-caps longer than 5 chars → likely trial acronym (FLAURA, MONARCH)
  if (candidate === candidate.toUpperCase() && candidate.length > 5) return candidate;
  // Short all-caps (3–5): denylist already filtered risky ones; accept the rest
  return candidate;
}

export interface ExtractedTrialMetadata {
  nctId: string;
  title: string;
  phase: string;
  sponsor: string;
  status: string;
  cancerType: string;
  abstractId: string;
  year: string | number;
}

/**
 * Extract and normalize trial metadata from document.
 * Handles various metadata field name variations.
 */
export function extractTrialMetadata(data: Document): ExtractedTrialMetadata {
  const metadata = data.metadata || {};
  const getStr = (val: unknown): string => typeof val === 'string' || typeof val === 'number' ? String(val) : '';

  return {
    nctId: getStr(metadata.nct_number) || getStr(metadata.trial_id) || 'N/A',
    title: getStr(metadata.title) || data.original_filename || 'Untitled',
    phase: getStr(metadata.phase) || getStr(metadata.clinical_trial_phase) || 'N/A',
    sponsor: getStr(metadata.sponsor) || getStr(metadata.sponsors) || 'N/A',
    status: getStr(metadata.status) || 'Unknown',
    cancerType: getStr(metadata.cancer_type) || 'N/A',
    abstractId: getStr(metadata.abstract_id) || getStr(metadata.abstract_number) || 'N/A',
    year: getStr(metadata.year) || 'N/A',
  };
}

/**
 * Safely format a date string to a localized date string.
 * Returns 'N/A' if date is invalid or cannot be parsed.
 */
export function formatDate(dateString: string | undefined): string {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleDateString();
  } catch {
    return 'N/A';
  }
}

/**
 * Extract attribute value from abstract arm attributes.
 * Handles both direct values and nested value objects.
 */
export function extractAttributeValue(attributes: Record<string, unknown> | null | undefined, key: string): string {
  if (!attributes || !key) return '';
  
  // Try direct key
  let attr = attributes[key];
  if (!attr) {
    // Try lowercase key
    attr = attributes[key.toLowerCase()];
  }
  if (!attr) {
    // Try AttributeType.KEY format
    attr = attributes[`AttributeType.${key}`];
  }
  
  if (!attr) return '';
  
  // Handle both direct values and nested value objects
  if (typeof attr === 'string') return attr;
  if (typeof attr === 'object' && attr !== null) {
    const attrObj = attr as Record<string, unknown>;
    const val = attrObj.value ?? attrObj.attribute_type ?? '';
    return typeof val === 'string' || typeof val === 'number' ? String(val) : '';
  }
  
  return String(attr);
}

/**
 * Check if a value is meaningful (not empty, null, or "Not found")
 */
function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed !== '' && trimmed.toLowerCase() !== 'not found';
  }
  if (typeof value === 'boolean') return true;
  if (typeof value === 'number') return true;
  return true;
}

/**
 * Get a clean display value from an attribute
 */
function getAttributeDisplayValue(attr: unknown): string | null {
  if (!attr) return null;
  
  // Handle direct value
  if (typeof attr === 'string' || typeof attr === 'number' || typeof attr === 'boolean') {
    return hasValue(attr) ? String(attr) : null;
  }
  
  // Handle object with value property
  if (typeof attr === 'object' && attr !== null) {
    const attrObj = attr as Record<string, unknown>;
    const value = attrObj.value !== undefined ? attrObj.value : attr;
    return hasValue(value) ? String(value) : null;
  }
  
  return null;
}

/**
 * Mapping from enum names to display names (matches json_to_csv.py)
 * This ensures consistent display names across the application
 */
const ENUM_TO_DISPLAY_NAME: Record<string, string> = {
  'CONFERENCE': 'Conference',
  'PUBLISHED_YEAR': 'Published Year',
  'ABSTRACT_NUMBER': 'Abstract Number',
  'COMMENTS': 'Comments',
  'TRIAL_NAME': 'Trial Name',
  'CANCER_TYPE': 'Cancer Type',
  'CANCER_STAGE': 'Cancer Stage',
  'SPONSORS': 'Sponsors',
  'CLINICAL_TRIAL_PHASE': 'Clinical Trial Phase',
  'CHEMOTHERAPY_NAIVE': 'Chemotherapy Naive',
  'CHEMOTHERAPY_FAILED': 'Chemotherapy Failed',
  'ICI_NAIVE': 'Immune Checkpoint Inhibitor (ICI) Naive',
  'ICI_FAILED': 'Immune Checkpoint Inhibitor (ICI) failed',
  'IPILIMUMAB_FAILURE': 'Ipilimumab-failure or Ipilimumab-refractory',
  'ANTI_PD1_FAILURE': 'Anti PD-1/L1-failure or Anti PD-1/L1-refractory',
  'MUTATION_STATUS': 'Mutation status',
  'BRAF_MUTATION': 'BRAF-Mutation',
  'NRAS_MUTATION': 'NRAS-Mutation',
  'BIOSIMILAR': 'Biosimilar',
  'LINE_OF_TREATMENT': 'Line of Treatment',
  'NCT_NUMBER': 'NCT Number',
  'PRIMARY_ENDPOINT': 'Primary Endpoint',
  'SECONDARY_ENDPOINT': 'Secondary Endpoint',
  'BIOMARKER_INCLUSION': 'Biomarker Inclusion',
  'BIOMARKERS_INCLUSION_CRITERIA': 'Biomarkers Inclusion Criteria',
  'BIOMARKERS_EXCLUSION_CRITERIA': 'Biomarkers Exclusion Criteria',
  'STUDY_START_DATE': 'Study Start Date',
  'STUDY_COMPLETION_DATE': 'Study Completion Date',
  'STUDY_TYPE': 'Study Type',
  'PRIMARY_COMPLETION_DATE': 'Primary Completion Date',
  'FIRST_RESULTS': 'First Results',
  'TRIAL_RUN_IN_EUROPE': 'Trial run in Europe',
  'TRIAL_RUN_IN_US': 'Trial run in US',
  'TRIAL_RUN_IN_CHINA': 'Trial run in China',
  'GENERIC_NAME': 'Generic name',
  'BRAND_NAME': 'Brand name',
  'DOSAGE': 'Dosage',
  'TYPE_OF_DOSING': 'Type of dosing',
  'MECHANISM_OF_ACTION': 'Mechanism of action',
  'TARGET_PROTEIN': 'Target Protein',
  'TYPE_OF_THERAPY': 'Type of therapy',
  'SUB_THERAPY': 'Sub-therapy',
  'MEDIAN_AGE': 'Median Age',
  'NUMBER_OF_PATIENTS': 'Number of patients',
  'MEDIAN_PFS': 'Median Progression free survival (PFS)',
  'MEDIAN_FOLLOWUP_PFS': 'Median follow-up for measuring PFS',
  'P_VALUE_PFS': 'p-value of median PFS',
  'HR_PFS': 'Hazard ratio (HR) PFS',
  'MEDIAN_OS': 'Median Overall survival (OS)',
  'MEDIAN_FOLLOWUP_OS': 'Median follow-up for measuring OS',
  'P_VALUE_OS': 'p-value of OS',
  'HR_OS': 'Hazard ratio (HR) OS',
  'OBJECTIVE_RESPONSE_RATE': 'Objective response rate (ORR)',
  'COMPLETE_RESPONSE': 'Complete Response (CR)',
  'PATHOLOGICAL_COMPLETE_RESPONSE': 'Pathological Complete Response (pCR)',
  'COMPLETE_METABOLIC_RESPONSE': 'Complete Metabolic Response (CMR)',
  'DISEASE_CONTROL_RATE': 'Disease Control Rate or DCR',
  'CLINICAL_BENEFIT_RATE': 'Clinical Benefit Rate (CBR)',
  'MEDIAN_DOR': 'Median Duration of response or DOR',
  'DOR_RATE': 'Duration of Response (DOR) rate',
  'PFS_RATE_6M': 'PFS rate at 6 months',
  'PFS_RATE_9M': 'PFS rate at 9 months',
  'PFS_RATE_12M': 'PFS rate at 12 months or 1 year',
  'PFS_RATE_18M': 'PFS rate at 18 months',
  'PFS_RATE_24M': 'PFS rate at 24 months or 2 years',
  'PFS_RATE_36M': 'PFS rate at 36 months or 3 years',
  'PFS_RATE_48M': 'PFS rate at 48 months or 4 years',
  'OS_RATE_6M': 'OS rate at 6 months',
  'OS_RATE_9M': 'OS rate at 9 months',
  'OS_RATE_12M': 'OS rate at 12 months or 1 year',
  'OS_RATE_18M': 'OS rate at 18 months',
  'OS_RATE_24M': 'OS rate at 24 months or 2 years',
  'OS_RATE_36M': 'OS rate at 36 months or 3 years',
  'OS_RATE_48M': 'OS rate at 48 months or 4 years',
  'EFS': 'Event-Free Survival (EFS)',
  'P_VALUE_EFS': 'p-value of EFS',
  'HR_EFS': 'Hazard ratio (HR) EFS',
  'RFS': 'Recurrence-Free Survival (RFS)',
  'P_VALUE_RFS': 'p-value of RFS',
  'LENGTH_RFS': 'Length of measuring RFS',
  'HR_RFS': 'Hazard ratio (HR) RFS',
  'MFS': 'Metastasis-Free Survival (MFS)',
  'LENGTH_MFS': 'Length of measuring MFS',
  'HR_MFS': 'Hazard ratio (HR) MFS',
  'TTR': 'Time to response (TTR)',
  'TTP': 'Time to Progression (TTP)',
  'TTNT': 'Time to Next Treatment (TTNT)',
  'TTF': 'Time to Treatment Failure (TTF)',
  'AE': 'Adverse events (AE)',
  'GRADE_3_PLUS_AE': 'Grade 3+ or Grade 3 higher AE',
  'AE_LEADING_TO_DISCONTINUATION': 'AE leading to discontinuation',
  'SERIOUS_AE': 'Serious AE',
  'IMMUNE_RELATED_AE': 'Immune related AE',
  'SERIOUS_IMMUNE_RELATED_AE': 'Serious Immune related AE',
  'AE_LEADING_TO_DEATH': 'AE led or leading to death',
  'TEAE': 'Treatment-emergent adverse events (TEAE)',
  'GRADE_3_PLUS_TEAE': 'Grade 3+ or Grade 3 higher TEAE',
  'GRADE_3_TEAE': 'Grade 3 TEAE',
  'GRADE_4_TEAE': 'Grade 4 TEAE',
  'GRADE_5_TEAE': 'Grade 5 TEAE',
  'TEAE_LEADING_TO_DISCONTINUATION': 'TEAE led or leading to treatment discontinuation',
  'TEAE_LEADING_TO_DEATH': 'TEAE led or leading to death',
  'SERIOUS_TEAE': 'Serious TEAE',
  'TEAE_IMMUNE_RELATED': 'TEAE Immune related adverse events',
  'TRAE': 'Treatment-related adverse events (TRAE)',
  'GRADE_3_PLUS_TRAE': 'Grade 3+ or Grade 3 higher TRAE',
  'GRADE_3_TRAE': 'Grade 3 TRAE',
  'GRADE_4_TRAE': 'Grade 4 TRAE',
  'GRADE_5_TRAE': 'Grade 5 TRAE',
  'TRAE_LEADING_TO_DISCONTINUATION': 'TRAE led or leading to treatment discontinuation',
  'TRAE_LEADING_TO_DEATH': 'TRAE led or leading to death',
  'TRAE_IMMUNE_RELATED': 'TRAE Immune related adverse events',
  'SERIOUS_TRAE': 'Serious TRAE',
  'CRS': 'Cytokine Release Syndrome or CRS',
  'WBC_DECREASED': 'White blood cell (WBC) decreased',
};

/**
 * Clean attribute name from 'AttributeType.XXX' to 'XXX'
 */
function cleanAttributeName(attrStr: string): string {
  if (attrStr.startsWith('AttributeType.')) {
    return attrStr.replace('AttributeType.', '');
  }
  return attrStr;
}

/**
 * Format attribute key for display using the enum-to-display mapping
 */
function formatAttributeKey(key: string): string {
  // Clean the key (remove AttributeType. prefix if present)
  const cleanKey = cleanAttributeName(key);
  
  // Try to get display name from mapping
  const displayName = ENUM_TO_DISPLAY_NAME[cleanKey.toUpperCase()];
  if (displayName) {
    return displayName;
  }
  
  // Fallback: convert snake_case to Title Case for unmapped attributes
  return cleanKey
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
    .replace(/\b(Id|Nct|Orr|Pfs|Os|Ae|Trae|Teae|Ici|Crs|Wbc|Efs|Rfs|Mfs|Ttp|Ttnt|Ttf|Ttr|Pcr|Cmr|Dcr|Cbr|Dor|Hr|Ecog|Nci|Ctcae|UlN|Ast|Alt|Anc|Hiv|Ct|Pd|L1|Lag|Mek|BraF|Nras|Mcc)\b/gi, (match) => {
      const upper = match.toUpperCase();
      const specialCases: Record<string, string> = {
        'ID': 'ID',
        'NCT': 'NCT',
        'ORR': 'ORR',
        'PFS': 'PFS',
        'OS': 'OS',
        'AE': 'AE',
        'TRAE': 'TRAE',
        'TEAE': 'TEAE',
        'ICI': 'ICI',
        'CRS': 'CRS',
        'WBC': 'WBC',
        'EFS': 'EFS',
        'RFS': 'RFS',
        'MFS': 'MFS',
        'TTP': 'TTP',
        'TTNT': 'TTNT',
        'TTF': 'TTF',
        'TTR': 'TTR',
        'PCR': 'pCR',
        'CMR': 'CMR',
        'DCR': 'DCR',
        'CBR': 'CBR',
        'DOR': 'DOR',
        'HR': 'HR',
        'ECOG': 'ECOG',
        'NCI': 'NCI',
        'CTCAE': 'CTCAE',
        'ULN': 'ULN',
        'AST': 'AST',
        'ALT': 'ALT',
        'ANC': 'ANC',
        'HIV': 'HIV',
        'CT': 'CT',
        'PD': 'PD',
        'L1': 'L1',
        'LAG': 'LAG',
        'MEK': 'MEK',
        'BRAF': 'BRAF',
        'NRAS': 'NRAS',
        'MCC': 'MCC',
      };
      return specialCases[upper] || match;
    });
}

interface AbstractDataInput {
  abstract_id?: string;
  publication_id?: string;
  title?: string;
  arm_results?: Record<string, ArmResultInput>;
  outcome?: Record<string, unknown> | null;
  trial?: {
    nct_id?: string;
    brief_title?: string | null;
    overall_status?: string | null;
    phases?: string[] | null;
    enrollment_count?: number | null;
    lead_sponsor_name?: string | null;
    lead_sponsor_class?: string | null;
    conditions?: string[] | null;
  } | null;
  landscape?: {
    nct_id?: string;
    cancer_type?: string | null;
    modality?: string | null;
    treatment_name?: string | null;
    stage?: string | null;
    biomarker?: string | null;
    line_of_therapy?: string | null;
    acronym?: string | null;
  } | null;
  [key: string]: unknown;
}

interface ArmResultInput {
  arm_id?: string;
  arm_name?: string;
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * Extract abstract details from full abstract JSON structure.
 */
export function extractAbstractDetails(abstractData: AbstractDataInput | null) {
  if (!abstractData) return null;
  
  const armResults = abstractData.arm_results || {};
  const firstArmKey = Object.keys(armResults)[0];
  const firstArm = firstArmKey ? armResults[firstArmKey] : null;
  const attributes = firstArm?.attributes || {};
  
  // Determine if it's a publication
  const isPublication = !!abstractData.publication_id;
  const abstractId = abstractData.abstract_id || abstractData.publication_id || '';
  
  const outcome = (abstractData.outcome ?? {}) as Record<string, unknown>;
  const trial = abstractData.trial ?? null;
  const landscape = abstractData.landscape ?? null;
  const outcomeStr = (key: string): string => {
    const v = outcome[key];
    return typeof v === 'string' || typeof v === 'number' ? String(v) : '';
  };

  // Extract conference/year — prefer the flat outcome columns, fallback to abstract_id parsing.
  let conference = outcomeStr('conference');
  let year = outcomeStr('published_year') || outcomeStr('publication_year');
  if (abstractId) {
    if (!conference && abstractId.startsWith('ASCO_')) conference = 'ASCO';
    if (!conference && abstractId.startsWith('ESMO_')) conference = 'ESMO';
    if (!year) {
      const match = abstractId.match(/_(\d{4})/);
      if (match) year = match[1];
    }
  }

  // Extract common fields — prefer joined relational data when present.
  const nctNumber = (trial?.nct_id as string) ||
                    outcomeStr('nct_id') ||
                    extractAttributeValue(attributes, 'NCT_NUMBER') ||
                    extractAttributeValue(attributes, 'nct_number') || '';
  const title = (trial?.brief_title as string) ||
                outcomeStr('trial_name') ||
                extractAttributeValue(attributes, 'TRIAL_NAME') ||
                extractAttributeValue(attributes, 'trial_name') ||
                abstractData.title || '';
  const phase = outcomeStr('phase') ||
                (Array.isArray(trial?.phases) ? (trial!.phases as string[]).join(', ') : '') ||
                extractAttributeValue(attributes, 'CLINICAL_TRIAL_PHASE') ||
                extractAttributeValue(attributes, 'clinical_trial_phase') || '';
  const sponsor = (trial?.lead_sponsor_name as string) ||
                  extractAttributeValue(attributes, 'SPONSORS') ||
                  extractAttributeValue(attributes, 'sponsors') || '';
  const status = (trial?.overall_status as string) ||
                 extractAttributeValue(attributes, 'STATUS') ||
                 extractAttributeValue(attributes, 'status') || '';
  const outcomeCancerType = Array.isArray(outcome.cancer_type)
    ? ((outcome.cancer_type as string[])[0] ?? '')
    : outcomeStr('cancer_type');
  const cancerType = outcomeCancerType ||
                     (Array.isArray(trial?.conditions) ? (trial!.conditions as string[])[0] ?? '' : '') ||
                     extractAttributeValue(attributes, 'CANCER_TYPE') ||
                     extractAttributeValue(attributes, 'cancer_type') || '';
  const lineOfTherapy = (landscape?.line_of_therapy as string) ||
                        extractAttributeValue(attributes, 'LINE_OF_TREATMENT') ||
                        extractAttributeValue(attributes, 'line_of_treatment') || '';
  const treatment = outcomeStr('arm_name') ||
                    (landscape?.treatment_name as string) ||
                    extractAttributeValue(attributes, 'GENERIC_NAME') ||
                    extractAttributeValue(attributes, 'generic_name') || '';
  const indication = cancerType;
  const population = extractAttributeValue(attributes, 'POPULATION') ||
                     extractAttributeValue(attributes, 'population') || '';
  const target = outcomeStr('target') ||
                 extractAttributeValue(attributes, 'TARGET') ||
                 extractAttributeValue(attributes, 'target') || '';
  const modality = outcomeStr('modality') ||
                   extractAttributeValue(attributes, 'MODALITY') ||
                   extractAttributeValue(attributes, 'modality') || '';
  const sessionType = extractAttributeValue(attributes, 'SESSION_TYPE') ||
                      extractAttributeValue(attributes, 'session_type') || '';
  const numberOfPatients = (typeof trial?.enrollment_count === 'number' ? String(trial!.enrollment_count) : '') ||
                           outcomeStr('num_patients') ||
                           extractAttributeValue(attributes, 'NUMBER_OF_PATIENTS') ||
                           extractAttributeValue(attributes, 'number_of_patients') || '';
  
  // Clean phase value
  const cleanPhase = phase.replace(/PHASE/gi, '').trim() || phase;
  
  // Extract source URL for web-scraped trials
  const sourceUrl = typeof abstractData.source_url === 'string' ? abstractData.source_url : '';
  
  return {
    abstractId,
    isPublication,
    conference,
    year,
    nctNumber,
    title,
    phase: cleanPhase,
    sponsor,
    status,
    cancerType,
    lineOfTherapy,
    treatment,
    indication,
    population,
    target,
    modality,
    sessionType,
    numberOfPatients,
    sourceUrl,
    armResults,
    attributes,
    rawData: abstractData,
  };
}

type NestedResultsSection = { Efficacy: Record<string, string>; Safety: Record<string, string> };
type SectionValue = Record<string, string> | NestedResultsSection;

/**
 * Organize attributes into logical sections
 */
export function organizeAttributesBySection(armResults: Record<string, ArmResultInput>): Record<string, SectionValue> {
  const sections: Record<string, Record<string, string>> = {};
  
  // Helper function to check if key matches any pattern
  const matchesPattern = (key: string, patterns: string[]): boolean => {
    const lowerKey = key.toLowerCase();
    return patterns.some(pattern => {
      const lowerPattern = pattern.toLowerCase();
      return lowerKey === lowerPattern || 
             lowerKey.includes(lowerPattern) || 
             lowerPattern.includes(lowerKey);
    });
  };
  
  // Attributes to hide from display
  const hiddenAttributes = new Set([
    'AttributeType.BIOMARKERS_EXCLUSION_CRITERIA',
    'BIOMARKERS_EXCLUSION_CRITERIA',
    'biomarkers_exclusion_criteria',
    'AttributeType.BIOMARKERS_INCLUSION_CRITERIA',
    'BIOMARKERS_INCLUSION_CRITERIA',
    'biomarkers_inclusion_criteria',
  ]);
  
  // Initialize Results section with Efficacy and Safety sub-sections
  const resultsSection: { Efficacy: Record<string, string>; Safety: Record<string, string> } = {
    'Efficacy': {},
    'Safety': {},
  };
  
  // Process each arm
  Object.entries(armResults).forEach(([armId, armData]) => {
    const armAttributes = armData?.attributes || {};
    const armName = armData?.arm_name || armId;
    
    // Process each attribute
    Object.entries(armAttributes).forEach(([key, value]) => {
      // Skip hidden attributes
      if (hiddenAttributes.has(key)) return;
      
      const displayValue = getAttributeDisplayValue(value);
      if (!displayValue) return;
      
      const lowerKey = key.toLowerCase();
      let category = 'Other';
      let subCategory: 'Efficacy' | 'Safety' | null = null;
      
      // Trial Information
      if (matchesPattern(key, ['trial_name', 'nct_number', 'abstract_number', 'publication_name', 
                               'publication_year', 'published_year', 'conference', 'abstract_id', 
                               'publication_id', 'pdf_number', 'comments', 'study_type', 'first_results'])) {
        category = 'Trial Information';
      }
      // Trial Design
      else if (matchesPattern(key, ['clinical_trial_phase', 'status', 'study_start_date', 
                                     'study_completion_date', 'primary_completion_date', 
                                     'trial_run_in_europe', 'trial_run_in_us', 'trial_run_in_china'])) {
        category = 'Trial Design';
      }
      // Disease & Population
      else if (matchesPattern(key, ['cancer_type', 'cancer_stage', 'line_of_treatment', 'population',
                                     'chemotherapy_naive', 'chemotherapy_failed', 'ici_naive', 'ici_failed',
                                     'ipilimumab_failure', 'anti_pd1_failure', 'mutation_status', 
                                     'braf_mutation', 'nras_mutation', 'biomarker_inclusion', 
                                     'biomarkers_inclusion_criteria', 'biomarkers_exclusion_criteria',
                                     'maximum_age', 'minimum_age', 'sex'])) {
        category = 'Disease & Population';
      }
      // Sponsor
      else if (matchesPattern(key, ['sponsors', 'company_eu', 'company_us', 'company_china'])) {
        category = 'Sponsor';
      }
      // Endpoints
      else if (matchesPattern(key, ['primary_endpoint', 'secondary_endpoint'])) {
        category = 'Endpoints';
      }
      // Treatment
      else if (matchesPattern(key, ['generic_name', 'brand_name', 'arm_name', 'dosage', 
                                     'type_of_dosing', 'mechanism_of_action', 'target_protein', 
                                     'type_of_therapy', 'sub_therapy', 'biosimilar', 
                                     'number_of_doses_per_year'])) {
        category = 'Treatment';
      }
      // Number of patients goes to Efficacy
      else if (matchesPattern(key, ['number_of_patients'])) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      // Patient Demographics
      else if (matchesPattern(key, ['median_age'])) {
        category = 'Patient Demographics';
      }
      // Efficacy - PFS
      else if (lowerKey.includes('pfs') && !lowerKey.includes('rate')) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      else if (lowerKey.includes('pfs_rate') || lowerKey.includes('pfs at')) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      // Efficacy - OS
      else if (lowerKey.includes('os') && !lowerKey.includes('rate') && !lowerKey.includes('dose')) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      else if (lowerKey.includes('os_rate') || lowerKey.includes('os at')) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      // Efficacy - Response
      else if (matchesPattern(key, ['orr', 'objective_response_rate', 'complete_response', 'cr',
                                     'pathological_complete_response', 'pcr', 'complete_metabolic_response',
                                     'cmr', 'disease_control_rate', 'dcr', 'clinical_benefit_rate',
                                     'cbr', 'duration_of_response', 'dor'])) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      // Efficacy - Other
      else if (matchesPattern(key, ['efs', 'event_free_survival', 'rfs', 'recurrence_free_survival',
                                     'mfs', 'metastasis_free_survival', 'ttr', 'time_to_response',
                                     'ttp', 'time_to_progression', 'ttnt', 'time_to_next_treatment',
                                     'ttf', 'time_to_treatment_failure'])) {
        category = 'Results';
        subCategory = 'Efficacy';
      }
      // Safety - TEAE
      else if (lowerKey.includes('teae') || (lowerKey.includes('treatment_emergent') && lowerKey.includes('adverse'))) {
        category = 'Results';
        subCategory = 'Safety';
      }
      // Safety - TRAE
      else if (lowerKey.includes('trae') || (lowerKey.includes('treatment_related') && lowerKey.includes('adverse'))) {
        category = 'Results';
        subCategory = 'Safety';
      }
      // Safety - General
      else if (lowerKey.includes('adverse') || lowerKey.includes('ae') || 
               lowerKey.includes('serious') || lowerKey.includes('immune_related')) {
        category = 'Results';
        subCategory = 'Safety';
      }
      
      // Store attribute with arm context (only if multiple arms, otherwise just show the key)
      const attrKey = Object.keys(armResults).length > 1 
        ? `${armName} - ${formatAttributeKey(key)}`
        : formatAttributeKey(key);
      
      // If it's a Results category, store in the nested structure
      if (category === 'Results' && subCategory) {
        if (!resultsSection[subCategory][attrKey]) {
          resultsSection[subCategory][attrKey] = displayValue;
        }
      } else {
        // Initialize category if needed
        if (!sections[category]) {
          sections[category] = {};
        }
        sections[category][attrKey] = displayValue;
      }
    });
  });
  
  // Add Results section if it has any content
  const result: Record<string, SectionValue> = { ...sections };
  if (Object.keys(resultsSection['Efficacy']).length > 0 || Object.keys(resultsSection['Safety']).length > 0) {
    result['Results'] = resultsSection;
  }
  
  return result;
}

/**
 * Extract short form from display name (e.g., "Objective response rate (ORR)" -> "ORR")
 */
function extractShortForm(displayName: string): string {
  const lowerName = displayName.toLowerCase();
  
  // First, try to extract from parentheses (e.g., "(ORR)", "(PFS)", "(HR)")
  const parenMatch = displayName.match(/\(([A-Z0-9]+)\)/);
  if (parenMatch) {
    const acronym = parenMatch[1];
    // For time-based rates, add the time period
    if (lowerName.includes('rate at')) {
      const timeMatch = displayName.match(/(\d+)\s*(month|year|m|y)/i);
      if (timeMatch) {
        const num = timeMatch[1];
        const unit = timeMatch[2].toLowerCase().startsWith('m') ? 'M' : 'Y';
        return `${acronym} ${num}${unit}`;
      }
    }
    return acronym;
  }
  
  // Handle time-based PFS/OS rates (e.g., "PFS rate at 6 months" -> "PFS 6M")
  if (lowerName.includes('pfs rate at') || lowerName.includes('os rate at')) {
    const metric = lowerName.includes('pfs') ? 'PFS' : 'OS';
    const timeMatch = displayName.match(/(\d+)\s*(month|year|m|y)/i);
    if (timeMatch) {
      const num = timeMatch[1];
      const unit = timeMatch[2].toLowerCase().startsWith('m') ? 'M' : 'Y';
      return `${metric} ${num}${unit}`;
    }
    return metric;
  }
  
  // Handle p-value attributes
  if (lowerName.includes('p-value')) {
    if (lowerName.includes('pfs')) return 'PFS p';
    if (lowerName.includes('os')) return 'OS p';
    if (lowerName.includes('efs')) return 'EFS p';
    if (lowerName.includes('rfs')) return 'RFS p';
    return 'p-value';
  }
  
  // Handle Hazard ratio (HR) attributes
  if (lowerName.includes('hazard ratio') || lowerName.includes('hr')) {
    if (lowerName.includes('pfs')) return 'PFS HR';
    if (lowerName.includes('os')) return 'OS HR';
    if (lowerName.includes('efs')) return 'EFS HR';
    if (lowerName.includes('rfs')) return 'RFS HR';
    if (lowerName.includes('mfs')) return 'MFS HR';
    return 'HR';
  }
  
  // Handle Median follow-up
  if (lowerName.includes('median follow-up') || lowerName.includes('follow-up')) {
    if (lowerName.includes('pfs')) return 'PFS FU';
    if (lowerName.includes('os')) return 'OS FU';
    return 'FU';
  }
  
  // Handle Length of measuring
  if (lowerName.includes('length of measuring')) {
    if (lowerName.includes('rfs')) return 'RFS Length';
    if (lowerName.includes('mfs')) return 'MFS Length';
    return 'Length';
  }
  
  // Handle Grade-based attributes (including specific adverse events)
  if (lowerName.includes('grade')) {
    const gradeMatch = displayName.match(/Grade\s*(\d+)\s*\+?/i);
    const hasPlus = displayName.includes('+') || displayName.includes('higher');
    const grade = gradeMatch ? `G${gradeMatch[1]}${hasPlus ? '+' : ''}` : '';
    
    // Handle Grade 3+ specific adverse events (e.g., "Grade 3+ AE Thrombocytopenia")
    if (grade && (lowerName.includes('ae') || lowerName.includes('trae') || lowerName.includes('teae'))) {
      // Extract the specific condition/event name
      const specificConditions: Array<[string, string]> = [
        ['immune related adverse events', 'irAE'],
        ['iraes', 'irAE'],
        ['cytokine release syndrome', 'CRS'],
        ['crs', 'CRS'],
        ['thrombocytopenia', 'Thromb'],
        ['neutropenia', 'Neutro'],
        ['leukopenia', 'Leuko'],
        ['nausea', 'Nausea'],
        ['anemia', 'Anemia'],
        ['diarrhea', 'Diarrhea'],
        ['colitis', 'Colitis'],
        ['hyperglycemia', 'Hypergly'],
        ['neutrophil count decreased', 'Neutrophil'],
        ['dyspnea', 'Dyspnea'],
        ['pyrexia', 'Pyrexia'],
        ['bleeding', 'Bleeding'],
        ['pruritus', 'Pruritus'],
        ['rash', 'Rash'],
        ['pneumonia', 'Pneumonia'],
        ['thyroiditis', 'Thyroid'],
        ['hypophysitis', 'Hypophy'],
        ['hepatitis', 'Hepatitis'],
        ['pneumonitis', 'Pneumon'],
        ['alanine aminotransferase', 'ALT'],
        ['white blood cell', 'WBC'],
        ['wbc', 'WBC'],
      ];
      
      // Check for specific conditions first (longer matches first)
      const sortedConditions = specificConditions.sort((a, b) => b[0].length - a[0].length);
      for (const [condition, conditionShort] of sortedConditions) {
        if (lowerName.includes(condition)) {
          if (lowerName.includes('teae')) return `${grade} TEAE ${conditionShort}`;
          if (lowerName.includes('trae')) return `${grade} TRAE ${conditionShort}`;
          if (lowerName.includes('ae') && !lowerName.includes('teae') && !lowerName.includes('trae')) {
            return `${grade} AE ${conditionShort}`;
          }
        }
      }
    }
    
    // General grade-based attributes
    if (lowerName.includes('teae')) return `TEAE ${grade}`;
    if (lowerName.includes('trae')) return `TRAE ${grade}`;
    if (lowerName.includes('ae') && !lowerName.includes('teae') && !lowerName.includes('trae')) {
      return `AE ${grade}`;
    }
    return grade || 'Grade';
  }
  
  // Handle specific attribute patterns
  const attributePatterns: Array<[RegExp | string, string]> = [
    ['objective response rate', 'ORR'],
    ['median progression free survival', 'PFS'],
    ['median overall survival', 'OS'],
    ['complete response', 'CR'],
    ['pathological complete response', 'pCR'],
    ['complete metabolic response', 'cmr'],
    ['disease control rate', 'DCR'],
    ['clinical benefit rate', 'cbr'],
    ['duration of response', 'DOR'],
    ['event-free survival', 'EFS'],
    ['recurrence-free survival', 'RFS'],
    ['metastasis-free survival', 'MFS'],
    ['time to response', 'TTR'],
    ['time to progression', 'TTP'],
    ['time to next treatment', 'TTNT'],
    ['time to treatment failure', 'TTF'],
    ['treatment-emergent adverse events', 'TEAE'],
    ['treatment-related adverse events', 'TRAE'],
    ['adverse events', 'AE'],
    ['serious ae', 'SAE'],
    ['immune related ae', 'irAE'],
    ['serious immune related ae', 'SirAE'],
    ['ae leading to discontinuation', 'AE Disc'],
    ['ae led or leading to death', 'AE Death'],
    ['teae led or leading to treatment discontinuation', 'TEAE Disc'],
    ['teae led or leading to death', 'TEAE Death'],
    ['teae immune related', 'TEAE ir'],
    ['trae led or leading to treatment discontinuation', 'TRAE Disc'],
    ['trae led or leading to death', 'TRAE Death'],
    ['trae immune related', 'TRAE ir'],
    ['serious teae', 'STEAE'],
    ['serious trae', 'STRAE'],
    ['cytokine release syndrome', 'CRS'],
    ['white blood cell', 'WBC'],
  ];
  
  for (const [pattern, acronym] of attributePatterns) {
    if (typeof pattern === 'string' ? lowerName.includes(pattern) : pattern.test(displayName)) {
      return acronym;
    }
  }
  
  // Fallback: extract uppercase acronyms (2-5 characters)
  const upperMatch = displayName.match(/\b([A-Z]{2,5})\b/);
  if (upperMatch) {
    return upperMatch[1];
  }
  
  // Last resort: return first 3-4 characters, capitalized
  const words = displayName.split(/\s+/).filter(w => w.length > 0);
  if (words.length > 0) {
    const firstWord = words[0];
    if (firstWord.length >= 3) {
      return firstWord.substring(0, 3).toUpperCase();
    }
    return firstWord.toUpperCase();
  }
  
  return displayName.substring(0, 3).toUpperCase();
}

/**
 * Extract all Efficacy and Safety attributes from abstract data
 * Excludes "number of patients"
 * Uses the same categorization logic as organizeAttributesBySection to ensure consistency
 */
export function extractEfficacyAndSafetyMetrics(abstractData: AbstractDataInput | null): Record<string, { value: string; shortForm: string }> {
  if (!abstractData) return {};
  
  const armResults = abstractData.arm_results || {};
  const metrics: Record<string, { value: string; shortForm: string }> = {};
  
  // Use organizeAttributesBySection to get properly categorized attributes
  const organizedSections = organizeAttributesBySection(armResults);
  
  // Extract Efficacy and Safety from Results section
  const resultsSection = organizedSections['Results'];
  if (!resultsSection || typeof resultsSection !== 'object') {
    return metrics;
  }
  
  // Get Efficacy attributes (excluding number of patients)
  const efficacyAttrs = resultsSection['Efficacy'] || {};
  Object.entries(efficacyAttrs).forEach(([displayName, value]) => {
    // Skip number of patients
    if (displayName.toLowerCase().includes('number of patients') || 
        displayName.toLowerCase().includes('number_of_patients')) {
      return;
    }
    
    const shortForm = extractShortForm(displayName);
    if (!metrics[shortForm]) {
      metrics[shortForm] = {
        value: String(value),
        shortForm: shortForm,
      };
    }
  });
  
  // Get Safety attributes
  const safetyAttrs = resultsSection['Safety'] || {};
  Object.entries(safetyAttrs).forEach(([displayName, value]) => {
    const shortForm = extractShortForm(displayName);
    if (!metrics[shortForm]) {
      metrics[shortForm] = {
        value: String(value),
        shortForm: shortForm,
      };
    }
  });
  
  return metrics;
}

/**
 * Extract key efficacy metrics from abstract data
 */
export function extractKeyMetrics(abstractData: AbstractDataInput | null): {
  metrics?: Record<string, { value: string; shortForm: string }>;
  conference?: string;
  year?: string;
  date?: string;
  abstractId?: string;
  publicationName?: string;
} {
  if (!abstractData) return {};
  
  const armResults = abstractData.arm_results || {};
  const firstArmKey = Object.keys(armResults)[0];
  const firstArm = firstArmKey ? armResults[firstArmKey] : null;
  const attributes = firstArm?.attributes || {};
  
  // Extract all Efficacy and Safety metrics
  const metrics = extractEfficacyAndSafetyMetrics(abstractData);
  
  // Extract conference and year
  const abstractId = abstractData.abstract_id || abstractData.publication_id || '';
  const isPublication = !!abstractData.publication_id;
  let conference = '';
  let year = '';
  
  if (abstractId) {
    if (abstractId.startsWith('ASCO_')) {
      conference = 'ASCO';
      const match = abstractId.match(/ASCO_(\d{4})/);
      year = match ? match[1] : '';
    } else if (abstractId.startsWith('ESMO_')) {
      conference = 'ESMO';
      const match = abstractId.match(/ESMO_(\d{4})/);
      year = match ? match[1] : '';
    }
  }
  
  // Extract publication year as fallback
  if (!year) {
    const pubYear = extractAttributeValue(attributes, 'PUBLICATION_YEAR') ||
                    extractAttributeValue(attributes, 'publication_year') ||
                    extractAttributeValue(attributes, 'PUBLISHED_YEAR') ||
                    extractAttributeValue(attributes, 'published_year') || '';
    year = pubYear;
  }
  
  // Extract publication name for publications
  let publicationName = '';
  if (isPublication) {
    publicationName = extractAttributeValue(attributes, 'PUBLICATION_NAME') ||
                      extractAttributeValue(attributes, 'publication_name') || '';
  }
  
  // For publications without a conference, use "Publication" as the conference label
  if (isPublication && !conference && year) {
    conference = 'Publication';
  }
  
  // Format date (typically ASCO is May 30-31, ESMO is in September/October)
  // Try to extract actual date from attributes first
  let date = '';
  const studyDate = extractAttributeValue(attributes, 'STUDY_START_DATE') ||
                    extractAttributeValue(attributes, 'study_start_date') ||
                    extractAttributeValue(attributes, 'FIRST_RESULTS') ||
                    extractAttributeValue(attributes, 'first_results');
  
  if (studyDate && studyDate !== 'Not found') {
    try {
      const dateObj = new Date(studyDate);
      if (!isNaN(dateObj.getTime())) {
        date = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      }
    } catch {
      // Fall through to default dates
    }
  }
  
  // Use default dates based on conference if no date found
  if (!date && conference && year) {
    if (conference === 'ASCO') {
      date = `May 30, ${year}`;
    } else if (conference === 'ESMO') {
      date = `Sep 15, ${year}`;
    }
  }
  
  return {
    metrics: Object.keys(metrics).length > 0 ? metrics : undefined,
    conference: conference || undefined,
    year: year || undefined,
    date: date || undefined,
    abstractId: abstractId || undefined,
    publicationName: publicationName || undefined,
  };
}

/**
 * Format abstract ID for display (e.g., ASCO-2025-6452)
 */
export function formatAbstractIdForDisplay(abstractId: string): string {
  if (!abstractId) return '';
  
  // Convert ASCO_2025_001 to ASCO-2025-001
  // Convert ESMO_2020_1076O to ESMO-2020-1076O
  return abstractId.replace(/_/g, '-');
}

