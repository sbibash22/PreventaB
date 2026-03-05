# core/views.py
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.utils import timezone
from zoneinfo import ZoneInfo

from devices.models import Device
from telemetry.models import SystemLog, TelemetrySample
from alerts.models import Alert
from telemetry.services.explain import build_xai_report

User = get_user_model()


def about(request):
    return render(request, "public/about.html", {"page_title": "About Us"})


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_admin():
            return redirect("user_dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def _log_time_field() -> str | None:
    """
    Support both possible datetime fields in SystemLog:
    - timestamp
    - created_at
    """
    fields = {f.name for f in SystemLog._meta.fields}
    if "timestamp" in fields:
        return "timestamp"
    if "created_at" in fields:
        return "created_at"
    return None


def _sample_value(sample, *names, default=0.0) -> float:
    for n in names:
        if hasattr(sample, n):
            try:
                return float(getattr(sample, n))
            except Exception:
                return default
    return default


@login_required
@admin_required
def admin_dashboard(request):
    # ---- Stat cards ----
    devices_count = Device.objects.count()
    users_count = User.objects.count()
    open_alerts = Alert.objects.filter(status="OPEN").count()

    #  FIX: Logs(24h) counts correctly for timestamp OR created_at
    since_24h = timezone.now() - timezone.timedelta(hours=24)
    time_field = _log_time_field()
    if time_field:
        logs_24h = SystemLog.objects.filter(**{f"{time_field}__gte": since_24h}).count()
    else:
        logs_24h = SystemLog.objects.count()

    # ---- Recent panels ----
    recent_samples = TelemetrySample.objects.select_related("device").order_by("-id")[:10]
    recent_logs = SystemLog.objects.select_related("device").order_by("-id")[:10]

    # ---- Chart device selector ----
    devices = Device.objects.all().order_by("name")
    device_id = request.GET.get("device")
    selected_device = Device.objects.filter(id=device_id).first() if device_id else devices.first()

    #  Always use Kathmandu for charts
    kathmandu_tz = ZoneInfo("Asia/Kathmandu")

    timestamps, labels, cpu, ram, disk = [], [], [], [], []
    xai_report = None

    if selected_device:
        # last N samples newest->oldest then reverse for chart oldest->newest
        qs = TelemetrySample.objects.filter(device=selected_device).order_by("-timestamp")[:20]
        qs = list(reversed(list(qs)))

        # logs for explainable report
        log_qs = list(SystemLog.objects.filter(device=selected_device).order_by("-id")[:200])

        # explainable report
        xai_report = build_xai_report(qs, log_qs)

        #  chart arrays (Kathmandu time ISO)
        for s in qs:
            ts = getattr(s, "timestamp", None)
            if ts:
                ts_local = timezone.localtime(ts, kathmandu_tz)
                timestamps.append(ts_local.isoformat())  #  correct Kathmandu time +05:45
                labels.append(ts_local.strftime("%b %d, %I:%M %p").replace(" 0", " "))
            else:
                timestamps.append("")
                labels.append("")

            cpu.append(_sample_value(s, "cpu", "cpu_usage"))
            ram.append(_sample_value(s, "ram", "ram_usage"))
            disk.append(_sample_value(s, "disk", "disk_usage"))

    chart_payload = {
        "timestamps": timestamps,  #  use this in charts.js
        "labels": labels,          # fallback
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
    }

    return render(request, "admin/dashboard.html", {
        "page_title": "Dashboard",
        "devices_count": devices_count,
        "users_count": users_count,
        "logs_24h": logs_24h,
        "open_alerts": open_alerts,
        "recent_samples": recent_samples,
        "recent_logs": recent_logs,
        "devices": devices,
        "selected_device": selected_device,
        "chart_payload": chart_payload,
        "xai_report": xai_report,
    })


@login_required
def user_dashboard(request):
    """
    User dashboard: show ONLY devices assigned to logged-in user + charts + XAI report.
    """
    devices = request.user.devices.all().order_by("name")

    #  Always use Kathmandu for charts
    kathmandu_tz = ZoneInfo("Asia/Kathmandu")

    if not devices.exists():
        return render(request, "user/dashboard.html", {
            "page_title": "Dashboard",
            "devices": devices,
            "selected_device": None,
            "chart_payload": {"timestamps": [], "labels": [], "cpu": [], "ram": [], "disk": []},
            "recent_samples": [],
            "xai_report": None,
        })

    device_id = request.GET.get("device")
    selected_device = devices.filter(id=device_id).first() if device_id else devices.first()

    qs = TelemetrySample.objects.filter(device=selected_device).order_by("-timestamp")[:20]
    qs = list(reversed(list(qs)))

    timestamps, labels, cpu, ram, disk = [], [], [], [], []
    for s in qs:
        ts = getattr(s, "timestamp", None)
        if ts:
            ts_local = timezone.localtime(ts, kathmandu_tz)
            timestamps.append(ts_local.isoformat())
            labels.append(ts_local.strftime("%b %d, %I:%M %p").replace(" 0", " "))  # fallback only
        else:
            timestamps.append("")
            labels.append("")

        cpu.append(_sample_value(s, "cpu", "cpu_usage"))
        ram.append(_sample_value(s, "ram", "ram_usage"))
        disk.append(_sample_value(s, "disk", "disk_usage"))

    chart_payload = {
        "timestamps": timestamps,  #  use this in charts_user.js
        "labels": labels,          # fallback
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
    }

    log_qs = list(SystemLog.objects.filter(device=selected_device).order_by("-id")[:200])
    xai_report = build_xai_report(qs, log_qs)

    recent_samples = TelemetrySample.objects.filter(device__in=devices).select_related("device").order_by("-id")[:10]

    return render(request, "user/dashboard.html", {
        "page_title": "Dashboard",
        "devices": devices,
        "selected_device": selected_device,
        "chart_payload": chart_payload,
        "recent_samples": recent_samples,
        "xai_report": xai_report,
    })