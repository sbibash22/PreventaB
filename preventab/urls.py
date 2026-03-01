from django.contrib import admin
from django.urls import path, include
from accounts.views import login_view, logout_view, route_after_login
from core.views import about

urlpatterns = [
    path("admin-django/", admin.site.urls),

    path("", route_after_login, name="route_after_login"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    path("admin/", include("core.admin_urls")),
    path("user/", include("core.user_urls")),

    path("accounts/", include("accounts.urls")),
    path("devices/", include("devices.urls")),
    path("telemetry/", include("telemetry.urls")),
    path("alerts/", include("alerts.urls")),
    path("about/", about, name="about"),
]