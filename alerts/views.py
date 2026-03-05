from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.views import admin_required
from .models import Notification, Alert, AlertSetting, SystemSetting
from .forms import SendAlertForm, AlertSettingForm, SystemSettingForm
from .services.alerting import create_notification, send_alert_email

@login_required
def notifications_list(request):
    notes = request.user.notifications.order_by("-id")[:200]
    tpl = "admin/notifications.html" if request.user.is_admin() else "user/notifications.html"
    return render(request, tpl, {"page_title": "Notifications", "notes": notes})

@login_required
def notification_read(request, pk):
    n = get_object_or_404(Notification, pk=pk)

    # Optional: owner check (only if model has user field)
    if hasattr(n, "user") and n.user and n.user != request.user and not request.user.is_admin():
        messages.error(request, "You are not allowed to view this notification.")
        return redirect("login")

    #  Mark as read using REAL DB fields (not @property)
    updated_fields = []

    if hasattr(n, "is_read"):
        if not n.is_read:
            n.is_read = True
            updated_fields.append("is_read")

    elif hasattr(n, "read"):
        if not n.read:
            n.read = True
            updated_fields.append("read")

    elif hasattr(n, "read_at"):
        if not n.read_at:
            n.read_at = timezone.now()
            updated_fields.append("read_at")

    else:
        # fallback: do nothing if model has no read-state field
        pass

    if updated_fields:
        n.save(update_fields=updated_fields)

    #  Correct redirect:
    if request.user.is_admin():
        return redirect("send_alert")
    return redirect("user_dashboard")

@login_required
@admin_required
def send_alert(request):
    form = SendAlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        device = form.cleaned_data["device"]
        risk_level = form.cleaned_data["risk_level"]
        recipients = list(form.cleaned_data["recipients"])
        subject = form.cleaned_data["subject"]
        message = form.cleaned_data["message"]
        require_password = form.cleaned_data.get("require_password", False)

        alert = Alert.objects.create(
            device=device,
            risk_level=risk_level,
            subject=subject,
            message=message,
            created_by=request.user,
            require_password=require_password
        )
        alert.recipients.set(recipients)

        for u in recipients:
            create_notification(u, title=subject, body=message, link="/alerts/user/")

        # email
        sent = send_alert_email(recipients, subject, message)
        alert.sent_email = sent
        alert.save(update_fields=["sent_email"])

        messages.success(request, "Alert sent successfully.")
        return redirect("alert_history")

    return render(request, "admin/send_alert.html", {"page_title":"Send Alert", "form": form})

@login_required
@admin_required
def alert_history(request):
    alerts = Alert.objects.select_related("device").order_by("-id")[:200]
    return render(request, "admin/alert_history.html", {"page_title":"Alert History", "alerts": alerts})

@login_required
@admin_required
def alert_settings(request):
    obj = AlertSetting.get_solo()
    form = AlertSettingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Alert settings updated.")
        return redirect("alert_settings")
    return render(request, "admin/alert_settings.html", {"page_title":"Alert Settings", "form": form})

@login_required
@admin_required
def system_settings(request):
    obj = SystemSetting.get_solo()
    form = SystemSettingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "System settings updated.")
        return redirect("system_settings")
    return render(request, "admin/system_settings.html", {"page_title":"System Settings", "form": form})

@login_required
@admin_required
def ack_alert_admin(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    if request.method == "POST":
        alert.status = "ACK"
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status","acknowledged_by","acknowledged_at"])
        messages.success(request, "Alert acknowledged.")
        return redirect("alert_history")
    return render(request, "admin/ack_alert.html", {"page_title":"Acknowledge Alert", "alert": alert})

@login_required
def user_alerts(request):
    alerts = request.user.alerts.select_related("device").order_by("-id")[:200]
    return render(request, "user/alerts.html", {"page_title":"Alerts", "alerts": alerts})

@login_required
def ack_alert_user(request, pk):
    alert = get_object_or_404(Alert, pk=pk, recipients=request.user)
    if request.method == "POST":
        # simple ack (password feature can be expanded later)
        alert.status = "ACK"
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status","acknowledged_by","acknowledged_at"])
        messages.success(request, "Alert acknowledged.")
        return redirect("user_alerts")
    return render(request, "user/ack_alert.html", {"page_title":"Acknowledge Alert", "alert": alert})

@login_required
def user_settings(request):
    # Preferences row (create if missing)
    from django.contrib.auth.forms import SetPasswordForm
    from accounts.models import UserPreference
    from accounts.forms import UserPreferenceForm

    pref, _ = UserPreference.objects.get_or_create(user=request.user)

    pref_form = UserPreferenceForm(request.POST or None, instance=pref, user=request.user, prefix="pref")
    pwd_form = SetPasswordForm(request.user, request.POST or None, prefix="pwd")

    # Style password fields
    base_cls = (
        "w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 "
        "bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 "
        "placeholder:text-slate-400 dark:placeholder:text-slate-500 "
        "focus:outline-none focus:ring-2 focus:ring-blue-500/60 focus:border-blue-500"
    )
    for f in ("new_password1", "new_password2"):
        if f in pwd_form.fields:
            pwd_form.fields[f].widget.attrs.update({"class": base_cls, "placeholder": "••••••••"})


    if request.method == "POST":
        # Which form was submitted?
        if "pref-submit" in request.POST and pref_form.is_valid():
            pref_form.save()
            messages.success(request, "Settings saved.")
            return redirect("user_settings")

        if "pwd-submit" in request.POST and pwd_form.is_valid():
            pwd_form.save()
            messages.success(request, "Password updated. Please use your new password next time you log in.")
            return redirect("user_settings")

    return render(
        request,
        "user/settings.html",
        {
            "page_title": "Settings",
            "pref_form": pref_form,
            "pwd_form": pwd_form,
        },
    )
