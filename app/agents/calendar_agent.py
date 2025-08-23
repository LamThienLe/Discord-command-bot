from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, Optional, Tuple

import dateparser
from dateparser.search import search_dates
from zoneinfo import ZoneInfo

from ..services.llm import call_ollama


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    try:
        import json

        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            import json

            return json.loads(snippet)
        except Exception:
            import re as _re

            cleaned = _re.sub(r"```[a-zA-Z]*", "", snippet)
            cleaned = cleaned.replace("```", "")
            try:
                import json

                return json.loads(cleaned)
            except Exception:
                return None
    return None


async def parse_event_with_llm(details: str, default_timezone: str) -> Optional[Dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    system_instructions = (
        "Parse the user input into strict JSON with keys: summary, start_date, start_time, "
        "timezone, duration_minutes. Assume times are in the provided timezone if not stated. "
        "Prefer future dates. Use 24-hour time. Duration must be minutes as an integer. "
        "If only a date and time are given, combine them for the start; if ambiguous like 'today', resolve relative to now."
    )
    prompt = (
        f"{system_instructions}\n"
        f"User input: {details}\n"
        f"Now (ISO, UTC): {now}\n"
        f"Default timezone: {default_timezone}\n"
        "Respond with ONLY the JSON object, no explanations."
    )
    text = await call_ollama(prompt)
    data = _extract_json_object(text)
    return data


def _build_datetimes_from_parsed(parsed: Dict[str, Any], user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime], str]:
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    summary: str = "Event"

    tz = parsed.get("timezone") or user_tz
    try:
        tzinfo = ZoneInfo(tz)
    except Exception:
        tzinfo = ZoneInfo(user_tz)

    start_date = parsed.get("start_date")
    start_time = parsed.get("start_time")
    if start_date and "T" in start_date:
        try:
            start = dt.datetime.fromisoformat(start_date)
            if start.tzinfo is None:
                start = start.replace(tzinfo=tzinfo)
            else:
                start = start.astimezone(tzinfo)
        except Exception:
            start = None
    elif start_date and start_time:
        try:
            y, m, d = [int(x) for x in start_date.split("-")]
            hh, mm = [int(x) for x in start_time.split(":")]
            start = dt.datetime(y, m, d, hh, mm, tzinfo=tzinfo)
        except Exception:
            start = None

    duration_minutes = parsed.get("duration_minutes")
    if isinstance(duration_minutes, (int, float)):
        duration = dt.timedelta(minutes=int(duration_minutes))
    else:
        duration = dt.timedelta(hours=1)

    if isinstance(parsed.get("summary"), str) and parsed.get("summary").strip():
        summary = parsed.get("summary").strip()[:128]

    if start is not None:
        end = start + duration

    return start, end, summary


def _fallback_parse(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    dp_settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": user_tz,
    }
    when = dateparser.parse(details, settings=dp_settings)
    if not when:
        try:
            found = search_dates(details, settings=dp_settings)
            if found and len(found) > 0:
                when = found[0][1]
        except Exception:
            when = None
    if not when:
        return None, None
    start = when if when.tzinfo else when.replace(tzinfo=ZoneInfo(user_tz))
    end = start + dt.timedelta(hours=1)
    return start, end


def _concise_summary(details: str, current: str) -> str:
    if current and current.lower() not in {"event", "meeting"}:
        return current
    summary_source = details
    text = re.sub(r"\b(today|tomorrow|tonight|this\s+\w+|next\s+\w+|at|on|from|to|by|around|about)\b", " ", summary_source, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b([01]?\d|2[0-3])(?:[:.]\d{2})\b", " ", text)
    text = re.sub(r"\b(add|create|schedule|set|make|meeting|event)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title()[:128] if text else (current or "Event")


async def parse_times_and_summary(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime], str]:
    parsed = await parse_event_with_llm(details, user_tz)
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    summary: str = "Event"

    if parsed:
        start, end, summary = _build_datetimes_from_parsed(parsed, user_tz)

    if start is None or end is None:
        start, end = _fallback_parse(details, user_tz)
        if start is None or end is None:
            return None, None, ""

    summary = _concise_summary(details, summary)
    return start, end, summary


