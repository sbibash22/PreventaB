"""
PreventaB - PDF reporting utilities (Admin "Send Reports")

TEXT-ONLY PDF (no charts, no Kaggle content).

Includes:
1) Device Summary
2) Risk Level Summary
3) Telemetry Usage
4) Logs Found & Log Usage
5) Explainable AI (XAI) Report (uses telemetry.services.explain.build_xai_report)

Fixes:
- TypeError: build_device_report_pdf() takes 0 positional arguments...
  -> Accepts an optional positional `request` as first arg to stay compatible with your view call.
- TypeError: expected str, bytes or os.PathLike object, not ImageReader
  -> No ReportLab Image/ImageReader usage anymore.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Iterable, List, Dict
from xml.sax.saxutils import escape

from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT

from devices.models import Device
from accounts.models import User
from telemetry.models import TelemetrySample, SystemLog
from telemetry.services.explain import build_xai_report


@dataclass
class ReportWindow:
    days: int = 7
    max_telemetry_points: int = 2000
    max_logs: int = 250
    max_log_highlights: int = 12
    max_xai_samples: int = 200  # send last N telemetry samples into XAI generator


def _safe_text(v, default: str = "-") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _fmt_dt(dt) -> str:
    if not dt:
        return "-"
    try:
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return str(dt)


def _mean(values: Iterable[Optional[float]]) -> float:
    vals = [float(v) for v in values if v is not None]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _max(values: Iterable[Optional[float]]) -> float:
    vals = [float(v) for v in values if v is not None]
    return float(max(vals)) if vals else 0.0


def _level_bucket(level: Optional[str]) -> str:
    s = (level or "").strip().upper()
    if s in {"CRITICAL", "ERROR", "WARNING", "INFO"}:
        return s
    return "OTHER"


def _bullet_block(items: List[str], style) -> Paragraph:
    if not items:
        return Paragraph("• -", style)
    html = "<br/>".join([f"• {escape(str(x))}" for x in items])
    return Paragraph(html, style)


def build_device_report_pdf(
    request=None,  # keeps compatibility if your view calls build_device_report_pdf(request, ...)
    *,
    user: User,
    device: Device,
    window: ReportWindow = ReportWindow(),
) -> bytes:
    """
    Build a PDF report for one user + one device and return PDF bytes.
    """
    now = timezone.now()
    since = now - timedelta(days=int(window.days))

    # Telemetry
    telemetry_qs = (
        TelemetrySample.objects
        .filter(device=device, timestamp__gte=since)
        .order_by("-timestamp")[: int(window.max_telemetry_points)]
    )
    telemetry_rows = list(reversed(list(telemetry_qs)))  # chronological

    # Logs
    logs_qs = (
        SystemLog.objects
        .filter(device=device, timestamp__gte=since)
        .order_by("-timestamp")[: int(window.max_logs)]
    )
    log_rows = list(logs_qs)

    # Risk stats
    telemetry_count = len(telemetry_rows)

    if telemetry_count:
        last = telemetry_rows[-1]
        last_risk = float(last.risk_score or 0.0)
        last_level = _safe_text(last.risk_level, "N/A")

        risk_scores = [s.risk_score for s in telemetry_rows]
        avg_risk = _mean(risk_scores)
        peak_risk = _max(risk_scores)

        dist: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for s in telemetry_rows:
            lvl = _safe_text(s.risk_level, "OTHER").upper()
            if lvl not in dist:
                dist[lvl] = 0
            dist[lvl] += 1
    else:
        last_risk = 0.0
        last_level = "N/A"
        avg_risk = 0.0
        peak_risk = 0.0
        dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}

    # Telemetry usage stats
    avg_cpu = _mean([s.cpu for s in telemetry_rows])
    avg_ram = _mean([s.ram for s in telemetry_rows])
    avg_disk = _mean([s.disk for s in telemetry_rows])

    peak_cpu = _max([s.cpu for s in telemetry_rows])
    peak_ram = _max([s.ram for s in telemetry_rows])
    peak_disk = _max([s.disk for s in telemetry_rows])

    # Adjust these field names if your TelemetrySample model differs
    avg_critical = _mean([getattr(s, "critical_count_1h", 0) for s in telemetry_rows])
    avg_error = _mean([getattr(s, "error_count_1h", 0) for s in telemetry_rows])
    avg_warning = _mean([getattr(s, "warning_count_1h", 0) for s in telemetry_rows])

    peak_critical = _max([getattr(s, "critical_count_1h", 0) for s in telemetry_rows])
    peak_error = _max([getattr(s, "error_count_1h", 0) for s in telemetry_rows])
    peak_warning = _max([getattr(s, "warning_count_1h", 0) for s in telemetry_rows])

    # Log stats
    log_total = len(log_rows)
    log_levels = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0, "OTHER": 0}
    for l in log_rows:
        log_levels[_level_bucket(getattr(l, "level", None))] += 1

    # XAI block
    xai_block = None
    if telemetry_rows:
        samples_for_xai = telemetry_rows[-int(min(window.max_xai_samples, len(telemetry_rows))):]
        try:
            xai_block = build_xai_report(samples_for_xai, log_rows)
        except Exception:
            xai_block = None

    # Build PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title="PreventaB Device Report"
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    h2 = styles["Heading2"]
    body = ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
        alignment=TA_LEFT,
    )
    small = ParagraphStyle(
        name="Small",
        parent=body,
        fontSize=9,
        leading=12,
    )

    story = []

    # Header
    story.append(Paragraph("PreventaB — Device Telemetry & Risk Report", title_style))
    story.append(Paragraph("Explainable AI for Computer System Failure Prediction & Prevention", body))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>Generated:</b> {escape(_fmt_dt(now))}", body))
    story.append(Paragraph(
        f"<b>Recipient:</b> {escape(_safe_text(user.get_full_name() or user.username))} "
        f"({escape(_safe_text(user.email))})",
        body
    ))
    story.append(Paragraph(
        f"<b>Reporting window:</b> Last {int(window.days)} day(s) "
        f"(since {escape(_fmt_dt(since))})",
        body
    ))
    story.append(Spacer(1, 14))

    # 1) Device Summary
    story.append(Paragraph("1) Device Summary", h2))
    story.append(Paragraph(f"<b>Device Name:</b> {escape(_safe_text(device.name))}", body))
    story.append(Paragraph(f"<b>Operating System:</b> {escape(_safe_text(device.os_type))}", body))
    story.append(Paragraph(f"<b>IP Address:</b> {escape(_safe_text(device.ip_address))}", body))
    story.append(Paragraph(f"<b>Risk Profile:</b> {escape(_safe_text(device.risk_profile))}", body))
    story.append(Paragraph(f"<b>Online Status:</b> {'Yes' if device.is_online else 'No'}", body))
    story.append(Paragraph(f"<b>Last Seen:</b> {escape(_fmt_dt(device.last_seen))}", body))
    story.append(Spacer(1, 12))

    # 2) Risk Level Summary
    story.append(Paragraph("2) Risk Level Summary", h2))
    story.append(Paragraph(
        f"This device has <b>{telemetry_count}</b> telemetry sample(s) in the selected window. "
        f"The latest recorded risk is <b>{last_risk:.3f}</b> and the current risk level is "
        f"<b>{escape(last_level)}</b>. Across the reporting period, the average risk is "
        f"<b>{avg_risk:.3f}</b> and the peak risk reached <b>{peak_risk:.3f}</b>.",
        body
    ))
    dist_str = ", ".join([f"{k}: {int(v)}" for k, v in dist.items()])
    story.append(Paragraph(f"Risk-level distribution in this window is: <b>{escape(dist_str)}</b>.", body))
    story.append(Spacer(1, 12))

    # 3) Telemetry Usage
    story.append(Paragraph("3) Telemetry Usage", h2))
    if telemetry_count:
        story.append(Paragraph(
            "Resource metrics were summarised from the device's telemetry stream. "
            f"Average utilisation over the window was: "
            f"<b>CPU {avg_cpu:.1f}%</b>, <b>RAM {avg_ram:.1f}%</b>, and <b>Disk {avg_disk:.1f}%</b>. "
            f"Peak observed values were: <b>CPU {peak_cpu:.1f}%</b>, <b>RAM {peak_ram:.1f}%</b>, "
            f"and <b>Disk {peak_disk:.1f}%</b>. "
            "These values reflect operational load and are used by PreventaB to estimate failure risk.",
            body
        ))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Log-derived counters linked to telemetry were also summarised. "
            f"Average hourly counts were: <b>CRITICAL {avg_critical:.1f}</b>, "
            f"<b>ERROR {avg_error:.1f}</b>, <b>WARNING {avg_warning:.1f}</b>. "
            f"Peak hourly counts were: <b>CRITICAL {peak_critical:.0f}</b>, "
            f"<b>ERROR {peak_error:.0f}</b>, <b>WARNING {peak_warning:.0f}</b>.",
            body
        ))
    else:
        story.append(Paragraph(
            "No telemetry samples were found in the selected reporting window, so utilisation and risk trends "
            "cannot be summarised for this period.",
            body
        ))
    story.append(Spacer(1, 12))

    # 4) Logs Found & Log Usage
    story.append(Paragraph("4) Logs Found & Log Usage", h2))
    if log_total:
        lvl_parts = [f"{k}: {v}" for k, v in log_levels.items() if int(v) > 0]
        story.append(Paragraph(
            f"A total of <b>{log_total}</b> log entr{'y' if log_total == 1 else 'ies'} were detected in the reporting window. "
            f"Severity breakdown is: <b>{escape(', '.join(lvl_parts) if lvl_parts else 'No classified logs')}</b>. "
            "Frequent ERROR/CRITICAL events can indicate instability (driver issues, service crashes, disk problems) "
            "and may correlate with elevated failure risk.",
            body
        ))

        story.append(Spacer(1, 8))
        story.append(Paragraph("Recent log highlights (most recent first):", body))

        highlights = []
        for l in log_rows[: int(window.max_log_highlights)]:
            ts = _fmt_dt(getattr(l, "timestamp", None))
            lvl = _safe_text(getattr(l, "level", None), "OTHER")
            src = _safe_text(getattr(l, "source", None), "-")
            msg = _safe_text(getattr(l, "message", None), "-")
            if len(msg) > 180:
                msg = msg[:180].rstrip() + "..."
            highlights.append(f"{ts} — {lvl} — {src}: {msg}")

        story.append(_bullet_block(highlights, small))
    else:
        story.append(Paragraph(
            "No system logs were found in the selected reporting window for this device.",
            body
        ))
    story.append(Spacer(1, 12))

    # 5) Explainable AI (XAI) Report — matches dashboard layout
    story.append(Paragraph("5) Explainable AI (XAI) Report", h2))
    if not xai_block:
        story.append(Paragraph(
            "No explainability report was generated for this window. This usually occurs when there are no telemetry "
            "samples available, or when the explainability service cannot compute insights for the selected period.",
            body
        ))
    else:
        # ── Summary line (matches dashboard: xai_report.summary) ──
        summary = _safe_text(xai_block.get("summary"))
        story.append(Paragraph(f"{escape(summary)}", body))
        story.append(Spacer(1, 6))

        # ── Latest telemetry snapshot (matches dashboard: CPU · RAM · Disk) ──
        latest = xai_block.get("latest")
        if latest and isinstance(latest, dict):
            latest_cpu = latest.get("cpu", 0)
            latest_ram = latest.get("ram", 0)
            latest_disk = latest.get("disk", 0)
            story.append(Paragraph(
                f"<b>Latest:</b> CPU {float(latest_cpu):.1f}% · "
                f"RAM {float(latest_ram):.1f}% · "
                f"Disk {float(latest_disk):.1f}%",
                body
            ))
            story.append(Spacer(1, 6))

        # ── Headline (matches dashboard: xai_report.headline) ──
        headline = _safe_text(xai_block.get("headline"))
        story.append(Paragraph(f"<b>{escape(headline)}</b>", body))
        story.append(Spacer(1, 10))

        # ── What we observed (matches dashboard: xai_report.bullets) ──
        bullets = xai_block.get("bullets") or []
        if bullets:
            story.append(Paragraph("<b>What we observed</b>", body))
            story.append(_bullet_block([str(b) for b in bullets], small))
            story.append(Spacer(1, 8))

        # ── Recommended actions (matches dashboard: xai_report.actions) ──
        actions = xai_block.get("actions") or []
        if actions:
            story.append(Paragraph("<b>Recommended actions</b>", body))
            story.append(_bullet_block([str(a) for a in actions], small))
            story.append(Spacer(1, 8))

        # ── Log signals (matches dashboard: xai_report.log_stats) ──
        log_stats = xai_block.get("log_stats")
        if log_stats and isinstance(log_stats, dict):
            errors = log_stats.get("errors", 0)
            warnings = log_stats.get("warnings", 0)
            story.append(Paragraph(
                f"<b>Log signals:</b> {errors} error(s), {warnings} warning(s).",
                small
            ))
            story.append(Spacer(1, 6))

        # ── Additional XAI fields (keep existing extras if present) ──
        why = xai_block.get("why")
        if why:
            story.append(Paragraph(f"<b>Why this matters:</b> {escape(_safe_text(why))}", body))
            story.append(Spacer(1, 6))

        risk_bucket = xai_block.get("risk_bucket")
        xai_window = xai_block.get("window")
        sample_count = xai_block.get("sample_count")
        last_r = xai_block.get("last_risk")

        meta_parts = []
        if risk_bucket:
            meta_parts.append(f"Risk bucket: {escape(_safe_text(risk_bucket))}")
        if xai_window:
            meta_parts.append(f"Window: {escape(_safe_text(xai_window))}")
        if sample_count:
            meta_parts.append(f"Samples analysed: {escape(_safe_text(sample_count))}")
        if last_r is not None:
            try:
                meta_parts.append(f"Latest risk score: {float(last_r):.3f}")
            except Exception:
                meta_parts.append(f"Latest risk score: {escape(_safe_text(last_r))}")

        if meta_parts:
            story.append(Paragraph(f"<b>{' | '.join(meta_parts)}</b>", small))
            story.append(Spacer(1, 6))

        # ── Key signals (fallback if bullets not present but signals exist) ──
        signals = xai_block.get("signals") or []
        if signals and not bullets:
            story.append(Paragraph("<b>Key signals detected:</b>", body))
            story.append(_bullet_block([str(s) for s in signals], small))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "This report is generated by PreventaB for operational visibility and preventive maintenance planning.",
        body
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()