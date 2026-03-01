from django.contrib import admin
from .models import SystemLog, TelemetrySample

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "device", "level", "source", "event_id")
    list_filter = ("level", "source")
    search_fields = ("message", "device__name", "device__ip_address")

@admin.register(TelemetrySample)
class TelemetrySampleAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "device", "cpu", "ram", "disk", "risk_level", "risk_score")
    list_filter = ("risk_level",)
