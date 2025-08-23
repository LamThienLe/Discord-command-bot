from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Set

from .calendar_agent import parse_times_and_summary, contains_time
from ..services.mcp_client import get_mcp_client, NotUsingMCPError
from ..tools.google_calendar import GoogleCalendarClient
from ..google_oauth import get_user_credentials


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_iso(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).isoformat()


@dataclass
class Specialist:
    name: str
    allowed_tools: Set[str] = field(default_factory=set)

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    async def _invoke_allowed(self, tool: str, params: Dict[str, Any]) -> Any:
        if tool not in self.allowed_tools:
            raise PermissionError(f"{self.name} cannot call tool '{tool}'")
        client = get_mcp_client()
        call_params = dict(params)
        call_params.setdefault("caller", self.name)
        return await client.invoke_tool(tool, call_params)


class PersonalSpecialist(Specialist):
    def __init__(self) -> None:
        super().__init__(name="personal", allowed_tools={"create_event"})

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:
        user_id: int = int(ctx["user_id"])  # required
        user_tz: str = str(ctx.get("user_tz") or "Asia/Ho_Chi_Minh")

        if not contains_time(input):
            return "What time should I schedule it? (e.g., 10:30 or 3pm)"

        start, end, summary = await parse_times_and_summary(input, user_tz)
        if start is None or end is None:
            return "I couldn’t parse a time. Try: 'tomorrow 3pm for 45m Team sync'"

        if _env_bool("DRY_RUN", False):
            payload = {"user_id": user_id, "summary": summary, "start_iso": _to_iso(start), "end_iso": _to_iso(end)}
            return f"DRY_RUN create_event {json.dumps(payload)}"

        try:
            link = await self._invoke_allowed(
                "create_event",
                {"user_id": user_id, "summary": summary, "start_iso": _to_iso(start), "end_iso": _to_iso(end)},
            )
            return f"Event created: {link}"
        except NotUsingMCPError:
            creds = get_user_credentials(user_id)
            if not creds:
                return "Missing Google credentials. Use /connect_google."
            link = GoogleCalendarClient(creds).create_event(summary=summary, start=start, end=end)
            return f"Event created: {link}"
        except Exception as e:
            return f"Failed to create event: {e}"


class CommandSpecialist(Specialist):
    def __init__(self) -> None:
        super().__init__(name="command", allowed_tools={"search_docs"})

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:
        if _env_bool("DRY_RUN", False):
            return f"DRY_RUN search_docs {json.dumps({'query': input})}"
        try:
            data = await self._invoke_allowed("search_docs", {"query": input})
            content = str(data.get("content") or "")
            sources = [str(s) for s in (data.get("sources") or [])][:3]
            tail = ("\n\nSources: " + ", ".join(sources)) if sources else ""
            return content + tail
        except NotUsingMCPError:
            # Fallback handled in bot via help_agent, we just signal empty
            return ""
        except Exception as e:
            return f"Failed to search docs: {e}"


