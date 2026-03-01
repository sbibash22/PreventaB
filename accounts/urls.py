# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("admin/users/", views.user_list, name="user_list"),
    path("admin/users/add/", views.user_add, name="user_add"),
    path("admin/users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("admin/users/<int:pk>/delete/", views.user_delete, name="user_delete"),

    path("set-password/<uidb64>/<token>/", views.set_password_view, name="account_set_password"),

    # Reset password (forgot password)
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
]