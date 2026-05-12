import logging
from datetime import date, datetime

import feedparser
import requests

from .base import NewsArticleRaw, NewsSourceBase

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.onclive.com/rss"


def _parse_feed_date(entry: object) -> date | None:
    parsed = getattr(entry, "published_parsed", None)
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6]).date()
    except Exception:
        return None


class OncLiveScraper(NewsSourceBase):
    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def _fetch_feed_text(self) -> str:
        resp = requests.get(_RSS_URL, timeout=self._timeout)
        resp.raise_for_status()
        return resp.text

    def fetch_articles(self, since: date) -> list[NewsArticleRaw]:
        try:
            xml = self._fetch_feed_text()
        except Exception as exc:
            logger.warning("OncLive RSS fetch failed: %s", exc)
            return []

        feed = feedparser.parse(xml)
        articles: list[NewsArticleRaw] = []
        for entry in feed.entries:
            pub_date = _parse_feed_date(entry)
            if pub_date is None or pub_date < since:
                continue
            articles.append(
                NewsArticleRaw(
                    source="onclive",
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    published_date=pub_date,
                    description=entry.get("summary", ""),
                    full_text=None,
                )
            )

        logger.info("OncLive: %d articles since %s", len(articles), since)
        return articles
