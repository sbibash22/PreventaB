import secrets, string
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _bcc_admin():
    return [settings.EMAIL_HOST_USER] if getattr(settings, "EMAIL_HOST_USER", "") else []


def send_account_setup_email(request, user) -> int:
    """
    Sends a secure setup link so the user sets their own password.
    Returns number of messages sent (1 = success).
    """
    to_email = (user.email or "").strip()
    if not to_email:
        return 0

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    path = reverse("account_set_password", kwargs={"uidb64": uid, "token": token})
    setup_link = request.build_absolute_uri(path)

    subject = "Set up your PreventaB account"
    text_body = (
        f"Hello {user.username},\n\n"
        f"Your PreventaB account has been created.\n\n"
        f"Please set your password using this secure link:\n"
        f"{setup_link}\n\n"
        f"If you did not expect this email, you can ignore it.\n\n"
        f"Regards,\nPreventaB"
    )

    html_body = f"""
    <p>Hello <b>{user.username}</b>,</p>
    <p>Your <b>PreventaB</b> account has been created.</p>
    <p>Please set your password using this secure link:</p>
    <p><a href="{setup_link}">{setup_link}</a></p>
    <p>If you did not expect this email, you can ignore it.</p>
    <p>Regards,<br>PreventaB</p>
    """

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
        bcc=_bcc_admin(),
    )
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def send_password_reset_email(request, user) -> int:
    """
    Sends a secure password reset link.
    """
    to_email = (user.email or "").strip()
    if not to_email:
        return 0

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    path = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    reset_link = request.build_absolute_uri(path)

    subject = "Reset your PreventaB password"
    text_body = (
        f"Hello {user.username},\n\n"
        f"You requested a password reset.\n\n"
        f"Reset your password using this secure link:\n"
        f"{reset_link}\n\n"
        f"If you did not request this, ignore this email.\n\n"
        f"Regards,\nPreventaB"
    )

    html_body = f"""
    <p>Hello <b>{user.username}</b>,</p>
    <p>You requested a password reset.</p>
    <p>Click this secure link to reset your password:</p>
    <p><a href="{reset_link}">{reset_link}</a></p>
    <p>If you did not request this, you can ignore this email.</p>
    <p>Regards,<br>PreventaB</p>
    """

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
        bcc=_bcc_admin(),
    )
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)