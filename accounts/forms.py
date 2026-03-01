from django import forms
from django.contrib.auth import get_user_model
from devices.models import Device

User = get_user_model()


BASE_INPUT = (
    "w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 "
    "bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 "
    "placeholder:text-slate-400 dark:placeholder:text-slate-500 "
    "focus:outline-none focus:ring-2 focus:ring-blue-500/60 focus:border-blue-500"
)


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT,
            "placeholder": "Username or Email",
            "id": "id_username",
            "autocomplete": "username",
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": BASE_INPUT + " pr-12",
            "placeholder": "Password",
            "id": "id_password",
            "autocomplete": "current-password",
        })
    )


class PasswordResetRequestForm(forms.Form):
    identifier = forms.CharField(
        label="Email or Username",
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT,
            "placeholder": "Enter your email or username",
            "id": "id_identifier",
            "autocomplete": "username",
        })
    )


class AdminUserForm(forms.ModelForm):
    """Used for both Add and Edit in Admin User Management."""
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Assign devices this user can view."
    )

    class Meta:
        model = User
        fields = ["username", "email", "role", "devices"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base = (
            "w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 "
            "bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 "
        )
        for f in ("username", "email", "role"):
            if f in self.fields:
                self.fields[f].widget.attrs.setdefault("class", base)

        if self.instance and self.instance.pk:
            self.fields["devices"].initial = self.instance.devices.all()

from .models import UserPreference

class UserPreferenceForm(forms.ModelForm):
    class Meta:
        model = UserPreference
        fields = [
            "default_device",
            "timezone",
            "inapp_notifications",
            "email_notifications",
            "notify_on_medium",
            "notify_on_high",
            "compact_sidebar",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Limit device choices to devices assigned to this user (safer UX).
        if user is not None and "default_device" in self.fields:
            self.fields["default_device"].queryset = user.devices.all().order_by("name")

        # Basic styling
        select_cls = BASE_INPUT
        chk_cls = "h-4 w-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500/60"

        if "default_device" in self.fields:
            self.fields["default_device"].required = False
            self.fields["default_device"].widget.attrs.update({"class": select_cls})

        if "timezone" in self.fields:
            self.fields["timezone"].widget.attrs.update({
                "class": BASE_INPUT,
                "placeholder": "e.g., UTC, Australia/Sydney, Asia/Kathmandu",
            })

        for f in ("inapp_notifications","email_notifications","notify_on_medium","notify_on_high","compact_sidebar"):
            if f in self.fields:
                self.fields[f].widget.attrs.update({"class": chk_cls})
