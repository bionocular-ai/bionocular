from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class NewsArticleRaw:
    source: str
    title: str
    url: str
    published_date: date
    description: str
    full_text: str | None


class NewsSourceBase(ABC):
    @abstractmethod
    def fetch_articles(self, since: date) -> list[NewsArticleRaw]: ...
