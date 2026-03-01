# core/admin_urls.py
from django.urls import path
from core import views as core_views

urlpatterns = [
    path("", core_views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/", core_views.admin_dashboard, name="admin_dashboard"),
]
