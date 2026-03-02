"""Open Targets Platform GraphQL API client and repository.

Provides:
- OpenTargetsClient: fetches knownDrugs data via GraphQL
- OpenTargetsRepository: reads/writes open_targets_data table in trials.db
- CANCER_TYPE_EFO_MAP: mapping from normalized cancer type tags to EFO IDs
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OT_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# ---------------------------------------------------------------------------
# Cancer type → EFO mapping
# ---------------------------------------------------------------------------
# Brain/CNS metastasis has no dedicated EFO ID in the OT ontology.
# We query it as cutaneous melanoma (EFO_0000389) and store under the
# combined tag "Cutaneous melanoma with Brain/CNS metastasis".
CANCER_TYPE_EFO_MAP: dict[str, list[str]] = {
    "Cutaneous melanoma": ["EFO_0000389"],
    "Cutaneous Squamous Cell Carcinoma": ["EFO_1001927"],
    "Uveal Melanoma": ["EFO_1000616"],
    "Acral Melanoma": ["MONDO_0003865"],
    "Mucosal Melanoma": ["MONDO_0000544"],
    "Basal Cell Carcinoma": ["EFO_0004193"],
    "Merkel Cell Carcinoma": ["EFO_1001471"],
}

# GraphQL page size (OT allows up to 10 000 but 500 is safe and fast)
PAGE_SIZE = 500

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class OTDrugRow:
    """Represents one flattened row from knownDrugs API response."""

    cancer_type: str
    efo_id: str
    disease_name: str
    drug_id: str
    drug_name: str
    drug_type: str
    max_phase: int | None
    action_type: str
    mechanism_of_action: str
    target_id: str
    target_symbol: str
    target_name: str
    target_class: list[str]
    phase: int | None
    status: str
    nct_ids: list[str]
    urls: list[dict]
    moa_targets: list[dict]


# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------
KNOWN_DRUGS_QUERY = """
query KnownDrugs($efoId: String!, $size: Int!, $cursor: String) {
  disease(efoId: $efoId) {
    id
    name
    knownDrugs(size: $size, cursor: $cursor) {
      count
      cursor
      rows {
        drug {
          id
          name
          drugType
          maximumClinicalTrialPhase
          mechanismsOfAction {
            rows {
              actionType
              mechanismOfAction
              targets {
                id
                approvedSymbol
                approvedName
              }
            }
          }
        }
        disease {
          id
          name
        }
        phase
        status
        urls {
          url
          name
        }
        mechanismOfAction
        approvedName
        targetId
        targetClass
      }
    }
  }
}
"""

NCT_PATTERN = re.compile(r"(NCT\d+)", re.IGNORECASE)


def _extract_nct_ids(urls: list[dict]) -> list[str]:
    """Extract NCT IDs from ClinicalTrials.gov URLs."""
    ncts: list[str] = []
    for u in urls:
        href = u.get("url", "")
        matches = NCT_PATTERN.findall(href)
        ncts.extend(m.upper() for m in matches)
    return list(dict.fromkeys(ncts))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OpenTargetsClient:
    """Thin wrapper around the Open Targets Platform GraphQL API."""

    def __init__(self, url: str = OT_GRAPHQL_URL, timeout: int = 45):
        self.url = url
        self.timeout = timeout

    def _post(self, query: str, variables: dict) -> dict:
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:500]
            raise RuntimeError(
                f"HTTP {exc.code} from Open Targets API: {body}"
            ) from exc

        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data

    def fetch_known_drugs_page(
        self,
        efo_id: str,
        size: int = PAGE_SIZE,
        cursor: str | None = None,
    ) -> tuple[int, str | None, list[dict]]:
        """Fetch one page of knownDrugs.

        Returns:
            (total_count, next_cursor, rows)
        """
        variables: dict = {"efoId": efo_id, "size": size}
        if cursor:
            variables["cursor"] = cursor

        data = self._post(KNOWN_DRUGS_QUERY, variables)
        disease = data.get("data", {}).get("disease") or {}
        kd = disease.get("knownDrugs") or {}
        total = kd.get("count", 0)
        next_cursor = kd.get("cursor")
        rows = kd.get("rows") or []
        return total, next_cursor, rows

    def iter_known_drugs(
        self,
        efo_id: str,
        delay_s: float = 0.3,
    ) -> Iterator[dict]:
        """Iterate over all knownDrugs rows for a disease EFO ID, paginating automatically."""
        cursor: str | None = None
        fetched = 0
        page = 0

        while True:
            page += 1
            total, next_cursor, rows = self.fetch_known_drugs_page(
                efo_id, size=PAGE_SIZE, cursor=cursor
            )
            if page == 1:
                logger.info("EFO %s → %d total rows", efo_id, total)

            if not rows:
                break

            yield from rows
            fetched += len(rows)
            logger.debug("Page %d: fetched %d/%d", page, fetched, total)

            if next_cursor is None or fetched >= total:
                break

            cursor = next_cursor
            if delay_s > 0:
                time.sleep(delay_s)


# ---------------------------------------------------------------------------
# Flattening helper
# ---------------------------------------------------------------------------


def flatten_row(row: dict, cancer_type: str, efo_id: str) -> list[OTDrugRow]:
    """Flatten one API row into one or more OTDrugRow objects (one per target).

    Each drug×disease row is stored once per primary target (targetId), which
    is the combination that uniquely identifies a row in the API response.
    """
    drug = row.get("drug") or {}
    disease = row.get("disease") or {}
    moa_rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []

    nct_ids = _extract_nct_ids(row.get("urls") or [])

    return [
        OTDrugRow(
            cancer_type=cancer_type,
            efo_id=efo_id,
            disease_name=disease.get("name", ""),
            drug_id=drug.get("id", ""),
            drug_name=drug.get("name", ""),
            drug_type=drug.get("drugType", ""),
            max_phase=drug.get("maximumClinicalTrialPhase"),
            action_type=row.get("mechanismOfAction", ""),  # row-level MoA description
            mechanism_of_action=row.get("mechanismOfAction", ""),
            target_id=row.get("targetId", ""),
            target_symbol=_find_symbol(moa_rows, row.get("targetId", "")),
            target_name=row.get("approvedName", ""),
            target_class=row.get("targetClass") or [],
            phase=row.get("phase"),
            status=row.get("status", ""),
            nct_ids=nct_ids,
            urls=row.get("urls") or [],
            moa_targets=moa_rows,
        )
    ]


def _find_symbol(moa_rows: list[dict], target_id: str) -> str:
    """Find approvedSymbol for a given targetId within mechanismsOfAction rows."""
    for moa in moa_rows:
        for t in moa.get("targets") or []:
            if t.get("id") == target_id:
                return t.get("approvedSymbol", "")
    return ""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS open_targets_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cancer_type TEXT NOT NULL,
    efo_id TEXT NOT NULL,
    disease_name TEXT,
    drug_id TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    drug_type TEXT,
    max_phase INTEGER,
    action_type TEXT,
    mechanism_of_action TEXT,
    target_id TEXT,
    target_symbol TEXT,
    target_name TEXT,
    target_class TEXT,
    phase INTEGER,
    status TEXT,
    nct_ids TEXT,
    urls_json TEXT,
    moa_targets_json TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cancer_type, drug_id, target_id, phase, status)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_ot_cancer_type ON open_targets_data(cancer_type);",
    "CREATE INDEX IF NOT EXISTS idx_ot_drug_id ON open_targets_data(drug_id);",
    "CREATE INDEX IF NOT EXISTS idx_ot_target_id ON open_targets_data(target_id);",
    "CREATE INDEX IF NOT EXISTS idx_ot_phase ON open_targets_data(phase);",
    "CREATE INDEX IF NOT EXISTS idx_ot_status ON open_targets_data(status);",
]

UPSERT_SQL = """
INSERT INTO open_targets_data (
    cancer_type, efo_id, disease_name,
    drug_id, drug_name, drug_type, max_phase,
    action_type, mechanism_of_action,
    target_id, target_symbol, target_name, target_class,
    phase, status,
    nct_ids, urls_json, moa_targets_json,
    fetched_at
) VALUES (
    :cancer_type, :efo_id, :disease_name,
    :drug_id, :drug_name, :drug_type, :max_phase,
    :action_type, :mechanism_of_action,
    :target_id, :target_symbol, :target_name, :target_class,
    :phase, :status,
    :nct_ids, :urls_json, :moa_targets_json,
    CURRENT_TIMESTAMP
)
ON CONFLICT(cancer_type, drug_id, target_id, phase, status)
DO UPDATE SET
    efo_id = excluded.efo_id,
    disease_name = excluded.disease_name,
    drug_name = excluded.drug_name,
    drug_type = excluded.drug_type,
    max_phase = excluded.max_phase,
    action_type = excluded.action_type,
    mechanism_of_action = excluded.mechanism_of_action,
    target_symbol = excluded.target_symbol,
    target_name = excluded.target_name,
    target_class = excluded.target_class,
    nct_ids = excluded.nct_ids,
    urls_json = excluded.urls_json,
    moa_targets_json = excluded.moa_targets_json,
    fetched_at = CURRENT_TIMESTAMP;
