from __future__ import annotations

import asyncio
from typing import Dict

import httpx

from .config import get_settings


PROMPT_TEMPLATE = (
    "You are a helpful assistant that explains commands and tools.\n"
    "- Always explain what the command does.\n"
    "- Show syntax in a code block.\n"
    "- Give a working example.\n"
    "- Be concise and beginner-friendly.\n"
    "User question: {query}\n"
    "Context (from FireCrawl/docs if available): {context}\n"
)


async def call_ollama(prompt: str) -> str:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model

    payload: Dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # You can tune options like temperature here
        # "options": {"temperature": 0.2}
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                return (
                    "I couldn't reach the local LLM (Ollama). "
                    f"Status: {resp.status_code}. Please ensure Ollama is running."
                )
            data = resp.json()
            # Shape: { "model": "...", "created_at": "...", "response": "...", ... }
            text = data.get("response") or ""
            return str(text).strip() if isinstance(text, str) else ""
    except Exception:
        return (
            "Local LLM (Ollama) is unavailable. Install Ollama and run: "
            f"ollama pull {model} && ollama run {model}"
        )


async def generate_structured_answer(query: str, context: str) -> str:
    prompt = PROMPT_TEMPLATE.format(query=query, context=context or "")
    llm_text = await call_ollama(prompt)

    # Ensure it contains the required sections; if not, do a light post-format.
    normalized = llm_text.strip()

    lower_text = normalized.lower()
    has_explanation = "explanation" in lower_text
    has_syntax = "syntax" in lower_text or "```" in normalized
    has_example = "example" in lower_text or "```" in normalized

    formatted_parts = []

    if not has_explanation:
        formatted_parts.append("Explanation:\n" + normalized)
    else:
        formatted_parts.append(normalized)

    # Only add placeholders for missing sections to avoid duplicates
    if not has_syntax:
        formatted_parts.append(
            "Syntax:\n" "```\n" "<fill based on command>\n" "```"
        )
    if not has_example:
        formatted_parts.append(
            "Example:\n" "```\n" "<example>\n" "```"
        )

    return "\n\n".join(formatted_parts)


