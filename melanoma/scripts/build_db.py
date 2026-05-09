#!/usr/bin/env python3
"""Build SQLite database from JSON files for efficient querying.

This script reads all JSON files containing abstracts and publications,
and creates a SQLite database that can be queried efficiently without
loading all data into memory.
"""

import gzip
import json
import logging
import sqlite3
from pathlib import Path

from src.app.json_trials_service import JSONTrialsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database with schema for trials data.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database connection
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        logger.info(f"Removing existing database at {db_path}")
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
    conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed

    # Create abstracts table
    conn.execute(
        """
        CREATE TABLE abstracts (
            id TEXT PRIMARY KEY,
            abstract_id TEXT,
            publication_id TEXT,
            file TEXT,
            source_url TEXT,  -- For web-scraped trials
            total_arms INTEGER,
            total_attributes_extracted INTEGER,
            overall_confidence REAL,
            processing_time_ms INTEGER,
            errors TEXT,  -- JSON array
            warnings TEXT,  -- JSON array
            arm_results TEXT,  -- JSON object
            created_at TEXT,
            UNIQUE(abstract_id, publication_id)
        )
    """
    )

    # Create indexes for efficient filtering
    conn.execute("CREATE INDEX idx_abstract_id ON abstracts(abstract_id)")
    conn.execute("CREATE INDEX idx_publication_id ON abstracts(publication_id)")
    conn.execute("CREATE INDEX idx_file ON abstracts(file)")

    # Create disease_landscape_stats table for pre-computed statistics
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS disease_landscape_stats (
            cancer_type TEXT PRIMARY KEY,
            status_json TEXT NOT NULL,  -- JSON object with status counts
            phase_json TEXT NOT NULL,   -- JSON object with phase counts
            funder_type_json TEXT NOT NULL,  -- JSON object with funder type counts
            extracted_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create live_ticker table (articles + efficacy/safety results per category)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS live_ticker (
            category TEXT PRIMARY KEY,
            articles_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create clinical trials tables (for dashboard functionality)
    # Pre-create so build can optionally load from clinical_trials_api_seed.json
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_trials_cache (
            nct_number TEXT PRIMARY KEY,
            api_response_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_updated_at ON clinical_trials_cache(updated_at)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_discovery (
            nct_number TEXT NOT NULL,
            cancer_type_tag TEXT NOT NULL,
            current_status TEXT NOT NULL,
            discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (nct_number, cancer_type_tag)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cancer_type_tag ON api_discovery(cancer_type_tag)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_discovery_nct_number ON api_discovery(nct_number)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trial_categorization (
            nct_number TEXT PRIMARY KEY,
            cancer_type TEXT,
            modality TEXT,
            treatment_name TEXT,
            biomarker TEXT,
            stage TEXT,
            line_of_therapy TEXT,
            previous_treatment_criteria TEXT,
            extraction_status TEXT,
            error_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Add cancer_type to existing DBs created before this column existed (before creating index on it)
    try:
        conn.execute("ALTER TABLE trial_categorization ADD COLUMN cancer_type TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_categorization_modality ON trial_categorization(modality)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_categorization_cancer_type ON trial_categorization(cancer_type)"
    )

    # Enable JSON1 extension for querying JSON fields
    conn.execute("PRAGMA foreign_keys=ON")

    logger.info(f"Created database schema at {db_path}")
    return conn


def _abstract_to_row(abstract: dict) -> tuple:
    """Convert abstract dict to row tuple for abstracts table. Used by insert_abstract and batch inserts."""
    import hashlib

    abstract_id = abstract.get("abstract_id")
    publication_id = abstract.get("publication_id")
    if abstract_id:
        record_id = f"abstract_{abstract_id}"
    elif publication_id:
        record_id = f"publication_{publication_id}"
    else:
        content = json.dumps(abstract, sort_keys=True)
        record_id = f"record_{hashlib.md5(content.encode()).hexdigest()[:16]}"

    errors_json = json.dumps(abstract.get("errors", []))
    warnings_json = json.dumps(abstract.get("warnings", []))
    arm_results_json = json.dumps(abstract.get("arm_results", {}))
    return (
        record_id,
        abstract_id,
        publication_id,
        abstract.get("file"),
        abstract.get("source_url"),
        len(abstract.get("arm_results", {})),
        abstract.get("total_attributes_extracted", 0),
        abstract.get("overall_confidence", 0.0),
        abstract.get("processing_time_ms"),
        errors_json,
        warnings_json,
        arm_results_json,
        abstract.get("created_at"),
    )


def insert_abstract(conn: sqlite3.Connection, abstract: dict) -> None:
    """Insert an abstract/publication into the database.

    Args:
        conn: Database connection
        abstract: Abstract/publication dictionary
    """
    row = _abstract_to_row(abstract)
    conn.execute(
        """
        INSERT OR REPLACE INTO abstracts (
            id, abstract_id, publication_id, file, source_url,
            total_arms, total_attributes_extracted, overall_confidence,
            processing_time_ms, errors, warnings, arm_results, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        row,
    )


def transform_web_scrape_to_abstract(trial: dict, source_file: str) -> dict:
    """Transform web scrape trial format to abstract format.

    Args:
        trial: Trial data from web_scrape.json
        source_file: Source file name

    Returns:
        Transformed abstract dictionary
    """
    from datetime import datetime

    trial_id = trial.get("trial_id", "")

    # Get arm results
    arm_results = trial.get("arm_results", {})

    # Count total attributes across all arms
    total_attributes = 0
    for arm_data in arm_results.values():
        total_attributes += arm_data.get("total_attributes", 0)

    # Transform to abstract format
    abstract = {
        "abstract_id": f"webscrape_{trial_id}",  # Prefix to distinguish from conference abstracts
        "file": source_file,
        "total_arms": trial.get("total_arms", len(arm_results)),
        "total_attributes_extracted": total_attributes,
        "overall_confidence": 1.0,  # Web-scraped data has high confidence
        "processing_time_ms": 0,
        "errors": [],
        "warnings": [],
        "arm_results": arm_results,
        "created_at": trial.get("web_scrape_timestamp", datetime.now().isoformat()),
    }

    return abstract


def build_database(
    db_path: Path,
    json_file_paths: list[Path] | None = None,
    include_web_scrape: bool = True,
    deployed_dir: Path | None = None,
) -> None:
    """Build SQLite database from JSON files.

    Args:
        db_path: Path where SQLite database should be created
        json_file_paths: Optional list of JSON file paths. If None, uses default paths.
        include_web_scrape: Whether to include web-scraped trials from web_scrape.json
        deployed_dir: Optional path to data/deployed. If None, uses repo data/deployed. Used for tests.
    """
    if deployed_dir is None:
        deployed_dir = Path(__file__).parent.parent / "data" / "deployed"
    logger.info("Starting database build process...")

    # Create database
    conn = create_database(db_path)

    try:
        # Load data from JSON files
        if json_file_paths is None:
            # Use JSONTrialsService to get default paths
            service = JSONTrialsService()
            json_file_paths = service.json_file_paths

        logger.info(f"Loading data from {len(json_file_paths)} JSON file(s)...")

        total_inserted = 0
        for json_file_path in json_file_paths:
            if not json_file_path.exists():
                logger.warning(f"JSON file not found, skipping: {json_file_path}")
                continue

            try:
                logger.info(f"Processing {json_file_path.name}...")
                with open(json_file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Extract abstracts and publications
                abstracts = data.get("abstracts", [])
                publications = data.get("publications", [])
                all_items = abstracts + publications

                # Filter out items with no treatment arms
                filtered_items = [
                    item
                    for item in all_items
                    if "No treatment arms identified" not in item.get("errors", [])
                ]

                # Batch insert abstracts (faster than per-row execute)
                abstract_sql = """
                    INSERT OR REPLACE INTO abstracts (
                        id, abstract_id, publication_id, file, source_url,
                        total_arms, total_attributes_extracted, overall_confidence,
                        processing_time_ms, errors, warnings, arm_results, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                batch_size = 2000
                cursor = conn.cursor()
                for i in range(0, len(filtered_items), batch_size):
                    chunk = filtered_items[i : i + batch_size]
                    cursor.executemany(
                        abstract_sql, [_abstract_to_row(item) for item in chunk]
                    )
                total_inserted += len(filtered_items)

                logger.info(
                    f"Inserted {len(filtered_items)} items from {json_file_path.name} "
                    f"({len(abstracts)} abstracts, {len(publications)} publications)"
                )

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {json_file_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing {json_file_path}: {e}")
                continue

        # Load web_scrape.json if it exists and include_web_scrape is True
        if include_web_scrape:
            web_scrape_path = deployed_dir / "web_scrape.json"
            if web_scrape_path.exists():
                logger.info(
                    f"Loading web-scraped trials from {web_scrape_path.name}..."
                )
                try:
                    with open(web_scrape_path, encoding="utf-8") as f:
                        web_scrape_data = json.load(f)

                    trials = web_scrape_data.get("trials", [])
                    logger.info(f"Found {len(trials)} web-scraped trials")

                    web_abstracts = []
                    for trial in trials:
                        try:
                            abstract = transform_web_scrape_to_abstract(
                                trial, source_file="web_scrape.json"
                            )
                            web_abstracts.append(abstract)
                        except Exception as e:
                            trial_id = trial.get("trial_id", "unknown")
                            logger.error(
                                f"Error processing web-scraped trial {trial_id}: {e}"
                            )
                    if web_abstracts:
                        abstract_sql = """
                            INSERT OR REPLACE INTO abstracts (
                                id, abstract_id, publication_id, file, source_url,
                                total_arms, total_attributes_extracted, overall_confidence,
                                processing_time_ms, errors, warnings, arm_results, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        batch_size = 2000
                        cursor = conn.cursor()
                        for i in range(0, len(web_abstracts), batch_size):
                            chunk = web_abstracts[i : i + batch_size]
                            cursor.executemany(
                                abstract_sql, [_abstract_to_row(a) for a in chunk]
                            )
                        total_inserted += len(web_abstracts)
                    logger.info(f"Inserted {len(web_abstracts)} web-scraped trials")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in {web_scrape_path}: {e}")
                except Exception as e:
                    logger.error(f"Error processing {web_scrape_path}: {e}")
            else:
                logger.info("No web_scrape.json found, skipping web-scraped trials")

        # Commit all changes
        conn.commit()
        logger.info(f"Database build complete! Inserted {total_inserted} records.")

        # Print statistics
        cursor = conn.execute("SELECT COUNT(*) FROM abstracts")
        count = cursor.fetchone()[0]
        logger.info(f"Total records in database: {count}")

        cursor = conn.execute(
            "SELECT COUNT(*) FROM abstracts WHERE abstract_id IS NOT NULL"
        )
        abstract_count = cursor.fetchone()[0]
        logger.info(f"Abstracts: {abstract_count}")

        cursor = conn.execute(
            "SELECT COUNT(*) FROM abstracts WHERE publication_id IS NOT NULL"
        )
        publication_count = cursor.fetchone()[0]
        logger.info(f"Publications: {publication_count}")

        # Load disease_landscape_stats.json if it exists
        stats_file = deployed_dir / "disease_landscape_stats.json"
        if stats_file.exists():
            logger.info(f"Loading disease landscape stats from {stats_file.name}...")
            try:
                with open(stats_file, encoding="utf-8") as f:
                    stats_data = json.load(f)

                # Clear existing stats
                conn.execute("DELETE FROM disease_landscape_stats")

                # Batch insert stats
                stats_rows = [
                    (
                        cancer_type,
                        json.dumps(stats.get("status", {})),
                        json.dumps(stats.get("phase", {})),
                        json.dumps(stats.get("funder_type", {})),
                        stats.get("extracted_count", 0),
                    )
                    for cancer_type, stats in stats_data.items()
                ]
                if stats_rows:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO disease_landscape_stats
                        (cancer_type, status_json, phase_json, funder_type_json, extracted_count, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        stats_rows,
                    )
                    conn.commit()
                logger.info(f"Loaded {len(stats_rows)} cancer type stats into database")
            except Exception as e:
                logger.error(f"Error loading disease landscape stats: {e}")
        else:
            logger.warning(f"Disease landscape stats file not found: {stats_file}")

        # Load live_ticker.json if it exists
        ticker_file = deployed_dir / "live_ticker.json"
        if ticker_file.exists():
            logger.info(f"Loading live ticker from {ticker_file.name}...")
            try:
                with open(ticker_file, encoding="utf-8") as f:
                    ticker_data = json.load(f)
                conn.execute("DELETE FROM live_ticker")
                ticker_rows = []
                for cat, payload in ticker_data.items():
                    if not isinstance(payload, dict):
                        continue
                    articles = payload.get("articles", [])
                    results = payload.get("results", [])
                    ticker_rows.append((cat, json.dumps(articles), json.dumps(results)))
                if ticker_rows:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO live_ticker
                        (category, articles_json, results_json, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        ticker_rows,
                    )
                conn.commit()
                logger.info(f"Loaded {len(ticker_rows)} categories into live_ticker")
            except Exception as e:
                logger.error(f"Error loading live ticker: {e}")
        else:
            logger.warning(f"Live ticker file not found: {ticker_file}")

        # Load clinical trials API seed (for production: bake API data into image)
        seed_gz = deployed_dir / "clinical_trials_api_seed.json.gz"
        seed_json = deployed_dir / "clinical_trials_api_seed.json"
        seed_file = seed_gz if seed_gz.exists() else seed_json
        if seed_file.exists():
            logger.info(f"Loading clinical trials API seed from {seed_file.name}...")
            try:
                open_fn = gzip.open if seed_file.suffix == ".gz" else open
                mode = "rt" if seed_file.suffix == ".gz" else "r"
                with open_fn(seed_file, mode, encoding="utf-8") as f:
                    seed_data = json.load(f)
                cache_list = seed_data.get("clinical_trials_cache", [])
                discovery_list = seed_data.get("api_discovery", [])
                if cache_list or discovery_list:
                    conn.execute("DELETE FROM clinical_trials_cache")
                    conn.execute("DELETE FROM api_discovery")
                    cursor = conn.cursor()
                    batch_size = 3000
                    cache_sql = """
                        INSERT OR REPLACE INTO clinical_trials_cache
                        (nct_number, api_response_json, created_at, updated_at, last_accessed_at)
                        VALUES (?, ?, ?, ?, ?)
                    """
                    for i in range(0, len(cache_list), batch_size):
                        batch = [
                            (
                                row.get("nct_number"),
                                row.get("api_response_json", "{}"),
                                row.get("created_at"),
                                row.get("updated_at"),
                                row.get("last_accessed_at"),
                            )
                            for row in cache_list[i : i + batch_size]
                        ]
                        cursor.executemany(cache_sql, batch)
                    discovery_sql = """
                        INSERT OR REPLACE INTO api_discovery
                        (nct_number, cancer_type_tag, current_status, discovery_date, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    for i in range(0, len(discovery_list), batch_size):
                        batch = [
                            (
                                row.get("nct_number"),
                                row.get("cancer_type_tag"),
                                row.get("current_status", ""),
                                row.get("discovery_date"),
                                row.get("is_active", 0),
                                row.get("updated_at"),
                            )
                            for row in discovery_list[i : i + batch_size]
                        ]
                        cursor.executemany(discovery_sql, batch)
                    conn.commit()
                    logger.info(
                        f"Loaded {len(cache_list)} cache rows, {len(discovery_list)} discovery rows"
                    )
                else:
                    logger.info("Seed file has no cache or discovery data, skipping")
            except Exception as e:
                logger.error(f"Error loading clinical trials API seed: {e}")
        else:
            logger.info(
                "No clinical_trials_api_seed.json or .json.gz (optional). "
                "Use sync_dashboard_data.py at runtime or export_clinical_trial_api_to_json.py + gzip + commit seed to populate."
            )

        # Load trial_categorization seed (Modality, Target, Trial_Name) if present
        cat_seed_file = deployed_dir / "trial_categorization_seed.json"
        if cat_seed_file.exists():
            logger.info(
                f"Loading trial_categorization seed from {cat_seed_file.name}..."
            )
            try:
                with open(cat_seed_file, encoding="utf-8") as f:
                    cat_list = json.load(f)
                if cat_list:
                    conn.execute("DELETE FROM trial_categorization")
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(trial_categorization)")
                    table_cols = [r[1] for r in cursor.fetchall()]

                    # Insert using the intersection of:
                    #   (a) columns that exist in the destination table
                    #   (b) keys present in the exported JSON seed
                    sample = cat_list[0] if cat_list else {}
                    insert_cols = [c for c in table_cols if c in sample]
                    if "nct_number" not in insert_cols:
                        raise ValueError(
                            "trial_categorization_seed.json is missing nct_number"
                        )

                    placeholders = ",".join("?" * len(insert_cols))
                    insert_sql = (
                        f"INSERT OR REPLACE INTO trial_categorization "
                        f"({','.join(insert_cols)}) VALUES ({placeholders})"
                    )

                    cat_rows = [
                        tuple(row.get(c) for c in insert_cols) for row in cat_list
                    ]
                    cursor.executemany(insert_sql, cat_rows)
                    conn.commit()
                    # Backfill cancer_type from api_discovery for any row missing it (all tags per NCT, comma-separated)
                    conn.execute(
                        """
                        UPDATE trial_categorization
                        SET cancer_type = (
                            SELECT group_concat(ad.cancer_type_tag, ', ')
                            FROM (
                                SELECT cancer_type_tag
                                FROM api_discovery ad
                                WHERE ad.nct_number = trial_categorization.nct_number
                                ORDER BY ad.cancer_type_tag
                            ) ad
                        )
                        WHERE EXISTS (
                            SELECT 1 FROM api_discovery ad
                            WHERE ad.nct_number = trial_categorization.nct_number
                        )
                        """
                    )
                    conn.commit()
                    logger.info(
                        f"Loaded {len(cat_list)} rows into trial_categorization"
                    )
            except Exception as e:
                logger.error(f"Error loading trial_categorization seed: {e}")

    finally:
        conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build SQLite database from JSON files"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "trials_db" / "trials.db",
        help="Path to SQLite database (default: data/trials_db/trials.db, same as app)",
    )
    parser.add_argument(
        "--json-files",
        type=str,
        nargs="+",
        help="Optional list of JSON file paths (default: uses JSONTrialsService defaults)",
    )

    args = parser.parse_args()

    json_file_paths = None
    if args.json_files:
        json_file_paths = [Path(p) for p in args.json_files]

    build_database(args.db_path, json_file_paths)
    logger.info(f"Database created successfully at {args.db_path}")


if __name__ == "__main__":
    main()
