"""
Cross-platform agent for PreventaB (Windows / Linux / macOS)

Sends CPU/RAM/Disk + recent OS logs to your Django ingest endpoint:
POST {SERVER_URL}/telemetry/agent/ingest/

Env vars:
- SERVER_URL        e.g. http://192.168.1.10:8000
- DEVICE_API_KEY    (copy from Device Overview page in admin UI)
- AGENT_INGEST_TOKEN (must match Django settings.AGENT_INGEST_TOKEN)
- INTERVAL_SECONDS  default 30
- MAX_EVENTS        default 30
"""

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, List

import psutil
import requests

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "").strip()
INGEST_TOKEN = os.getenv("AGENT_INGEST_TOKEN", "change-me-agent-token").strip()

INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "30"))
MAX_EVENTS = int(os.getenv("MAX_EVENTS", "30"))


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()


def _read_windows(max_events: int) -> List[Dict[str, Any]]:
    if platform.system().lower() != "windows":
        return []

    # Try pywin32
    try:
        import win32evtlog
        import win32evtlogutil
    except Exception:
        win32evtlog = None  # type: ignore

    if win32evtlog is not None:
        try:
            server = "localhost"
            logtype = "System"
            hand = win32evtlog.OpenEventLog(server, logtype)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            records = win32evtlog.ReadEventLog(hand, flags, 0) or []
            win32evtlog.CloseEventLog(hand)
        except Exception:
            records = []
        else:
            out = []
            for ev in records[:max_events]:
                try:
                    msg = win32evtlogutil.SafeFormatMessage(ev, "System")
                except Exception:
                    msg = "Event"
                out.append(
                    {
                        "timestamp": _now_iso(),
                        "level": "ERROR" if ev.EventType == 1 else ("WARNING" if ev.EventType == 2 else "INFO"),
                        "source": str(ev.SourceName),
                        "event_id": str(ev.EventID & 0xFFFF),
                        "message": (msg or "")[:2000],
                    }
                )
            if out:
                return out

    # PowerShell fallback
    ps = (
        f"$e = Get-WinEvent -LogName 'System' -MaxEvents {max_events} | "
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
        ts = item.get("TimeCreated") or _now_iso()
        lvl = level_map.get(str(item.get("LevelDisplayName", "Information")), "INFO")
        events.append(
            {
                "timestamp": str(ts),
                "level": lvl,
                "source": str(item.get("ProviderName", "") or "")[:120],
                "event_id": str(item.get("Id", "") or "")[:40],
                "message": str(item.get("Message", "") or "")[:2000],
            }
        )
    return events


def _read_linux(max_events: int) -> List[Dict[str, Any]]:
    if platform.system().lower() != "linux":
        return []
    if shutil.which("journalctl"):
        cmd = ["journalctl", "--since", "1 hour ago", "-n", str(max_events), "-o", "json"]
        try:
            out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
        except Exception:
            out = ""

        events: List[Dict[str, Any]] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
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
            msg = d.get("MESSAGE") or ""
            src = d.get("SYSLOG_IDENTIFIER") or d.get("_COMM") or d.get("_SYSTEMD_UNIT") or ""
            events.append({"timestamp": _now_iso(), "level": lvl, "source": str(src)[:120], "event_id": "", "message": str(msg)[:2000]})
        return events[:max_events]

    # syslog fallback
    for path in ["/var/log/syslog", "/var/log/messages"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-max_events:]
            except Exception:
                return []
            events = []
            for s in lines:
                s = s.strip()
                if not s:
                    continue
                low = s.lower()
                if "crit" in low or "fatal" in low:
                    lvl = "CRITICAL"
                elif "error" in low:
                    lvl = "ERROR"
                elif "warn" in low:
                    lvl = "WARNING"
                else:
                    lvl = "INFO"
                events.append({"timestamp": _now_iso(), "level": lvl, "source": "syslog", "event_id": "", "message": s[:2000]})
            return events
    return []


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
    lines = [l.strip() for l in out.splitlines() if l.strip()][-max_events:]
    events = []
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


def read_logs(max_events: int) -> List[Dict[str, Any]]:
    sysname = platform.system().lower()
    if sysname == "windows":
        return _read_windows(max_events)
    if sysname == "linux":
        return _read_linux(max_events)
    if sysname == "darwin":
        return _read_macos(max_events)
    return []


def collect_metrics():
    cpu = float(psutil.cpu_percent(interval=0.4))
    ram = float(psutil.virtual_memory().percent)
    if platform.system().lower() == "windows":
        drive = os.getenv("SystemDrive", "C:") + "\\"
        disk = float(psutil.disk_usage(drive).percent)
    else:
        disk = float(psutil.disk_usage("/").percent)
    return cpu, ram, disk


def main():
    if not DEVICE_API_KEY:
        raise SystemExit("DEVICE_API_KEY is required (copy from Device Overview page).")

    url = f"{SERVER_URL}/telemetry/agent/ingest/"
    headers = {"X-INGEST-TOKEN": INGEST_TOKEN}

    print("Sending to:", url)
    print("Interval:", INTERVAL_SECONDS, "seconds | Max events:", MAX_EVENTS)
    print("OS:", platform.system())

    while True:
        cpu, ram, disk = collect_metrics()
        logs = read_logs(MAX_EVENTS)

        payload = {
            "api_key": DEVICE_API_KEY,
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "logs": logs,
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            print("POST", r.status_code, r.text[:200])
        except Exception as e:
            print("POST failed:", e)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
