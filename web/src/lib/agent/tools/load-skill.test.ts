import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import { buildLoadSkillTool } from './load-skill';
import { createTurnState } from './turn';

const enumFor = (cancerSlug: string) => {
  const { load_skill } = buildLoadSkillTool({ userId: 'u', traceId: 't', cancerSlug, turn: createTurnState() });
  return (z.toJSONSchema(load_skill.inputSchema as unknown as z.ZodType) as unknown as { properties: { skill: { enum: string[] } } })
    .properties.skill.enum;
};

describe('load_skill', () => {
  it('offers melanoma sessions the original four skills in their original order', () => {
    const original = ['trial-outcomes', 'trial-landscape', 'coverage-and-citation', 'standard-of-care'];
    expect(enumFor('cutaneous-melanoma')).toEqual(original);
    expect(enumFor('uveal-melanoma')).toEqual(original);
  });

  it('offers heme sessions only the citation and heme outcome skills', () => {
    expect(enumFor('multiple-myeloma')).toEqual(['coverage-and-citation', 'heme-outcomes']);
  });
});
