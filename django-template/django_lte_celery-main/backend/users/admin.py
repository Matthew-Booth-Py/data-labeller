from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from backend.users.forms import UserAdminChangeForm, UserAdminCreationForm
from backend.users import models as users_models
from simple_history.admin import SimpleHistoryAdmin

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(users_models.User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "date_of_birth", "gender", "phone_number")}),
        (_("Profile"), {"fields": ("profile_image", "bio", "website")}),
        (_("Preferences"), {"fields": ("platform_language", "timezone")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "first_name", "last_name", "is_active", "is_staff", "is_superuser", "date_joined"]
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    ordering = ["email"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(users_models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "message_short", "importance_colored", "is_read", "created_at"]
    list_filter = ["importance", "is_read", "created_at"]
    search_fields = ["user__email", "message"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("user", "message", "importance", "action_link", "is_read")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )

    def message_short(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_short.short_description = "Message"

    def importance_colored(self, obj):
        color = obj.importance_to_bootstrap_class
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_importance_display())
    importance_colored.short_description = "Importance"


@admin.register(users_models.APIKey)
class APIKeyAdmin(SimpleHistoryAdmin):
    list_display = ["user", "name", "key_partial", "is_active", "is_expired_colored", "valid_until", "created_at"]
    list_filter = ["is_active", "valid_until", "created_at"]
    search_fields = ["user__email", "name", "key"]
    ordering = ["-created_at"]
    readonly_fields = ["key", "created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("user", "name", "key", "is_active", "valid_until")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )

    def key_partial(self, obj):
        return obj.key[:10] + "..." if len(obj.key) > 10 else obj.key
    key_partial.short_description = "API Key"

    def is_expired_colored(self, obj):
        if obj.is_expired:
            return format_html('<span class="badge badge-danger">Expired</span>')
        else:
            return format_html('<span class="badge badge-success">Active</span>')
    is_expired_colored.short_description = "Status"
