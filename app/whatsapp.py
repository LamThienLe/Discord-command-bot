from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .config import get_settings
from .cache import get_cached_answer
from .firecrawl import fetch_context_for_query
from .agent import generate_structured_answer


logger = logging.getLogger(__name__)


async def extract_text_and_sender(incoming: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Parse WhatsApp webhook payload (Cloud API)."""
    try:
        entry = incoming.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])
        msg = messages[0]
        sender = msg.get("from")
        text = None
        if msg.get("type") == "text":
            text = (msg.get("text") or {}).get("body")
        elif msg.get("type") == "interactive":
            interactive = msg.get("interactive") or {}
            # Support button replies or list selections
            text = (
                (interactive.get("button_reply") or {}).get("title")
                or (interactive.get("list_reply") or {}).get("title")
            )
        return text, sender
    except Exception:
        return None, None


async def send_whatsapp_text(to: str, body: str) -> None:
    settings = get_settings()
    if not settings.whatsapp_token or not settings.whatsapp_phone_id:
        logger.error("Missing WhatsApp credentials.")
        return

    url = (
        f"https://graph.facebook.com/{settings.graph_api_version}/"
        f"{settings.whatsapp_phone_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 300:
            logger.error("WhatsApp send failed: %s %s", resp.status_code, resp.text)


async def handle_incoming(incoming: Dict[str, Any]) -> Dict[str, Any]:
    text, sender = await extract_text_and_sender(incoming)
    if not text or not sender:
        return {"status": "ignored"}

    logger.info("Incoming message from %s: %s", sender, text)

    cached = get_cached_answer(text)
    if cached:
        await send_whatsapp_text(sender, cached)
        return {"status": "ok", "source": "cache"}

    context = await fetch_context_for_query(text)
    answer = await generate_structured_answer(text, context)
    await send_whatsapp_text(sender, answer)
    return {"status": "ok", "source": "llm"}


