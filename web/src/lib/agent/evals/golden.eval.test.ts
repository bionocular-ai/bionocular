import { afterAll, describe, expect, it } from 'vitest';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { MODELS, resolveModel } from '../model';
import { GOLDEN_CASES } from './cases';
import { runCase, summarise, type CaseResult } from './harness';

/**
 * The golden set against every model named in EVAL_MODELS (comma-separated
 * names from `MODELS`; default: the model the route serves). Real models,
 * real database, real money; skipped without credentials. One report per
 * model lands in `.evals/`, which is what the before/after comparison and
 * the regression check read.
 *
 *   EVAL_MODELS=gemini-3.8-flash,haiku-4.5 npm run test:evals
 */
const MODEL_NAMES = (process.env.EVAL_MODELS ?? resolveModel().name).split(',').map((s) => s.trim());
const CASE_FILTER = process.env.EVAL_CASES?.split(',').map((s) => s.trim());
const CASES = CASE_FILTER ? GOLDEN_CASES.filter((c) => CASE_FILTER.includes(c.id)) : GOLDEN_CASES;

const READY = Boolean(process.env.SUPABASE_SECRET_KEY) &&
  MODEL_NAMES.every((name) =>
    MODELS[name]?.provider === 'anthropic' ? Boolean(process.env.ANTHROPIC_API_KEY) : Boolean(process.env.GOOGLE_VERTEX_PROJECT),
  );

const REPORT_DIR = path.join(process.cwd(), '.evals');

describe.skipIf(!READY)('golden evals', () => {
  for (const name of MODEL_NAMES) {
    describe(name, () => {
      const results: CaseResult[] = [];

      afterAll(() => {
        mkdirSync(REPORT_DIR, { recursive: true });
        const summary = summarise(results);
        writeFileSync(
          path.join(REPORT_DIR, `${name}.json`),
          JSON.stringify({ summary, results, ranAt: new Date().toISOString() }, null, 2),
        );
      });

      for (const c of CASES) {
        it(`${c.category} · ${c.id}`, async () => {
          const result = await runCase(c, resolveModel(name));
          results.push(result);
          expect(result.failures, result.answer.slice(0, 400)).toEqual([]);
        }, 600_000);
      }
    });
  }
});
