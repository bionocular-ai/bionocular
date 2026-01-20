#!/usr/bin/env python3
"""Build SQLite database from JSON files for efficient querying.

This script reads all JSON files containing abstracts and publications,
and creates a SQLite database that can be queried efficiently without
loading all data into memory.
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    # Remove existing database if it exists
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

    # Create clinical trials tables (for dashboard functionality)
    # These tables are created by the repository, but we ensure they exist here
    # api_discovery, extraction_provenance, clinical_trials_cache will be created
    # by the repository when it initializes, but we can pre-create them here

    # Enable JSON1 extension for querying JSON fields
    conn.execute("PRAGMA foreign_keys=ON")

    logger.info(f"Created database schema at {db_path}")
    return conn


def insert_abstract(conn: sqlite3.Connection, abstract: dict) -> None:
    """Insert an abstract/publication into the database.

    Args:
        conn: Database connection
        abstract: Abstract/publication dictionary
    """
    # Generate ID from abstract_id or publication_id
    abstract_id = abstract.get("abstract_id")
    publication_id = abstract.get("publication_id")

    # Use abstract_id or publication_id as primary key
    if abstract_id:
        record_id = f"abstract_{abstract_id}"
    elif publication_id:
        record_id = f"publication_{publication_id}"
    else:
        # Fallback: use a hash or generate ID
        import hashlib

        content = json.dumps(abstract, sort_keys=True)
        record_id = f"record_{hashlib.md5(content.encode()).hexdigest()[:16]}"

    # Convert lists/dicts to JSON strings
    errors_json = json.dumps(abstract.get("errors", []))
    warnings_json = json.dumps(abstract.get("warnings", []))
    arm_results_json = json.dumps(abstract.get("arm_results", {}))

    conn.execute(
        """
        INSERT OR REPLACE INTO abstracts (
            id, abstract_id, publication_id, file, source_url,
            total_arms, total_attributes_extracted, overall_confidence,
            processing_time_ms, errors, warnings, arm_results, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
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
        ),
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
    nct_numbers = trial.get("nct_numbers", []) or trial.get("nct_number", "")

    # Handle both list and string NCT numbers
    if isinstance(nct_numbers, list):
        nct_number = nct_numbers[0] if nct_numbers else trial_id
    else:
        nct_number = nct_numbers or trial_id

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
) -> None:
    """Build SQLite database from JSON files.

    Args:
        db_path: Path where SQLite database should be created
        json_file_paths: Optional list of JSON file paths. If None, uses default paths.
        include_web_scrape: Whether to include web-scraped trials from web_scrape.json
    """
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

                # Insert into database
                for item in filtered_items:
                    insert_abstract(conn, item)
                    total_inserted += 1

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
            web_scrape_path = (
                Path(__file__).parent.parent / "data" / "deployed" / "web_scrape.json"
            )
            if web_scrape_path.exists():
                logger.info(
                    f"Loading web-scraped trials from {web_scrape_path.name}..."
                )
                try:
                    with open(web_scrape_path, encoding="utf-8") as f:
                        web_scrape_data = json.load(f)

                    trials = web_scrape_data.get("trials", [])
                    logger.info(f"Found {len(trials)} web-scraped trials")

                    for trial in trials:
                        try:
                            # Transform trial to abstract format
                            abstract = transform_web_scrape_to_abstract(
                                trial, source_file="web_scrape.json"
                            )

                            # Insert into database
                            insert_abstract(conn, abstract)
                            total_inserted += 1

                        except Exception as e:
                            trial_id = trial.get("trial_id", "unknown")
                            logger.error(
                                f"Error processing web-scraped trial {trial_id}: {e}"
                            )
                            continue

                    logger.info(f"Inserted {len(trials)} web-scraped trials")

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
        stats_file = (
            Path(__file__).parent.parent
            / "data"
            / "deployed"
            / "disease_landscape_stats.json"
        )
        if stats_file.exists():
            logger.info(f"Loading disease landscape stats from {stats_file.name}...")
            try:
                with open(stats_file, encoding="utf-8") as f:
                    stats_data = json.load(f)

                # Clear existing stats
                conn.execute("DELETE FROM disease_landscape_stats")

                # Insert stats for each cancer type
                stats_inserted = 0
                for cancer_type, stats in stats_data.items():
                    status_json = json.dumps(stats.get("status", {}))
                    phase_json = json.dumps(stats.get("phase", {}))
                    funder_type_json = json.dumps(stats.get("funder_type", {}))
                    extracted_count = stats.get("extracted_count", 0)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO disease_landscape_stats
                        (cancer_type, status_json, phase_json, funder_type_json, extracted_count, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            cancer_type,
                            status_json,
                            phase_json,
                            funder_type_json,
                            extracted_count,
                        ),
                    )
                    stats_inserted += 1

                conn.commit()
                logger.info(f"Loaded {stats_inserted} cancer type stats into database")
            except Exception as e:
                logger.error(f"Error loading disease landscape stats: {e}")
        else:
            logger.warning(f"Disease landscape stats file not found: {stats_file}")

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
        default=Path(__file__).parent.parent / "trials.db",
        help="Path to SQLite database file (default: trials.db in project root)",
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
