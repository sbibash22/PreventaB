from __future__ import annotations

import getpass
import os
import socket
import time
import platform

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from devices.models import Device
from telemetry.services.collector import collect_and_store
from alerts.models import SystemSetting


User = get_user_model()


def _local_ip() -> str:
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception:
        return "127.0.0.1"


class Command(BaseCommand):
    help = "Collect local Windows metrics/logs and store them for demo purposes."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Collect only once and exit")
        parser.add_argument("--interval", type=int, default=0, help="Seconds between collections (overrides SystemSettings if >0)")
        parser.add_argument("--events", type=int, default=30, help="Max Windows events to ingest per run")

    def handle(self, *args, **options):
        # Device naming: prefer env, else computer name.
        device_name = os.getenv("DEMO_DEVICE_NAME") or platform.node() or "Windows Device"

        # If you want exactly: HP Envy x360
        # set DEMO_DEVICE_NAME=HP Envy x360 in your .env

        ip = os.getenv("DEMO_DEVICE_IP") or _local_ip()
        os_type = "WINDOWS"

        device, created = Device.objects.get_or_create(
            name=device_name,
            defaults={
                "ip_address": ip,
                "os_type": os_type,
                "monitoring_enabled": True,
                "risk_profile": "MEDIUM",
            },
        )

        # Ensure key properties stay updated
        if not created:
            changed = False
            if device.ip_address != ip:
                device.ip_address = ip
                changed = True
            if device.os_type != os_type:
                device.os_type = os_type
                changed = True
            if changed:
                device.save(update_fields=["ip_address", "os_type"])

        # Assign to first admin user (or superuser) so it shows in UI
        admin_user = User.objects.filter(role="ADMIN").first() or User.objects.filter(is_superuser=True).first()
        if admin_user:
            device.assigned_users.add(admin_user)

        self.stdout.write(self.style.SUCCESS(f"Using device: {device.name} ({device.ip_address}) api_key={device.api_key[:8]}..."))
        self.stdout.write(self.style.SUCCESS(f"Logged in Windows user: {getpass.getuser()}"))

        # Interval
        interval = int(options.get("interval") or 0)
        if interval <= 0:
            interval = SystemSetting.get_solo().collection_interval_seconds

        once = bool(options.get("once"))
        max_events = int(options.get("events") or 30)

        while True:
            sample = collect_and_store(device=device, max_events=max_events)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Collected: cpu={sample.cpu:.1f}% ram={sample.ram:.1f}% disk={sample.disk:.1f}% risk={sample.risk_level}({sample.risk_score:.2f})"
                )
            )
            if once:
                break
            time.sleep(interval)
