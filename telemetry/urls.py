from django.urls import path, include
from . import views

urlpatterns = [
    path("logs/", views.logs_view, name="logs_view"),
    path("admin/risk/", views.risk_analytics, name="risk_analytics"),

    # Agent ingestion endpoint (POST)
    path("agent/", include("telemetry.agent_urls")),
    # Admin: PDF report sending
    path("admin/reports/", views.send_reports, name="send_reports"),
    path("admin/reports/send/<int:user_id>/<int:device_id>/", views.send_report, name="send_report"),
]
