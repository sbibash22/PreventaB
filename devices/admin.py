from django.contrib import admin
from .models import Device

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "os_type", "monitoring_enabled", "is_online", "last_seen")
    search_fields = ("name", "ip_address")
    list_filter = ("os_type", "monitoring_enabled", "is_online")
