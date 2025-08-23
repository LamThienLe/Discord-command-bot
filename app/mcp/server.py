from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Set
import json
import sys
import inspect

try:
    # Optional: keep import for future true-MCP wiring, not required for stdio loop
    from mcp.server.fastmcp import FastMCP  # type: ignore
except Exception:  # pragma: no cover - optional
    FastMCP = None  # type: ignore

from ..google_oauth import get_user_credentials
from ..tools.google_calendar import GoogleCalendarClient
from ..services.context import fetch_context_for_query
from ..services.llm import call_ollama


mcp = FastMCP("whatsapp-bot-mcp") if FastMCP else None


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


async def search_docs(query: str, caller: str = "") -> Dict[str, Any]:
    _enforce_caller(caller, "search_docs")
    context_text, sources = await fetch_context_for_query(query)

    # Try LLM synthesis first
    tmpl = (
        "You are a concise command explainer.\n"
        "- Explain clearly, simple, in detail what the command/topic does.\n"
        "- Show syntax in a code block if applicable.\n"
        "- Give one minimal working example.\n"
        "- Keep it short and beginner-friendly.\n"
        "User question: {q}\n"
        "Context: {c}\n"
    )
    prompt = tmpl.format(q=query, c=(context_text or "")[:4000])
    llm_text = await call_ollama(prompt)
    text_norm = (llm_text or "").strip()
    use_fallback = (not text_norm) or ("ollama" in text_norm.lower())

    if use_fallback:
        # Best-effort extract: keep lines containing the query term and code-ish snippets
        lines = (context_text or "").splitlines()
        key = query.split()[0].lower() if query else ""
        picked: List[str] = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if key and key in s.lower():
                picked.append(s)
            elif s.startswith("$") or "```" in s or s.endswith(":"):
                picked.append(s)
            if len("\n".join(picked)) > 2000:
                break
        text_norm = ("\n".join(picked) or (context_text or ""))[:3500]

    # Ensure we don't exceed embed limits too much before client-side truncation
    text_norm = text_norm[:3800]
    return {"content": text_norm, "sources": _summarize_sources(sources or [])}

TOOLS: Dict[str, Any] = {
    "create_event": create_event,
    "search_docs": search_docs,
}


def _call_tool(name: str, arguments: Dict[str, Any]) -> Any:
    func = TOOLS.get(name)
    if func is None:
        raise RuntimeError(f"Unknown tool: {name}")
    if inspect.iscoroutinefunction(func):
        import asyncio
        return asyncio.run(func(**arguments))
    return func(**arguments)


def _dispatch(method: str, params: Dict[str, Any]) -> Any:
    if method == "initialize":
        # Minimal MCP handshake response
        return {"protocolVersion": "0.1", "capabilities": {}}
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = dict(params.get("arguments") or {})
        if not name:
            raise RuntimeError("Missing tool name")
        return _call_tool(name, arguments)
    if method == "tools/list":
        return {"tools": [{"name": k} for k in TOOLS.keys()]}
    raise RuntimeError(f"Unknown method: {method}")


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
            rid = req.get("id")
            method = str(req.get("method") or "")
            params = dict(req.get("params") or {})
            result = _dispatch(method, params)
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:  # pragma: no cover - best-effort server
            rid = None
            try:
                rid = req.get("id")  # type: ignore
            except Exception:
                pass
            resp = {"jsonrpc": "2.0", "id": rid, "error": str(e)}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()