# core/user_urls.py
from django.urls import path
from core import views as core_views

urlpatterns = [
    path("", core_views.user_dashboard, name="user_dashboard"),
    path("dashboard/", core_views.user_dashboard, name="user_dashboard"),
]
