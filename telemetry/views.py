import json
import os
from django.contrib.auth.decorators import login_required
from django.db.models import Avg

#  ADDED (new imports for Send Reports feature)
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models import Q, OuterRef, Subquery
from django.shortcuts import redirect, get_object_or_404, render
from django.views.decorators.http import require_POST

from django.conf import settings

from core.views import admin_required
from .models import SystemLog, TelemetrySample
from devices.models import Device

#  ADDED (PDF builder service)
from .services.report_pdf import ReportWindow, build_device_report_pdf


def _load_json(path, default):
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _make_hist(values, n_bins=10):
    edges = [i / n_bins for i in range(n_bins + 1)]
    counts = [0] * n_bins

    for v in values:
        try:
            x = float(v)
        except Exception:
            continue
        x = max(0.0, min(1.0, x))
        idx = int(x * n_bins)
        if idx == n_bins:
            idx = n_bins - 1
        counts[idx] += 1

    labels = [f"{edges[i]:.1f}–{edges[i+1]:.1f}" for i in range(n_bins)]
    return {"bin_edges": edges, "labels": labels, "counts": counts}


def _to_percent(counts, total):
    if not total:
        return [0 for _ in counts]
    return [round((c * 100.0) / total, 2) for c in counts]


@login_required
def logs_view(request):
    """
    Admin sees all logs.
    Normal user sees logs only for their assigned devices.
    """
    if hasattr(request.user, "is_admin") and request.user.is_admin():
        logs = SystemLog.objects.select_related("device").order_by("-id")[:200]
        template = "admin/logs.html"
        title = "Logs"
    else:
        # if you use ManyToMany: user.devices
        user_devices = getattr(request.user, "devices", None)
        if user_devices is not None:
            logs = SystemLog.objects.select_related("device").filter(
                device__in=user_devices.all()
            ).order_by("-id")[:200]
        else:
            # fallback if no user->devices relation exists
            logs = SystemLog.objects.none()

        template = "user/logs.html"
        title = "Logs"

    return render(request, template, {"page_title": title, "logs": logs})


@login_required
@admin_required
def risk_analytics(request):
    # Website/live telemetry (DB)
    qs = TelemetrySample.objects.select_related("device").order_by("-timestamp")[:200]
    samples = list(qs)[::-1]  # oldest first for charts
    n_web = len(samples)

    # Trend (Website)
    trend_labels = [s.timestamp.strftime("%b %d %H:%M") for s in samples]
    trend_scores = [round(float(s.risk_score), 3) for s in samples]
    trend_devices = [s.device.name for s in samples]

    # Risk level distribution (Website)
    website_levels = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for s in samples:
        website_levels[s.risk_level] = website_levels.get(s.risk_level, 0) + 1

    website_levels_pct = {
        k: round((v * 100.0 / n_web), 2) if n_web else 0
        for k, v in website_levels.items()
    }

    # Histogram (Website)
    website_hist = _make_hist([s.risk_score for s in samples], n_bins=10)
    website_hist_pct = _to_percent(website_hist["counts"], n_web)

    # Avg risk by device (Website)
    avg_qs = (
        TelemetrySample.objects.values("device__name")
        .annotate(avg=Avg("risk_score"))
        .order_by("-avg")[:10]
    )
    avg_labels = [r["device__name"] for r in avg_qs]
    avg_values = [round(float(r["avg"] or 0), 3) for r in avg_qs]

    # Kaggle/Notebook insights (exported JSON)
    kaggle = _load_json(getattr(settings, "ML_KAGGLE_INSIGHTS_PATH", ""), {})
    n_kaggle = int(kaggle.get("n_test") or 0)

    k_levels = kaggle.get("risk_level_distribution_pred", {"LOW": 0, "MEDIUM": 0, "HIGH": 0})
    k_levels = {
        "LOW": int(k_levels.get("LOW", 0)),
        "MEDIUM": int(k_levels.get("MEDIUM", 0)),
        "HIGH": int(k_levels.get("HIGH", 0)),
    }
    k_levels_total = n_kaggle or sum(k_levels.values())
    k_levels_pct = {
        k: round((v * 100.0 / k_levels_total), 2) if k_levels_total else 0
        for k, v in k_levels.items()
    }

    k_hist = kaggle.get("probability_histogram", {})
    k_hist_counts = [int(x) for x in (k_hist.get("counts") or [0]*10)]
    k_hist_pct = _to_percent(k_hist_counts, (n_kaggle or sum(k_hist_counts)))

    # Model card metadata
    model_card = _load_json(getattr(settings, "ML_METADATA_PATH", ""), {})

    payload = {
        "website": {
            "n": n_web,
            "trend": {"labels": trend_labels, "scores": trend_scores, "devices": trend_devices},
            "levels": {"counts": website_levels, "pct": website_levels_pct},
            "hist": {"labels": website_hist["labels"], "counts": website_hist["counts"], "pct": website_hist_pct},
            "avgByDevice": {"labels": avg_labels, "values": avg_values},
        },
        "kaggle": {
            **kaggle,
            "n_test": n_kaggle,
            "levels": {"counts": k_levels, "pct": k_levels_pct},
            "hist": {"labels": website_hist["labels"], "counts": k_hist_counts, "pct": k_hist_pct},
        },
        "modelCard": model_card,
    }

    devices = Device.objects.order_by("name")

    return render(request, "admin/risk_analytics.html", {
        "page_title": "Risk Analytics / AI Insights",
        "samples": qs,
        "devices": devices,
        "risk_payload": json.dumps(payload),
    })


