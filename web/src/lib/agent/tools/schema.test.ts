import { describe, expect, it } from 'vitest';
import { AGENT_TABLE_NAMES, describeTables, tablesFor } from './schema';

describe('tablesFor', () => {
  it('tablesFor heme offers only the tables that hold heme data', () => {
    expect(tablesFor('Multiple Myeloma')).toEqual(['clinical_trials', 'arm_outcomes', 'outcome_fields']);
  });

  it('tablesFor melanoma is unchanged', () => {
    // The list on main, typed out so a new table cannot slip into melanoma
    // sessions by being added to AGENT_TABLE_NAMES.
    const main = ['clinical_trials', 'trial_landscape', 'trial_outcomes', 'km_curves', 'news_feed', 'approved_therapies'];
    expect(AGENT_TABLE_NAMES).toEqual(main);
    expect(tablesFor('Cutaneous Melanoma')).toEqual(main);
  });
});

describe('describeTables', () => {
  it('describes only the tables it is given', () => {
    const text = describeTables(tablesFor('Multiple Myeloma'));

    expect(text).toContain('`arm_outcomes`');
    expect(text).toContain('`outcome_fields`');
    expect(text).not.toContain('`trial_outcomes`');
    expect(text).not.toContain('`km_curves`');
  });
});
