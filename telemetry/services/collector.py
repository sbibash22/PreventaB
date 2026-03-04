from __future__ import annotations

import hashlib
import os
import platform

import psutil
from django.utils import timezone

from devices.models import Device
from telemetry.models import SystemLog, TelemetrySample
from telemetry.services.risk import predict_risk
from telemetry.services.os_logs import read_recent_events
from alerts.services.alerting import maybe_raise_risk_alert


def _disk_percent() -> float:
    # Windows should use SystemDrive, others use "/"
    if platform.system().lower() == "windows":
        drive = os.getenv("SystemDrive", "C:") + "\\"
        return float(psutil.disk_usage(drive).percent)
    return float(psutil.disk_usage("/").percent)


def collect_and_store(device: Device, max_events: int = 30) -> TelemetrySample:
    """Collect local system metrics + OS logs and store them for a device."""

    now = timezone.now()

    # Mark device online
    device.is_online = True
    device.last_seen = now
    device.save(update_fields=["is_online", "last_seen"])

    # System metrics
    cpu = float(psutil.cpu_percent(interval=0.4))
    ram = float(psutil.virtual_memory().percent)
    disk = _disk_percent()

    # OS logs (Windows/Linux/macOS). Safe fallback to []
    events = read_recent_events(max_events=max_events, log_type="System")

    # Save logs (avoid duplicates in last hour by hash)
    one_hour_ago = now - timezone.timedelta(hours=1)
    existing_hashes = set(
        SystemLog.objects.filter(device=device, timestamp__gte=one_hour_ago)
        .values_list("msg_hash", flat=True)
    )

    for e in events:
        msg = (e.get("message") or "")[:2000]
        src = (e.get("source") or "")[:120]
        lvl = (e.get("level") or "INFO").upper()
        event_id = str(e.get("event_id") or "")[:40]
        ts_iso = e.get("timestamp")

        try:
            ts_dt = timezone.datetime.fromisoformat(str(ts_iso).replace("Z", ""))
            if timezone.is_naive(ts_dt):
                ts_dt = timezone.make_aware(ts_dt, timezone=timezone.utc)
        except Exception:
            ts_dt = now

        h = hashlib.sha256((device.api_key + src + event_id + msg).encode("utf-8")).hexdigest()
        if h in existing_hashes:
            continue

        SystemLog.objects.create(
            device=device,
            timestamp=ts_dt,
            level=lvl if lvl in ["INFO", "WARNING", "ERROR", "CRITICAL"] else "INFO",
            source=src,
            event_id=event_id,
            message=msg,
            raw_json=dict(e),
            msg_hash=h,
        )
        existing_hashes.add(h)

    # Log counts last hour
    recent = SystemLog.objects.filter(device=device, timestamp__gte=one_hour_ago)
    critical_count = recent.filter(level="CRITICAL").count()
    error_count = recent.filter(level="ERROR").count()
    warning_count = recent.filter(level="WARNING").count()

    features = {
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "critical_count_1h": critical_count,
        "error_count_1h": error_count,
        "warning_count_1h": warning_count,
    }

    risk_score, risk_level, explanation = predict_risk(features)

    sample = TelemetrySample.objects.create(
        device=device,
        cpu=cpu,
        ram=ram,
        disk=disk,
        critical_count_1h=critical_count,
        error_count_1h=error_count,
        warning_count_1h=warning_count,
        risk_score=risk_score,
        risk_level=risk_level,
        explanation=explanation,
    )

    # Raise alert if needed
    maybe_raise_risk_alert(device=device, risk_level=risk_level, risk_score=risk_score, sample=sample)

    return sample
