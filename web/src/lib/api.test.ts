import { describe, expect, it, vi } from 'vitest';

// Every table is empty: each query resolves to no rows
vi.mock('@/lib/supabase/client', () => ({
  createClient: () => {
    const empty = {
      select: () => empty,
      eq: () => empty,
      limit: () => empty,
      maybeSingle: async () => ({ data: null, error: null }),
      then: (resolve: (v: unknown) => unknown) => resolve({ data: [], error: null }),
    };
    return { from: () => empty };
  },
}));

import { OUTCOME_COL_TO_ATTR, trialsApi } from './api';
import { TRIAL_OUTCOMES_ENDPOINTS } from './agent/tools/schema';
import { EFFICACY_METRICS, SAFETY_METRICS } from '@/types/analytics';

describe('trialsApi.getByAbstractId', () => {
  it('returns null for an abstract id with no rows', async () => {
    expect(await trialsApi.getByAbstractId('does-not-exist')).toBeNull();
  });

  it('returns null for an NCT id with no outcome, trial or landscape rows', async () => {
    expect(await trialsApi.getByAbstractId('NCT99999999')).toBeNull();
  });
});

describe('OUTCOME_COL_TO_ATTR', () => {
  // Every metric the abstract page can show, by the column that feeds it
  const shown = Object.entries(OUTCOME_COL_TO_ATTR).filter(([, key]) => key in EFFICACY_METRICS || key in SAFETY_METRICS);

  it('reads only columns that exist on trial_outcomes', () => {
    const missing = shown.map(([col]) => col).filter((col) => col !== 'num_patients' && !TRIAL_OUTCOMES_ENDPOINTS.has(col));
    expect(missing).toEqual([]);
  });

  it('names a defined metric for every column it maps', () => {
    const undefinedKeys = Object.entries(OUTCOME_COL_TO_ATTR)
      .filter(([col, key]) => TRIAL_OUTCOMES_ENDPOINTS.has(col) && !(key in EFFICACY_METRICS) && !(key in SAFETY_METRICS))
      .map(([col, key]) => `${col} -> ${key}`);
    expect(undefinedKeys).toEqual([]);
  });

  it('gives every efficacy and safety metric a column', () => {
    const fed = new Set(shown.map(([, key]) => key));
    const unfed = [...Object.keys(EFFICACY_METRICS), ...Object.keys(SAFETY_METRICS)].filter((key) => !fed.has(key));
    expect(unfed).toEqual([]);
  });
});
