import type { LiveTickerResult } from '@/lib/api';

const SOURCES: Record<string, string> = {
  'biospace.com': 'BioSpace',
  'onclive.com': 'OncLive',
  'targetedonc.com': 'Targeted Oncology',
  'cancernetwork.com': 'CancerNetwork',
};

/** Publication name for an article URL; unknown hosts show as the bare host. */
export function sourceOf(url: string): string {
  let host: string;
  try {
    host = new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
  const known = Object.keys(SOURCES).find((h) => host === h || host.endsWith(`.${h}`));
  return known ? SOURCES[known] : host;
}

/** Drops a trailing " - BioSpace" style suffix when it repeats the source already shown. */
export function cleanTitle(title: string, source: string): string {
  const t = title.trim();
  const suffix = ` - ${source}`;
  return source && t.toLowerCase().endsWith(suffix.toLowerCase()) ? t.slice(0, -suffix.length) : t;
}

const ACRONYMS: Record<string, string> = {
  hr: 'HR', os: 'OS', pfs: 'PFS', rfs: 'RFS', efs: 'EFS', dmfs: 'DMFS', orr: 'ORR', dcr: 'DCR',
  cr: 'CR', pr: 'PR', pd: 'PD', dor: 'DoR', ae: 'AE', aes: 'AEs', trae: 'TRAE', teae: 'TEAE',
  teaes: 'TEAEs', ctdna: 'ctDNA', itt: 'ITT', ci: 'CI', pct: '%', us: 'US',
};

/** "grade_3_plus_trae_rate_combination_arm" -> "Grade 3+ TRAE rate combination arm". Already-readable keys pass through. */
export function humanizeMetric(key: string): string {
  // Keys with spaces are already prose; snake_case ones may carry a non-ASCII token like "sIFNγ".
  if (/\s/.test(key)) return key;
  const words = key.split('_').filter(Boolean).map((w) => ACRONYMS[w] ?? w);
  const out: string[] = [];
  for (const w of words) {
    if (w === 'plus' && /^\d+$/.test(out[out.length - 1] ?? '')) out[out.length - 1] += '+';
    else if (w === 'month' && /^\d+$/.test(out[out.length - 1] ?? '')) out[out.length - 1] += '-month';
    else out.push(w);
  }
  // "0 6 months" was a range: "0-6 months".
  const s = out.join(' ').replace(/\b(\d+) (\d+) (months?|years?|weeks?)\b/g, '$1-$2 $3');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export interface NewsMetric {
  label: string;
  value: string;
}

/** Efficacy and safety values of a readout, in feed order, with readable labels. */
export function readoutMetrics(result: LiveTickerResult): { efficacy: NewsMetric[]; safety: NewsMetric[] } {
  const ed = result.efficacy_or_safety_data as {
    value?: string;
    efficacy_metrics?: Array<{ metric: string; value: string }>;
    safety_metrics?: Array<{ metric: string; value: string }>;
  };
  const toMetric = ({ metric, value }: { metric: string; value: string }) => ({
    label: humanizeMetric(metric),
    value: String(value).replace(/^=\s*/, ''),
  });
  if (ed.value) {
    // Legacy flat format: "ORR: 40%; median PFS: 6 months".
    const efficacy = ed.value
      .split(';')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((part) => {
        const i = part.indexOf(':');
        return i > 0 ? { label: part.slice(0, i).trim(), value: part.slice(i + 1).trim() } : { label: '', value: part };
      });
    return { efficacy, safety: [] };
  }
  return {
    efficacy: rankMetrics((ed.efficacy_metrics ?? []).map(toMetric)),
    safety: (ed.safety_metrics ?? []).map(toMetric),
  };
}

/** Headline endpoints (ORR, medians, HRs) first; p values and follow-up last; feed order otherwise. */
export function rankMetrics(metrics: NewsMetric[]): NewsMetric[] {
  const rank = ({ label }: NewsMetric) =>
    /p[- ]value|follow/i.test(label) ? 2 : /\b(ORR|DCR|CR|PFS|OS|RFS|EFS|DMFS|HR)\b|hazard/.test(label) ? 0 : 1;
  return metrics.map((m, i) => ({ m, i })).sort((a, b) => rank(a.m) - rank(b.m) || a.i - b.i).map(({ m }) => m);
}

/** "62.5% (95% CI: 40.6, 81.2)" -> { main: "62.5%", note: "95% CI: 40.6, 81.2" }. */
export function splitValue(value: string): { main: string; note: string } {
  const m = /^([^(]+?)\s*\((.+)\)$/.exec(value.trim());
  return m ? { main: m[1], note: m[2] } : { main: value.trim(), note: '' };
}
