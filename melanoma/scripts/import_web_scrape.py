#!/usr/bin/env python3
"""Import web-scraped trial data into SQLite database.

This script reads the web_scrape.json file and imports the trial data
into the trials.db database, making it available for the frontend analytics.
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def transform_web_scrape_to_abstract(trial: dict, source_file: str) -> dict:
    """Transform web scrape trial format to abstract format.
    
    Args:
        trial: Trial data from web_scrape.json
        source_file: Source file name
    
    Returns:
        Transformed abstract dictionary
    """
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


def insert_web_scrape_trial(conn: sqlite3.Connection, abstract: dict) -> None:
    """Insert a web-scraped trial into the database.
    
    Args:
        conn: Database connection
        abstract: Abstract dictionary (transformed from trial)
    """
    abstract_id = abstract.get("abstract_id")
    
    # Generate record ID
    record_id = f"webscrape_{abstract_id}"
    
    # Convert lists/dicts to JSON strings
    errors_json = json.dumps(abstract.get("errors", []))
    warnings_json = json.dumps(abstract.get("warnings", []))
    arm_results_json = json.dumps(abstract.get("arm_results", {}))
    
    try:
        conn.execute("""
            INSERT OR REPLACE INTO abstracts (
                id, abstract_id, publication_id, file,
                total_arms, total_attributes_extracted, overall_confidence,
                processing_time_ms, errors, warnings, arm_results, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_id,
            abstract_id,
            None,  # Web scrape trials are not publications
            abstract.get("file"),
            abstract.get("total_arms", 0),
            abstract.get("total_attributes_extracted", 0),
            abstract.get("overall_confidence", 1.0),
            abstract.get("processing_time_ms", 0),
            errors_json,
            warnings_json,
            arm_results_json,
            abstract.get("created_at"),
        ))
        logger.debug(f"Inserted trial: {abstract_id}")
    except sqlite3.IntegrityError as e:
        logger.warning(f"Skipping duplicate trial {abstract_id}: {e}")
    except Exception as e:
        logger.error(f"Error inserting trial {abstract_id}: {e}")
        raise


def import_web_scrape_data(db_path: Path, web_scrape_path: Path) -> None:
    """Import web scrape data into SQLite database.
    
    Args:
        db_path: Path to SQLite database file
        web_scrape_path: Path to web_scrape.json file
    """
    logger.info("Starting web scrape data import...")
    
    # Check if database exists
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.error("Please run 'poetry run python scripts/build_db.py' first to create the database")
        return
    
    # Check if web_scrape.json exists
    if not web_scrape_path.exists():
        logger.error(f"Web scrape file not found at {web_scrape_path}")
        return
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    
    try:
        # Load web_scrape.json
        logger.info(f"Loading web scrape data from {web_scrape_path.name}...")
        with open(web_scrape_path, encoding="utf-8") as f:
            data = json.load(f)
        
        trials = data.get("trials", [])
        logger.info(f"Found {len(trials)} trials in web scrape data")
        
        # Transform and insert each trial
        total_inserted = 0
        for trial in trials:
            try:
                # Transform trial to abstract format
                abstract = transform_web_scrape_to_abstract(
                    trial,
                    source_file="web_scrape.json"
                )
                
                # Insert into database
                insert_web_scrape_trial(conn, abstract)
                total_inserted += 1
                
            except Exception as e:
                trial_id = trial.get("trial_id", "unknown")
                logger.error(f"Error processing trial {trial_id}: {e}")
                continue
        
        # Commit changes
        conn.commit()
        logger.info(f"Successfully imported {total_inserted} web-scraped trials")
        
        # Print statistics
        cursor = conn.execute(
            "SELECT COUNT(*) FROM abstracts WHERE abstract_id LIKE 'webscrape_%'"
        )
        webscrape_count = cursor.fetchone()[0]
        logger.info(f"Total web-scraped trials in database: {webscrape_count}")
        
        cursor = conn.execute("SELECT COUNT(*) FROM abstracts")
        total_count = cursor.fetchone()[0]
        logger.info(f"Total records in database: {total_count}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {web_scrape_path}: {e}")
    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise
    finally:
        conn.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import web-scraped trial data into SQLite database"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "trials_db" / "trials.db",
        help="Path to SQLite database file (default: data/trials_db/trials.db)",
    )
    parser.add_argument(
        "--web-scrape-path",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "deployed" / "web_scrape.json",
        help="Path to web_scrape.json file (default: data/deployed/web_scrape.json)",
    )
    
    args = parser.parse_args()
    
    import_web_scrape_data(args.db_path, args.web_scrape_path)
    logger.info("Import complete!")


if __name__ == "__main__":
    main()

