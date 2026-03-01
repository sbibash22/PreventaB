from django.urls import path
from . import views

urlpatterns = [
    path("notifications/", views.notifications_list, name="notifications_list"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),

    path("admin/send/", views.send_alert, name="send_alert"),
    path("admin/history/", views.alert_history, name="alert_history"),
    path("admin/alert-settings/", views.alert_settings, name="alert_settings"),
    path("admin/system-settings/", views.system_settings, name="system_settings"),
    path("admin/ack/<int:pk>/", views.ack_alert_admin, name="ack_alert_admin"),

    path("user/", views.user_alerts, name="user_alerts"),
    path("user/ack/<int:pk>/", views.ack_alert_user, name="ack_alert_user"),
    path("user/settings/", views.user_settings, name="user_settings"),
]
