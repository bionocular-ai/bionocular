import { describe, expect, it } from 'vitest';
import { efficacyLinkFor } from './efficacy-link';

const outcomes = (input: Record<string, unknown>, coverage?: Record<string, unknown>) => ({
  input: { table: 'trial_outcomes', ...input },
  output: {
    ok: true,
    table: 'trial_outcomes',
    rows: [{ nct_id: 'NCT01740297', orr: 39 }],
    coverage: { returned: 1, matched: 1, complete: true, ...coverage },
  },
});

function params(href: string): URLSearchParams {
  return new URLSearchParams(href.slice(href.indexOf('?')));
}

describe('efficacyLinkFor', () => {
  it('carries the phase the agent filtered on', () => {
    const link = efficacyLinkFor([outcomes({ phase: 'PHASE1' })], 'cutaneous-melanoma');

    expect(link?.href.startsWith('/dashboard/cutaneous-melanoma/analytics?')).toBe(true);
    expect(params(link!.href).get('mode')).toBe('efficacy');
    expect(params(link!.href).get('phase')).toBe('PHASE1');
  });

  it('pins funding to all when the agent did not constrain it', () => {
    // The hub defaults to `industry`; on the Phase 1 cutaneous melanoma set
    // that default alone hides 96 of the 189 rows the answer showed.
    const link = efficacyLinkFor([outcomes({ phase: 'PHASE1' })], 'cutaneous-melanoma');

    expect(params(link!.href).get('funding')).toBe('all');
  });

  it('passes an explicit funding filter straight through', () => {
    const link = efficacyLinkFor([outcomes({ funding: 'non-industry' })], 'cutaneous-melanoma');

    expect(params(link!.href).get('funding')).toBe('non-industry');
  });

  it('carries several statuses as one comma-separated value', () => {
    const link = efficacyLinkFor(
      [outcomes({ status: ['RECRUITING', 'ACTIVE_NOT_RECRUITING'] })],
      'cutaneous-melanoma',
    );

    expect(params(link!.href).get('status')).toBe('RECRUITING,ACTIVE_NOT_RECRUITING');
  });

  it('offers no link for a filter the hub cannot reproduce', () => {
    // A substring drug match and an arbitrary NCT set both open a different
    // population than the answer, which is worse than no link.
    expect(efficacyLinkFor([outcomes({ drug: 'pembro' })], 'cutaneous-melanoma')).toBeNull();
    expect(
      efficacyLinkFor([outcomes({ nctIds: ['NCT01740297'] })], 'cutaneous-melanoma'),
    ).toBeNull();
  });

  it('offers no link for a turn that never queried the table the hub charts', () => {
    const trials = {
      input: { table: 'clinical_trials', phase: 'PHASE1' },
      output: { ok: true, table: 'clinical_trials', rows: [{ nct_id: 'NCT01740297' }] },
    };

    expect(efficacyLinkFor([trials], 'cutaneous-melanoma')).toBeNull();
  });

  it('offers no link for a failed or empty query', () => {
    const failed = {
      input: { table: 'trial_outcomes', phase: 'PHASE1' },
      output: { ok: false, reason: 'no_rows', table: 'trial_outcomes' },
    };
    const empty = {
      input: { table: 'trial_outcomes', phase: 'PHASE1' },
      output: { ok: true, table: 'trial_outcomes', rows: [] },
    };

    expect(efficacyLinkFor([failed], 'cutaneous-melanoma')).toBeNull();
    expect(efficacyLinkFor([empty], 'cutaneous-melanoma')).toBeNull();
  });

  it('finds the outcomes query among the other queries of the turn', () => {
    const trials = {
      input: { table: 'clinical_trials', phase: 'PHASE1' },
      output: { ok: true, table: 'clinical_trials', rows: [{ nct_id: 'NCT01740297' }] },
    };

    const link = efficacyLinkFor([trials, outcomes({ phase: 'PHASE1' })], 'cutaneous-melanoma');

    expect(params(link!.href).get('phase')).toBe('PHASE1');
  });

  it('says the hub will show more when the agent result was capped', () => {
    const capped = efficacyLinkFor(
      [outcomes({ phase: 'PHASE1' }, { complete: false, matched: 400 })],
      'cutaneous-melanoma',
    );
    const whole = efficacyLinkFor([outcomes({ phase: 'PHASE1' })], 'cutaneous-melanoma');

    expect(capped?.showsMore).toBe(true);
    expect(whole?.showsMore).toBe(false);
  });

  it('has nothing to offer a turn with no tool calls', () => {
    expect(efficacyLinkFor([], 'cutaneous-melanoma')).toBeNull();
  });
});
