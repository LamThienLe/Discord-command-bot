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
    "personal": {"create_event", "propose_slots", "list_today"},
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

def _format_time_local(d: dt.datetime, tz: dt.tzinfo) -> str:
    return d.astimezone(tz).strftime("%H:%M")


async def list_today(user_id: int, caller: str = "") -> str:
    _enforce_caller(caller, "list_today")
    creds = get_user_credentials(user_id)
    if not creds:
        raise RuntimeError("Missing Google credentials. Use /connect_google.")
    client = GoogleCalendarClient(creds)
    user_tz_name = client.get_user_timezone() or "Asia/Ho_Chi_Minh"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz_name)
    except Exception:
        tz = dt.timezone.utc

    # Query events from local midnight to end of day
    now_local = dt.datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local.replace(hour=23, minute=59, second=59, microsecond=0)

    service = client.service
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_local.astimezone(dt.timezone.utc).isoformat(),
            timeMax=end_local.astimezone(dt.timezone.utc).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = events_result.get("items", []) if isinstance(events_result, dict) else []

    if not items:
        return "No events today."

    lines: List[str] = []
    for ev in items:
        if not isinstance(ev, dict):
            continue
        summary = str(ev.get("summary") or "(no title)")
        start_raw = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end_raw = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        try:
            if isinstance(start_raw, str) and len(start_raw) > 10:
                st = dt.datetime.fromisoformat(start_raw)
                en = dt.datetime.fromisoformat(str(end_raw)) if isinstance(end_raw, str) else st
                line = f"{_format_time_local(st, tz)}–{_format_time_local(en, tz)}  {summary}"
            else:
                # All-day
                line = f"All day  {summary}"
        except Exception:
            line = summary
        lines.append(line)
        if len(lines) >= 20:
            break
    return "\n".join(lines)


async def propose_slots(user_id: int, minutes: int = 30, count: int = 3, caller: str = "") -> str:
    _enforce_caller(caller, "propose_slots")
    if minutes <= 0:
        minutes = 30
    if count <= 0:
        count = 3
    creds = get_user_credentials(user_id)
    if not creds:
        raise RuntimeError("Missing Google credentials. Use /connect_google.")
    client = GoogleCalendarClient(creds)
    user_tz_name = client.get_user_timezone() or "Asia/Ho_Chi_Minh"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz_name)
    except Exception:
        tz = dt.timezone.utc

    service = client.service
    now_utc = dt.datetime.now(dt.timezone.utc)
    horizon_utc = now_utc + dt.timedelta(days=3)
    body = {
        "timeMin": now_utc.isoformat(),
        "timeMax": horizon_utc.isoformat(),
        "timeZone": user_tz_name,
        "items": [{"id": "primary"}],
    }
    fb = service.freebusy().query(body=body).execute()
    busy = []
    try:
        busy_list = ((fb.get("calendars") or {}).get("primary") or {}).get("busy") or []
        for b in busy_list:
            s = b.get("start")
            e = b.get("end")
            if isinstance(s, str) and isinstance(e, str):
                bs = dt.datetime.fromisoformat(s)
                be = dt.datetime.fromisoformat(e)
                if bs.tzinfo is None:
                    bs = bs.replace(tzinfo=dt.timezone.utc)
                if be.tzinfo is None:
                    be = be.replace(tzinfo=dt.timezone.utc)
                busy.append((bs.astimezone(dt.timezone.utc), be.astimezone(dt.timezone.utc)))
    except Exception:
        busy = []

    # Generate candidate slots within local work hours 09:00–18:00
    slots: List[str] = []
    step = dt.timedelta(minutes=minutes)
    cur_local = dt.datetime.now(tz)

    def _day_bounds(dlocal: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
        start = dlocal.replace(hour=9, minute=0, second=0, microsecond=0)
        end = dlocal.replace(hour=18, minute=0, second=0, microsecond=0)
        return start, end

    cur_local = max(cur_local, _day_bounds(cur_local)[0])
    while len(slots) < count and cur_local.astimezone(dt.timezone.utc) < horizon_utc:
        day_start, day_end = _day_bounds(cur_local)
        if cur_local >= day_end:
            # move to next day start
            cur_local = (day_start + dt.timedelta(days=1)).replace(hour=9, minute=0)
            continue
        candidate_start_utc = cur_local.astimezone(dt.timezone.utc)
        candidate_end_utc = (cur_local + step).astimezone(dt.timezone.utc)
        if candidate_end_utc > day_end.astimezone(dt.timezone.utc):
            # jump to next day
            cur_local = (day_start + dt.timedelta(days=1)).replace(hour=9, minute=0)
            continue

        conflict = False
        for bs, be in busy:
            if not (candidate_end_utc <= bs or candidate_start_utc >= be):
                # overlap
                conflict = True
                # jump to end of busy block in local tz
                cur_local = be.astimezone(tz)
                break
        if conflict:
            continue
        # accept slot
        slots.append(f"{cur_local.strftime('%Y-%m-%d')} {cur_local.strftime('%H:%M')}–{(cur_local + step).strftime('%H:%M')} ({user_tz_name})")
        cur_local = cur_local + step

    if not slots:
        return "No free slots in the next 3 days during work hours."
    return "\n".join(slots[:count])


TOOLS: Dict[str, Any] = {
    "create_event": create_event,
    "search_docs": search_docs,
    "list_today": list_today,
    "propose_slots": propose_slots,
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