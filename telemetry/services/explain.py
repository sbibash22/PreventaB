# telemetry/services/explain.py
from __future__ import annotations
from collections import Counter
from typing import List, Dict, Any


def _safe_float(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def build_xai_report(samples: List[Any], logs: List[Any] | None = None) -> Dict[str, Any]:
    """
    Create a simple explainable report from telemetry + logs.
    Works even if model fields vary slightly (cpu vs cpu_usage, timestamp vs created_at).
    """

    if not samples:
        return {
            "headline": "No telemetry data available yet.",
            "summary": "Run the collector to start collecting CPU/RAM/Disk usage.",
            "bullets": [],
            "actions": ["Run the collector: python manage.py run_collector --once --events 30"],
            "latest": {},
            "log_stats": {"errors": 0, "warnings": 0},
        }

    def get_attr(obj, names, default=None):
        for n in names:
            if hasattr(obj, n):
                return getattr(obj, n)
        return default

    # Extract numeric series
    cpu_vals, ram_vals, disk_vals = [], [], []
    for s in samples:
        cpu_vals.append(_safe_float(get_attr(s, ["cpu", "cpu_usage"]), 0.0))
        ram_vals.append(_safe_float(get_attr(s, ["ram", "ram_usage"]), 0.0))
        disk_vals.append(_safe_float(get_attr(s, ["disk", "disk_usage"]), 0.0))

    latest_cpu = cpu_vals[-1]
    latest_ram = ram_vals[-1]
    latest_disk = disk_vals[-1]

    avg_cpu = sum(cpu_vals) / max(len(cpu_vals), 1)
    avg_ram = sum(ram_vals) / max(len(ram_vals), 1)
    avg_disk = sum(disk_vals) / max(len(disk_vals), 1)

    # Trend (compare early window vs recent window)
    k = min(3, len(cpu_vals))
    early_cpu = sum(cpu_vals[:k]) / max(k, 1)
    late_cpu = sum(cpu_vals[-k:]) / max(k, 1)

    early_ram = sum(ram_vals[:k]) / max(k, 1)
    late_ram = sum(ram_vals[-k:]) / max(k, 1)

    early_disk = sum(disk_vals[:k]) / max(k, 1)
    late_disk = sum(disk_vals[-k:]) / max(k, 1)

    def trend_label(early, late, tol=3.0):
        if late > early + tol:
            return "increasing"
        if late < early - tol:
            return "decreasing"
        return "stable"

    cpu_trend = trend_label(early_cpu, late_cpu, tol=5.0)
    ram_trend = trend_label(early_ram, late_ram, tol=3.0)
    disk_trend = trend_label(early_disk, late_disk, tol=2.0)

    # Spikes detection
    max_cpu = max(cpu_vals) if cpu_vals else 0
    max_ram = max(ram_vals) if ram_vals else 0

    # Logs signals (optional)
    errors = warnings = 0
    top_sources = []
    if logs:
        lvl_counts = Counter((getattr(l, "level", "") or "").upper() for l in logs)
        errors = lvl_counts.get("ERROR", 0) + lvl_counts.get("CRITICAL", 0)
        warnings = lvl_counts.get("WARNING", 0)

        src_counts = Counter((getattr(l, "source", "") or "").strip() for l in logs if getattr(l, "source", None))
        top_sources = [s for s, _ in src_counts.most_common(2) if s]

    # Build human explanations
    bullets = []
    actions = []

    # CPU explanation
    if avg_cpu < 25:
        bullets.append(f"CPU usage is generally low (avg ~{avg_cpu:.1f}%). This is normal for everyday use.")
    elif avg_cpu < 60:
        bullets.append(f"CPU usage is moderate (avg ~{avg_cpu:.1f}%). The device is working but not overloaded.")
    else:
        bullets.append(f"CPU usage is high (avg ~{avg_cpu:.1f}%). This can cause lag and heat.")

    if max_cpu >= 80:
        bullets.append(f"There were CPU spikes up to ~{max_cpu:.1f}%. Spikes often happen during updates, scans, or heavy apps.")
        actions.append("Check Task Manager for apps causing high CPU (browser tabs, antivirus scan, Windows updates).")

    bullets.append(f"CPU trend is **{cpu_trend}** across recent samples.")

    # RAM explanation
    if avg_ram < 70:
        bullets.append(f"RAM usage is healthy (avg ~{avg_ram:.1f}%).")
    elif avg_ram < 85:
        bullets.append(f"RAM usage is elevated (avg ~{avg_ram:.1f}%). You may feel slowdowns with many apps open.")
        actions.append("Close unused apps/tabs. Disable unnecessary startup programs.")
    else:
        bullets.append(f"RAM usage is high (avg ~{avg_ram:.1f}%). This can slow the system and increase failure risk.")
        actions.append("Close heavy apps, restart the PC, and reduce startup background apps.")
        actions.append("If RAM stays high, consider checking for malware or memory-heavy processes.")

    if max_ram >= 90:
        bullets.append(f"RAM reached ~{max_ram:.1f}% at peak, meaning memory pressure is strong.")
    bullets.append(f"RAM trend is **{ram_trend}** across recent samples.")

    # Disk explanation
    if avg_disk < 70:
        bullets.append(f"Disk usage looks safe (avg ~{avg_disk:.1f}%). Storage pressure is not a concern.")
    elif avg_disk < 90:
        bullets.append(f"Disk usage is getting higher (avg ~{avg_disk:.1f}%). Keep some free space to maintain performance.")
        actions.append("Free space: remove large files, empty recycle bin, uninstall unused apps.")
    else:
        bullets.append(f"Disk usage is very high (avg ~{avg_disk:.1f}%). Low free space can cause Windows errors and update failures.")
        actions.append("Free disk space urgently (aim for at least 15–20% free).")

    bullets.append(f"Disk trend is **{disk_trend}** across recent samples.")

    # Logs explanation
    if logs is not None:
        if errors or warnings:
            bullets.append(f"Recent system logs include {errors} error(s) and {warnings} warning(s). These often correlate with higher risk.")
            if top_sources:
                bullets.append(f"Most common log sources: {', '.join(top_sources)}.")
            actions.append("Review error logs for repeating issues and apply fixes (drivers, updates, services).")
        else:
            bullets.append("No recent WARNING/ERROR logs detected in the selected window.")

    # Short summary headline
    headline_parts = []
    if avg_ram >= 85:
        headline_parts.append("High RAM pressure is the main risk driver.")
    if max_cpu >= 80:
        headline_parts.append("CPU spikes were detected.")
    if avg_disk >= 90:
        headline_parts.append("Disk is critically full.")
    if not headline_parts:
        headline_parts.append("System health looks stable based on recent telemetry.")

    summary = " ".join(headline_parts)

    if not actions:
        actions = ["Continue monitoring. If risk rises, check logs and running applications."]

    return {
        "headline": summary,
        "summary": "This explanation is based on recent telemetry patterns (CPU/RAM/Disk) + log signals.",
        "bullets": bullets,
        "actions": actions[:5],
        "latest": {
            "cpu": latest_cpu,
            "ram": latest_ram,
            "disk": latest_disk,
        },
        "log_stats": {"errors": errors, "warnings": warnings},
    }