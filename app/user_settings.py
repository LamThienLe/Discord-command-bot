from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any

from zoneinfo import ZoneInfo


_STORE_PATH = os.path.join(os.path.dirname(__file__), "tokens", "user_settings.json")


def _ensure_store_dir() -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)


def _read_store() -> Dict[str, Any]:
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_store(data: Dict[str, Any]) -> None:
    _ensure_store_dir()
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def set_user_timezone(user_id: int, timezone_name: str) -> None:
    # Validate timezone
    _ = ZoneInfo(timezone_name)
    store = _read_store()
    store[str(user_id)] = {"timezone": timezone_name}
    _write_store(store)


def get_user_timezone(user_id: int) -> Optional[str]:
    store = _read_store()
    entry = store.get(str(user_id))
    if isinstance(entry, dict):
        tz = entry.get("timezone")
        if isinstance(tz, str) and tz:
            try:
                _ = ZoneInfo(tz)
                return tz
            except Exception:
                return None
    return None


