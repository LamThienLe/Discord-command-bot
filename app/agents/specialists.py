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
            return "I couldn't parse a time. Try: 'tomorrow 3pm for 45m Team sync'"

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


class NLPSpecialist(Specialist):
    """Specialist for natural language processing and understanding."""
    
    def __init__(self) -> None:
        super().__init__(name="nlp", allowed_tools={"search_docs", "create_event", "propose_slots", "list_today"})
        self._logger = logging.getLogger(__name__)

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:
        """Process natural language input and route to appropriate specialist."""
        user_id: int = int(ctx.get("user_id", 0))
        user_tz: str = str(ctx.get("user_tz") or "Asia/Ho_Chi_Minh")
        
        text_l = input.lower().strip()
        
        # Intent classification
        intent = self._classify_intent(text_l)
        
        if intent == "calendar":
            # Route to PersonalSpecialist for calendar operations
            personal = PersonalSpecialist()
            return await personal.act(input, ctx)
        elif intent == "help":
            # Route to CommandSpecialist for help/documentation
            command = CommandSpecialist()
            return await command.act(input, ctx)
        elif intent == "conversation":
            # Handle general conversation
            return await self._handle_conversation(input, ctx)
        else:
            # Default to help if intent is unclear
            command = CommandSpecialist()
            return await command.act(input, ctx)

    def _classify_intent(self, text: str) -> str:
        """Classify the intent of the user input."""
        # Calendar-related keywords
        calendar_keywords = {
            "schedule", "meeting", "appointment", "event", "calendar", "book", "reserve",
            "tomorrow", "today", "next week", "this week", "morning", "afternoon", "evening",
            "am", "pm", "o'clock", "hour", "minute", "duration", "time", "date",
            "busy", "free", "available", "slot", "agenda", "plan"
        }
        
        # Help/documentation keywords
        help_keywords = {
            "help", "how to", "what is", "explain", "guide", "tutorial", "documentation",
            "command", "tool", "usage", "example", "syntax", "parameter", "option"
        }
        
        # Conversation keywords
        conversation_keywords = {
            "hello", "hi", "hey", "thanks", "thank you", "goodbye", "bye", "see you",
            "how are you", "what's up", "nice to meet you", "pleasure"
        }
        
        words = set(text.split())
        
        calendar_score = len(words.intersection(calendar_keywords))
        help_score = len(words.intersection(help_keywords))
        conversation_score = len(words.intersection(conversation_keywords))
        
        if calendar_score > help_score and calendar_score > conversation_score:
            return "calendar"
        elif help_score > conversation_score:
            return "help"
        elif conversation_score > 0:
            return "conversation"
        else:
            return "help"  # Default to help

    async def _handle_conversation(self, input: str, ctx: Dict[str, Any]) -> str:
        """Handle general conversation."""
        text_l = input.lower().strip()
        
        # Greetings
        if any(word in text_l for word in ["hello", "hi", "hey"]):
            return "Hello! I'm your AI assistant. I can help you with:\n" \
                   "• Scheduling events and meetings\n" \
                   "• Getting help with commands and tools\n" \
                   "• Checking your calendar\n\n" \
                   "What would you like to do?"
        
        # Gratitude
        elif any(word in text_l for word in ["thanks", "thank you", "appreciate"]):
            return "You're welcome! I'm here to help. Is there anything else you need?"
        
        # Farewell
        elif any(word in text_l for word in ["goodbye", "bye", "see you", "later"]):
            return "Goodbye! Feel free to reach out if you need help later."
        
        # How are you
        elif "how are you" in text_l:
            return "I'm doing well, thank you for asking! I'm ready to help you with any tasks."
        
        # Default conversation response
        else:
            return "I'm here to help! You can ask me to:\n" \
                   "• Schedule events (e.g., 'schedule team meeting tomorrow 3pm')\n" \
                   "• Get help with commands (e.g., 'help git commit')\n" \
                   "• Check your calendar (e.g., 'show today's schedule')\n\n" \
                   "What would you like to do?"


class AnalyticsSpecialist(Specialist):
    """Specialist for analytics and insights."""
    
    def __init__(self) -> None:
        super().__init__(name="analytics", allowed_tools={"search_docs"})
        self._logger = logging.getLogger(__name__)

    async def act(self, input: str, ctx: Dict[str, Any]) -> str:
        """Provide analytics and insights based on user data."""
        from ..services.metrics import get_metrics_collector
        
        metrics = get_metrics_collector()
        user_id: int = int(ctx.get("user_id", 0))
        
        text_l = input.lower().strip()
        
        if "stats" in text_l or "analytics" in text_l or "usage" in text_l:
            # Get user statistics
            user_stats = await metrics.get_user_stats(user_id)
            if user_stats:
                return self._format_user_stats(user_stats)
            else:
                return "No usage statistics available yet."
        
        elif "system" in text_l or "bot" in text_l:
            # Get system statistics
            system_stats = await metrics.get_system_stats()
            return self._format_system_stats(system_stats)
        
        else:
            return "I can provide analytics on:\n" \
                   "• Your usage statistics\n" \
                   "• System performance\n" \
                   "• Command usage patterns\n\n" \
                   "Try asking for 'stats' or 'system analytics'."

    def _format_user_stats(self, stats: Dict[str, Any]) -> str:
        """Format user statistics for display."""
        lines = ["📊 **Your Usage Statistics:**"]
        
        if stats.get("total_commands"):
            lines.append(f"• Total commands: {stats['total_commands']}")
        
        if stats.get("commands_by_type"):
            lines.append("• Commands by type:")
            for cmd, count in stats["commands_by_type"].items():
                lines.append(f"  - {cmd}: {count}")
        
        if stats.get("last_active"):
            lines.append(f"• Last active: {stats['last_active']}")
        
        if stats.get("timezone"):
            lines.append(f"• Timezone: {stats['timezone']}")
        
        return "\n".join(lines)

    def _format_system_stats(self, stats: Dict[str, Any]) -> str:
        """Format system statistics for display."""
        lines = ["🤖 **System Analytics:**"]
        
        if stats.get("uptime_seconds"):
            uptime_hours = stats["uptime_seconds"] / 3600
            lines.append(f"• Uptime: {uptime_hours:.1f} hours")
        
        if stats.get("total_commands"):
            lines.append(f"• Total commands processed: {stats['total_commands']}")
        
        if stats.get("error_rate"):
            error_pct = stats["error_rate"] * 100
            lines.append(f"• Error rate: {error_pct:.1f}%")
        
        if stats.get("commands_per_minute"):
            lines.append(f"• Commands per minute: {stats['commands_per_minute']:.1f}")
        
        return "\n".join(lines)


