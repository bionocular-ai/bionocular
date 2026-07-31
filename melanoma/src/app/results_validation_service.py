"""LLM-as-a-Judge validation pipeline for extracted abstract / publication results.

Reads an extraction run's ``extraction_results_*.json``, re-loads the source
markdown each document was extracted from, runs a deterministic pre-pass, then
asks a Gemini judge three questions per document - one per attribute group
(identification, efficacy, safety) - each seeing the full source text and every
treatment arm together. Arms are then routed keep / fix / drop / HITL.

Mirrors ``trials_validation_service`` (config -> ``from_config`` factory ->
collaborator classes -> ``run()`` loop -> checkpoint -> merge-upsert writer, with
bounded concurrency and a lock around disk writes). Two things differ, because
the data differs:

* The unit of judgement is a **treatment arm**, not a document. A document's three
  group verdicts are demultiplexed back onto its arms before routing.
* Extraction normalises values as it reads them, so "the extracted value must
  appear in its supporting quote" only holds for the derivations that preserve the
  number. ``effective_status`` enforces it exactly there and nowhere else.

Authority is staged, as in the trials pipeline:

* ``apply_fixes=False`` (default) - the judge is advisory: everything it flags
  goes to the HITL queue and nothing is edited on its say-so.
* ``apply_fixes=True`` (after gold-set calibration) - a FAIL carrying a grounded,
  above-threshold correction is applied. A FAIL without one still goes to HITL
  rather than dropping the arm: one bad value among 165 is not grounds to discard
  an arm's good data.

The pure decision logic lives in module functions (``value_supported_by_quote``,
``effective_status``, ``route_arm``) so it is unit-testable without an LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..domain.constants import ResultsValidation
from ..domain.models import DocumentType
from ..domain.results_validation_models import (
    ArmFieldEvaluation,
    ArmValidationResult,
    AttributeGroup,
    DocValidationResult,
    GroupVerdict,
    MissedValue,
    ResultsValidationRunSummary,
    ValidationDecision,
    ValidationFieldStatus,
)
from ..domain.results_validation_prompts import build_group_prompt, group_for_field
from ..domain.structured_llm_interfaces import StructuredLLMService
from ..infrastructure.cost_calculator import CostCalculator
from ..infrastructure.document_source_loader import (
    DocumentSourceLoader,
    SourceDocumentNotFoundError,
)
from ..infrastructure.results_deterministic_validator import (
    DeterministicViolation,
    check_arm,
    has_value,
    is_droppable,
    render_value,
    violation_dict,
)
from .trials_validation_service import quote_grounded

logger = logging.getLogger(__name__)

# Where each document type's records live in an extraction results file, and
# which key carries the document id.
_RESULTS_LAYOUT: dict[str, tuple[str, str]] = {
    DocumentType.ABSTRACT.value: ("abstracts", "abstract_id"),
    DocumentType.PUBLICATION.value: ("publications", "pub_id"),
}

# Derivations that preserve the extracted number, so it must appear in the quote.
_LITERAL_DERIVATIONS = {"VERBATIM", "UNIT_STRIPPED"}

_DASHES = re.compile(r"[–—]")
# The Lancet and JCO set decimal points as a middle dot ("11·0"). Only rewrite one
# that sits between two digits, so markdown bullets are left alone.
_MIDDLE_DOT_DECIMAL = re.compile(r"(?<=\d)[·•∙⋅](?=\d)")
# Sources write interval bounds as "0.43 to 0.76"; the extractor stores "0.43-0.76"
# (the same normalisation `value_validator.validate_ci` performs).
_RANGE_TO = re.compile(r"(?<=\d)\s+to\s+(?=\d)", re.IGNORECASE)
_HAS_DIGIT = re.compile(r"\d")


# ---------------------------------------------------------------------------
# Pure logic (no I/O) - unit-testable without an LLM
# ---------------------------------------------------------------------------


def _normalise_numerals(text: str) -> str:
    """Fold typographic dash, decimal-point and range-separator variants to ASCII."""
    folded = _MIDDLE_DOT_DECIMAL.sub(".", _DASHES.sub("-", text))
    return _RANGE_TO.sub("-", folded)


def value_supported_by_quote(value: str, quote: str) -> bool:
    """Whether `value` appears as a distinct number inside `quote`.

    Percent signs, dash styles, middle-dot decimals and "0.43 to 0.76" ranges are
    normalised away: the extractor strips or rewrites all of them, so a raw
    comparison would reject correct values. The lookarounds stop "56" from being
    satisfied by "561" or "5.6".

    A value carrying no digits at all ("NR", "Significant") is a token the source
    states in words ("not reached"), which containment cannot express - such a
    value is left to the quote-grounding check alone.
    """
    if not value.strip() or not quote.strip():
        return False
    needle = _normalise_numerals(value.strip().rstrip("%").strip())
    if not _HAS_DIGIT.search(needle):
        return True
    haystack = _normalise_numerals(quote)
    pattern = rf"(?<![\d.]){re.escape(needle)}(?![\d])"
    return re.search(pattern, haystack) is not None


def effective_status(
    evaluation: ArmFieldEvaluation, source_text: str
) -> ValidationFieldStatus:
    """The status after applying the anti-hallucination guards.

    A PASS the judge cannot defend is downgraded rather than trusted:

    * no quote, or a quote that is not literally in the source -> UNCERTAIN.
    * a quote-preserving derivation whose value is missing from its own quote
      -> UNCERTAIN. Summed / computed / percent-of-count values are exempt: their
      number legitimately does not appear in the text.
    * a value the judge says belongs to another arm -> FAIL, whatever it claimed.
    """
    if not evaluation.arm_attribution_ok:
        return ValidationFieldStatus.FAIL
    if evaluation.status is not ValidationFieldStatus.PASS:
        return evaluation.status

    quote = evaluation.source_evidence_quote
    if not quote_grounded(quote, source_text):
        return ValidationFieldStatus.UNCERTAIN
    assert quote is not None  # quote_grounded rejects None/blank
    derivation = evaluation.derivation.value if evaluation.derivation else None
    if derivation in _LITERAL_DERIVATIONS and not value_supported_by_quote(
        evaluation.extracted_value, quote
    ):
        return ValidationFieldStatus.UNCERTAIN
    return ValidationFieldStatus.PASS


@dataclass
class RouteOutcome:
    decision: ValidationDecision
    applied_corrections: list[dict] = field(default_factory=list)


def _correction_is_gated(
    evaluation: ArmFieldEvaluation,
    source_text: str,
    validation_score: float,
    score_threshold: float,
) -> bool:
    """Whether a FAIL's proposed correction clears every safety gate."""
    if not evaluation.corrected_value or not evaluation.corrected_value.strip():
        return False
    if validation_score < score_threshold:
        return False
    return quote_grounded(evaluation.source_evidence_quote, source_text)


