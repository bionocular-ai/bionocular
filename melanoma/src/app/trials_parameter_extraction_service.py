"""Clinical trial parameter extraction service.

Orchestrates a single-pass LLM extraction pipeline over the trial export
files, pulling cancer type tags from trials.db and writing structured
JSON output with full cost tracking and checkpointing.

Architecture
------------
  TrialLoader          — reads .txt files from trial_api_exports/
  CancerTypeRepository — queries api_discovery in trials.db
  TrialParameterExtractor — runs one LLM call per trial
  CheckpointManager    — persists per-trial status to checkpoint.json
  ResultWriter         — writes final results.json and cost_report.json
  TrialParameterExtractionService — wires all of the above together
"""

import asyncio
import hashlib
import itertools
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from ..domain.extraction_interfaces import LLMService
from ..domain.trial_parameter_models import (
    ExtractionRunSummary,
    ExtractionStatus,
    TrialParameterResult,
    TrialText,
)
from ..domain.trials_extraction_prompts import (
    BIOMARKER_VALUES,
    LINE_OF_THERAPY_VALUES,
    MODALITY_VALUES,
    PREVIOUS_TREATMENT_VALUES,
    STAGE_VALUES,
    build_extraction_prompt,
    build_modality_prompt,
)
from ..infrastructure.clinical_trials.snapshot_source import SnapshotTrialSource
from ..infrastructure.cost_calculator import CostCalculator
from ..infrastructure.openrouter_service import OpenRouterLLMService

_MODALITY_SET = set(MODALITY_VALUES)
_BIOMARKER_SET = set(BIOMARKER_VALUES)
_STAGE_SET = set(STAGE_VALUES)
_LOT_SET = set(LINE_OF_THERAPY_VALUES)
_PREV_TX_SET = set(PREVIOUS_TREATMENT_VALUES)

logger = logging.getLogger(__name__)

