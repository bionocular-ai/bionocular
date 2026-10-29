import { describe, expect, it } from 'vitest';
import type { LiveTickerResult } from '@/lib/api';
import { cleanTitle, humanizeMetric, rankMetrics, readoutMetrics, sourceOf, splitValue } from './live-news';

describe('live news helpers', () => {
  it('names the source from the host, subdomains included', () => {
    expect(sourceOf('https://www.biospace.com/x')).toBe('BioSpace');
    expect(sourceOf('https://jobs.biospace.com/x')).toBe('BioSpace');
    expect(sourceOf('https://example.org/x')).toBe('example.org');
    expect(sourceOf('not a url')).toBe('');
  });

  it('drops a title suffix only when it repeats the source', () => {
    expect(cleanTitle('Drug X Extends PFS - BioSpace', 'BioSpace')).toBe('Drug X Extends PFS');
    expect(cleanTitle('Phase 1/2 - Interim Data', 'BioSpace')).toBe('Phase 1/2 - Interim Data');
  });

  it('humanizes snake_case metric keys and leaves readable ones alone', () => {
    expect(humanizeMetric('grade_3_plus_trae_rate_combination_arm')).toBe('Grade 3+ TRAE rate combination arm');
    expect(humanizeMetric('12_month_os_rate_triplet')).toBe('12-month OS rate triplet');
    expect(humanizeMetric('median_pfs')).toBe('Median PFS');
    expect(humanizeMetric('hr_rfs_0_6_months')).toBe('HR RFS 0-6 months');
    expect(humanizeMetric('dmfs_hr_us_subgroup')).toBe('DMFS HR US subgroup');
    expect(humanizeMetric('median_overall_survival_low_sIFNγ')).toBe('Median overall survival low sIFNγ');
    expect(humanizeMetric('MIA nomogram AUC')).toBe('MIA nomogram AUC');
  });

  it('reads both the nested and the legacy flat readout formats', () => {
    const nested = {
      efficacy_or_safety_data: { efficacy_metrics: [{ metric: 'orr', value: '41.7%' }], safety_metrics: [] },
    } as unknown as LiveTickerResult;
    expect(readoutMetrics(nested)).toEqual({ efficacy: [{ label: 'ORR', value: '41.7%' }], safety: [] });
    const flat = { efficacy_or_safety_data: { metric: 'ORR', value: 'ORR: 40%; stable' } } as unknown as LiveTickerResult;
    expect(readoutMetrics(flat).efficacy).toEqual([{ label: 'ORR', value: '40%' }, { label: '', value: 'stable' }]);
  });

  it('puts headline endpoints before p values and follow-up', () => {
    const labels = ['PFS p value', 'Median follow up', 'Median DoR', 'ORR', 'PFS hazard ratio'];
    expect(rankMetrics(labels.map((label) => ({ label, value: '1' }))).map((m) => m.label)).toEqual([
      'ORR', 'PFS hazard ratio', 'Median DoR', 'PFS p value', 'Median follow up',
    ]);
  });

  it('splits a value from its parenthetical', () => {
    expect(splitValue('62.5% (95% CI: 40.6, 81.2)')).toEqual({ main: '62.5%', note: '95% CI: 40.6, 81.2' });
    expect(splitValue('not reached')).toEqual({ main: 'not reached', note: '' });
  });
});