def route_arm(
    *,
    evaluations: list[ArmFieldEvaluation],
    missed_values: list[MissedValue],
    violations: list[DeterministicViolation],
    source_text: str,
    validation_score: float,
    apply_fixes: bool,
    score_threshold: float,
) -> RouteOutcome:
    """Decide one arm's fate from its deterministic and judge findings (pure)."""
    if is_droppable(violations):
        return RouteOutcome(ValidationDecision.DROPPED)

    fails: list[ArmFieldEvaluation] = []
    uncertain = False
    for evaluation in evaluations:
        status = effective_status(evaluation, source_text)
        if status is ValidationFieldStatus.FAIL:
            fails.append(evaluation)
        elif status is ValidationFieldStatus.UNCERTAIN:
            uncertain = True

    flagged = bool(fails) or uncertain or bool(missed_values) or bool(violations)
    if not flagged:
        return RouteOutcome(ValidationDecision.KEPT)

    if not apply_fixes:
        # Advisory mode: never act on the judge, queue everything it flagged.
        return RouteOutcome(ValidationDecision.HITL)

    # Mature mode. Anything a correction cannot express needs a human: an
    # ambiguous source, a value the extractor omitted, a deterministic warning.
    if uncertain or missed_values or violations:
        return RouteOutcome(ValidationDecision.HITL)

    corrections: list[dict] = []
    for evaluation in fails:
        if not _correction_is_gated(
            evaluation, source_text, validation_score, score_threshold
        ):
            return RouteOutcome(ValidationDecision.HITL)
        corrections.append(
            {
                "field": evaluation.field_name,
                "corrected": (evaluation.corrected_value or "").strip(),
                "evidence_quote": evaluation.source_evidence_quote,
                "score": validation_score,
            }
        )
    return RouteOutcome(ValidationDecision.FIXED, corrections)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class ResultsValidationConfig:
    """Runtime configuration for a results-validation run."""

    results_paths: list[Path]
    doc_type: str
    output_dir: Path
    model: str
    concurrency: int = 5
    apply_fixes: bool = False
    score_threshold: float = 0.75
    sample: int | None = None
    resume: bool = True
    dry_run: bool = False
    doc_allowlist: list[str] | None = None


