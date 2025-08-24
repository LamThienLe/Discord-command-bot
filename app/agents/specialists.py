from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Set
import re

from ..utils.timeparse import parse_times_and_summary, contains_time
from ..services.mcp_client import get_mcp_client, NotUsingMCPError


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
        super().__init__(name="personal", allowed_tools={"create_event", "propose_slots", "list_today"})
        self._logger = logging.getLogger(__name__)

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:
        user_id: int = int(ctx["user_id"])  # required
        user_tz: str = str(ctx.get("user_tz") or "Asia/Ho_Chi_Minh")

        text_l = input.lower().strip()

        # 1) List today's agenda
        if (
            "list today" in text_l
            or "today's schedule" in text_l
            or "today schedule" in text_l
            or text_l in {"today", "today?"}
        ):
            payload = {"user_id": user_id}
            if _env_bool("DRY_RUN", False):
                return f"DRY_RUN list_today {json.dumps(payload)}"
            try:
                return await self._invoke_allowed("list_today", payload)
            except NotUsingMCPError:
                return "MCP disabled. Set USE_MCP=true and run the MCP server."
            except Exception as e:
                return f"Failed to list today: {e}"

        # 2) Propose free slots
        if (
            "slot" in text_l
            or "availability" in text_l
            or "free time" in text_l
            or "find time" in text_l
            or "propose" in text_l
        ):
            def _minutes_from_text(t: str) -> int:
                m = re.search(r"(\d{1,3})\s*(m|min|minutes?)", t.lower())
                if m:
                    try:
                        return max(5, int(m.group(1)))
                    except Exception:
                        pass
                h = re.search(r"(\d{1,2})\s*(h|hours?)", t.lower())
                if h:
                    try:
                        return max(5, int(h.group(1)) * 60)
                    except Exception:
                        pass
                return 30

            def _count_from_text(t: str) -> int:
                c = re.search(r"(\d)\s*(slots?)", t.lower())
                if c:
                    try:
                        return max(1, int(c.group(1)))
                    except Exception:
                        pass
                return 3

            minutes = _minutes_from_text(input)
            count = _count_from_text(input)
            payload = {"user_id": user_id, "minutes": minutes, "count": count}

            if _env_bool("DRY_RUN", False):
                return f"DRY_RUN propose_slots {json.dumps(payload)}"
            try:
                return await self._invoke_allowed("propose_slots", payload)
            except NotUsingMCPError:
                return "MCP disabled. Set USE_MCP=true and run the MCP server."
            except Exception as e:
                return f"Failed to propose slots: {e}"

        # 3) Scheduling flow (create event)
        if not contains_time(input):
            return "What should I do? Try 'schedule X at Y', 'propose slots', or 'list today'."

        start, end, summary = parse_times_and_summary(input, user_tz)
        if start is None or end is None:
            return "I couldn’t parse a time. Try: 'tomorrow 3pm for 45m Team sync'"

        # Prepare payload and log it regardless of DRY_RUN so we can observe real requests
        payload = {"user_id": user_id, "summary": summary, "start_iso": _to_iso(start), "end_iso": _to_iso(end)}
        try:
            # Include JSON directly in the message so default formatter prints it
            self._logger.info(f"tool_request create_event {json.dumps(payload)}")
        except Exception:
            pass

        if _env_bool("DRY_RUN", False):
            return f"DRY_RUN create_event {json.dumps(payload)}"

        try:
            link = await self._invoke_allowed("create_event", payload)
            return f"Event created: {link}"
        except NotUsingMCPError:
            return "MCP disabled. Set USE_MCP=true and run the MCP server."
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


