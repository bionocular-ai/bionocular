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

import { trialsApi } from './api';

describe('trialsApi.getByAbstractId', () => {
  it('returns null for an abstract id with no rows', async () => {
    expect(await trialsApi.getByAbstractId('does-not-exist')).toBeNull();
  });

  it('returns null for an NCT id with no outcome, trial or landscape rows', async () => {
    expect(await trialsApi.getByAbstractId('NCT99999999')).toBeNull();
  });
});