# ---------------------------------------------------------------------------
# Checkpoint (resume across runs)
# ---------------------------------------------------------------------------


class ValidationCheckpointManager:
    """Persists which documents have been validated so a run can resume."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._done: dict[str, dict] = {}
        if path.exists():
            self._done = json.loads(path.read_text())

    def is_done(self, doc_id: str) -> bool:
        return doc_id in self._done

    def record(self, doc_id: str, decision: str) -> None:
        self._done[doc_id] = {
            "decision": decision,
            "recorded_at": datetime.utcnow().isoformat(),
        }
        self._path.write_text(json.dumps(self._done, indent=2))


# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------


class ResultsValidationWriter:
    """Writes validation.json (merge-upsert) plus the derived routing files."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

    def write_validation(
        self,
        results: list[DocValidationResult],
        summary: ResultsValidationRunSummary,
    ) -> Path:
        path = self._output_dir / ResultsValidation.VALIDATION_FILE
        merged: dict[str, dict] = {}
        if path.exists():
            existing = json.loads(path.read_text())
            for row in existing.get("documents", []):
                merged[row["doc_id"]] = row
        for result in results:
            merged[result.doc_id] = result.to_dict()
        rows = list(merged.values())

        arms = [arm for row in rows for arm in row["arms"]]
        decisions = [arm["decision"] for arm in arms]
        metadata = summary.to_dict()
        metadata["total_documents"] = len(rows)
        metadata["total_arms"] = len(arms)
        metadata["kept"] = decisions.count(ValidationDecision.KEPT.value)
        metadata["fixed"] = decisions.count(ValidationDecision.FIXED.value)
        metadata["dropped"] = decisions.count(ValidationDecision.DROPPED.value)
        metadata["hitl"] = decisions.count(ValidationDecision.HITL.value)
        metadata["errored"] = sum(1 for r in rows if r["error_message"])
        metadata["total_missed_values"] = sum(len(a["missed_values"]) for a in arms)

        path.write_text(
            json.dumps(
                {"metadata": metadata, "documents": rows},
                indent=2,
                ensure_ascii=False,
            )
        )
        return path

    def write_derived(
        self,
        *,
        cleaned: dict,
        hitl: list[dict],
        dropped: list[dict],
        missed_by_field: dict[str, list[dict]],
    ) -> None:
        """Write the cleaned cohort and the review / drop / recall side files."""
        self._write(ResultsValidation.CLEANED_FILE, cleaned)
        self._write(ResultsValidation.HITL_FILE, {"arms": hitl})
        self._write(ResultsValidation.DROPPED_ARMS_FILE, {"arms": dropped})
        self._write(
            ResultsValidation.MISSED_VALUES_FILE,
            {
                "total": sum(len(v) for v in missed_by_field.values()),
                "by_field": dict(
                    sorted(
                        missed_by_field.items(),
                        key=lambda item: len(item[1]),
                        reverse=True,
                    )
                ),
            },
        )

    def write_cost_report(self, cost_calculator: CostCalculator) -> Path:
        """Write cost_report.json incrementally, so a mid-run kill keeps the spend."""
        path = self._output_dir / ResultsValidation.COST_REPORT_FILE
        cost_calculator.save_detailed_report(str(path))
        return path

    def _write(self, filename: str, payload: dict) -> None:
        (self._output_dir / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False)
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ResultsValidationService:
    """Orchestrates deterministic + LLM validation over an extraction run."""

    def __init__(
        self,
        config: ResultsValidationConfig,
        llm: StructuredLLMService,
        source_loader: DocumentSourceLoader,
        checkpoint: ValidationCheckpointManager,
        writer: ResultsValidationWriter,
        cost_calculator: CostCalculator,
    ) -> None:
        self._config = config
        self._llm = llm
        self._sources = source_loader
        self._checkpoint = checkpoint
        self._writer = writer
        self._cost_calculator = cost_calculator
        self._write_lock = asyncio.Lock()

    @classmethod
    def from_config(
        cls,
        config: ResultsValidationConfig,
        llm: StructuredLLMService,
        source_loader: DocumentSourceLoader,
        cost_calculator: CostCalculator,
    ) -> ResultsValidationService:
        return cls(
            config=config,
            llm=llm,
            source_loader=source_loader,
            checkpoint=ValidationCheckpointManager(
                config.output_dir / ResultsValidation.CHECKPOINT_FILE
            ),
            writer=ResultsValidationWriter(config.output_dir),
            cost_calculator=cost_calculator,
        )

    # -- candidate selection ------------------------------------------------

    def _documents(self) -> list[dict]:
        """Every extracted document across the configured results files."""
        container, id_key = _RESULTS_LAYOUT[self._config.doc_type]
        documents: list[dict] = []
        for path in self._config.results_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for record in payload.get(container, []):
                documents.append({**record, "doc_id": record[id_key]})

        if self._config.doc_allowlist:
            wanted = set(self._config.doc_allowlist)
            documents = [d for d in documents if d["doc_id"] in wanted]
        documents.sort(key=lambda d: str(d["doc_id"]))
        if self._config.sample is not None:
            documents = documents[: self._config.sample]
        return documents

    # -- per-document validation -------------------------------------------

    async def _validate_document(self, record: dict) -> DocValidationResult:
        doc_id = str(record["doc_id"])
        source = self._sources.load(doc_id)
        arms: dict[str, dict] = record.get("arm_results") or {}

        deterministic = {arm_id: check_arm(arm) for arm_id, arm in arms.items()}
        judged_arms = {
            arm_id: arm
            for arm_id, arm in arms.items()
            if not is_droppable(deterministic[arm_id])
        }

        verdicts: dict[AttributeGroup, GroupVerdict] = {}
        if judged_arms:
            verdicts = await self._judge_groups(source.text, judged_arms)

        evaluations_by_arm: dict[str, list[ArmFieldEvaluation]] = {a: [] for a in arms}
        missed_by_arm: dict[str, list[MissedValue]] = {a: [] for a in arms}
        unknown_arm_ids: set[str] = set()
        for verdict in verdicts.values():
            for evaluation in verdict.field_evaluations:
                if evaluation.arm_id in evaluations_by_arm:
                    evaluations_by_arm[evaluation.arm_id].append(evaluation)
                else:
                    unknown_arm_ids.add(evaluation.arm_id)
            for missed in verdict.missed_values:
                if missed.arm_id in missed_by_arm:
                    missed_by_arm[missed.arm_id].append(missed)
                else:
                    unknown_arm_ids.add(missed.arm_id)
        if unknown_arm_ids:
            # Findings against an arm that does not exist cannot be routed. Losing
            # them silently would understate the review queue.
            logger.warning(
                "%s: judge referenced %d unknown arm id(s), findings discarded: %s",
                doc_id,
                len(unknown_arm_ids),
                ", ".join(sorted(unknown_arm_ids)),
            )

        worst_score = min((v.validation_score for v in verdicts.values()), default=1.0)
        arm_results = [
            self._route_one_arm(
                doc_id=doc_id,
                arm_id=arm_id,
                arm=arm,
                violations=deterministic[arm_id],
                evaluations=evaluations_by_arm[arm_id],
                missed_values=missed_by_arm[arm_id],
                source_text=source.text,
                validation_score=worst_score,
            )
            for arm_id, arm in arms.items()
        ]

        return DocValidationResult(
            doc_id=doc_id,
            doc_type=self._config.doc_type,
            arms=arm_results,
            source_sha256=source.sha256,
            source_path=str(source.path),
            group_scores={
                group.value: verdict.validation_score
                for group, verdict in verdicts.items()
            },
        )

    async def _judge_groups(
        self, source_text: str, arms: dict[str, dict]
    ) -> dict[AttributeGroup, GroupVerdict]:
        """Run all three group judges for one document concurrently."""
        groups = list(AttributeGroup)
        verdicts = await asyncio.gather(
            *(self._judge_group(group, source_text, arms) for group in groups)
        )
        return dict(zip(groups, verdicts))

    async def _judge_group(
        self, group: AttributeGroup, source_text: str, arms: dict[str, dict]
    ) -> GroupVerdict:
        prompt = build_group_prompt(
            group=group,
            doc_type=self._config.doc_type,
            source_text=source_text,
            arms_json=_candidate_json(arms, group),
            arm_count=len(arms),
        )
        return await self._llm.generate_structured(
            prompt,
            response_schema=GroupVerdict,
            operation=ResultsValidation.OPERATION,
            attribute_type=f"{ResultsValidation.ATTRIBUTE_TYPE}_{group.value}",
        )

    def _route_one_arm(
        self,
        *,
        doc_id: str,
        arm_id: str,
        arm: dict,
        violations: list[DeterministicViolation],
        evaluations: list[ArmFieldEvaluation],
        missed_values: list[MissedValue],
        source_text: str,
        validation_score: float,
    ) -> ArmValidationResult:
        outcome = route_arm(
            evaluations=evaluations,
            missed_values=missed_values,
            violations=violations,
            source_text=source_text,
            validation_score=validation_score,
            apply_fixes=self._config.apply_fixes,
            score_threshold=self._config.score_threshold,
        )
        return ArmValidationResult(
            doc_id=doc_id,
            arm_id=arm_id,
            arm_name=arm.get("arm_name"),
            decision=outcome.decision,
            is_valid=outcome.decision
            in (ValidationDecision.KEPT, ValidationDecision.FIXED),
            validation_score=validation_score,
            deterministic_violations=[violation_dict(v) for v in violations],
            field_evaluations=[
                {
                    **e.model_dump(mode="json"),
                    "effective_status": effective_status(e, source_text).value,
                }
                for e in evaluations
            ],
            missed_values=[m.model_dump(mode="json") for m in missed_values],
            applied_corrections=outcome.applied_corrections,
        )

    # -- run loop -----------------------------------------------------------

    async def run(self) -> list[DocValidationResult]:
        run_start = datetime.utcnow()
        summary = ResultsValidationRunSummary(
            model=self._config.model,
            run_date=run_start,
            doc_type=self._config.doc_type,
            apply_fixes=self._config.apply_fixes,
        )

        documents = self._documents()
        pending = [
            d
            for d in documents
            if not (self._config.resume and self._checkpoint.is_done(str(d["doc_id"])))
        ]
        logger.info(
            "Validation starting | documents=%d pending=%d apply_fixes=%s",
            len(documents),
            len(pending),
            self._config.apply_fixes,
        )

        if self._config.dry_run:
            self._report_dry_run(pending)
            return []

        results: list[DocValidationResult] = []
        semaphore = asyncio.Semaphore(max(1, self._config.concurrency))

        async def _worker(record: dict) -> None:
            doc_id = str(record["doc_id"])
            async with semaphore:
                try:
                    result = await self._validate_document(record)
                except (SourceDocumentNotFoundError, ValueError, KeyError) as exc:
                    logger.error("Validation failed for %s: %s", doc_id, exc)
                    result = DocValidationResult(
                        doc_id=doc_id,
                        doc_type=self._config.doc_type,
                        error_message=str(exc),
                    )
                except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                    logger.exception("Unexpected failure validating %s", doc_id)
                    result = DocValidationResult(
                        doc_id=doc_id,
                        doc_type=self._config.doc_type,
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                async with self._write_lock:
                    results.append(result)
                    if result.error_message is None:
                        # Errored documents stay off the checkpoint so --resume
                        # retries them; a transient timeout must not silently
                        # exclude a document from the cohort forever.
                        self._checkpoint.record(result.doc_id, result.decision.value)
                    self._record_cost(summary)
                    self._writer.write_validation(results, summary)
                    self._writer.write_cost_report(self._cost_calculator)
                    logger.info(
                        "Validated %d/%d | %s | %s | %d arm(s)",
                        len(results),
                        len(pending),
                        result.doc_id,
                        result.decision.value,
                        len(result.arms),
                    )

        await asyncio.gather(*(_worker(record) for record in pending))

        self._write_derived_outputs(documents)
        self._record_cost(summary)
        self._writer.write_validation(results, summary)
        self._writer.write_cost_report(self._cost_calculator)
        logger.info("Validation complete | %d documents", len(results))
        return results

    def _record_cost(self, summary: ResultsValidationRunSummary) -> None:
        cost = self._cost_calculator.get_summary()
        summary.total_cost_usd = cost.total_cost
        summary.total_tokens = cost.total_tokens

    def _report_dry_run(self, pending: list[dict]) -> None:
        """Confirm every pending document resolves to a source before spending."""
        available = self._sources.available_ids()
        missing = [
            str(d["doc_id"]) for d in pending if str(d["doc_id"]) not in available
        ]
        arms = sum(len(d.get("arm_results") or {}) for d in pending)
        logger.info(
            "Dry run | %d document(s), %d arm(s), %d judge call(s) would run",
            len(pending),
            arms,
            len(pending) * len(AttributeGroup),
        )
        if missing:
            logger.error(
                "%d document(s) have no source markdown: %s",
                len(missing),
                ", ".join(missing[:10]),
            )
        else:
            logger.info("All %d document(s) resolved to a source file.", len(pending))

    # -- derived outputs ----------------------------------------------------

    def _write_derived_outputs(self, documents: list[dict]) -> None:
        """Recompute the cleaned cohort and side files from validation.json."""
        validation = json.loads(
            (self._config.output_dir / ResultsValidation.VALIDATION_FILE).read_text()
        )
        verdicts = {row["doc_id"]: row for row in validation.get("documents", [])}
        container, _ = _RESULTS_LAYOUT[self._config.doc_type]

        cleaned_documents: list[dict] = []
        hitl: list[dict] = []
        dropped: list[dict] = []
        missed_by_field: dict[str, list[dict]] = {}

        for record in documents:
            doc_id = str(record["doc_id"])
            verdict = verdicts.get(doc_id)
            if verdict is None:
                continue
            arms: dict[str, dict] = record.get("arm_results") or {}
            kept_arms: dict[str, dict] = {}

            for arm_verdict in verdict["arms"]:
                arm_id = arm_verdict["arm_id"]
                arm = arms.get(arm_id)
                if arm is None:
                    continue
                decision = arm_verdict["decision"]
                if decision == ValidationDecision.KEPT.value:
                    kept_arms[arm_id] = arm
                elif decision == ValidationDecision.FIXED.value:
                    kept_arms[arm_id] = _apply_corrections(arm, arm_verdict)
                elif decision == ValidationDecision.DROPPED.value:
                    dropped.append(arm_verdict)
                else:
                    hitl.append(arm_verdict)

                for missed in arm_verdict["missed_values"]:
                    missed_by_field.setdefault(missed["field_name"], []).append(
                        {"doc_id": doc_id, **missed}
                    )

            cleaned_documents.append(
                {**record, "arm_results": kept_arms, "total_arms": len(kept_arms)}
            )

        cleaned = {
            "source": f"{self._config.doc_type}_validation",
            "total_documents": len(cleaned_documents),
            "total_arms": sum(len(d["arm_results"]) for d in cleaned_documents),
            container: cleaned_documents,
        }
        self._writer.write_derived(
            cleaned=cleaned,
            hitl=hitl,
            dropped=dropped,
            missed_by_field=missed_by_field,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate_json(arms: dict[str, dict], group: AttributeGroup) -> str:
    """Render the arms' candidate values for one group as the judge's input.

    Empty values are kept but collapsed to a single sentinel, so the judge can see
    which attributes the extractor claimed to find nothing for - that claim is what
    the recall sweep tests.
    """
    payload: dict[str, dict] = {}
    for arm_id, arm in arms.items():
        extracted: dict[str, str] = {}
        for name, attribute in (arm.get("attributes") or {}).items():
            if group_for_field(name) is not group:
                continue
            raw = attribute.get("value") if isinstance(attribute, dict) else attribute
            rendered = render_value(raw)
            extracted[name] = rendered if has_value(rendered) else ""
        payload[arm_id] = {
            "arm_name": arm.get("arm_name"),
            "generic_name": arm.get("generic_name"),
            "patient_count": arm.get("patient_count"),
            "arm_source_text": arm.get("source_text"),
            "extracted": extracted,
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _apply_corrections(arm: dict, arm_verdict: dict) -> dict:
    """Return a copy of `arm` with the judge's gated corrections applied."""
    fixed = json.loads(json.dumps(arm))
    attributes = fixed.setdefault("attributes", {})
    for correction in arm_verdict.get("applied_corrections", []):
        attribute = attributes.setdefault(correction["field"], {})
        attribute["value"] = correction["corrected"]
        attribute["source"] = ResultsValidation.OPERATION
    return fixed
