from django import forms
from .models import AlertSetting, SystemSetting, Alert
from devices.models import Device
from django.contrib.auth import get_user_model

User = get_user_model()

BASE = "w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"

class SendAlertForm(forms.Form):
    device = forms.ModelChoiceField(queryset=Device.objects.all(), widget=forms.Select(attrs={"class": BASE}))
    risk_level = forms.ChoiceField(choices=[("LOW","LOW"),("MEDIUM","MEDIUM"),("HIGH","HIGH")], widget=forms.Select(attrs={"class": BASE}))
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by("username"),
        widget=forms.SelectMultiple(attrs={"class": BASE, "size": "5"}),
        required=True
    )
    subject = forms.CharField(widget=forms.TextInput(attrs={"class": BASE}))
    message = forms.CharField(widget=forms.Textarea(attrs={"class": BASE, "rows": 6}))
    require_password = forms.BooleanField(required=False)

class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ["collection_interval_seconds", "retention_days"]
        widgets = {
            "collection_interval_seconds": forms.NumberInput(attrs={"class": BASE}),
            "retention_days": forms.NumberInput(attrs={"class": BASE}),
        }

class AlertSettingForm(forms.ModelForm):
    class Meta:
        model = AlertSetting
        fields = ["threshold_medium", "threshold_high", "cooldown_minutes", "email_on_high"]
        widgets = {
            "threshold_medium": forms.NumberInput(attrs={"class": BASE}),
            "threshold_high": forms.NumberInput(attrs={"class": BASE}),
            "cooldown_minutes": forms.NumberInput(attrs={"class": BASE}),
        }