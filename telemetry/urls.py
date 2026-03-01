from django.urls import path
from . import views

urlpatterns = [
    path("logs/", views.logs_view, name="logs_view"),
    path("admin/risk/", views.risk_analytics, name="risk_analytics"),
]
