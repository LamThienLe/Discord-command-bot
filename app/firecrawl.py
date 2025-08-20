from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .config import get_settings


logger = logging.getLogger(__name__)


class FirecrawlClient:
    """Async client for FireCrawl API.

    The API commonly exposes endpoints like:
      - POST /v1/scrape
      - POST /v1/crawl

    We keep it minimal and resilient: try a search-oriented scrape by building
    a docs/tutorials URL list, then attempt to extract readable text.
    """

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        settings = get_settings()
        self.base_url = settings.firecrawl_base_url.rstrip("/")
        self.api_key = settings.firecrawl_api_key
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def scrape_urls(self, urls: List[str]) -> tuple[str, List[str]]:
        """Scrape multiple URLs and concatenate cleaned text contents.

        Returns a tuple of (combined_text, successful_source_urls).
        Falls back gracefully on errors and returns best-effort text.
        """
        if not self.api_key:
            return "", []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        texts: List[str] = []
        successful_sources: List[str] = []
        for url in urls:
            try:
                resp = await self._client.post(
                    f"{self.base_url}/v2/scrape",
                    headers=headers,
                    json={"url": url, "formats": ["markdown"]},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # v2 shape: { success: true, data: { markdown: "...", html: "..." } }
                    data_obj = data.get("data") if isinstance(data, dict) else None
                    text = None
                    if isinstance(data_obj, dict):
                        text = data_obj.get("markdown") or data_obj.get("html")
                    # Fallback to older shapes if present
                    if not text and isinstance(data, dict):
                        text = data.get("content") or (data.get("data") or {}).get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
                        successful_sources.append(url)
                else:
                    if resp.status_code == 401:
                        logger.warning(
                            "Firecrawl returned 401 Unauthorized for %s. Check FIRECRAWL_API_KEY and account status.",
                            url,
                        )
                    # ignore and continue on non-200s
            except Exception:
                # Ignore per-URL errors
                continue

        return "\n\n".join(texts), successful_sources

    async def fetch_docs_for_query(self, query_text: str) -> tuple[str, List[str]]:
        """Heuristically generate likely documentation URLs and scrape them.

        Returns (combined_text, source_urls).
        """
        keyword = query_text.strip().split()[0].lower() if query_text.strip() else ""
        candidate_urls = [
            f"https://man7.org/linux/man-pages/man1/{keyword}.1.html",
            f"https://www.gnu.org/software/{keyword}/manual/",
            f"https://tldr.inbrowser.app/pages/common/{keyword}.md",
            f"https://explainshell.com/explain?cmd={keyword}",
        ]
        return await self.scrape_urls(candidate_urls)


async def fetch_context_for_query(query_text: str) -> tuple[str, List[str]]:
    client = FirecrawlClient()
    try:
        return await client.fetch_docs_for_query(query_text)
    finally:
        await client.aclose()


