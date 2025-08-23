from __future__ import annotations

from typing import Dict

import httpx

from ..config import get_settings


async def call_ollama(prompt: str) -> str:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model

    payload: Dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
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
            text = data.get("response") or ""
            return str(text).strip() if isinstance(text, str) else ""
    except Exception:
        return (
            "Local LLM (Ollama) is unavailable. Install Ollama and run: "
            f"ollama pull {model} && ollama run {model}"
        )


