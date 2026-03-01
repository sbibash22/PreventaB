from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("USER", "User"),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="USER")

    def is_admin(self):
        return self.role == "ADMIN" or self.is_superuser

    def save(self, *args, **kwargs):
        # Keep Django staff flag aligned with role so admin pages work consistently.
        self.is_staff = self.is_admin()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


from django.conf import settings
from devices.models import Device

class UserPreference(models.Model):
    """Per-user settings shown in the User Portal > Settings page."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference")

    # Notifications
    inapp_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    notify_on_medium = models.BooleanField(default=False)
    notify_on_high = models.BooleanField(default=True)

    # UX
    timezone = models.CharField(max_length=64, default="UTC")
    default_device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    compact_sidebar = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences({self.user.username})"
