# Bionocular

## Project overview

Bionocular is an oncology intelligence platform that surfaces clinical trial data, treatment landscapes, and regulatory timelines for cancer researchers. Two packages: `melanoma/` (Python/FastAPI backend and data pipelines) and `web/` (Next.js frontend). Each has its own `AGENTS.md` with the conventions for that package.

**Production today**: `web` + Supabase only. `melanoma` runs locally and in scheduled CI jobs.

## Working principles

**Simplicity first - but simple isn't short-sighted.** Write the minimum code that solves the problem: no speculative abstractions, no configurability or error handling for cases that can't happen. Reach quality and long-term maintainability *through* simplicity, not by building for imagined futures - add structure only when a second real caller or requirement exists.

**Surgical changes.** Touch only what you must. Don't "improve" adjacent code, comments, or formatting; don't refactor what isn't broken. Match existing style. If a change orphans an import/var/function, remove it - but leave pre-existing dead code unless asked.

**Think before coding; define done.** State assumptions; if interpretations differ or something is unclear, surface it instead of guessing, and push back when a simpler approach exists. Set a success criterion before coding ("fix the bug" -> "test reproducing it passes"), and for multi-step work sketch a brief plan with checkpoints.

## Git and PR conventions

**Branch naming:**
```
feature/<short-description>
fix/<short-description>
chore/<short-description>
```

**Commit messages** follow Conventional Commits with a scope:
```
feat(web): add regulatory timeline filter
fix(auth): fix email confirmation redirect to production URL
chore(melanoma): align tests with Supabase migration
```

**PRs** target `main`. Keep them focused - one concern per PR.

**Git hooks** run automatically on commit and push (hooks live in `web/.husky/`):
- `pre-commit` - ESLint (staged files) + TypeScript type check
- `pre-push` - unit tests + production build

To bypass in a genuine emergency (e.g. hotfix under incident):
```bash
git commit --no-verify
git push --no-verify
```
Use sparingly - CI will still catch failures.

CI in `.github/workflows/` gates every push/PR to `main`. Scheduled jobs commit on their own (`sync-trials.yml`, `scrape-news.yml`) and run scripts in `melanoma/scripts/`.

## Running locally

Setup steps are in each package README.

`python` is not on this machine, only `python3`. Run backend scripts with `poetry run python3` from `melanoma/`:
```bash
cd melanoma && poetry run python3 run_abstract_pipeline.py
```
