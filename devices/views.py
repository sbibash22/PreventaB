from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.views import admin_required
from .forms import DeviceForm
from .models import Device
from telemetry.models import SystemLog, TelemetrySample


def _online_window_seconds() -> int:
    """
    How long a device should still appear online after the latest telemetry.
    You can override this in settings.py with:
    DEVICE_ONLINE_WINDOW_SECONDS = 120
    """
    return int(getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 10))


def _is_device_online(device, now=None) -> bool:
    """
    A device is online if it has sent telemetry recently.
    Falls back safely if last_seen is missing.
    """
    if now is None:
        now = timezone.now()

    window = timedelta(seconds=_online_window_seconds())

    if getattr(device, "last_seen", None):
        return device.last_seen >= now - window

    return False


def _attach_online_status(devices):
    """
    Add a computed `online_now` attribute to device objects.
    """
    now = timezone.now()
    for device in devices:
        device.online_now = _is_device_online(device, now=now)
    return devices


@login_required
@admin_required
def device_list(request):
    devices = list(Device.objects.order_by("name"))
    _attach_online_status(devices)

    return render(
        request,
        "admin/device_list.html",
        {
            "page_title": "Device Management",
            "devices": devices,
            "online_window_seconds": _online_window_seconds(),
        },
    )


@login_required
@admin_required
def device_add(request):
    form = DeviceForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        device = form.save()
        device.assigned_users.set(form.cleaned_data.get("assigned_users"))
        messages.success(request, "Device created.")
        return redirect("device_list")

    return render(
        request,
        "admin/device_form.html",
        {
            "page_title": "Add Device",
            "form": form,
            "mode": "add",
        },
    )


@login_required
@admin_required
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)

    form = DeviceForm(
        request.POST or None,
        instance=device,
        initial={"assigned_users": device.assigned_users.all()},
    )

    if request.method == "POST" and form.is_valid():
        device = form.save()
        device.assigned_users.set(form.cleaned_data.get("assigned_users"))
        messages.success(request, "Device updated.")
        return redirect("device_detail", pk=device.pk)

    return render(
        request,
        "admin/device_form.html",
        {
            "page_title": "Edit Device",
            "form": form,
            "mode": "edit",
            "device": device,
        },
    )


@login_required
@admin_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)

    if request.method == "POST":
        device.delete()
        messages.success(request, "Device deleted.")
        return redirect("device_list")

    return render(
        request,
        "admin/confirm_delete.html",
        {
            "page_title": "Delete Device",
            "object": device,
            "back_url": "device_list",
        },
    )


@login_required
@admin_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device.online_now = _is_device_online(device)

    samples = TelemetrySample.objects.filter(device=device).order_by("-timestamp", "-id")[:20]
    logs = SystemLog.objects.filter(device=device).order_by("-timestamp", "-id")[:20]

    latest_sample = samples[0] if samples else None
    latest_log = logs[0] if logs else None

    return render(
        request,
        "admin/device_detail.html",
        {
            "page_title": "Device Overview",
            "device": device,
            "samples": samples,
            "logs": logs,
            "latest_sample": latest_sample,
            "latest_log": latest_log,
            "online_window_seconds": _online_window_seconds(),
        },
    )