# Melanoma backend and data pipeline

## Scope and architecture

This package owns the local FastAPI service, clinical-trial ingestion, LLM-assisted extraction and validation, and scheduled Supabase syncs. Production application reads are served by `web/`; do not create a backend dependency for the frontend unless the task explicitly changes that architecture.

| Layer | Location | Rule |
|---|---|---|
| Domain | `src/domain/` | Pure Python + Pydantic. No imports from `infrastructure/` or `app/`. |
| Infrastructure | `src/infrastructure/` | External integrations, persistence, parsing, provider-specific code. Implements domain interfaces. |
| Application | `src/app/` | Orchestration, CLIs and FastAPI routers. Depends on domain interfaces, not concrete classes. |

Never import from a lower layer into a higher one (e.g. no FastAPI in `domain/`).

- Existing services use ABC interfaces in `src/domain/*interfaces.py` with constructor injection; FastAPI `Depends()` only at the endpoint boundary. Match that when extending a service. Do not add an interface for a single implementation - prefer a direct function or an existing interface, and add a new layer only when there is a demonstrated second use.
- Put regression tests in `tests/`, flat as `test_*.py`, mirroring the behavior or module under test.
- Treat `scripts/` entry points and `.github/workflows/` scheduled jobs as operational interfaces. Preserve their argument and environment-variable contracts.

### Naming

| Suffix | Purpose | Example |
|---|---|---|
| `interfaces.py` / `*_interfaces.py` | Abstract contracts (ABCs) | `StorageInterface` in `interfaces.py` |
| `_service.py` | Concrete service implementations | `IngestionService` |
| `_repository.py` | Data persistence | `SQLAlchemyDocumentRepository` |
| `_model.py` / `_models.py` | Domain entities (Pydantic) | `Document`, `Chunk` |
| `_config.py` / `config.py` | Configuration objects | `ServiceConfiguration` |
| `_api.py` | FastAPI routers | `clinical_api`, `trials_api` |
| `_cli.py` | Command-line entry points | `ingest_cli` |

## Code rules

- Full type annotations on every function signature. MyPy runs with strict-equivalent flags (`pyproject.toml` `[tool.mypy]`); don't bypass it.
- Pydantic for domain models; SQLAlchemy for ORM models. Keep them separate; convert at the repository boundary.
- Async-first: all I/O (DB, file, HTTP, LLM) uses `async`/`await`.
- Shared constants and enums live in `src/domain/constants.py`; don't duplicate a value that already exists there.
- Services log via `logger = logging.getLogger(__name__)`. `print()` is for `*_cli.py` entry points and script output only.
- No bare `except`. Catch a specific type, log with context, then re-raise or return a status-based response (e.g. `DocumentStatus.PROCESSING_FAILED`) for recoverable errors instead of letting exceptions bubble to the client.
- External calls retry with backoff. Gemini goes through `GeminiLLMService`, which owns its retry, truncation and quota breaker; other providers use `tenacity`.

## Data and provider safety

- Do not make live Gemini, OpenAI, ClinicalTrials.gov, Supabase, or news-source calls in ordinary tests. Integration tests are opt-in: `poetry run pytest -m integration`.
- Prefer deterministic validation and fixtures for logic tests. Clearly label any test that needs network access or credentials.
- Do not change historical generated outputs, local data, or Supabase records as a side effect of a code change unless explicitly requested.
- Preserve identifiers and source provenance. A missing or uncertain extracted value must remain missing or be routed through the existing validation flow - never guessed.

## Pipelines

Entry points at the package root: `run_trials_extraction.py`, `run_trials_validation.py`, `run_results_validation.py`, `run_abstract_pipeline.py`, `run_publication_pipeline.py`. Scheduled jobs run `scripts/sync_trials_supabase.py` and `scripts/scrape_news_supabase.py`. Run all of them with `poetry run python3`; see `--help` for flags.

- Gemini runs on Vertex AI via application-default credentials. `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` must be set; `EXTRACTION_MODEL` selects the model.
- To target specific trials, pass `--nct-file <path>` (one NCT id per line), not many `--nct` flags.
- `--concurrency` bounds trial-level parallelism. Inside the abstract pipeline `FAMILY_CONCURRENCY` stays at 1; raising it causes quota bursts.
- Validation scripts run advisory by default; `--apply-fixes` writes back and is a human-gated decision.
- Scripts that write to RLS-protected tables (`trial_outcomes`, backfills) need `SUPABASE_SECRET_KEY`, not the anon key.

## Development commands

Run from `melanoma/`:

```bash
poetry install --with dev
poetry run pytest
poetry run ruff check src/ tests/
poetry run black --check src/ tests/
poetry run mypy src/
```

This is the gate CI runs. For a focused change, run its individual test first. `pytest` excludes tests marked `integration` by default; mark async tests `@pytest.mark.asyncio` and slow ones `@pytest.mark.slow`. Run `poetry run bandit -r src/` when changing input handling, secrets, HTTP, filesystem, or database code.

Use `poetry run uvicorn src.app.api:app --reload` for the local API only when the task needs it. Run Alembic migrations or sync and scrape scripts only with explicit task scope and the required credentials.

## Style

- Python targets the configuration in `pyproject.toml`: Black line length 88, Ruff, and strict MyPy.
- Keep types explicit at module boundaries and match the existing Pydantic and SQLAlchemy patterns.
