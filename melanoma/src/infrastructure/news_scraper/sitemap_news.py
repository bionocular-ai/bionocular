import logging
import xml.etree.ElementTree as ET
from datetime import date

import requests

from .base import NewsArticleRaw, NewsSourceBase

logger = logging.getLogger(__name__)

_SM_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"


class NewsSitemapScraper(NewsSourceBase):
    """Reads a Google News sitemap (sitemap-news.xml).

    OncLive, CancerNetwork and TargetedOnc share one publisher platform and
    publish the same sitemap shape, covering roughly the last week of articles.
    """

    def __init__(self, source: str, sitemap_url: str, timeout: int = 30) -> None:
        self._source = source
        self._sitemap_url = sitemap_url
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0 (compatible; Bionocular/1.0)"

    def _fetch_sitemap_text(self) -> str:
        resp = self._session.get(self._sitemap_url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.text

    def fetch_articles(self, since: date) -> list[NewsArticleRaw]:
        root = ET.fromstring(self._fetch_sitemap_text())
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
                    source=self._source,
                    title=title,
                    url=loc,
                    published_date=pub_date,
                    description="",
                    full_text=None,
                )
            )

        logger.info("%s: %d articles since %s", self._source, len(articles), since)
        return articles
