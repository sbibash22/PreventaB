import os, time, platform, datetime as dt
import requests, psutil

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
INGEST_TOKEN = os.getenv("AGENT_INGEST_TOKEN", "change-me-agent-token")

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
            "message": msg[:1200]
        })

    win32evtlog.CloseEventLog(hand)
    return out

def collect():
    return {
        "cpu": psutil.cpu_percent(interval=0.4),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "logs": read_windows_logs(),
    }

def main():
    if not DEVICE_API_KEY:
        raise SystemExit("Set DEVICE_API_KEY env var from Device.api_key in Django device overview page.")

    while True:
        payload = collect()
        r = requests.post(
            f"{SERVER_URL}/agent/ingest/",
            headers={"X-INGEST-TOKEN": INGEST_TOKEN},
            json={"api_key": DEVICE_API_KEY, **payload},
            timeout=10
        )
        print(r.status_code, r.text[:200])
        time.sleep(15)

if __name__ == "__main__":
    main()
