import type { KmCurveRow, KmPoint } from '@/lib/api';
import { formatArmName } from '@/lib/utils/arm-name';

const LANDMARKS = [12, 24, 36];

/** Twin survival (%) at `t` months on the KM step curve, or null past its last point. */
function survAt(coords: KmPoint[], t: number): number | null {
  if (!coords.length || t > coords[coords.length - 1].time) return null;
  let s = 100;
  for (const pt of coords) {
    if (pt.time > t) break;
    s = pt.surv;
  }
  return Math.round(s);
}

const round = (n: number | null) => (n == null ? null : Math.round(n * 10) / 10);

const pair = (label: string, published: number | null, twin: number | null, unit: string) => {
  const parts = [
    published == null ? null : `${round(published)}${unit} published`,
    twin == null ? null : `${round(twin)}${unit} twin`,
  ].filter(Boolean);
  if (!parts.length) return null;
  return `${label} ${parts.join(', ')}${published == null ? ' (not published)' : ''}`;
};

/**
 * The curves on the KM page as context for the agent: what the user is looking
 * at, with the twin landmarks read off the reconstructed curves, which no agent
 * tool returns.
 */
export function describeKmSelection(
  endpointLabel: string,
  curves: KmCurveRow[],
  hr: { value: number; cmpName: string; refName: string } | null,
): string {
  const lines = curves.map((c) => {
    const source = [c.nct_id, c.comparison_label && `cohort ${c.comparison_label}`, c.publication_id].filter(Boolean).join(', ');
    const landmarks = LANDMARKS.flatMap((t) => {
      const s = survAt(c.twin_coords, t);
      return s == null ? [] : [`${s}% at ${t}m`];
    });
    const facts = [
      pair('median', c.published_median, c.twin_median, 'm'),
      c.rate_timepoint != null ? pair(`${c.rate_timepoint}m rate`, c.published_rate, c.twin_rate, '%') : null,
      landmarks.length ? `twin survival ${landmarks.join(', ')}` : null,
      c.median_follow_up != null ? `median follow-up ${c.median_follow_up}m` : null,
      c.match_pct != null ? `twin match ${c.match_pct}%` : null,
      c.n_points != null ? `${c.n_points} reconstructed patients` : null,
    ].filter(Boolean);
    return `- ${formatArmName(c.arm_name)} (${source})${facts.length ? `: ${facts.join('; ')}` : ''}.`;
  });
  const these = curves.length === 1 ? 'this digitized-twin KM curve' : 'these digitized-twin KM curves';
  return [
    `About ${these} (${endpointLabel}; twins are reconstructed from the published figures):`,
    ...lines,
    ...(hr ? [`Approximate HR from the twins, ${hr.cmpName} vs ${hr.refName}: ${hr.value.toFixed(2)}.`] : []),
  ].join('\n');
}
