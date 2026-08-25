import { defineConfig } from 'vitest/config';

// `*.eval.test.ts` files call the real model against the real database, so the
// default run excludes them and `npm run test:evals` flips this on. It is an
// env flag rather than a CLI `--include` because vitest 4 dropped that option,
// and `--exclude` only ever adds exclusions - it cannot lift one.
const EVALS = Boolean(process.env.VITEST_EVALS);

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
