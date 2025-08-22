from __future__ import annotations

from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials

TOKENS_DIR = Path(__file__).resolve().parent / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def _token_path(discord_user_id: int) -> Path:
    return TOKENS_DIR / f"{discord_user_id}.json"

def get_user_credentials(discord_user_id: int) -> Optional[Credentials]:
    p = _token_path(discord_user_id)
    if p.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(p), scopes=SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                save_user_credentials(discord_user_id, creds)
                return creds
        except Exception:
            return None
    return None

def save_user_credentials(discord_user_id: int, creds: Credentials) -> None:
    p = _token_path(discord_user_id)
    p.write_text(creds.to_json())


