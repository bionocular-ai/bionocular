import { describe, expect, it } from 'vitest';
import { extractAbstractDetails, extractEfficacyAndSafetyMetrics, extractKeyMetrics } from './trial-utils';

describe('conference parsing from abstract ids', () => {
  it.each([
    ['ASCO_2025_9598', 'ASCO', '2025', 'May 30, 2025'],
    ['ESMO_2020_1076O', 'ESMO', '2020', 'Sep 15, 2020'],
    ['SITC_2025_599', 'SITC', '2025', 'Nov 7, 2025'],
  ])('%s', (abstractId, conference, year, date) => {
    expect(extractKeyMetrics({ abstract_id: abstractId })).toMatchObject({ conference, year, date });
    expect(extractAbstractDetails({ abstract_id: abstractId })).toMatchObject({ conference, year });
  });
});

describe('abstract title fallback', () => {
  it('labels a conference abstract with no title by conference, year and number', () => {
    expect(extractAbstractDetails({ abstract_id: 'ASCO_2025_9546' })?.title).toBe('ASCO 2025 Abstract 9546');
    expect(extractAbstractDetails({ abstract_id: 'ESMO_2020_1076O' })?.title).toBe('ESMO 2020 Abstract 1076O');
  });

  it('prefers a real title', () => {
    expect(extractAbstractDetails({ abstract_id: 'ASCO_2025_9546', title: 'CheckMate 067' })?.title).toBe('CheckMate 067');
  });

  it('leaves non-conference ids untitled', () => {
    expect(extractAbstractDetails({ abstract_id: 'PMID_12345' })?.title).toBe('');
  });
});

describe('extractEfficacyAndSafetyMetrics short forms', () => {
  it('gives each result attribute its own label', () => {
    const keys = [
      'MEDIAN_DOR', 'DOR_RATE', 'COMPLETE_RESPONSE', 'PATHOLOGICAL_COMPLETE_RESPONSE',
      'HR_PFS', 'HR_OS', 'HR_EFS', 'HR_RFS', 'HR_MFS',
      'AE_LEADING_TO_DEATH', 'TEAE_LEADING_TO_DEATH', 'TRAE_LEADING_TO_DEATH',
      'AE', 'TEAE_IMMUNE_RELATED', 'TRAE_IMMUNE_RELATED', 'IMMUNE_RELATED_AE', 'SERIOUS_IMMUNE_RELATED_AE',
    ];
    const attributes = Object.fromEntries(keys.map((k, i) => [`AttributeType.${k}`, { value: String(i + 1) }]));
    const metrics = extractEfficacyAndSafetyMetrics({ arm_results: { a: { arm_id: 'a', arm_name: 'x', attributes } } });

    expect(Object.keys(metrics)).toHaveLength(keys.length);
    expect(metrics['DOR'].value).toBe('1');
    expect(metrics['DOR rate'].value).toBe('2');
    expect(metrics['pCR'].value).toBe('4');
    expect(metrics['PFS HR'].value).toBe('5');
  });
});
