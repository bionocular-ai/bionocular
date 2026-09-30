/**
 * Which rows of one trial are the same treatment, and which readout of it is newest.
 *
 * One arm reaches `trial_outcomes` once per readout: RELATIVITY-047's
 * combination arm is "Relatlimab-Nivolumab" in NEJM 2022, "Relatlimab +
 * Nivolumab" at ASCO 2021 and "NIVO + RELA" at ASCO 2026. `arm_id` is positional
 * per source (ESMO_2025_1619P's `arm_2` is the combination) and `generic_name`
 * is empty on abstracts, so neither identifies it. The drug set does.
 */

type Row = Record<string, unknown>;

/** Abbreviations abstracts use for drugs the other readouts name in full. */
const ALIASES: Record<string, string> = {
  nivo: 'nivolumab',
  rela: 'relatlimab',
  ipi: 'ipilimumab',
  pembro: 'pembrolizumab',
  dab: 'dabrafenib',
  tram: 'trametinib',
  enco: 'encorafenib',
  bini: 'binimetinib',
  vem: 'vemurafenib',
  cobi: 'cobimetinib',
  atezo: 'atezolizumab',
  nuru: 'nurulimab',
  prolgo: 'prolgolimab',
};

/**
 * Words that describe the arm, not the drugs in it. A placebo add-on is the
 * same treatment as the drugs beside it, and the setting is the table's
 * section, not part of the regimen.
 */
const NOT_DRUGS = /\b(placebo|monotherapy|mono|neoadjuvant|adjuvant|first[- ]line)\b/g;

const SEPARATORS = /\s*(?:\+|\/|,|-|\bplus\b|\band\b|\bwith\b)\s*/;

/**
 * The drugs of an arm name, expanded and sorted, so every spelling of one
 * regimen gives one key. Dosing words stay: KEYNOTE-006's two pembrolizumab
 * schedules are two treatments. A name that is only a placebo keeps "placebo"
 * rather than an empty key.
 */
export function regimenKey(armName: string): string {
  const lower = armName.toLowerCase();
  const drugs = lower
    .replace(NOT_DRUGS, ' ')
    .split(SEPARATORS)
    .map((word) => word.replace(/\s+/g, ' ').trim())
    .filter((word) => word !== '')
    .map((word) => ALIASES[word] ?? word);
  if (drugs.length === 0) return /placebo/.test(lower) ? 'placebo' : lower.trim();
  return [...new Set(drugs)].sort().join('+');
}

/** The one source a row came from: an abstract, a publication or a web page. */
export function readoutOf(row: Row): string | null {
  const source = row.abstract_id ?? row.publication_id ?? row.source_url;
  return typeof source === 'string' ? source : null;
}

/** Meeting months, so an ESMO abstract reads as newer than the same year's ASCO. */
const MEETING_MONTH: Record<string, number> = { ASCO: 6, ESMO: 10, SITC: 11 };

/**
 * `[year, month]` of a readout, for newest-first ordering. A publication's
 * month is not recorded, so it is 0. A citation with no year ("J Clin Oncol
 * 36:383-390." - 28 of 130 in production) and a web page date to `[0, 0]`:
 * oldest, never guessed newer.
 */
export function readoutDate(row: Row): [number, number] {
  const meeting = typeof row.abstract_id === 'string' ? /^([A-Z]+)_(\d{4})_/.exec(row.abstract_id) : null;
  if (meeting) return [Number(meeting[2]), MEETING_MONTH[meeting[1]] ?? 0];
  const year = typeof row.publication_id === 'string' ? /\b(?:19|20)\d\d\b/.exec(row.publication_id) : null;
  return [year ? Number(year[0]) : 0, 0];
}
