/** Cancer type options for dashboard dropdown (slug + display label). */
export const DASHBOARD_CANCER_TYPES = [
  { value: 'cutaneous-melanoma', label: 'Cutaneous/Metastasis Melanoma' },
  { value: 'acral-melanoma', label: 'Acral Melanoma' },
  { value: 'mucosal-melanoma', label: 'Mucosal Melanoma' },
  { value: 'uveal-melanoma', label: 'Uveal Melanoma' },
  { value: 'cutaneous-melanoma-with-brain-cns-metastasis', label: 'Cutaneous Melanoma with Brain/CNS Metastasis' },
  { value: 'cutaneous-squamous-cell-carcinoma', label: 'Cutaneous Squamous Cell Carcinoma' },
  { value: 'merkel-cell-carcinoma', label: 'Merkel Cell Carcinoma' },
  { value: 'basal-cell-carcinoma', label: 'Basal Cell Carcinoma' },
] as const;

export const DEFAULT_CANCER_TYPE_SLUG = 'cutaneous-melanoma';

/** Phase options for filter (display names). */
export const PHASE_OPTIONS = [
  'Early Phase 1',
  'Phase 1',
  'Phase 2',
  'Phase 3',
  'Phase 4',
  'Not applicable',
] as const;

/** Status options for filter (match study_status on trial cards). */
export const STATUS_OPTIONS = [
  'Open',
  'Closed',
  'Suspended',
  'Enrolling by invitation',
  'Unknown',
] as const;
