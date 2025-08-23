from __future__ import annotations

import logging
from typing import List

import httpx

from ..config import get_settings


logger = logging.getLogger(__name__)


class FirecrawlClient:
    """Async client for FireCrawl API."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        settings = get_settings()
        self.base_url = settings.firecrawl_base_url.rstrip("/")
        self.api_key = settings.firecrawl_api_key
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def scrape_urls(self, urls: List[str]) -> tuple[str, List[str]]:
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
                    data_obj = data.get("data") if isinstance(data, dict) else None
                    text = None
                    if isinstance(data_obj, dict):
                        text = data_obj.get("markdown") or data_obj.get("html")
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
            except Exception:
                continue

        return "\n\n".join(texts), successful_sources


