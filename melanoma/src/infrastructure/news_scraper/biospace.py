import logging
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from .base import NewsArticleRaw, NewsSourceBase

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.biospace.com"
_PAGE_URL = f"{_BASE_URL}/cancer"
_DATE_FORMATS = ["%B %d, %Y", "%b %d, %Y"]

_SKIN_CANCER_PRE_FILTER = re.compile(
    r"\b(melanoma|squamous cell carcinoma|cscc|basal cell carcinoma|bcc|"
    r"merkel cell|mcc)\b",
    re.IGNORECASE,
)


def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class BioSpaceScraper(NewsSourceBase):
    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0 (compatible; Bionocular/1.0)"

    def _fetch_page_html(self) -> str:
        resp = self._session.get(_PAGE_URL, timeout=self._timeout)
        resp.raise_for_status()
        return resp.text

    def fetch_articles(self, since: date) -> list[NewsArticleRaw]:
        try:
            html = self._fetch_page_html()
        except Exception as exc:
            logger.warning("BioSpace fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(html, "lxml")
        articles: list[NewsArticleRaw] = []

        for card in soup.find_all("article"):
            title_tag = card.find("a", href=True)
            if title_tag is None:
                continue
            title = title_tag.get_text(strip=True)
            href: str = title_tag["href"]

            # Pre-filter: skip articles with no skin cancer keyword in title or summary
            if not _SKIN_CANCER_PRE_FILTER.search(title):
                summary_tag = card.find("p")
                summary_text = summary_tag.get_text(strip=True) if summary_tag else ""
                if not _SKIN_CANCER_PRE_FILTER.search(summary_text):
                    continue

            date_tag = card.find(["span", "time"])
            if date_tag is None:
                continue
            pub_date = _parse_date(date_tag.get_text(strip=True))
            if pub_date is None or pub_date < since:
                continue

            url = href if href.startswith("http") else f"{_BASE_URL}{href}"

            summary_tag = card.find("p")
            description = summary_tag.get_text(strip=True) if summary_tag else ""

            articles.append(
                NewsArticleRaw(
                    source="biospace",
                    title=title,
                    url=url,
                    published_date=pub_date,
                    description=description,
                    full_text=None,
                )
            )

        logger.info("BioSpace: %d articles since %s", len(articles), since)
        return articles
