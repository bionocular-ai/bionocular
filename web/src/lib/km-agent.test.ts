import { describe, expect, it } from 'vitest';
import type { KmCurveRow } from '@/lib/api';
import { describeKmSelection } from './km-agent';

const curve = (over: Partial<KmCurveRow> = {}): KmCurveRow => ({
  id: 'c1',
  publication_id: 'N Engl J Med 2022;386:24-34.',
  nct_id: 'NCT03470922',
  cancer_type: 'Cutaneous Melanoma',
  comparison_label: 'Overall',
  arm_name: 'relatlimab_nivolumab',
  endpoint: 'PFS',
  twin_coords: [
    { time: 0, surv: 100 },
    { time: 10, surv: 60 },
    { time: 20, surv: 48.4 },
    { time: 30, surv: 40 },
  ],
  published_median: 10.1,
  twin_median: 10.2,
  rate_timepoint: 12,
  published_rate: 47.7,
  twin_rate: 48,
  median_follow_up: 13.2,
  match_pct: 98,
  n_points: 355,
  reference: null,
  ...over,
});

describe('describeKmSelection', () => {
  it('lists each arm with published vs twin numbers and twin landmarks within follow-up', () => {
    expect(describeKmSelection('Progression-free survival', [curve()], null)).toBe(
      'About this digitized-twin KM curve (Progression-free survival; twins are reconstructed from the published figures):\n' +
        '- Relatlimab Nivolumab (NCT03470922, cohort Overall, N Engl J Med 2022;386:24-34.): ' +
        'median 10.1m published, 10.2m twin; 12m rate 47.7% published, 48% twin; ' +
        'twin survival 60% at 12m, 48% at 24m; median follow-up 13.2m; twin match 98%; 355 reconstructed patients.',
    );
  });

  it('rounds to one decimal and flags a twin-only median', () => {
    const text = describeKmSelection('Overall survival', [curve({ published_median: null, twin_median: 40.378 })], null);
    expect(text).toContain(': median 40.4m twin (not published); 12m rate');
  });

  it('drops missing facts and appends the twin HR', () => {
    const bare = curve({
      arm_name: 'nivolumab',
      nct_id: null,
      comparison_label: null,
      twin_coords: [],
      published_median: null,
      twin_median: null,
      rate_timepoint: null,
      median_follow_up: null,
      match_pct: null,
      n_points: null,
    });
    const text = describeKmSelection('Overall survival', [curve(), bare], { value: 0.754, cmpName: 'A', refName: 'B' });
    expect(text.split('\n').slice(2)).toEqual([
      '- Nivolumab (N Engl J Med 2022;386:24-34.).',
      'Approximate HR from the twins, A vs B: 0.75.',
    ]);
  });
});
