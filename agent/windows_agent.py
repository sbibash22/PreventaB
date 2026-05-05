from pathlib import Path
import os
import time
import platform
import datetime as dt

import requests
import psutil
from dotenv import load_dotenv

# Load .env from the same folder as this script
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "").strip()
INGEST_TOKEN = os.getenv("AGENT_INGEST_TOKEN", "change-me-agent-token").strip()
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "15"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
VERIFY_TLS = os.getenv("VERIFY_TLS", "1").strip() not in {"0", "false", "False", "no", "NO"}


def read_windows_logs():
    if platform.system().lower() != "windows":
        return []
    try:
        import win32evtlog
        import win32evtlogutil
    except Exception:
        return []

    server = "localhost"
    logtype = "System"
    hand = win32evtlog.OpenEventLog(server, logtype)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    records = win32evtlog.ReadEventLog(hand, flags, 0) or []

    out = []
    for ev in records[:30]:
        try:
            msg = win32evtlogutil.SafeFormatMessage(ev, logtype)
        except Exception:
            msg = "Event"

        out.append({
            "timestamp": dt.datetime.utcnow().isoformat(),
            "level": "ERROR" if ev.EventType == 1 else ("WARNING" if ev.EventType == 2 else "INFO"),
            "source": str(ev.SourceName),
            "event_id": str(ev.EventID & 0xFFFF),
            "message": msg[:1200],
        })

    win32evtlog.CloseEventLog(hand)
    return out


def collect():
    if platform.system().lower() == "windows":
        disk_path = os.getenv("SystemDrive", "C:") + "\\"
    else:
        disk_path = "/"

    return {
        "cpu": psutil.cpu_percent(interval=0.4),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(disk_path).percent,
        "logs": read_windows_logs(),
    }


def main():
    if not DEVICE_API_KEY:
        raise SystemExit("DEVICE_API_KEY is required (copy from Device Overview page).")

    if not SERVER_URL:
        raise SystemExit("SERVER_URL is required.")

    if not INGEST_TOKEN:
        raise SystemExit("AGENT_INGEST_TOKEN is required.")

    print("Loaded .env from:", ENV_PATH)
    print("Sending to:", f"{SERVER_URL}/telemetry/agent/ingest/")
    print("TLS verify:", VERIFY_TLS)

    while True:
        payload = collect()
        r = requests.post(
            f"{SERVER_URL}/telemetry/agent/ingest/",
            headers={"X-INGEST-TOKEN": INGEST_TOKEN},
            json={"api_key": DEVICE_API_KEY, **payload},
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=VERIFY_TLS,
        )
        print(r.status_code, r.text[:200])
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()