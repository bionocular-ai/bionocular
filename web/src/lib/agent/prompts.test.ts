import { describe, expect, it } from 'vitest';
import { buildInstructions } from './prompts';

describe('instructions', () => {
  const text = buildInstructions({ cancerType: 'Uveal Melanoma' });

  it('names the scope the route pinned, and nothing else about what the database holds', () => {
    expect(text).toContain('scoped to Uveal Melanoma');
    // The enumerated cancer list and the measured row counts used to live
    // here; they are data, and data reaches the model through tools.
    expect(text).not.toMatch(/Merkel|basal cell|acral/i);
    expect(text).not.toMatch(/\b\d{1,3}(,\d{3})+\b/);
    expect(text).not.toMatch(/\b\d+ rows\b/);
  });

  it('tells the model the app draws the rows, so it reasons rather than transcribes', () => {
    expect(text).toMatch(/Do not reproduce rows/);
    expect(text).not.toMatch(/tables when comparing/);
  });

  it('stays small: rules that hold every turn, plus one line per skill', () => {
    expect(text.length).toBeLessThan(3_200);
    expect(text).toContain('`trial-outcomes`');
    expect(text).toContain('`coverage-and-citation`');
  });
});
