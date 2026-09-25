import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { MODELS, onFlexLane, resolveModel } from '../model';
import { RateLimitBreaker } from '../model-calls';
import { GOLDEN_CASES } from './cases';
import { runCase, summarise, type CaseResult } from './harness';
import { holdVertexLock } from './vertex-lock';

/**
 * The golden set against every model named in EVAL_MODELS (comma-separated
 * names from `MODELS`; default: the model the route serves). Real models,
 * real database, real money; skipped without credentials. One report per
 * model lands in `.evals/`, which is what the before/after comparison and
 * the regression check read.
 *
 * Vertex models run on the Flex lane - half the price, queued rather than
 * refused - unless `EVAL_TRAFFIC=standard`, for when the Flex queue is not
 * being served (seen 2026-09-25: Flex 504s while Standard answered in 2s).
 * A refusal is retried where it happened; after `EVAL_BREAKER_THRESHOLD`
 * (default 3) in a row the run stops sending, the rest of the cases are
 * skipped, and the report says `aborted_rate_limited` - a refused case is not
 * a model failure and never counts as one.
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
const BREAKER_THRESHOLD = Number(process.env.EVAL_BREAKER_THRESHOLD ?? 3);
if (!['flex', 'standard', undefined].includes(process.env.EVAL_TRAFFIC)) {
  throw new Error(`EVAL_TRAFFIC must be flex or standard, got ${JSON.stringify(process.env.EVAL_TRAFFIC)}`);
}

describe.skipIf(!READY)('golden evals', () => {
  // Not while a melanoma pipeline is using the same project (see vertex-lock.ts).
  let releaseLock = () => {};
  beforeAll(() => {
    if (MODEL_NAMES.some((name) => MODELS[name]?.provider === 'google-vertex')) {
      releaseLock = holdVertexLock(process.env.GOOGLE_VERTEX_PROJECT!, 'web golden evals');
    }
  });
  afterAll(() => releaseLock());

  for (const name of MODEL_NAMES) {
    describe(name, () => {
      const model = process.env.EVAL_TRAFFIC === 'standard' ? resolveModel(name) : onFlexLane(resolveModel(name));
      const breaker = new RateLimitBreaker(BREAKER_THRESHOLD);
      const results: CaseResult[] = [];

      afterAll(() => {
        mkdirSync(REPORT_DIR, { recursive: true });
        const summary = summarise(results);
        const run = {
          status: breaker.open ? 'aborted_rate_limited' : 'complete',
          requestedTrafficType: model.trafficType ?? 'n/a',
          breakerThreshold: BREAKER_THRESHOLD,
          casesRun: results.length,
          casesNotRun: CASES.length - results.length,
        };
        if (breaker.open) {
          console.warn(`golden evals ${name}: ABORTED on provider refusals after ${results.length} of ${CASES.length} cases`, summary.modelCalls);
        }
        writeFileSync(
          path.join(REPORT_DIR, `${name}.json`),
          JSON.stringify({ run, summary, results, ranAt: new Date().toISOString() }, null, 2),
        );
      });

      for (const c of CASES) {
        // A Flex call can queue for minutes, and a refused one waits out its
        // backoff; the breaker, not this timeout, bounds a refusing pool.
        it(`${c.category} · ${c.id}`, async (ctx) => {
          if (breaker.open) ctx.skip('not run: rate-limit breaker open');
          const result = await runCase(c, model, { breaker });
          results.push(result);
          if (result.status === 'rate_limited') ctx.skip('rate-limited by the provider; not a model failure');
          expect(result.failures, result.answer.slice(0, 400)).toEqual([]);
        }, 1_800_000);
      }
    });
  }
});