# =====================================================================
#  ADDED: Admin "Send Reports" page + Send Report action (PDF to email)
# =====================================================================

@login_required
@admin_required
def send_reports(request):
    """
    Admin page: list user-device pairs and provide a button to email a PDF report
    to that user's email for that specific device.
    """
    q = (request.GET.get("q") or "").strip()

    # Latest sample fields per device (fast + DB-friendly)
    latest = TelemetrySample.objects.filter(device=OuterRef("pk")).order_by("-timestamp")
    devices_qs = (
        Device.objects.prefetch_related("assigned_users")
        .annotate(
            last_sample_at=Subquery(latest.values("timestamp")[:1]),
            last_risk_score=Subquery(latest.values("risk_score")[:1]),
            last_risk_level=Subquery(latest.values("risk_level")[:1]),
        )
        .order_by("name")
    )

    if q:
        devices_qs = devices_qs.filter(
            Q(name__icontains=q)
            | Q(os_type__icontains=q)
            | Q(assigned_users__username__icontains=q)
            | Q(assigned_users__email__icontains=q)
        ).distinct()

    rows = []
    for d in devices_qs:
        users = list(d.assigned_users.all())
        for u in users:
            rows.append({
                "device": d,
                "user": u,
                "last_sample_at": getattr(d, "last_sample_at", None),
                "last_risk_score": getattr(d, "last_risk_score", None),
                "last_risk_level": getattr(d, "last_risk_level", None),
            })

    return render(request, "admin/send_reports.html", {
        "page_title": "Send Reports",
        "q": q,
        "rows": rows,
    })


@login_required
@admin_required
@require_POST
def send_report(request, device_id: int, user_id: int):
    """
    Action endpoint: build PDF report for (user, device) and email it.
    """
    User = get_user_model()
    device = get_object_or_404(Device, pk=device_id)
    user = get_object_or_404(User, pk=user_id)

    # Ensure this user is actually assigned to this device
    if not device.assigned_users.filter(pk=user.pk).exists():
        messages.error(request, "That user is not assigned to this device.")
        return redirect("send_reports")

    if not user.email:
        messages.error(request, "This user has no email address saved.")
        return redirect("send_reports")

    # Days window (1..90)
    try:
        days = int(request.POST.get("days") or 7)
    except Exception:
        days = 7
    days = max(1, min(days, 90))

    window = ReportWindow(days=days)
    pdf_bytes = build_device_report_pdf(device=device, user=user, window=window)

    subject = f"PreventaB Report — {device.name} ({days} days)"
    body = (
        f"Hello {user.username},\n\n"
        f"Attached is your PreventaB telemetry + risk + explainability report for:\n"
        f"- Device: {device.name}\n"
        f"- Window: last {days} day(s)\n\n"
        f"Regards,\nPreventaB Admin"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None)
    email = EmailMessage(subject=subject, body=body, to=[user.email], from_email=from_email)

    safe_device = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in device.name)
    filename = f"preventaB_report_{safe_device}_{days}d.pdf"
    email.attach(filename, pdf_bytes, "application/pdf")

    email.send(fail_silently=False)
    messages.success(request, f"Report sent to {user.email} for device '{device.name}' ({days} day(s)).")
    return redirect("send_reports")