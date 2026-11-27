/**
 * The agent's skills: task-specific methodology the model loads on demand.
 *
 * Each skill is a `SKILL.md` with a frontmatter `name` and `description`. The
 * descriptions go into the system prompt (one line each) on every turn; the
 * body is sent only when the model calls `load_skill`. That keeps the
 * always-paid prefix to rules that hold on every turn, and gives table-specific
 * interpretation a home that is neither the prompt nor a tool description.
 *
 * The set of names is fixed here, so `load_skill` is an enum over it and can
 * never be asked for a path. Files are read from this directory only.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { isHemeCancerType } from '@/lib/heme-cancers';

export const SKILL_NAMES = ['trial-outcomes', 'trial-landscape', 'coverage-and-citation', 'standard-of-care', 'heme-outcomes'] as const;
export type SkillName = (typeof SKILL_NAMES)[number];

/** Heme sessions swap the melanoma outcomes skill for the heme one, as `tablesFor` swaps the tables. */
const HEME_SKILLS: readonly SkillName[] = ['heme-outcomes'];
const MELANOMA_SKILLS: readonly SkillName[] = ['trial-outcomes'];

/** The skills a session may load, by the database cancer type it is pinned to. */
export function skillsFor(dbCancerType: string): [SkillName, ...SkillName[]] {
  const heme = isHemeCancerType(dbCancerType);
  return SKILL_NAMES.filter((name) => !(heme ? MELANOMA_SKILLS : HEME_SKILLS).includes(name)) as [SkillName, ...SkillName[]];
}

export interface Skill {
  name: SkillName;
  description: string;
  /** Markdown after the frontmatter. */
  body: string;
}

// Resolved from the working directory rather than `import.meta.url`: the
// bundler rewrites module URLs, and `next.config.ts` traces this directory into
// the standalone output so the same path holds in production.
const SKILLS_DIR = path.join(process.cwd(), 'src', 'lib', 'agent', 'skills');

const FRONTMATTER = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/;

export function parseSkill(name: SkillName, markdown: string): Skill {
  const match = FRONTMATTER.exec(markdown);
  if (!match) throw new Error(`skill ${name}: missing frontmatter`);
  const [, frontmatter, body] = match;
  const fields = new Map<string, string>();
  for (const line of frontmatter.split('\n')) {
    const colon = line.indexOf(':');
    if (colon === -1) continue;
    fields.set(line.slice(0, colon).trim(), line.slice(colon + 1).trim());
  }
  const declared = fields.get('name');
  const description = fields.get('description');
  if (declared !== name) throw new Error(`skill ${name}: frontmatter name is ${JSON.stringify(declared)}`);
  if (!description) throw new Error(`skill ${name}: missing description`);
  if (!body.trim()) throw new Error(`skill ${name}: empty body`);
  return { name, description, body: body.trim() };
}

const cache = new Map<SkillName, Skill>();

export function loadSkill(name: SkillName): Skill {
  const cached = cache.get(name);
  if (cached) return cached;
  const markdown = readFileSync(path.join(SKILLS_DIR, name, 'SKILL.md'), 'utf8');
  const skill = parseSkill(name, markdown);
  cache.set(name, skill);
  return skill;
}

/** One line per skill, for the system prompt. */
export function describeSkills(names: readonly SkillName[] = SKILL_NAMES): string {
  return names.map((name) => {
    const { description } = loadSkill(name);
    return `- \`${name}\`: ${description}`;
  }).join('\n');
}
