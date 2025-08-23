from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, Optional, Tuple

import dateparser
from dateparser.search import search_dates
from zoneinfo import ZoneInfo


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

    duration_minutes = _extract_duration_minutes(details)
    cleaned = _DURATION_RE.sub(" ", details)

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
    m12 = re.search(r"\b(1[0-2]|0?[1-9])(?::(\d{2}))?\s?(am|pm)\b", text, re.IGNORECASE)
    if m12:
        hour = int(m12.group(1)) % 12
        minute = int(m12.group(2)) if m12.group(2) else 0
        meridian = m12.group(3).lower()
        if meridian == "pm":
            hour += 12
        return hour, minute

    m24 = re.search(r"\b([01]?\d|2[0-3]):(\d{2})\b", text)
    if m24:
        return int(m24.group(1)), int(m24.group(2))
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


def _next_occurrence_of_weekday(base: dt.datetime, weekday_index: int, target_time: Tuple[int, int], qualifier: Optional[str]) -> dt.datetime:
    today_idx = base.weekday()
    hour, minute = target_time
    if isinstance(qualifier, str) and qualifier.lower() == "next":
        days_ahead = (weekday_index - today_idx + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
    else:
        days_ahead = (weekday_index - today_idx) % 7
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0) + dt.timedelta(days=days_ahead)
        if candidate <= base:
            days_ahead = (days_ahead + 7) % 7 or 7
    target_date = (base + dt.timedelta(days=days_ahead)).date()
    return base.replace(year=target_date.year, month=target_date.month, day=target_date.day, hour=hour, minute=minute, second=0, microsecond=0)


def _deterministic_weekday_time_parse(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    m = _WEEKDAY_RE.search(details)
    if not m:
        return None, None
    wd_qualifier = m.group(1)
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
    duration_minutes = _extract_duration_minutes(details)
    minutes = duration_minutes if isinstance(duration_minutes, int) else 60
    end = start + dt.timedelta(minutes=minutes)
    return start, end


def _concise_summary(details: str, current: str) -> str:
    if current and current.lower() not in {"event", "meeting"}:
        return current
    text = re.sub(r"\b(today|tomorrow|tonight|this\s+\w+|next\s+\w+|at|on|from|to|by|around|about)\b", " ", details, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b([01]?\d|2[0-3])(?:[:.]\d{2})\b", " ", text)
    text = re.sub(r"\b(add|create|schedule|set|make|meeting|event)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title()[:128] if text else (current or "Event")


def parse_times_and_summary(details: str, user_tz: str) -> Tuple[Optional[dt.datetime], Optional[dt.datetime], str]:
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    summary: str = "Event"

    det_start, det_end = _deterministic_weekday_time_parse(details, user_tz)
    if det_start is not None and det_end is not None:
        start, end = det_start, det_end

    if start is None or end is None:
        start, end = _fallback_parse(details, user_tz)
        if start is None or end is None:
            return None, None, ""

    summary = _concise_summary(details, summary)
    return start, end, summary


