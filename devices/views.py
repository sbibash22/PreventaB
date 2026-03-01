from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from core.views import admin_required
from .models import Device
from .forms import DeviceForm
from telemetry.models import TelemetrySample, SystemLog

@login_required
@admin_required
def device_list(request):
    devices = Device.objects.order_by("name")
    return render(request, "admin/device_list.html", {"page_title":"Device Management", "devices": devices})

@login_required
@admin_required
def device_add(request):
    form = DeviceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        device = form.save()
        device.assigned_users.set(form.cleaned_data.get("assigned_users"))
        messages.success(request, "Device created.")
        return redirect("device_list")
    return render(request, "admin/device_form.html", {"page_title":"Add Device", "form": form, "mode":"add"})

@login_required
@admin_required
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)
    form = DeviceForm(request.POST or None, instance=device, initial={"assigned_users": device.assigned_users.all()})
    if request.method == "POST" and form.is_valid():
        device = form.save()
        device.assigned_users.set(form.cleaned_data.get("assigned_users"))
        messages.success(request, "Device updated.")
        return redirect("device_detail", pk=device.pk)
    return render(request, "admin/device_form.html", {"page_title":"Edit Device", "form": form, "mode":"edit", "device": device})

@login_required
@admin_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        device.delete()
        messages.success(request, "Device deleted.")
        return redirect("device_list")
    return render(request, "admin/confirm_delete.html", {"page_title":"Delete Device", "object": device, "back_url":"device_list"})

@login_required
@admin_required
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    samples = TelemetrySample.objects.filter(device=device).order_by("-id")[:20]
    logs = SystemLog.objects.filter(device=device).order_by("-id")[:20]
    return render(request, "admin/device_detail.html", {
        "page_title":"Device Overview",
        "device": device,
        "samples": samples,
        "logs": logs,
    })
