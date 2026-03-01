from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.views import admin_required
from .models import SystemLog, TelemetrySample
from devices.models import Device

@login_required
def logs_view(request):
    if request.user.is_admin():
        logs = SystemLog.objects.select_related("device").order_by("-id")[:200]
        tpl = "admin/logs.html"
        title = "Logs"
    else:
        logs = SystemLog.objects.select_related("device").filter(device__in=request.user.devices.all()).order_by("-id")[:200]
        tpl = "user/logs.html"
        title = "Logs"

    return render(request, tpl, {"page_title": title, "logs": logs})

@login_required
@admin_required
def risk_analytics(request):
    samples = TelemetrySample.objects.select_related("device").order_by("-id")[:100]
    devices = Device.objects.order_by("name")
    return render(request, "admin/risk_analytics.html", {
        "page_title":"Risk Analytics / AI Insights",
        "samples": samples,
        "devices": devices,
    })
