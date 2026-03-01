from django.urls import path
from . import views

urlpatterns = [
    path("admin/", views.device_list, name="device_list"),
    path("admin/add/", views.device_add, name="device_add"),
    path("admin/<int:pk>/", views.device_detail, name="device_detail"),
    path("admin/<int:pk>/edit/", views.device_edit, name="device_edit"),
    path("admin/<int:pk>/delete/", views.device_delete, name="device_delete"),
]
