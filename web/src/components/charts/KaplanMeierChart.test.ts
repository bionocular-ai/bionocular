import { describe, expect, it } from 'vitest';
import type { KmCurveRow } from '@/lib/api';
import { armColors } from './KaplanMeierChart';

const curve = (id: string, arm_name: string, endpoint: string, comparison_label = 'Overall'): KmCurveRow => ({
  id,
  publication_id: 'N Engl J Med 2022;386:24-34.',
  nct_id: 'NCT03470922',
  cancer_type: 'Cutaneous Melanoma',
  comparison_label,
  arm_name,
  endpoint,
  twin_coords: [],
  published_median: null,
  twin_median: null,
  rate_timepoint: null,
  published_rate: null,
  twin_rate: null,
  median_follow_up: null,
  match_pct: null,
  n_points: null,
  reference: null,
});

describe('armColors', () => {
  it('gives an arm the same color under both endpoints, whatever the figure label', () => {
    const colors = armColors([
      [curve('os-rn', 'relatlimab_nivolumab', 'OS', '01'), curve('os-n', 'nivolumab', 'OS', '01')],
      [curve('pfs-n', 'nivolumab', 'PFS', '02'), curve('pfs-rn', 'relatlimab_nivolumab', 'PFS', '02')],
    ]);
    expect(colors.get('pfs-rn')).toBe(colors.get('os-rn'));
    expect(colors.get('pfs-n')).toBe(colors.get('os-n'));
    expect(colors.get('os-rn')).not.toBe(colors.get('os-n'));
  });

  it('keeps same-named arms from two cohorts of one endpoint apart', () => {
    const colors = armColors([
      [curve('a', 'nivolumab', 'PFS', 'LAG-3 <1'), curve('b', 'nivolumab', 'PFS', 'LAG-3 >=1')],
    ]);
    expect(colors.get('a')).not.toBe(colors.get('b'));
  });
});
