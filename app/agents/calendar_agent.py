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


# Time and duration helpers
_TIME_RE = re.compile(r"\b((1[0-2]|0?[1-9])(:\d{2})?\s?(am|pm)\b|([01]?\d|2[0-3])(:\d{2})\b)", re.IGNORECASE)
_DURATION_RE = re.compile(r"\bfor\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.IGNORECASE)
_WEEKDAY_RE = re.compile(
    r"\b(?:(this|next)\s+)?(mon|monday|tue|tues|tuesday|wed|weds|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b",
    re.IGNORECASE,
)


def contains_time(text: str) -> bool:
    return bool(_TIME_RE.search(text))


def _extract_duration_minutes(text: str) -> Optional[int]:
    m = _DURATION_RE.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except Exception:
        return None
    unit = m.group(2).lower()
    return int(value * 60) if unit.startswith("h") else int(value)


def _fallback_parse(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    dp_settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": user_tz,
    }

    # Extract and strip duration to avoid confusing date parsing
    duration_minutes = _extract_duration_minutes(details)
    cleaned = _DURATION_RE.sub(" ", details)

    # Require explicit time to avoid auto-creating at arbitrary default
    if not contains_time(cleaned):
        return None, None

    when = dateparser.parse(cleaned, settings=dp_settings)
    if not when:
        try:
            found = search_dates(cleaned, settings=dp_settings)
            if found and len(found) > 0:
                when = found[0][1]
        except Exception:
            when = None
    if not when:
        return None, None
    start = when if when.tzinfo else when.replace(tzinfo=ZoneInfo(user_tz))
    minutes = duration_minutes if isinstance(duration_minutes, int) else 60
    end = start + dt.timedelta(minutes=minutes)
    return start, end


def _extract_time_components(text: str) -> Optional[Tuple[int, int]]:
    # Handle "10am", "10:30am", "3 pm"
    m12 = re.search(r"\b(1[0-2]|0?[1-9])(?::(\d{2}))?\s?(am|pm)\b", text, re.IGNORECASE)
    if m12:
        hour = int(m12.group(1)) % 12
        minute = int(m12.group(2)) if m12.group(2) else 0
        meridian = m12.group(3).lower()
        if meridian == "pm":
            hour += 12
        return hour, minute

    # Handle 24h like "15:30" or "09:00"
    m24 = re.search(r"\b([01]?\d|2[0-3]):(\d{2})\b", text)
    if m24:
        hour = int(m24.group(1))
        minute = int(m24.group(2))
        return hour, minute
    return None


def _weekday_to_index(name: str) -> Optional[int]:
    n = name.lower()
    mapping = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "weds": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    return mapping.get(n)


def _next_occurrence_of_weekday(
    base: dt.datetime, weekday_index: int, target_time: Tuple[int, int], qualifier: Optional[str]
) -> dt.datetime:
    # base is timezone-aware
    today_idx = base.weekday()
    hour, minute = target_time

    # Compute days ahead per qualifier
    if isinstance(qualifier, str) and qualifier.lower() == "next":
        days_ahead = (weekday_index - today_idx + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
    else:
        # default or "this": choose the next occurrence that is not in the past
        days_ahead = (weekday_index - today_idx) % 7
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0) + dt.timedelta(days=days_ahead)
        if candidate <= base:
            days_ahead = (days_ahead + 7) % 7 or 7

    target_date = (base + dt.timedelta(days=days_ahead)).date()
    return base.replace(year=target_date.year, month=target_date.month, day=target_date.day, hour=hour, minute=minute, second=0, microsecond=0)


def _deterministic_weekday_time_parse(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    # If the text contains an explicit weekday and explicit time, compute deterministically
    m = _WEEKDAY_RE.search(details)
    if not m:
        return None, None
    wd_qualifier = m.group(1)  # "this" | "next" | None
    wd_name = m.group(2)
    weekday_index = _weekday_to_index(wd_name)
    if weekday_index is None:
        return None, None

    time_parts = _extract_time_components(details)
    if time_parts is None:
        return None, None

    tzinfo = ZoneInfo(user_tz)
    base_now = dt.datetime.now(tzinfo)
    start = _next_occurrence_of_weekday(base_now, weekday_index, time_parts, wd_qualifier)

    # Duration from text, else 1h
    duration_minutes = _extract_duration_minutes(details)
    minutes = duration_minutes if isinstance(duration_minutes, int) else 60
    end = start + dt.timedelta(minutes=minutes)
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

    # 1) Deterministic weekday+time handling first
    det_start, det_end = _deterministic_weekday_time_parse(details, user_tz)
    if det_start is not None and det_end is not None:
        start, end = det_start, det_end

    # 2) If still missing, try LLM
    if (start is None or end is None) and parsed:
        start, end, summary = _build_datetimes_from_parsed(parsed, user_tz)

    # 3) Fallback parser
    if start is None or end is None:
        start, end = _fallback_parse(details, user_tz)
        if start is None or end is None:
            return None, None, ""

    summary = _concise_summary(details, summary)
    return start, end, summary


