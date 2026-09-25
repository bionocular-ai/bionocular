import { describe, expect, it } from 'vitest';
import { extractAbstractDetails, extractKeyMetrics } from './trial-utils';

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
