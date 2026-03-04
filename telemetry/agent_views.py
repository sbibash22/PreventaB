import hashlib
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from devices.models import Device
from .models import SystemLog, TelemetrySample
from .services.risk import predict_risk
from alerts.services.alerting import maybe_raise_risk_alert


@csrf_exempt
def ingest(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    token = request.headers.get("X-INGEST-TOKEN", "")
    if token != settings.AGENT_INGEST_TOKEN:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)

    try:
        import json
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    api_key = payload.get("api_key", "")
    cpu = float(payload.get("cpu", 0))
    ram = float(payload.get("ram", 0))
    disk = float(payload.get("disk", 0))
    logs = payload.get("logs", []) or []

    device = Device.objects.filter(api_key=api_key).first()
    if not device:
        return JsonResponse({"ok": False, "error": "Unknown device api_key"}, status=404)

    now = timezone.now()
    device.is_online = True
    device.last_seen = now
    device.save(update_fields=["is_online", "last_seen"])

    # Deduplicate by hash in last hour
    one_hour_ago = now - timezone.timedelta(hours=1)
    existing_hashes = set(
        SystemLog.objects.filter(device=device, timestamp__gte=one_hour_ago)
        .values_list("msg_hash", flat=True)
    )

    # save logs
    for item in logs[:200]:
        ts = item.get("timestamp", "")
        try:
            ts_dt = timezone.datetime.fromisoformat(str(ts).replace("Z",""))
            if timezone.is_naive(ts_dt):
                ts_dt = timezone.make_aware(ts_dt, timezone=timezone.utc)
        except Exception:
            ts_dt = now

        msg = (item.get("message") or "")[:2000]
        src = (item.get("source") or "")[:120]
        lvl = (item.get("level") or "INFO").upper()
        event_id = str(item.get("event_id") or "")[:40]

        h = hashlib.sha256((device.api_key + src + event_id + msg).encode("utf-8")).hexdigest()
        if h in existing_hashes:
            continue

        SystemLog.objects.create(
            device=device,
            timestamp=ts_dt,
            level=lvl if lvl in ["INFO","WARNING","ERROR","CRITICAL"] else "INFO",
            source=src,
            event_id=event_id,
            message=msg,
            raw_json=dict(item),
            msg_hash=h
        )
        existing_hashes.add(h)

    # compute last 1h log counts
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

    score, level, explanation = predict_risk(features)

    sample = TelemetrySample.objects.create(
        device=device,
        cpu=cpu, ram=ram, disk=disk,
        critical_count_1h=critical_count,
        error_count_1h=error_count,
        warning_count_1h=warning_count,
        risk_score=score,
        risk_level=level,
        explanation=explanation,
    )

    maybe_raise_risk_alert(device=device, risk_level=level, risk_score=score, sample=sample)

    return JsonResponse({"ok": True, "risk_level": level, "risk_score": score})
