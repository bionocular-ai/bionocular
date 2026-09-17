import { describe, expect, it } from 'vitest';
import { describeSkills, loadSkill, parseSkill, SKILL_NAMES } from './index';

describe('skills', () => {
  it('every registered skill loads from disk with a name, description and body', () => {
    for (const name of SKILL_NAMES) {
      const skill = loadSkill(name);
      expect(skill.name).toBe(name);
      expect(skill.description.length).toBeGreaterThan(40);
      expect(skill.body.length).toBeGreaterThan(200);
    }
  });

  it('keeps provider and live-data facts out of the skill bodies', () => {
    for (const name of SKILL_NAMES) {
      const { body, description } = loadSkill(name);
      const text = `${description}\n${body}`;
      // Provider-neutral: a skill is method, not model configuration.
      expect(text).not.toMatch(/gemini|claude|anthropic|openai|vertex|thinking/i);
      // No point-in-time measurements: counts of rows, percentages of the
      // table, or dates. Those come from the database through tool results.
      expect(text).not.toMatch(/\b\d{1,3}(,\d{3})+\b/);
      expect(text).not.toMatch(/\b\d+%/);
      expect(text).not.toMatch(/\b20\d\d-\d\d(-\d\d)?\b/);
    }
  });

  it('lists every skill for the system prompt, one line each', () => {
    const lines = describeSkills().split('\n');
    expect(lines).toHaveLength(SKILL_NAMES.length);
    for (const name of SKILL_NAMES) expect(lines.some((l) => l.includes(`\`${name}\``))).toBe(true);
  });

  it('rejects a file whose frontmatter does not match its directory', () => {
    expect(() => parseSkill('trial-outcomes', '---\nname: other\ndescription: x\n---\nbody')).toThrow(/frontmatter name/);
    expect(() => parseSkill('trial-outcomes', 'no frontmatter')).toThrow(/missing frontmatter/);
  });
});
