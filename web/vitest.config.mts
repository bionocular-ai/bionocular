import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Resolves the `@/` alias from tsconfig.json.
  resolve: { tsconfigPaths: true },
  test: {
    // The agent's tools are server-side; nothing under test touches the DOM.
    environment: 'node',
    // `*.eval.test.ts` files call the real model against the real database, so
    // they are excluded here and run by `npm run test:evals` instead. The
    // default suite needs no credentials and no network.
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    exclude: ['**/node_modules/**', 'src/**/*.eval.test.ts'],
  },
});
