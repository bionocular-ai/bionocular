import logging
from datetime import date, datetime

import feedparser
import requests
from googlenewsdecoder import gnewsdecoder

from .base import NewsArticleRaw, NewsSourceBase

logger = logging.getLogger(__name__)

_SEARCH_KEYWORDS: list[str] = [
    "cutaneous+melanoma",
    "uveal+melanoma",
    "acral+melanoma",
    "mucosal+melanoma",
    "merkel+cell+carcinoma",
    "basal+cell+carcinoma",
    "cutaneous+squamous+cell+carcinoma",
]

_GNEWS_URL = (
    "https://news.google.com/rss/search"
    "?q=site:biospace.com+{keyword}&hl=en-US&gl=US&ceid=US:en"
)


def _parse_feed_date(entry: object) -> date | None:
    parsed = getattr(entry, "published_parsed", None)
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6]).date()
    except Exception:
        return None


class BioSpaceScraper(NewsSourceBase):
    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0 (compatible; Bionocular/1.0)"

    def _fetch_gnews_text(self, keyword: str) -> str:
        url = _GNEWS_URL.format(keyword=keyword)
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.text

    def _resolve_url(self, google_url: str) -> str:
        result = gnewsdecoder(google_url, interval=1)
        if result.get("status"):
            return result["decoded_url"]
        logger.warning("gnewsdecoder returned no URL for %s: %s", google_url, result)
        return google_url

    def fetch_articles(self, since: date) -> list[NewsArticleRaw]:
        seen_urls: set[str] = set()
        articles: list[NewsArticleRaw] = []

        for keyword in _SEARCH_KEYWORDS:
            try:
                xml = self._fetch_gnews_text(keyword)
            except Exception as exc:
                logger.warning("BioSpace Google News fetch failed for %s: %s", keyword, exc)
                continue

            feed = feedparser.parse(xml)
            for entry in feed.entries:
                pub_date = _parse_feed_date(entry)
                if pub_date is None or pub_date < since:
                    continue

                google_url: str = entry.get("link", "")
                try:
                    resolved_url = self._resolve_url(google_url)
                except Exception as exc:
                    logger.warning("URL decode failed for %s: %s", google_url, exc)
                    resolved_url = google_url

                if resolved_url in seen_urls:
                    continue
                seen_urls.add(resolved_url)

                articles.append(
                    NewsArticleRaw(
                        source="biospace",
                        title=entry.get("title", ""),
                        url=resolved_url,
                        published_date=pub_date,
                        description=entry.get("summary", ""),
                        full_text=None,
                    )
                )

        logger.info("BioSpace: %d articles since %s", len(articles), since)
        return articles
