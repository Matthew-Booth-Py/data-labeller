import uuid
import secrets
from typing import ClassVar
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from backend.users.managers import UserManager
from django.contrib.auth.models import AbstractUser
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext_lazy as _


def upload_user_profile_image(instance, filename):
    user_id = str(instance.id)
    file_extension = filename.split('.')[-1]
    return f"{user_id}/profile_image.{file_extension}"


class User(AbstractUser):
    """
    Custom user model for a generic Django application.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """
    USER_GENDERS = [
        ('male', _("Male")),
        ('female', _("Female")),
        ('other', _("Other")),
    ]


    # Unique identifier
    id = models.UUIDField(_("ID"), primary_key=True, default=uuid.uuid4, editable=False, help_text=_("Unique identifier for the user."))

    # Personal Information
    first_name = models.CharField(_("First Name"), max_length=250, blank=True, help_text=_("Your first name."))
    last_name = models.CharField(_("Last Name"), max_length=250, blank=True, help_text=_("Your last name."))
    date_of_birth = models.DateField(_("Date of Birth"), blank=True, null=True, help_text=_("Your date of birth for age verification and personalization."))
    gender = models.CharField(_("Gender"), max_length=10, choices=USER_GENDERS, blank=True, help_text=_("Your gender identity."))

    # Contact Information
    email = models.EmailField(_("Email Address"), unique=True, help_text=_("Your email address, used for login."))
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, help_text=_("Your contact phone number."))

    # Profile Information
    profile_image = models.ImageField(_("Profile Image"), upload_to=upload_user_profile_image, blank=True, null=True, help_text=_("Upload a profile image."))
    bio = models.TextField(_("Bio"), blank=True, help_text=_("A short description about yourself."))
    website = models.URLField(_("Website"), blank=True, help_text=_("Your personal or professional website URL."))

    # Preferences
    platform_language = models.CharField(_("Platform Language"),choices=settings.LANGUAGES,max_length=5,default='en',help_text=_("The language you prefer for the platform interface."))
    timezone = models.CharField(_("Timezone"), max_length=200, default='Europe/London', help_text=_("Your preferred timezone for displaying dates and times."))

    # Notifications Settings
    email_notifications = models.BooleanField(_("Email Notifications"), default=True, help_text=_("Receive notifications via email."))
    push_notifications = models.BooleanField(_("Push Notifications"), default=True, help_text=_("Receive push notifications in your browser."))
    marketing_emails = models.BooleanField(_("Marketing Emails"), default=False, help_text=_("Receive promotional and marketing emails."))
    security_alerts = models.BooleanField(_("Security Alerts"), default=True, help_text=_("Important security and account alerts."))

    username = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def __str__(self) -> str:
        return self.email
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def initials(self) -> str:
        initials = ''

        if self.first_name:
            initials += self.first_name[0].upper()
            
        if self.last_name:
            initials += self.last_name[0].upper()
            
        return initials or self.email[0].upper()
    
    @property
    def unread_notifications_count(self) -> int:
        return self.notifications.filter(is_read=False).count()
    
    @property
    def latest_notifications(self):
        return self.notifications.all().order_by('-created_at')[:5]
    

    def send_notification(self, message: str, importance: str = 'standard', action_link: str = '') -> None:
        """
        Send a notification to the user.
        """
        Notification.objects.create(
            user=self,
            message=message,
            importance=importance,
            action_link=action_link
        )


    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['email']
        indexes = [
            models.Index(fields=['email'], name='user_email_idx'),
        ]


class Notification(models.Model):
    """
    Model to store user notifications.
    """

    IMPORTANCE_LEVELS = [
        ('standard', _("Standard")),
        ('important', _("Important")),
        ('critical', _("Critical")),
    ]

    id = models.UUIDField(_("ID"), primary_key=True, default=uuid.uuid4, editable=False, help_text=_("Unique identifier for the notification."))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', help_text=_("The user to whom this notification belongs."))

    message = models.TextField(_("Message"), help_text=_("The content of the notification."))
    importance = models.CharField(_("Importance"), max_length=10, choices=IMPORTANCE_LEVELS, default='standard', help_text=_("The importance level of the notification."))
    action_link = models.URLField(_("Action Link"), blank=True, null=True, help_text=_("A URL that the user can follow for more information or to take action."))

    is_read = models.BooleanField(_("Is Read"), default=False, help_text=_("Indicates whether the notification has been read."))
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, help_text=_("The date and time when the notification was created."))
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True, help_text=_("The date and time when the notification was last updated."))

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read'], name='notif_user_isread_idx'),
            models.Index(fields=['user', 'created_at'], name='notif_user_createdat_idx'),
        ]

    @property
    def importance_to_bootstrap_class(self) -> str:
        mapping = {
            'standard': 'info',
            'important': 'warning',
            'critical': 'danger',
        }
        return mapping.get(self.importance, 'info')

    def __str__(self) -> str:
        return f"Notification for {self.user.email}: {self.message[:20]}..."
    


class APIKey(models.Model):
    """
    Model to store API keys for users.
    """

    id = models.UUIDField(_("ID"), primary_key=True, default=uuid.uuid4, editable=False, help_text=_("Unique identifier for the API key."))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys', help_text=_("The user who owns this API key."))
    is_active = models.BooleanField(_("Is Active"), default=True, help_text=_("Indicates whether the API key is active."))

    key = models.CharField(_("API Key"), max_length=250, unique=True, help_text=_("The API key string used for authentication."))
    name = models.CharField(_("Name"), max_length=250, help_text=_("A name to identify the API key."))

    valid_until = models.DateTimeField(_("Valid Until"), blank=True, null=True, help_text=_("The date and time until which the API key is valid. Leave blank for no expiration."))

    history = HistoricalRecords()
    
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, help_text=_("The date and time when the API key was created."))
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True, help_text=_("The date and time when the API key was last updated."))

    class Meta:
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user'], name='apikey_user_idx'),
        ]

    def __str__(self) -> str:
        return f"API Key {self.name} for {self.user.email}"
    
    def generate_api_key(self) -> None:
        
        return secrets.token_urlsafe(64)
    
    @property
    def is_expired(self) -> bool:
        if self.valid_until:
            return self.valid_until < timezone.now()
        return False
    
    def save(self, *args, **kwargs) -> None:
        if not self.key:
            self.key = self.generate_api_key()
        return super().save(*args, **kwargs)