from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List


# ============================================================
# Cross-platform log reader for PreventaB
#
# Output schema (per event dict):
# {
#   "timestamp": "<ISO8601>",
#   "level": "CRITICAL|ERROR|WARNING|INFO",
#   "source": "<short source>",
#   "event_id": "<optional id>",
#   "message": "<text>"
# }
#
# Notes:
# - Windows: uses pywin32 first, then PowerShell Get-WinEvent fallback
# - Linux: uses journalctl (JSON) if available, else /var/log/syslog|messages
# - macOS: uses `log show` as a practical fallback
# ============================================================


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()


# -------------------- WINDOWS --------------------
def _read_windows(max_events: int, log_type: str = "System") -> List[Dict[str, Any]]:
    if platform.system().lower() != "windows":
        return []

    # Try pywin32 (fast and structured)
    try:
        import win32evtlog
        import win32evtlogutil
        import pywintypes  # noqa
    except Exception:
        win32evtlog = None  # type: ignore

    if win32evtlog is not None:
        try:
            server = "localhost"
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            hand = win32evtlog.OpenEventLog(server, log_type)
            try:
                records = win32evtlog.ReadEventLog(hand, flags, 0) or []
            finally:
                win32evtlog.CloseEventLog(hand)
        except Exception:
            records = []
        else:
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
                        "timestamp": _now_iso(),
                        "level": level,
                        "source": str(getattr(ev, "SourceName", "")),
                        "event_id": str(getattr(ev, "EventID", 0) & 0xFFFF),
                        "message": (msg or "")[:2000],
                    }
                )
            if out:
                return out

    # PowerShell fallback (works even without pywin32)
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
        ts = tc if isinstance(tc, str) and tc else _now_iso()
        lvl = level_map.get(str(item.get("LevelDisplayName", "Information")), "INFO")
        src = str(item.get("ProviderName", "") or "")[:120]
        event_id = str(item.get("Id", "") or "")[:40]
        msg = str(item.get("Message", "") or "")[:2000]
        events.append({"timestamp": ts, "level": lvl, "source": src, "event_id": event_id, "message": msg})

    return events


# -------------------- LINUX --------------------
def _read_linux_journalctl(max_events: int) -> List[Dict[str, Any]]:
    if platform.system().lower() != "linux":
        return []
    if not shutil.which("journalctl"):
        return []

    cmd = ["journalctl", "--since", "1 hour ago", "-n", str(max_events), "-o", "json"]
    try:
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    except Exception:
        return []

    events: List[Dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue

        # PRIORITY: 0 emerg,1 alert,2 crit,3 err,4 warning,5 notice,6 info,7 debug
        try:
            pr = int(d.get("PRIORITY", 6))
        except Exception:
            pr = 6

        if pr <= 2:
            lvl = "CRITICAL"
        elif pr == 3:
            lvl = "ERROR"
        elif pr == 4:
            lvl = "WARNING"
        else:
            lvl = "INFO"

        ts_iso = _now_iso()
        rt = d.get("__REALTIME_TIMESTAMP")
        try:
            ts_iso = dt.datetime.fromtimestamp(int(rt) / 1_000_000, tz=dt.timezone.utc).isoformat()
        except Exception:
            pass

        src = d.get("SYSLOG_IDENTIFIER") or d.get("_COMM") or d.get("_SYSTEMD_UNIT") or ""
        msg = d.get("MESSAGE") or ""
        eid = d.get("MESSAGE_ID") or d.get("_PID") or ""

        events.append(
            {
                "timestamp": ts_iso,
                "level": lvl,
                "source": str(src)[:120],
                "event_id": str(eid)[:40],
                "message": str(msg)[:2000],
            }
        )

    return events[:max_events]


def _read_linux_syslog_files(max_events: int) -> List[Dict[str, Any]]:
    if platform.system().lower() != "linux":
        return []
    candidates = ["/var/log/syslog", "/var/log/messages"]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-2000:]
    except Exception:
        return []

    events: List[Dict[str, Any]] = []
    for s in lines[-max_events:]:
        s = s.strip()
        if not s:
            continue
        low = s.lower()
        if "crit" in low or "fatal" in low:
            lvl = "CRITICAL"
        elif "error" in low or " err " in low:
            lvl = "ERROR"
        elif "warn" in low:
            lvl = "WARNING"
        else:
            lvl = "INFO"
        events.append({"timestamp": _now_iso(), "level": lvl, "source": "syslog", "event_id": "", "message": s[:2000]})
    return events


def _read_linux(max_events: int) -> List[Dict[str, Any]]:
    events = _read_linux_journalctl(max_events)
    if events:
        return events
    return _read_linux_syslog_files(max_events)


# -------------------- macOS --------------------
def _read_macos(max_events: int) -> List[Dict[str, Any]]:
    if platform.system().lower() != "darwin":
        return []
    if not shutil.which("log"):
        return []

    predicate = (
        '(eventMessage CONTAINS[c] "error") OR '
        '(eventMessage CONTAINS[c] "warning") OR '
        '(eventMessage CONTAINS[c] "critical") OR '
        '(eventMessage CONTAINS[c] "fault")'
    )
    cmd = ["log", "show", "--last", "1h", "--style", "syslog", "--predicate", predicate]

    try:
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = [l.strip() for l in out.splitlines() if l.strip()]
    lines = lines[-max_events:]

    events: List[Dict[str, Any]] = []
    for s in lines:
        low = s.lower()
        if "fault" in low or "critical" in low:
            lvl = "CRITICAL"
        elif "error" in low:
            lvl = "ERROR"
        elif "warn" in low:
            lvl = "WARNING"
        else:
            lvl = "INFO"
        events.append({"timestamp": _now_iso(), "level": lvl, "source": "macos-log", "event_id": "", "message": s[:2000]})
    return events


# -------------------- PUBLIC API --------------------
def read_recent_events(max_events: int = 30, log_type: str = "System") -> List[Dict[str, Any]]:
    """
    Read recent events on the current OS.

    - Windows uses `log_type` (default System)
    - Linux/macOS ignore `log_type` but keep the signature compatible with existing code
    """
    sysname = platform.system().lower()
    if sysname == "windows":
        return _read_windows(max_events=max_events, log_type=log_type)
    if sysname == "linux":
        return _read_linux(max_events=max_events)
    if sysname == "darwin":
        return _read_macos(max_events=max_events)
    return []
