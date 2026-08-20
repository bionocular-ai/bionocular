import { describe, expect, it } from 'vitest';
import { checkCompleteness, checkGroundedness, extractIdentifiers } from './groundedness';

describe('extractIdentifiers', () => {
  it('finds NCT numbers, PMIDs and DOIs', () => {
    const answer =
      'See NCT00006368 and NCT04234567 (PMID: 35123456), plus 10.1056/NEJMoa1234567.';

    expect(extractIdentifiers(answer)).toEqual([
      'NCT00006368',
      'NCT04234567',
      '35123456',
      '10.1056/NEJMoa1234567.',
    ]);
  });

  it('ignores prose that merely looks identifier-adjacent', () => {
    expect(extractIdentifiers('This trial enrolled 240 patients across 12 sites.')).toEqual([]);
  });
});

describe('checkGroundedness', () => {
  // The assertion is over tool results, never over the database: the question
  // is whether anything this turn returned the identifier, not whether it
  // exists. That keeps working if a non-database source is added later.
  const toolResults = [
    {
      ok: true,
      table: 'clinical_trials',
      rows: [{ nct_id: 'NCT00006368', brief_title: 'A melanoma trial' }],
    },
  ];

  it('passes when every identifier came back from a tool', () => {
    const result = checkGroundedness('NCT00006368 is a phase 3 trial.', toolResults);
    expect(result).toEqual({ grounded: true, ungrounded: [], cited: ['NCT00006368'] });
  });

  it('catches a trial the answer invented', () => {
    const result = checkGroundedness(
      'NCT00006368 and NCT04234567 both reported OS.',
      toolResults,
    );
    expect(result.grounded).toBe(false);
    expect(result.ungrounded).toEqual(['NCT04234567']);
  });

  it('catches a citation to a source the agent no longer has', () => {
    // Nothing returns PMIDs now that the literature tools are gone, so any PMID
    // in an answer is fabricated by definition.
    const result = checkGroundedness('Reported in PMID: 35123456.', toolResults);
    expect(result.grounded).toBe(false);
    expect(result.ungrounded).toEqual(['35123456']);
  });

  it('accepts an identifier nested anywhere in the results', () => {
    const nested = [{ found: true, tables: { news_feed: { rows: [{ nct_ids: ['NCT04234567'] }] } } }];
    expect(checkGroundedness('See NCT04234567.', nested).grounded).toBe(true);
  });

  it('treats an answer with no identifiers as grounded', () => {
    expect(checkGroundedness('We hold no data on that trial.', []).grounded).toBe(true);
  });
});

describe('checkCompleteness', () => {
  // The mirror of checkGroundedness. That one catches `cited − returned`: a
  // trial the answer named that nothing looked up. This catches `returned −
  // cited`: a trial a tool handed the model that never reached the answer. A
  // sweep of 53 Phase 3 trials was written up as 45 because the answer pivoted
  // to one row per treatment and merged trials sharing a drug.
  const sweep = (ids: string[]) => [
    { ok: true, table: 'clinical_trials', rows: ids.map((nct_id) => ({ nct_id })) },
  ];

  it('passes when the answer accounts for every trial the tools returned', () => {
    const result = checkCompleteness('NCT00006368 and NCT00084656 are recruiting.', sweep([
      'NCT00006368',
      'NCT00084656',
    ]));
    expect(result).toEqual({
      complete: true,
      uncited: [],
      returned: ['NCT00006368', 'NCT00084656'],
    });
  });

  it('catches a trial the tools returned that the answer dropped', () => {
    const result = checkCompleteness('NCT00006368 is recruiting.', sweep([
      'NCT00006368',
      'NCT00084656',
      'NCT00096083',
    ]));
    expect(result.complete).toBe(false);
    expect(result.uncited).toEqual(['NCT00084656', 'NCT00096083']);
  });

  it('reports an empty result as complete rather than as a silent pass', () => {
    const result = checkCompleteness('No trials matched.', [
      { ok: false, reason: 'no_rows', table: 'clinical_trials' },
    ]);
    expect(result).toEqual({ complete: true, uncited: [], returned: [] });
  });

  it('counts a trial once however many rows carried it', () => {
    const result = checkCompleteness('NCT00006368 has two arms.', [
      { ok: true, table: 'trial_outcomes', rows: [{ nct_id: 'NCT00006368' }, { nct_id: 'NCT00006368' }] },
    ]);
    expect(result.returned).toEqual(['NCT00006368']);
  });

  it('reads rows, not the whole payload, so a coverage note demands no citation', () => {
    // `coverage.missing` names trials the table had no row for. They are worth
    // mentioning, but they are not rows this tool returned - counting them here
    // would fail an answer for omitting what it was never given.
    const result = checkCompleteness('NCT00006368 is recruiting.', [
      {
        ok: true,
        table: 'trial_landscape',
        rows: [{ nct_id: 'NCT00006368' }],
        coverage: { requested: 2, missing: ['NCT00084656'] },
      },
    ]);
    expect(result).toEqual({ complete: true, uncited: [], returned: ['NCT00006368'] });
  });
});
