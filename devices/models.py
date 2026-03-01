import secrets
from django.db import models
from django.conf import settings

class Device(models.Model):
    class OSType(models.TextChoices):
        WINDOWS = "WINDOWS", "Windows"
        LINUX = "LINUX", "Linux"
        MAC = "MAC", "Mac"

    class RiskProfile(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    name = models.CharField(max_length=120)
    ip_address = models.GenericIPAddressField()
    os_type = models.CharField(max_length=10, choices=OSType.choices, default=OSType.WINDOWS)

    assigned_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="devices")

    monitoring_enabled = models.BooleanField(default=True)
    risk_profile = models.CharField(max_length=10, choices=RiskProfile.choices, default=RiskProfile.MEDIUM)

    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    api_key = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.ip_address})"
