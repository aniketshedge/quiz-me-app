from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote

import requests

from app.config import Settings


@dataclass
class WikiCandidate:
    title: str
    page_id: int
    url: str
    summary: str
    image_url: Optional[str]
    image_caption: Optional[str]
    is_disambiguation: bool


@dataclass
class WikiArticle:
    title: str
    page_id: int
    url: str
    summary: str
    image_url: Optional[str]
    image_caption: Optional[str]
    extract: str


class WikipediaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lang = settings.wiki_lang
        self.api_base = f"https://{self.lang}.wikipedia.org"

    def _search(self, topic: str, limit: int = 5) -> list[dict]:
        endpoint = f"{self.api_base}/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": topic,
            "srlimit": limit,
            "format": "json",
        }
        response = requests.get(endpoint, params=params, timeout=8)
        response.raise_for_status()
        return response.json().get("query", {}).get("search", [])

    def _summary_for_title(self, title: str) -> dict:
        safe_title = quote(title.replace(" ", "_"), safe="")
        endpoint = f"{self.api_base}/api/rest_v1/page/summary/{safe_title}"
        response = requests.get(endpoint, timeout=8)
        if response.status_code >= 400:
            return {}
        return response.json()

    def _extract_for_page_id(self, page_id: int) -> str:
        endpoint = f"{self.api_base}/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts",
            "pageids": page_id,
            "explaintext": 1,
            "exsectionformat": "plain",
            "format": "json",
        }
        response = requests.get(endpoint, params=params, timeout=8)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        extract = pages.get(str(page_id), {}).get("extract", "")
        return extract or ""

    def resolve_topic(self, topic: str) -> List[WikiCandidate]:
        hits = self._search(topic=topic, limit=5)
        candidates: list[WikiCandidate] = []
        for hit in hits:
            title = hit.get("title", "")
            page_id = int(hit.get("pageid"))
            summary_data = self._summary_for_title(title)
            url = (
                summary_data.get("content_urls", {})
                .get("desktop", {})
                .get("page", f"{self.api_base}/wiki/{quote(title.replace(' ', '_'))}")
            )
            summary = summary_data.get("extract") or hit.get("snippet", "")
            image_url = summary_data.get("thumbnail", {}).get("source")
            image_caption = summary_data.get("description")
            is_disambiguation = summary_data.get("type") == "disambiguation"
            candidates.append(
                WikiCandidate(
                    title=title,
                    page_id=page_id,
                    url=url,
                    summary=(summary or "No summary available.").strip(),
                    image_url=image_url,
                    image_caption=image_caption,
                    is_disambiguation=is_disambiguation,
                )
            )
        return candidates

    def get_article(self, page_id: int) -> WikiArticle:
        endpoint = f"{self.api_base}/w/api.php"
        params = {
            "action": "query",
            "prop": "info",
            "inprop": "url",
            "pageids": page_id,
            "format": "json",
        }
        response = requests.get(endpoint, params=params, timeout=8)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        page = pages.get(str(page_id), {})
        if not page or "title" not in page:
            raise ValueError("Could not locate Wikipedia page for selected page_id")

        title = page["title"]
        canonical_url = page.get("fullurl", f"{self.api_base}/wiki/{quote(title.replace(' ', '_'))}")
        summary_data = self._summary_for_title(title)
        summary = (summary_data.get("extract") or "").strip()
        image_url = summary_data.get("thumbnail", {}).get("source")
        image_caption = summary_data.get("description")

        extract = self._extract_for_page_id(page_id)
        if not extract:
            extract = summary

        if len(extract) > self.settings.wiki_max_chars:
            extract = extract[: self.settings.wiki_max_chars]

        return WikiArticle(
            title=title,
            page_id=page_id,
            url=canonical_url,
            summary=summary,
            image_url=image_url,
            image_caption=image_caption,
            extract=extract,
        )
