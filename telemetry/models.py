from django.db import models
from devices.models import Device

class SystemLog(models.Model):
    class Level(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        CRITICAL = "CRITICAL", "Critical"

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    source = models.CharField(max_length=120, blank=True, default="")
    event_id = models.CharField(max_length=40, blank=True, default="")
    message = models.TextField()
    raw_json = models.JSONField(default=dict, blank=True)
    msg_hash = models.CharField(max_length=64, db_index=True)

class TelemetrySample(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    cpu = models.FloatField()
    ram = models.FloatField()
    disk = models.FloatField()

    critical_count_1h = models.IntegerField(default=0)
    error_count_1h = models.IntegerField(default=0)
    warning_count_1h = models.IntegerField(default=0)

    risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.LOW)

    explanation = models.JSONField(default=dict, blank=True)
