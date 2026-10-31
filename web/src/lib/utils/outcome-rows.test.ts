import { describe, expect, it } from 'vitest';
import type { TrialOutcomeRow } from '@/lib/api';
import { buildEfficacyRows, buildSafetyRows } from './outcome-rows';

describe('outcome rows', () => {
  it('shows N once, in efficacy', () => {
    const row = { num_patients: 44, orr: 36.4 } as unknown as TrialOutcomeRow;
    expect(buildEfficacyRows(row).map((r) => r.key)).toContain('NUMBER_OF_PATIENTS');
    expect(buildSafetyRows(row)).toEqual([]);
  });
});
