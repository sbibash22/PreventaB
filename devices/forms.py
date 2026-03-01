from django import forms
from .models import Device
from accounts.models import User

class DeviceForm(forms.ModelForm):
    assigned_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full px-3 py-2 rounded border"})
    )

    class Meta:
        model = Device
        fields = ["name", "ip_address", "os_type", "monitoring_enabled", "risk_profile"]
        widgets = {
            "name": forms.TextInput(attrs={"class":"w-full px-3 py-2 rounded border"}),
            "ip_address": forms.TextInput(attrs={"class":"w-full px-3 py-2 rounded border"}),
            "os_type": forms.Select(attrs={"class":"w-full px-3 py-2 rounded border"}),
            "monitoring_enabled": forms.CheckboxInput(),
            "risk_profile": forms.Select(attrs={"class":"w-full px-3 py-2 rounded border"}),
        }
