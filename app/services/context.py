from __future__ import annotations

from typing import List, Tuple

from ..tools.firecrawl_client import FirecrawlClient


async def fetch_context_for_query(query_text: str) -> Tuple[str, List[str]]:
    client = FirecrawlClient()
    try:
        keyword = query_text.strip().split()[0].lower() if query_text.strip() else ""
        candidate_urls = [
            f"https://man7.org/linux/man-pages/man1/{keyword}.1.html",
            f"https://www.gnu.org/software/{keyword}/manual/",
            f"https://tldr.inbrowser.app/pages/common/{keyword}.md",
            f"https://explainshell.com/explain?cmd={keyword}",
        ]
        return await client.scrape_urls(candidate_urls)
    finally:
        await client.aclose()


