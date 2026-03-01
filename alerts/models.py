from django.db import models
from django.conf import settings
from devices.models import Device

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_unread(self):
        return self.read_at is None

class Alert(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACK = "ACK", "Acknowledged"
        CLOSED = "CLOSED", "Closed"

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="alerts")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    require_password = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ack_alerts")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    sent_email = models.BooleanField(default=False)

class AlertSetting(models.Model):
    threshold_medium = models.FloatField(default=0.4)
    threshold_high = models.FloatField(default=0.7)
    cooldown_minutes = models.IntegerField(default=15)
    email_on_high = models.BooleanField(default=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

class SystemSetting(models.Model):
    collection_interval_seconds = models.IntegerField(default=30)
    retention_days = models.IntegerField(default=30)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