"""


class OpenTargetsRepository:
    """Read/write open_targets_data in trials.db."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def ensure_table(self) -> None:
        """Create table and indexes if they do not exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_TABLE_SQL)
            for idx_sql in CREATE_INDEXES_SQL:
                conn.execute(idx_sql)
            conn.commit()
        logger.info("open_targets_data table ready.")

    def upsert_rows(self, rows: list[OTDrugRow]) -> int:
        """Upsert a batch of rows. Returns number inserted/updated."""
        if not rows:
            return 0

        records = [
            {
                "cancer_type": r.cancer_type,
                "efo_id": r.efo_id,
                "disease_name": r.disease_name,
                "drug_id": r.drug_id,
                "drug_name": r.drug_name,
                "drug_type": r.drug_type,
                "max_phase": r.max_phase,
                "action_type": r.action_type,
                "mechanism_of_action": r.mechanism_of_action,
                "target_id": r.target_id,
                "target_symbol": r.target_symbol,
                "target_name": r.target_name,
                "target_class": json.dumps(r.target_class),
                "phase": r.phase,
                "status": r.status,
                "nct_ids": json.dumps(r.nct_ids),
                "urls_json": json.dumps(r.urls),
                "moa_targets_json": json.dumps(r.moa_targets),
            }
            for r in rows
        ]

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(UPSERT_SQL, records)
            conn.commit()

        return len(records)

    def count_by_cancer_type(self) -> dict[str, int]:
        """Return row counts per cancer type."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT cancer_type, COUNT(*) FROM open_targets_data GROUP BY cancer_type ORDER BY COUNT(*) DESC"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_rows(
        self,
        cancer_type: str | None = None,
        phase: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query rows with optional filters."""
        clauses = []
        params: list = []
        if cancer_type:
            clauses.append("cancer_type = ?")
            params.append(cancer_type)
        if phase is not None:
            clauses.append("phase = ?")
            params.append(phase)
        if status:
            clauses.append("status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT cancer_type, efo_id, disease_name, drug_id, drug_name, drug_type,
                   max_phase, action_type, mechanism_of_action,
                   target_id, target_symbol, target_name, target_class,
                   phase, status, nct_ids, fetched_at
            FROM open_targets_data
            {where}
            ORDER BY cancer_type, phase DESC, drug_name
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
