from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from core.views import admin_required
from .forms import LoginForm, AdminUserForm, PasswordResetRequestForm
from .services import send_account_setup_email, send_password_reset_email

User = get_user_model()


def route_after_login(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("admin_dashboard" if request.user.is_admin() else "user_dashboard")


def login_view(request):
    """
    Login using username OR email. Redirects by role.
    """
    if request.user.is_authenticated:
        return route_after_login(request)

    prefill_username = request.GET.get("u", "")
    form = LoginForm(request.POST or None, initial={"username": prefill_username})
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]

        # 1) Try username
        user = authenticate(request, username=identifier, password=password)

        # 2) Try email -> map to username
        if user is None:
            u = User.objects.filter(email__iexact=identifier).first()
            if u:
                user = authenticate(request, username=u.username, password=password)

        if user is None:
            messages.error(request, "Invalid username/email or password.")
            return render(request, "auth/login.html", {"form": form, "next": next_url})

        login(request, user)

        # Safe next redirect
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            if user.is_admin() and next_url.startswith("/admin/"):
                return redirect(next_url)
            if (not user.is_admin()) and next_url.startswith("/user/"):
                return redirect(next_url)

        return route_after_login(request)

    return render(request, "auth/login.html", {"form": form, "next": next_url})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ----------------------------
# Admin: User Management CRUD
# ----------------------------

@login_required
@admin_required
def user_list(request):
    users = User.objects.all().order_by("username")
    return render(request, "admin/user_list.html", {"page_title": "User Management", "users": users})


@login_required
@admin_required
def user_add(request):
    form = AdminUserForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.set_unusable_password()   # force email setup link
        user.is_staff = (user.role == "ADMIN")
        user.save()

        devices = form.cleaned_data.get("devices")
        if devices is not None:
            user.devices.set(devices)

        try:
            sent = send_account_setup_email(request, user)
            if sent == 1:
                messages.success(request, f"User created and setup email sent to {user.email}.")
            else:
                messages.warning(request, "User created but email not sent (missing email).")
        except Exception as e:
            messages.warning(request, f"User created but email failed: {e}")

        return redirect("user_list")

    return render(request, "admin/user_form.html", {"page_title": "Add User", "form": form})


@login_required
@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = AdminUserForm(request.POST or None, instance=user)

    if request.method == "POST" and form.is_valid():
        edited = form.save(commit=False)
        edited.is_staff = (edited.role == "ADMIN")
        edited.save()
        edited.devices.set(form.cleaned_data.get("devices"))
        messages.success(request, "User updated.")
        return redirect("user_list")

    return render(request, "admin/user_form.html", {"page_title": "Edit User", "form": form})


@login_required
@admin_required
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        if user.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account while logged in.")
            return redirect("user_list")

        user.delete()
        messages.success(request, "User deleted.")
        return redirect("user_list")

    return render(request, "admin/confirm_delete.html", {"page_title": "Delete User", "object": user, "back_url": "user_list"})


# ----------------------------
# Password setup via email link
# ----------------------------

def set_password_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "This password setup link is invalid or expired.")
        return redirect("login")

    form = SetPasswordForm(user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Password set successfully. Please login.")
        return redirect(f"{reverse('login')}?u={user.username}")

    return render(request, "auth/set_password.html", {"form": form, "page_title": "Set Password", "username_hint": user.username})


# ----------------------------
# Forgot password flow
# ----------------------------

def password_reset_request(request):
    """
    Enter email/username -> send reset link if account exists.
    Always show success message (avoid account enumeration).
    """
    if request.user.is_authenticated:
        return route_after_login(request)

    form = PasswordResetRequestForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"].strip()
        user = User.objects.filter(username__iexact=identifier).first()
        if user is None:
            user = User.objects.filter(email__iexact=identifier).first()

        if user and user.email:
            try:
                send_password_reset_email(request, user)
            except Exception:
                pass

        messages.success(request, "If an account exists, a reset link has been sent to the email.")
        return redirect("login")

    return render(request, "auth/password_reset_request.html", {"form": form, "page_title": "Reset Password"})


def password_reset_confirm(request, uidb64, token):
    """
    Link from email -> SetPasswordForm -> saves hashed password.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "This password reset link is invalid or expired.")
        return redirect("password_reset_request")

    form = SetPasswordForm(user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Password reset successful. Please login.")
        return redirect(f"{reverse('login')}?u={user.username}")

    return render(request, "auth/password_reset_confirm.html", {
        "form": form,
        "page_title": "Set New Password",
        "username_hint": user.username,
    })