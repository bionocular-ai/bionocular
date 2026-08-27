import { existsSync } from 'node:fs';
import { defineConfig } from 'vitest/config';

// `*.eval.test.ts` files call the real model against the real database, so the
// default run excludes them and `npm run test:evals` flips this on. It is an
// env flag rather than a CLI `--include` because vitest 4 dropped that option,
// and `--exclude` only ever adds exclusions - it cannot lift one.
const EVALS = Boolean(process.env.VITEST_EVALS);

// Next.js loads `.env.local` for the dev server and `next build`, but nothing
// does that for a vitest process - Vite's own env loading only ever populates
// `import.meta.env` for VITE_-prefixed keys, never `process.env`. The eval
// suite reads `process.env.ANTHROPIC_API_KEY` / `SUPABASE_SECRET_KEY` directly
// (same as the app code it exercises), so without this it throws on a missing
// var instead of skipping cleanly. Only loaded for the evals run, and only if
// the file exists, so CI (no `.env.local`, `VITEST_EVALS` unset) is unaffected.
if (EVALS && existsSync('.env.local')) {
  process.loadEnvFile('.env.local');
}

export default defineConfig({
  // Resolves the `@/` alias from tsconfig.json.
  resolve: { tsconfigPaths: true },
  test: {
    // The agent's tools are server-side; nothing under test touches the DOM.
    environment: 'node',
    include: EVALS
      ? ['src/**/*.eval.test.ts']
      : ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    // The default suite needs no credentials and no network.
    exclude: ['**/node_modules/**', ...(EVALS ? [] : ['src/**/*.eval.test.ts'])],
  },
});
