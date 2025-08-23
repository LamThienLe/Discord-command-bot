from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Set

from mcp.server.fastmcp import FastMCP

from ..google_oauth import get_user_credentials
from ..tools.google_calendar import GoogleCalendarClient
from ..services.context import fetch_context_for_query


mcp = FastMCP("whatsapp-bot-mcp")


def _iso_to_dt(value: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(value)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _summarize_sources(sources: List[str]) -> List[str]:
    return [s for s in sources if isinstance(s, str)][:10]


# Simple server-side allowlist: caller -> allowed tools
_ALLOWLIST: Dict[str, Set[str]] = {
    "personal": {"create_event"},
    "command": {"search_docs"},
}


def _enforce_caller(caller: str, tool: str) -> None:
    if not caller:
        raise RuntimeError("Missing 'caller' for tool invocation")
    allowed = _ALLOWLIST.get(str(caller), set())
    if tool not in allowed:
        raise RuntimeError(f"Caller '{caller}' is not allowed to use tool '{tool}'")


@mcp.tool()
def create_event(user_id: int, summary: str, start_iso: str, end_iso: str, caller: str = "") -> str:
    _enforce_caller(caller, "create_event")
    creds = get_user_credentials(user_id)
    if not creds:
        raise RuntimeError("Missing Google credentials. Use /connect_google.")
    start = _iso_to_dt(start_iso)
    end = _iso_to_dt(end_iso)
    client = GoogleCalendarClient(creds)
    link = client.create_event(summary=summary, start=start, end=end)
    return str(link)


@mcp.tool()
async def search_docs(query: str, caller: str = "") -> Dict[str, Any]:
    _enforce_caller(caller, "search_docs")
    content, sources = await fetch_context_for_query(query)
    return {"content": str(content or ""), "sources": _summarize_sources(sources or [])}


if __name__ == "__main__":
    # Start an MCP-compliant stdio server
    mcp.run_stdio()