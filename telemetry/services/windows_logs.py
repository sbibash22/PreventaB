from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
from typing import Any, Dict, List


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _read_pywin32(max_events: int, log_type: str) -> List[Dict[str, Any]]:
    """Try pywin32 EventLog API. Return [] on any failure."""
    try:
        import win32evtlog
        import win32evtlogutil
        import pywintypes  # noqa
    except Exception:
        return []

    try:
        server = "localhost"
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        hand = win32evtlog.OpenEventLog(server, log_type)
        try:
            records = win32evtlog.ReadEventLog(hand, flags, 0) or []
        finally:
            win32evtlog.CloseEventLog(hand)
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for ev in records[:max_events]:
        try:
            msg = win32evtlogutil.SafeFormatMessage(ev, log_type)
        except Exception:
            msg = "Event"

        et = getattr(ev, "EventType", None)
        if et == 1:
            level = "ERROR"
        elif et == 2:
            level = "WARNING"
        else:
            level = "INFO"

        out.append(
            {
                "timestamp": dt.datetime.utcnow().isoformat(),
                "level": level,
                "source": str(getattr(ev, "SourceName", "")),
                "event_id": str(getattr(ev, "EventID", 0) & 0xFFFF),
                "message": (msg or "")[:2000],
            }
        )
    return out


def _read_powershell(max_events: int, log_type: str) -> List[Dict[str, Any]]:
    """
    Fallback using PowerShell Get-WinEvent (works when wevtutil works).
    Includes the real 'Message' field which is great for demo.
    """
    ps = (
        f"$e = Get-WinEvent -LogName '{log_type}' -MaxEvents {max_events} | "
        "Select-Object TimeCreated, LevelDisplayName, ProviderName, Id, Message; "
        "$e | ConvertTo-Json -Compress"
    )

    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            text=True,
            encoding="utf-8",
            errors="ignore",
        ).strip()
        if not out:
            return []
        data = json.loads(out)
    except Exception:
        return []

    if isinstance(data, dict):
        data = [data]

    level_map = {
        "Critical": "CRITICAL",
        "Error": "ERROR",
        "Warning": "WARNING",
        "Information": "INFO",
        "Verbose": "INFO",
    }

    events: List[Dict[str, Any]] = []
    for item in data[:max_events]:
        tc = item.get("TimeCreated")
        # Keep timestamp simple; collector already handles bad timestamps safely.
        ts = tc if isinstance(tc, str) and tc else dt.datetime.utcnow().isoformat()

        lvl = level_map.get(str(item.get("LevelDisplayName", "Information")), "INFO")
        src = str(item.get("ProviderName", "") or "")
        event_id = str(item.get("Id", "") or "")
        msg = str(item.get("Message", "") or "")[:2000]

        events.append(
            {
                "timestamp": ts,
                "level": lvl,
                "source": src,
                "event_id": event_id,
                "message": msg,
            }
        )

    return events


def read_recent_events(max_events: int = 30, log_type: str = "System") -> List[Dict[str, Any]]:
    """
    Returns Windows events as list of dicts.
    Uses pywin32 first; if empty/fails, uses PowerShell Get-WinEvent fallback.
    """
    if not _is_windows():
        return []

    events = _read_pywin32(max_events=max_events, log_type=log_type)
    if events:
        return events

    return _read_powershell(max_events=max_events, log_type=log_type)