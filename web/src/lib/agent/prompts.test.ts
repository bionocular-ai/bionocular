import { describe, expect, it } from 'vitest';
import { buildInstructions } from './prompts';
import { describeSkills } from './skills';

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
    // Capped in two parts rather than one total: a single total had 6 chars
    // left with three skills, so it forbade any fourth skill however short.
    // What must stay small is the always-sent core and each skill's line.
    const skills = describeSkills();
    expect(text).toContain(skills);
    expect(text.length - skills.length).toBeLessThan(2_300);
    for (const line of skills.split('\n')) expect(line.length, line).toBeLessThan(340);
    expect(text).toContain('`trial-outcomes`');
    expect(text).toContain('`coverage-and-citation`');
  });
});
