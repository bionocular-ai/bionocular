/** ClinicalTrials.gov API v2 phase enum → human-readable label */
export const PHASE_MAP: Record<string, string> = {
  'EARLY_PHASE1': 'Early Phase 1',
  'PHASE1':       'Phase 1',
  'PHASE2':       'Phase 2',
  'PHASE3':       'Phase 3',
  'PHASE4':       'Phase 4',
  'NA':           'Not applicable',
};

/** ClinicalTrials.gov API v2 status enum → human-readable label */
export const STATUS_MAP: Record<string, string> = {
  'RECRUITING':              'Recruiting',
  'NOT_YET_RECRUITING':      'Not yet recruiting',
  'ACTIVE_NOT_RECRUITING':   'Active, not recruiting',
  'COMPLETED':               'Completed',
  'TERMINATED':              'Terminated',
  'SUSPENDED':               'Suspended',
  'WITHDRAWN':               'Withdrawn',
  'ENROLLING_BY_INVITATION': 'Enrolling by invitation',
  'UNKNOWN':                 'Unknown',
};

export function normalizePhase(raw: string): string {
  return PHASE_MAP[raw] ?? raw;
}

export function normalizeStatus(raw: string): string {
  return STATUS_MAP[raw] ?? raw;
}
