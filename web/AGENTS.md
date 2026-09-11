<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Bionocular web application

## Scope

This is the production Next.js 16 application. It uses the App Router, React 19, TypeScript strict mode, Tailwind CSS 4, Supabase, and Vitest. Use the `@/*` alias for imports from `src/`.

- Routes and route handlers live in `src/app/`.
- Reusable UI belongs in `src/components/`; keep feature components in their feature directory.
- Browser-safe Supabase access belongs in `src/lib/supabase/client.ts`; server-only access belongs in `src/lib/supabase/server.ts` or `src/lib/supabase/service.ts`.
- The service-role client and model-provider keys are server-only. Never import them into client components or expose them through `NEXT_PUBLIC_*` variables.
- Agent behavior, tools, prompts, and agent tests live in `src/lib/agent/`. Preserve its source grounding and rate-limit safeguards.

## Supabase and schema changes

- Add schema changes as a new, forward-only file in `supabase/migrations/`. Never edit an applied migration.
- Give migrations a UTC timestamp prefix consistent with the existing files and make them safe for the intended deployment state.
- Keep database constraints and application validation aligned. Add migration-level protections for data integrity when appropriate.
- Do not modify `supabase/seed/`; it is ignored because it contains proprietary local data.

## Development and verification

Run commands from `web/`:

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

Run the smallest relevant Vitest file while iterating, then use the checks appropriate to the change. `npm run build` needs the public Supabase environment values from `.env.local` or the deployment environment. Do not commit `.env*` files.

Use `npm run dev` only when a task needs a browser-level check. For visual work, inspect desktop and narrow viewport behavior, keyboard access, loading, error and empty states, and contrast before calling it complete.

## Implementation conventions

- Default to Server Components. Add `"use client"` only for browser APIs, state, effects, or event handlers.
- Data queries go through `src/lib/api.ts`. Server Components call it directly; client components call it through React Query (`useQuery` / `useMutation`), not `useEffect` + `fetch`. Auth flows and route handlers use the Supabase clients in `src/lib/supabase/` directly.
- `any` requires a `// eslint-disable-next-line @typescript-eslint/no-explicit-any` comment. Untyped PostgREST query builders in `api.ts` are the accepted case.
- Compose Tailwind classes with `cn()` from `src/lib/utils.ts`, never string interpolation.
- Route paths live in `src/lib/constants.ts` (`ROUTES`); cancer-type constants in `src/lib/dashboard-constants.ts`. Don't hardcode either.
- Keep route params, external data, and action inputs validated at the boundary. Use the established Zod patterns where they already exist.
- Reuse existing UI primitives from `src/components/ui/` and existing design patterns before adding dependencies or parallel component systems.
- Keep changes accessible: semantic controls, labels, visible focus, keyboard operation, and non-color-only state indicators.

### Naming

| Pattern | Convention | Example |
|---|---|---|
| Components | PascalCase, default export | `TrialCard.tsx` |
| Hooks | `use` prefix, named export | `useSession()` |
| Utility functions | camelCase | `normalizePhase()` |
| Constants | UPPER_SNAKE_CASE | `ROUTES` |
| CSS variables | `--kebab-case` | `--brand-primary` |

Vitest test files sit next to the module they cover (`result-table.ts` -> `result-table.test.ts`).