_NCT_RE = re.compile(r"NCT\d{8}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionConfig:
    """Configuration for a single extraction run.

    Attributes:
        trials_db_path: Path to trials.db (contains api_discovery table).
        exports_dir: Directory containing per-trial .txt export files.
        output_dir: Directory where results.json, checkpoint.json and
            cost_report.json will be written.
        model: OpenRouter model identifier.
        limit: Maximum number of trials to process (None = all).
        offset: Number of trials to skip before applying limit. Combined with
            last=True, skips from the end (e.g. offset=50 + last=True + limit=50
            yields positions 51–100 from the end).
        last: If True, apply limit to the last N trials instead of the first N.
        resume: If True, skip trials already recorded in checkpoint.json.
        dry_run: If True, load and validate trials but make no LLM calls.
        cancer_type_filter: Optional list of cancer type tags to restrict
            processing to (None = all cancer types in api_discovery).
        nct_allowlist: Optional explicit list of NCT numbers to process,
            bypassing limit and cancer_type_filter.
        snapshot_path: Optional path to a Supabase snapshot JSON. When set, trial
            text and cancer types come from the snapshot instead of
            trials_db_path / exports_dir (which are then ignored).
        modality_only: If True, run the modality-only prompt. Every other
            parameter is left empty in the result, so such a run must never
            share an output_dir with a full run - results.json is merged by NCT
            and the emptier row would win.
        concurrency: Number of trials extracted in parallel. Matches the
            validation pipeline's default; the per-trial disk writes are guarded
            by a lock.
    """

    trials_db_path: Path
    exports_dir: Path
    output_dir: Path
    model: str = "google/gemini-3.1-pro-preview"
    limit: Optional[int] = 50
    offset: int = 0
    last: bool = False
    resume: bool = True
    dry_run: bool = False
    cancer_type_filter: Optional[list[str]] = None
    nct_allowlist: Optional[list[str]] = None
    snapshot_path: Optional[Path] = None
    modality_only: bool = False
    concurrency: int = 5


# ---------------------------------------------------------------------------
# Trial loader
# ---------------------------------------------------------------------------


class TrialLoader:
    """Reads individual trial .txt files and parses their sections."""

    def load(self, path: Path) -> TrialText:
        """Parse a trial export file into a TrialText object.

        The file format is:
            NCT Number: NCTXXXXXXXX
            <blank>
            officialTitle:
            <title text>
            <blank>
            briefSummary:
            <summary text>
            <blank>
            <remaining eligibility text ...>

        Args:
            path: Path to the .txt file.

        Returns:
            Parsed TrialText with all sections populated.

        Raises:
            ValueError: If the NCT number cannot be found in the file.
        """
        raw = path.read_text(encoding="utf-8", errors="replace")

        nct_match = _NCT_RE.search(raw)
        if not nct_match:
            raise ValueError(f"No NCT number found in {path.name}")
        nct_number = nct_match.group().upper()

        official_title = self._extract_section(raw, "officialTitle")
        brief_summary = self._extract_section(raw, "briefSummary")

        return TrialText(
            nct_number=nct_number,
            official_title=official_title,
            brief_summary=brief_summary,
            full_text=raw,
        )

    @staticmethod
    def _extract_section(text: str, section_name: str) -> str:
        """Extract a labelled section from the trial text.

        Handles two formats:
          - "officialTitle:\\n<content>" (section on next line)
          - "officialTitle: <content>" (content on same line)
        """
        block_pattern = re.compile(
            rf"^{re.escape(section_name)}\s*:\s*\n(.*?)(?=\n[A-Za-z]|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = block_pattern.search(text)
        if match:
            return match.group(1).strip()

        inline_pattern = re.compile(
            rf"^{re.escape(section_name)}\s*:\s*(.+)$", re.MULTILINE
        )
        match = inline_pattern.search(text)
        if match:
            return match.group(1).strip()

        return ""


# ---------------------------------------------------------------------------
# Cancer type repository
# ---------------------------------------------------------------------------


class CancerTypeRepository:
    """Looks up cancer type tags from the api_discovery table in trials.db."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)

    def get_cancer_types(self, nct_number: str) -> list[str]:
        """Return the list of cancer_type_tag values for a trial.

        Args:
            nct_number: NCT identifier (e.g. "NCT00002767").

        Returns:
            List of cancer type tags, or empty list if not found.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT cancer_type_tag FROM api_discovery WHERE nct_number = ?",
                    (nct_number,),
                ).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as exc:
            logger.warning("DB lookup failed for %s: %s", nct_number, exc)
            return []

    def get_all_nct_numbers(
        self, cancer_type_filter: Optional[list[str]] = None
    ) -> list[str]:
        """Return distinct NCT numbers from api_discovery.

        Args:
            cancer_type_filter: If provided, restrict to trials tagged
                with at least one of the given cancer types.

        Returns:
            Sorted list of unique NCT number strings.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                if cancer_type_filter:
                    placeholders = ",".join("?" * len(cancer_type_filter))
                    rows = conn.execute(
                        f"SELECT DISTINCT nct_number FROM api_discovery "
                        f"WHERE cancer_type_tag IN ({placeholders}) "
                        f"ORDER BY nct_number",
                        cancer_type_filter,
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT DISTINCT nct_number FROM api_discovery "
                        "ORDER BY nct_number"
                    ).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to fetch NCT numbers from DB: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Checkpoint manager
# ---------------------------------------------------------------------------


class CheckpointManager:
    """Persists per-trial extraction status to checkpoint.json.

    The checkpoint file is a flat JSON object keyed by NCT number:
        {
            "NCT00001234": {
                "status": "done",
                "recorded_at": "2026-03-04T10:05:00"
            },
            ...
        }
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning(
                    "Could not read checkpoint file %s, starting fresh.",
                    self._path,
                )
        return {}

    def is_done(self, nct_number: str) -> bool:
        """Return True if this trial has already been successfully extracted."""
        entry = self._data.get(nct_number, {})
        return entry.get("status") == ExtractionStatus.DONE.value

    def record(self, nct_number: str, status: ExtractionStatus) -> None:
        """Record the extraction outcome for a trial and flush to disk."""
        self._data[nct_number] = {
            "status": status.value,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        self._flush()

    def _flush(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to write checkpoint: %s", exc)

    @property
    def completed_count(self) -> int:
        return sum(
            1
            for v in self._data.values()
            if v.get("status") == ExtractionStatus.DONE.value
        )


# ---------------------------------------------------------------------------
# Per-trial LLM extractor
# ---------------------------------------------------------------------------


class TrialParameterExtractor:
    """Runs a single LLM call to extract all parameters for a trial."""

    def __init__(self, llm: LLMService, modality_only: bool = False) -> None:
        self._llm = llm
        self._modality_only = modality_only

    async def extract(
        self, trial: TrialText, cancer_types: list[str]
    ) -> TrialParameterResult:
        """Run single-pass extraction and return a consolidated result.

        One LLM call returns all six fields. If the call fails entirely the
        status is set to FAILED. If the call succeeds but some fields are
        empty the status is PARTIAL.

        In modality_only mode the narrow prompt is used instead and only
        `modality` is populated; see `_extract_modality_only`.

        Args:
            trial: Parsed trial text sections.
            cancer_types: Cancer type tags from api_discovery.

        Returns:
            TrialParameterResult with populated fields.
        """
        result = TrialParameterResult(
            nct_number=trial.nct_number,
            cancer_type=cancer_types,
        )
        if self._modality_only:
            return await self._extract_modality_only(trial, result)

        try:
            prompt = build_extraction_prompt(trial.full_text)
            raw = await self._llm.extract_json(
                prompt,
                operation="extraction",
                attribute_type="all_parameters",
            )

            result.treatment_name = raw.get("treatment_name") or None

            result.modality = [
                v for v in _coerce_list(raw.get("modality")) if v in _MODALITY_SET
            ]

            result.biomarker = [
                v for v in _coerce_list(raw.get("biomarker")) if v in _BIOMARKER_SET
            ]
            result.stage = [
                v for v in _coerce_list(raw.get("stage")) if v in _STAGE_SET
            ]
            result.line_of_therapy = [
                v for v in _coerce_list(raw.get("line_of_therapy")) if v in _LOT_SET
            ]
            result.previous_treatment_criteria = [
                v
                for v in _coerce_list(raw.get("previous_treatment_criteria"))
                if v in _PREV_TX_SET
            ]

            logger.debug(
                "%s | treatment=%s modality=%s biomarker=%s "
                "stage=%s lot=%s prev_tx=%s",
                trial.nct_number,
                result.treatment_name,
                result.modality,
                result.biomarker,
                result.stage,
                result.line_of_therapy,
                result.previous_treatment_criteria,
            )

            # Mark as PARTIAL if none of the core fields were populated
            populated = sum(
                [
                    result.treatment_name is not None,
                    bool(result.modality),
                    bool(result.biomarker),
                    bool(result.stage),
                    bool(result.line_of_therapy),
                ]
            )
            if populated == 0:
                result.extraction_status = ExtractionStatus.PARTIAL
                result.error_message = "LLM returned no extractable fields."
            else:
                result.extraction_status = ExtractionStatus.DONE

        except Exception as exc:
            logger.warning("%s | extraction failed: %s", trial.nct_number, exc)
            result.extraction_status = ExtractionStatus.FAILED
            result.error_message = str(exc)

        return result

    async def _extract_modality_only(
        self, trial: TrialText, result: TrialParameterResult
    ) -> TrialParameterResult:
        """Populate `modality` alone, leaving every other field untouched.

        `treatment_name` is requested by the prompt as the reasoning anchor for
        the modality decision and is kept on the result for human review of the
        backfill diff; no consumer of a modality-only run writes it back.

        An empty modality is PARTIAL, not DONE: for the backfill that means
        "the model could not tell", which must not overwrite a stored value.
        """
        try:
            prompt = build_modality_prompt(trial.full_text)
            raw = await self._llm.extract_json(
                prompt,
                operation="extraction",
                attribute_type="modality",
            )

            result.treatment_name = raw.get("treatment_name") or None
            result.modality = self._filter_modality(
                _coerce_list(raw.get("modality")), trial.nct_number
            )

            logger.debug(
                "%s | treatment=%s modality=%s",
                trial.nct_number,
                result.treatment_name,
                result.modality,
            )

            if result.modality:
                result.extraction_status = ExtractionStatus.DONE
            else:
                result.extraction_status = ExtractionStatus.PARTIAL
                result.error_message = "LLM returned no modality."

        except Exception as exc:
            logger.warning("%s | modality extraction failed: %s", trial.nct_number, exc)
            result.extraction_status = ExtractionStatus.FAILED
            result.error_message = str(exc)

        return result

    @staticmethod
    def _filter_modality(values: list[str], nct_number: str) -> list[str]:
        """Drop values outside MODALITY_VALUES, logging what was dropped.

        A value the vocabulary does not know is discarded silently everywhere
        else in this file, which makes a prompt/vocabulary mismatch look like a
        clean run. Log it loudly instead.
        """
        kept = [v for v in values if v in _MODALITY_SET]
        rejected = [v for v in values if v not in _MODALITY_SET]
        if rejected:
            logger.warning(
                "%s | modality values outside the vocabulary, dropped: %s",
                nct_number,
                rejected,
            )
        return kept


# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------


class ResultWriter:
    """Writes extraction results and cost report to the output directory."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

    def write_results(
        self,
        results: list[TrialParameterResult],
        summary: ExtractionRunSummary,
    ) -> Path:
        """Upsert `results` into results.json, keyed by NCT number.

        A resumed run only processes the trials it did not already complete, so
        `results` holds a subset of the file's trials. Merging with what is on
        disk keeps earlier runs' trials intact; writing `results` directly would
        truncate the file to just this run's work.

        Args:
            results: Extracted results for the trials processed this run.
            summary: High-level run statistics.

        Returns:
            Path to the written results file.
        """
        path = self._output_dir / "results.json"

        merged: dict[str, dict] = {}
        if path.exists():
            existing = json.loads(path.read_text())
            for trial in existing.get("trials", []):
                merged[trial["nct_number"]] = trial
        for result in results:
            trial = result.to_dict()
            merged[trial["nct_number"]] = trial
        trials = list(merged.values())

        # Counts describe every trial in the file, not just this run's, so the
        # metadata block stays consistent with the trials beside it.
        metadata = summary.to_dict()
        statuses = [t["extraction_status"] for t in trials]
        metadata["total_trials"] = len(trials)
        metadata["successful"] = statuses.count(ExtractionStatus.DONE.value)
        metadata["partial"] = statuses.count(ExtractionStatus.PARTIAL.value)
        metadata["failed"] = statuses.count(ExtractionStatus.FAILED.value)

        output = {"metadata": metadata, "trials": trials}
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        logger.info("Results written to %s (%d trials)", path, len(trials))
        return path

    def write_cost_report(self, cost_calculator: CostCalculator) -> Path:
        """Write cost_report.json from the CostCalculator.

        Args:
            cost_calculator: Calculator instance containing all recorded calls.

        Returns:
            Path to the written cost report file.
        """
        path = self._output_dir / "cost_report.json"
        cost_calculator.save_detailed_report(str(path))
        return path


# ---------------------------------------------------------------------------
# Main orchestration service
# ---------------------------------------------------------------------------


class TrialParameterExtractionService:
    """End-to-end orchestrator for the clinical trial parameter pipeline.

    Usage::

        service = TrialParameterExtractionService.from_config(config, api_key)
        await service.run()
    """

    def __init__(
        self,
        config: ExtractionConfig,
        llm: LLMService,
        loader: TrialLoader,
        cancer_repo: CancerTypeRepository,
        extractor: TrialParameterExtractor,
        checkpoint: CheckpointManager,
        writer: ResultWriter,
        cost_calculator: CostCalculator,
        snapshot_source: Optional[SnapshotTrialSource] = None,
    ) -> None:
        self._config = config
        self._llm = llm
        self._loader = loader
        self._cancer_repo = cancer_repo
        self._extractor = extractor
        self._checkpoint = checkpoint
        self._writer = writer
        self._cost_calculator = cost_calculator
        self._snapshot_source = snapshot_source

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: ExtractionConfig,
        api_key: str,
        llm_service: Optional[LLMService] = None,
        cost_calculator: Optional[CostCalculator] = None,
    ) -> "TrialParameterExtractionService":
        """Construct a fully wired service from config and API key.

        Args:
            config: Extraction run configuration.
            api_key: API key for the LLM provider.
            llm_service: Pre-built LLMService instance.  When supplied the
                         api_key argument is ignored and no service is created
                         internally.  Pass None to auto-create an
                         OpenRouterLLMService (legacy behaviour).
            cost_calculator: CostCalculator instance to use for cost tracking.
                             **Must be the same instance that was injected into
                             llm_service**, otherwise the cost report will be
                             empty.  When omitted, a new instance is created and
                             passed to the internally-built OpenRouterLLMService.

        Returns:
            Configured TrialParameterExtractionService ready to run.
        """
        config.output_dir.mkdir(parents=True, exist_ok=True)

        _cost_calculator = cost_calculator or CostCalculator()
        if llm_service is not None:
            llm = llm_service
        else:
            llm = OpenRouterLLMService(
                api_key=api_key,
                model=config.model,
                cost_calculator=_cost_calculator,
            )
        loader = TrialLoader()
        cancer_repo = CancerTypeRepository(config.trials_db_path)
        extractor = TrialParameterExtractor(llm, modality_only=config.modality_only)
        checkpoint = CheckpointManager(config.output_dir / "checkpoint.json")
        writer = ResultWriter(config.output_dir)

        snapshot_source: Optional[SnapshotTrialSource] = None
        if config.snapshot_path is not None:
            snapshot = json.loads(config.snapshot_path.read_text(encoding="utf-8"))
            snapshot_source = SnapshotTrialSource(snapshot)

        return cls(
            config=config,
            llm=llm,
            loader=loader,
            cancer_repo=cancer_repo,
            extractor=extractor,
            checkpoint=checkpoint,
            writer=writer,
            cost_calculator=_cost_calculator,
            snapshot_source=snapshot_source,
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self) -> list[TrialParameterResult]:
        """Execute the extraction pipeline.

        Workflow:
          1. Collect the candidate NCT numbers (from DB ∩ export files).
          2. Apply limit, then drop the trials already in the checkpoint.
          3. Extract up to `concurrency` trials in parallel; each worker loads
             the trial, fetches its cancer types, runs the LLM call, then takes
             the write lock to record its checkpoint entry and flush
             results.json.
          4. Write final results.json and cost_report.json.

        Returns:
            List of TrialParameterResult for every trial attempted.
        """
        run_start = datetime.now(UTC)
        summary = ExtractionRunSummary(
            model=self._config.model,
            run_date=run_start,
        )
        if self._config.snapshot_path is not None:
            snapshot_bytes = self._config.snapshot_path.read_bytes()
            summary.snapshot_path = str(self._config.snapshot_path)
            summary.snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()

        candidates = self._build_candidate_list()
        pending = [
            nct
            for nct in candidates
            if not (self._config.resume and self._checkpoint.is_done(nct))
        ]
        summary.skipped += len(candidates) - len(pending)
        summary.total_trials += len(candidates) - len(pending)
        logger.info(
            "Pipeline starting | candidates=%d pending=%d concurrency=%d "
            "limit=%s model=%s dry_run=%s",
            len(candidates),
            len(pending),
            self._config.concurrency,
            self._config.limit,
            self._config.model,
            self._config.dry_run,
        )

        results: list[TrialParameterResult] = []
        write_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(max(1, self._config.concurrency))

        async def _worker(nct_number: str) -> None:
            async with semaphore:
                try:
                    result = await self._extract_one(nct_number)
                except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                    logger.error(
                        "%s | unexpected extraction error: %s", nct_number, exc
                    )
                    result = TrialParameterResult(
                        nct_number=nct_number,
                        extraction_status=ExtractionStatus.FAILED,
                        error_message=str(exc),
                    )

            async with write_lock:
                summary.total_trials += 1
                if result is None:
                    summary.skipped += 1
                    return

                results.append(result)
                self._checkpoint.record(nct_number, result.extraction_status)
                if result.extraction_status == ExtractionStatus.DONE:
                    summary.successful += 1
                elif result.extraction_status == ExtractionStatus.PARTIAL:
                    summary.partial += 1
                else:
                    summary.failed += 1

                logger.info(
                    "Processed %d/%d | %s | status=%s",
                    summary.total_trials,
                    len(candidates),
                    nct_number,
                    result.extraction_status.value,
                )

                # Flush after every trial so progress survives an interruption
                cost_so_far = self._cost_calculator.get_summary()
                summary.total_cost_usd = cost_so_far.total_cost
                summary.total_tokens = cost_so_far.total_tokens
                self._writer.write_results(results, summary)

        await asyncio.gather(*(_worker(nct) for nct in pending))

        # ------------------------------------------------------------------
        # Finalise and write output
        # ------------------------------------------------------------------
        cost_summary = self._cost_calculator.get_summary()
        summary.total_cost_usd = cost_summary.total_cost
        summary.total_tokens = cost_summary.total_tokens

        if not self._config.dry_run:
            results_path = self._writer.write_results(results, summary)
            cost_path = self._writer.write_cost_report(self._cost_calculator)
            logger.info(
                "Run complete | successful=%d partial=%d failed=%d skipped=%d "
                "cost=$%.4f tokens=%d",
                summary.successful,
                summary.partial,
                summary.failed,
                summary.skipped,
                summary.total_cost_usd,
                summary.total_tokens,
            )
            logger.info("Results: %s", results_path)
            logger.info("Cost report: %s", cost_path)
        else:
            logger.info(
                "Dry run complete | would process %d trials",
                len(candidates) - summary.skipped,
            )

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _extract_one(self, nct_number: str) -> Optional[TrialParameterResult]:
        """Load one trial and run extraction on it.

        Args:
            nct_number: Trial to process.

        Returns:
            The extraction result, or None when the trial is skipped - no export
            file on disk, or a dry run that makes no LLM call.
        """
        try:
            if self._snapshot_source is not None:
                trial = self._snapshot_source.load_trial(nct_number)
            else:
                txt_path = self._config.exports_dir / f"{nct_number}.txt"
                if not txt_path.exists():
                    logger.warning("%s | export file not found, skipping", nct_number)
                    return None
                trial = self._loader.load(txt_path)
        except Exception as exc:
            logger.error("%s | failed to load trial: %s", nct_number, exc)
            return TrialParameterResult(
                nct_number=nct_number,
                extraction_status=ExtractionStatus.FAILED,
                error_message=f"Trial load error: {exc}",
            )

        if self._snapshot_source is not None:
            cancer_types = self._snapshot_source.get_cancer_types(nct_number)
        else:
            cancer_types = self._cancer_repo.get_cancer_types(nct_number)

        if self._config.dry_run:
            logger.info(
                "DRY RUN | %s | cancer_types=%s | title=%s",
                nct_number,
                cancer_types,
                trial.official_title[:80],
            )
            return None

        return await self._extractor.extract(trial, cancer_types)

    def _build_candidate_list(self) -> list[str]:
        """Build the ordered list of NCT numbers to attempt.

        Intersects:
          - NCTs available in api_discovery (optionally filtered by cancer type)
          - NCTs that have a corresponding .txt export file

        Applies the configured limit last.
        """
        if self._snapshot_source is not None:
            available = set(
                self._snapshot_source.get_all_nct_numbers(
                    self._config.cancer_type_filter
                )
            )
        else:
            db_ncts = set(
                self._cancer_repo.get_all_nct_numbers(self._config.cancer_type_filter)
            )
            export_ncts = {
                p.stem.upper() for p in self._config.exports_dir.glob("NCT*.txt")
            }
            available = db_ncts & export_ncts

        nct_allowlist = self._config.nct_allowlist
        if nct_allowlist:
            allowset = {n.upper() for n in nct_allowlist}
            candidates = sorted(allowset & available)
            logger.info("NCT allowlist applied: %d trial(s)", len(candidates))
            return candidates

        candidates = sorted(available)

        limit = self._config.limit
        if limit is not None:
            if self._config.last:
                end = len(candidates) - self._config.offset
                start = max(0, end - limit)
                candidates = list(itertools.islice(candidates, start, end))
            else:
                start = self._config.offset
                candidates = list(itertools.islice(candidates, start, start + limit))

        source = "snapshot" if self._snapshot_source is not None else "DB ∩ exports"
        logger.info(
            "Candidates: %d available (%s), %d after limit/offset",
            len(available),
            source,
            len(candidates),
        )
        return candidates


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _coerce_list(value: object) -> list[str]:
    """Coerce an LLM response value to a list of strings.

    Handles:
    - Already a list → returned as-is (non-string items are stringified)
    - A string → wrapped in a single-element list
    - None / missing → empty list
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value:
        return [value]
    return []
