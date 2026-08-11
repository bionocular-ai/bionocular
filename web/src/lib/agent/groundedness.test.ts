import { describe, expect, it } from 'vitest';
import { checkGroundedness, extractIdentifiers } from './groundedness';

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
