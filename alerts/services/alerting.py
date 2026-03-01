from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings

from alerts.models import Alert, Notification, AlertSetting

def create_notification(user, title, body, link=""):
    Notification.objects.create(user=user, title=title, body=body, link=link)

def send_alert_email(users, subject, message):
    emails = [u.email for u in users if u.email]
    if not emails:
        return False
    EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, emails).send(fail_silently=False)
    return True

def maybe_raise_risk_alert(device, risk_level, risk_score, sample=None):
    cfg = AlertSetting.get_solo()
    if risk_level == "LOW":
        return None

    # cooldown check
    cooldown_since = timezone.now() - timezone.timedelta(minutes=cfg.cooldown_minutes)
    existing = Alert.objects.filter(device=device, created_at__gte=cooldown_since, status="OPEN").first()
    if existing:
        return existing

    recipients = list(device.assigned_users.all())
    if not recipients:
        return None

    subject = f"[{risk_level}] Risk detected on {device.name}"
    msg = f"Device: {device.name} ({device.ip_address})\nRisk: {risk_level}\nScore: {risk_score:.2f}\n\nPlease check logs and take action."

    alert = Alert.objects.create(
        device=device,
        risk_level=risk_level,
        subject=subject,
        message=msg,
        created_by=None,
        require_password=False,
    )
    alert.recipients.set(recipients)

    for u in recipients:
        create_notification(u, title=subject, body=msg, link="/alerts/user/")

    if cfg.email_on_high and risk_level == "HIGH":
        sent = send_alert_email(recipients, subject, msg)
        alert.sent_email = sent
        alert.save(update_fields=["sent_email"])

    return alert
