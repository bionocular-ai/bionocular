import logging
import xml.etree.ElementTree as ET
from datetime import date

import requests

from .base import NewsArticleRaw, NewsSourceBase

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.onclive.com/sitemap-news.xml"
_SM_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"


class OncLiveScraper(NewsSourceBase):
    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def _fetch_sitemap_text(self) -> str:
        resp = requests.get(_SITEMAP_URL, timeout=self._timeout)
        resp.raise_for_status()
        return resp.text

    def fetch_articles(self, since: date) -> list[NewsArticleRaw]:
        try:
            xml_text = self._fetch_sitemap_text()
        except Exception as exc:
            logger.warning("OncLive sitemap fetch failed: %s", exc)
            return []

        root = ET.fromstring(xml_text)
        articles: list[NewsArticleRaw] = []

        for url_el in root.findall(f"{{{_SM_NS}}}url"):
            loc = url_el.findtext(f"{{{_SM_NS}}}loc") or ""
            news_el = url_el.find(f"{{{_NEWS_NS}}}news")
            if news_el is None:
                continue
            pub_str = news_el.findtext(f"{{{_NEWS_NS}}}publication_date") or ""
            title = news_el.findtext(f"{{{_NEWS_NS}}}title") or ""

            try:
                pub_date = date.fromisoformat(pub_str[:10])
            except ValueError:
                continue

            if pub_date < since:
                continue

            articles.append(
                NewsArticleRaw(
                    source="onclive",
                    title=title,
                    url=loc,
                    published_date=pub_date,
                    description="",
                    full_text=None,
                )
            )

        logger.info("OncLive: %d articles since %s", len(articles), since)
        return articles
