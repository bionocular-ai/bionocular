import { tool } from 'ai';
import { z } from 'zod';
import { loadSkill, SKILL_NAMES } from '../skills';
import { runTool } from './logging';
import type { AgentToolContext } from './supabase';

/**
 * Hand the model a skill's body. The name is an enum over the registry, so
 * this tool can read nothing but the three files it names.
 */
export function buildLoadSkillTool({ traceId, turn }: AgentToolContext) {
  return {
    load_skill: tool({
      description:
        'Load the methodology for a kind of question before answering it. The skills and when ' +
        'to load each are listed in your instructions. Load a skill once per conversation; ' +
        'its content stays in context.',
      inputSchema: z.object({
        skill: z.enum(SKILL_NAMES),
      }),
      execute: async (args) =>
        runTool('load_skill', { traceId, turn }, args, async () => {
          const skill = loadSkill(args.skill);
          turn.skillsLoaded.add(skill.name);
          return { ok: true as const, name: skill.name, content: skill.body };
        }),
    }),
  };
}
