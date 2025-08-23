from __future__ import annotations

import datetime as dt
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


class GoogleCalendarClient:
    def __init__(self, creds: Credentials) -> None:
        self.service = build("calendar", "v3", credentials=creds)

    def get_user_timezone(self) -> Optional[str]:
        try:
            tz_setting = self.service.settings().get(setting="timezone").execute()
            if isinstance(tz_setting, dict):
                return tz_setting.get("value")
        except Exception:
            return None
        return None

    def create_event(self, *, summary: str, start: dt.datetime, end: dt.datetime) -> str:
        start_utc = start.astimezone(dt.timezone.utc)
        end_utc = end.astimezone(dt.timezone.utc)
        body = {
            "summary": summary,
            "start": {"dateTime": start_utc.isoformat()},
            "end": {"dateTime": end_utc.isoformat()},
        }
        ev = self.service.events().insert(calendarId="primary", body=body).execute()
        return ev.get("htmlLink") or "(no link)"


