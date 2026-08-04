/**
 * Display formatting for `km_curves.arm_name`.
 *
 * Unlike `trial_outcomes.arm_name`, which the backend canonicalizes at write
 * time, KM curve arms carry the raw extraction key - snake_case, occasionally
 * with dose or biomarker suffixes (e.g. `atezolizumab_plus_cobimetinib_and_
 * vemurafenib`, `pembrolizumab_10_mg_kg`, `pd_l1_positive`).
 *
 * This formats for display only. It does not merge arms that differ purely by
 * spelling, so two rows can still render the same label.
 */

/** Tokens whose casing must survive title-casing. */
const ACRONYMS: Record<string, string> = {
  pdl1: 'PD-L1',
  ldh: 'LDH',
  trae: 'TRAE',
  braf: 'BRAF',
  brafi: 'BRAFi',
  dtic: 'DTIC',
  icc: 'ICC',
  ici: 'ICI',
};

/** Units and joining words that stay lowercase mid-label. */
const LOWERCASE = new Set(['mg/kg', 'mg', 'kg', 'of', 'with', 'per']);

function formatToken(token: string, index: number): string {
  const lower = token.toLowerCase();
  if (ACRONYMS[lower]) return ACRONYMS[lower];
  if (index > 0 && LOWERCASE.has(lower)) return lower;
  // Dosing schedules: q2w -> Q2W.
  if (/^q\d+w$/i.test(token)) return token.toUpperCase();
  // Cohort and group letters: group_a -> Group A.
  if (/^[a-z]$/.test(token)) return token.toUpperCase();
  // Already carries deliberate casing (pCR, NIVO, M1a) - leave it alone.
  if (token !== lower) return token;
  if (/^\d/.test(token)) return token;
  return token.charAt(0).toUpperCase() + token.slice(1);
}

export function formatArmName(raw: string): string {
  if (!raw) return raw;

  return raw
    .replace(/pd_l1/gi, 'pdl1')
    .replace(/_(?:plus|and)_/g, ' + ')
    .replace(/mg_kg/g, 'mg/kg')
    .replace(/_/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(formatToken)
    .join(' ')
    .trim();
}
