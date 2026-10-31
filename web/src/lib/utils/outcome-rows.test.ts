import { describe, expect, it } from 'vitest';
import type { TrialOutcomeRow } from '@/lib/api';
import { buildArmTable } from './outcome-rows';

const arm = (fields: Record<string, unknown>) => fields as unknown as TrialOutcomeRow;

// ASCO_2025_9553: experimental arm stored first, placebo control second
const lenvatinib = arm({ arm_id: 'arm_1', arm_name: 'Lenvatinib + Pembrolizumab', num_patients: 64, orr: 26.6, hr_pfs: 0.55 });
const placebo = arm({ arm_id: 'arm_2', arm_name: 'Placebo + Pembrolizumab', num_patients: 67, orr: 16.4, grade_3_plus_trae_pct: 1.5 });

describe('buildArmTable', () => {
  it('puts the control arm last, whatever order the rows arrive in', () => {
    const { arms } = buildArmTable([placebo, lenvatinib], 'efficacy');
    expect(arms).toEqual([
      { name: 'Lenvatinib + Pembrolizumab', patients: 64, control: false },
      { name: 'Placebo + Pembrolizumab', patients: 67, control: true },
    ]);
  });

  it('gives each metric one value per arm, with null where an arm did not report it', () => {
    const { rows } = buildArmTable([lenvatinib, placebo], 'safety');
    expect(rows.map((r) => [r.key, r.values])).toEqual([['GRADE_3_PLUS_TRAE', [null, '1.5%']]]);
  });

  it('marks the control arm as the reference for a hazard ratio', () => {
    const hr = buildArmTable([lenvatinib, placebo], 'efficacy').rows.find((r) => r.key === 'HR_PFS');
    expect(hr?.values).toEqual(['0.55', 'ref']);
  });

  it('shows N in the arm header, not as a table row', () => {
    const { rows } = buildArmTable([lenvatinib], 'efficacy');
    expect(rows.map((r) => r.key)).not.toContain('NUMBER_OF_PATIENTS');
  });

  it('builds a single arm the same way', () => {
    const { arms, rows } = buildArmTable([lenvatinib], 'efficacy');
    expect(arms).toHaveLength(1);
    expect(rows.find((r) => r.key === 'HR_PFS')?.values).toEqual(['0.55']);
  });

  it('orders arms by arm_id numerically', () => {
    const rows = ['arm_10', 'arm_2', 'arm_1'].map((arm_id) => arm({ arm_id, arm_name: arm_id }));
    expect(buildArmTable(rows, 'efficacy').arms.map((a) => a.name)).toEqual(['arm_1', 'arm_2', 'arm_10']);
  });
});
