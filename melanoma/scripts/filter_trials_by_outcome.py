#!/usr/bin/env python3
"""Filter a trials snapshot by outcome measure — snapshot in, snapshot out.

Reads a snapshot produced by `download_clinical_trials_snapshot.py`, keeps only
trials that pass the outcome-measure rule in `_keeps_trial`, and writes a filtered
snapshot with the same schema (fewer trials). The extraction pipeline then runs on
the filtered file via `--snapshot`.

The role is filter-only: it does not add or change any extracted field.

Rule: keep a trial if any primary or secondary outcome `measure` mentions a main
efficacy or safety endpoint (keyword patterns below). Stem-based and
case-insensitive so it is robust to spelling/spacing variants (e.g. "Overall
survival" / "overall Survival (OS)" / "Progression-Free Survival"). Validated
against the 2,338-trial non-industry snapshot: ~1,771 kept / ~567 dropped (167
with no outcomes + ~400 non-therapeutic, e.g. imaging/diagnostic agreement,
sun-exposure behaviour, wound healing, feasibility). To tighten, edit `_PATTERNS`.

Usage:
    cd melanoma
    poetry run python3 scripts/filter_trials_by_outcome.py \\
        --in  data/output/trials_extraction_nonindustry/2026-07-16-clinical-trials.json \\
        --out data/output/trials_extraction_nonindustry/2026-07-16-clinical-trials.filtered.json
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Main efficacy/safety endpoint patterns, matched case-insensitively against
# outcome `measure` labels. Stems (e.g. "surviv", "progression") absorb spelling
# and spacing variants. Bare ambiguous acronyms like "OS" are omitted on purpose
# — their spelled-out stems cover them without matching "dose"/"osteo".
_PATTERNS = [
    # efficacy
    r"surviv", r"progression", r"recurrence", r"relapse", r"metasta",
    r"\bresponse\b", r"remission", r"mortality", r"disease control",
    r"duration of response", r"clearance", r"\befficac", r"\bORR\b",
    # safety
    r"adverse", r"\bsafety\b", r"tolerat", r"toxicit", r"dose[- ]?limiting",
    r"\bDLT\b", r"\bMTD\b", r"maximum tolerated", r"serious adverse",
]
_RULE_DESCRIPTION = "primary/secondary outcome measure matches an efficacy/safety endpoint"
_ENDPOINT_RE = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def _measures(trial: dict) -> list[str]:
    """All primary + secondary outcome `measure` labels for a trial."""
    return [
        outcome.get("measure") or ""
        for key in ("primary_outcomes", "secondary_outcomes")
        for outcome in (trial.get(key) or [])
    ]


def _keeps_trial(trial: dict) -> bool:
    """Keep the trial if any outcome measure mentions an efficacy/safety endpoint."""
    return any(_ENDPOINT_RE.search(m) for m in _measures(trial))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filter_trials_by_outcome",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--in", dest="in_path", type=Path, required=True, metavar="PATH",
        help="Input snapshot JSON.",
    )
    parser.add_argument(
        "--out", dest="out_path", type=Path, required=True, metavar="PATH",
        help="Output filtered snapshot JSON.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if not args.in_path.exists():
        print(f"ERROR: input snapshot not found: {args.in_path}", file=sys.stderr)
        sys.exit(1)

    snapshot = json.loads(args.in_path.read_text(encoding="utf-8"))
    trials = snapshot.get("trials", [])
    kept = [t for t in trials if _keeps_trial(t)]
    dropped = [t for t in trials if not _keeps_trial(t)]

    metadata = dict(snapshot.get("metadata", {}))
    metadata["outcome_filter"] = {
        "rule": _RULE_DESCRIPTION,
        "patterns": _PATTERNS,
        "input_count": len(trials),
        "kept_count": len(kept),
        "dropped_count": len(dropped),
    }

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(
        json.dumps({"metadata": metadata, "trials": kept}, indent=2),
        encoding="utf-8",
    )

    # Companion file: dropped NCTs, so the excluded trials can be re-run later via
    # the extractor's --nct allowlist against the frozen full snapshot.
    dropped_path = args.out_path.with_suffix(args.out_path.suffix + ".dropped-ncts.json")
    dropped_path.write_text(
        json.dumps({"dropped_ncts": [t["nct_id"] for t in dropped]}, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Filtered %d trials → kept %d, dropped %d → %s (dropped NCTs → %s)",
        len(trials), len(kept), len(dropped), args.out_path, dropped_path,
    )


if __name__ == "__main__":
    main()
