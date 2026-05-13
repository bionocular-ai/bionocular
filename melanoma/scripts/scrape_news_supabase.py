#!/usr/bin/env python3
"""Daily sync of oncology news articles into Supabase news_feed table.

Scrapes OncLive (RSS), CancerNetwork (RSS), TargetedOnc (Google News RSS),
and BioSpace (HTML), filters to 8 skin cancer types, extracts NCT IDs and
efficacy/safety data via Gemini, and upserts into `news_feed`.

Usage:
    poetry run python3 scripts/scrape_news_supabase.py [--since YYYY-MM-DD]
                                                        [--days N]
                                                        [--source SOURCE]
                                                        [--dry-run]
"""

import argparse
import logging
import os
import pathlib
import sys
from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import Client, create_client

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.infrastructure.news_scraper.base import NewsArticleRaw
from src.infrastructure.news_scraper.biospace import BioSpaceScraper
from src.infrastructure.news_scraper.cancer_filter import assign_cancer_types
from src.infrastructure.news_scraper.cancernetwork import CancerNetworkScraper
from src.infrastructure.news_scraper.gemini_extractor import (
    GeminiNewsExtractor,
    NewsExtractionResult,
)
from src.infrastructure.news_scraper.onclive import OncLiveScraper
from src.infrastructure.news_scraper.targetedonc import TargetedOncScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scrape_news_supabase")

_ALL_SOURCES = ["onclive", "cancernetwork", "targetedonc", "biospace"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=str, default=None, dest="since_str",
                        help="Backfill from date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--days", type=int, default=2,
                        help="Lookback window in days (default: 2)")
    parser.add_argument("--source", type=str, choices=_ALL_SOURCES, default=None,
                        help="Run a single source only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and extract but do not write to Supabase")
    return parser.parse_args()


def compute_since(days: int, since_str: Optional[str]) -> date:
    if since_str:
        try:
            return datetime.strptime(since_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid --since date %r, expected YYYY-MM-DD", since_str)
            sys.exit(2)
    return date.today() - timedelta(days=days)


def fetch_full_text(url: str, session: requests.Session) -> Optional[str]:
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:50000]
    except Exception as exc:
        logger.warning("Full-text fetch failed for %s: %s", url, exc)
        return None


def build_upsert_row(
    article: NewsArticleRaw,
    cancer_types: list[str],
    extraction: Optional[NewsExtractionResult],
) -> dict[str, Any]:
    return {
        "source": article.source,
        "title": article.title,
        "url": article.url,
        "date": article.published_date.isoformat(),
        "cancer_type": cancer_types,
        "nct_ids": extraction.nct_ids if extraction else [],
        "has_efficacy": extraction.has_efficacy if extraction else False,
        "efficacy_data": extraction.efficacy_data if extraction else {},
        "has_safety": extraction.has_safety if extraction else False,
        "safety_data": extraction.safety_data if extraction else {},
        "extracted_at": datetime.utcnow().isoformat() if extraction else None,
    }


def main() -> int:
    args = parse_args()
    load_dotenv()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")

    if not args.dry_run and (not supabase_url or not supabase_key):
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set (or use --dry-run)")
        return 2
    if not args.dry_run and not gemini_key:
        logger.error("GEMINI_API_KEY must be set (or use --dry-run)")
        return 2

    supabase: Optional[Client] = (
        create_client(supabase_url, supabase_key)
        if (supabase_url and supabase_key and not args.dry_run)
        else None
    )
    extractor: Optional[GeminiNewsExtractor] = (
        GeminiNewsExtractor(api_key=gemini_key) if gemini_key else None
    )

    since = compute_since(days=args.days, since_str=args.since_str)
    logger.info("Scrape starting: since=%s, source=%s, dry_run=%s",
                since, args.source or "all", args.dry_run)

    active_sources = [args.source] if args.source else _ALL_SOURCES
    all_articles: list[NewsArticleRaw] = []

    scrapers = {
        "onclive": OncLiveScraper(),
        "cancernetwork": CancerNetworkScraper(),
        "targetedonc": TargetedOncScraper(),
        "biospace": BioSpaceScraper(),
    }
    for source_name in active_sources:
        try:
            articles = scrapers[source_name].fetch_articles(since)
            all_articles.extend(articles)
        except Exception as exc:
            logger.error("Scraper %s failed: %s", source_name, exc)

    logger.info("Collected %d raw articles across all sources", len(all_articles))

    matched: list[tuple[NewsArticleRaw, list[str]]] = []
    for article in all_articles:
        cancer_types = assign_cancer_types(article)
        if cancer_types:
            matched.append((article, cancer_types))

    logger.info("%d articles matched skin cancer types", len(matched))

    http_session = requests.Session()
    http_session.headers["User-Agent"] = "Mozilla/5.0 (compatible; Bionocular/1.0)"

    counts = {"upserted": 0, "skipped": 0, "error": 0}
    total = len(matched)

    for idx, (article, cancer_types) in enumerate(matched, start=1):
        full_text = fetch_full_text(article.url, http_session)

        extraction: Optional[NewsExtractionResult] = None
        if extractor and full_text:
            extraction = extractor.extract(article.title, full_text, cancer_types)
        elif full_text is None:
            logger.warning("Skipping extraction for %s — full text unavailable", article.url)

        row = build_upsert_row(article, cancer_types, extraction)

        if args.dry_run:
            logger.info(
                "[dry-run] %s | cancer_types=%s | nct_ids=%s | efficacy=%s | safety=%s",
                row["url"], row["cancer_type"], row["nct_ids"],
                row["has_efficacy"], row["has_safety"],
            )
            counts["upserted"] += 1
        else:
            assert supabase is not None
            try:
                supabase.table("news_feed").upsert(row, on_conflict="url").execute()
                counts["upserted"] += 1
            except Exception as exc:
                logger.error("Upsert failed for %s: %s", article.url, exc)
                counts["error"] += 1

        if idx % 10 == 0 or idx == total:
            logger.info("Progress: %d/%d | %s", idx, total, counts)

    logger.info("Scrape complete: %s", counts)
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
