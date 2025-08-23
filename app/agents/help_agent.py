from __future__ import annotations

from typing import List, Tuple
import re

from ..services.llm import call_ollama
from ..services.context import fetch_context_for_query


PROMPT_TEMPLATE = (
    "You are a helpful assistant that explains commands and tools.\n"
    "- Always explain what the command does.\n"
    "- Show syntax in a code block.\n"
    "- Give a working example.\n"
    "- Be concise and beginner-friendly.\n"
    "User question: {query}\n"
    "Context (from FireCrawl/docs if available): {context}\n"
)


def _post_format_llm_text(llm_text: str) -> str:
    normalized = llm_text.strip()
    lower_text = normalized.lower()
    has_explanation = "explanation" in lower_text
    has_syntax = "syntax" in lower_text or "```" in normalized
    has_example = "example" in lower_text or "```" in normalized

    parts = []
    if not has_explanation:
        parts.append("Explanation:\n" + normalized)
    else:
        parts.append(normalized)
    if not has_syntax:
        parts.append("Syntax:\n" "```\n" "<fill based on command>\n" "```")
    if not has_example:
        parts.append("Example:\n" "```\n" "<example>\n" "```")
    return "\n\n".join(parts)


async def answer_help_query(query: str) -> Tuple[str, List[str]]:
    context_text, source_urls = await fetch_context_for_query(query)
    prompt = PROMPT_TEMPLATE.format(query=query, context=context_text or "")
    llm_text = await call_ollama(prompt)
    content = _post_format_llm_text(llm_text)
    return content, source_urls


