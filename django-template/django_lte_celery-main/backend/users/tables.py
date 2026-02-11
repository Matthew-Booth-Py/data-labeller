import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from backend.users.models import APIKey
from django.urls import reverse_lazy


class APIKeyTable(tables.Table):
    """Django-tables2 table for displaying API keys"""
    
    name = tables.Column(
        verbose_name=_("Name"),
        attrs={
            "th": {"class": "text-start"},
            "td": {"class": "fw-semibold"}
        }
    )
    
    key = tables.Column(
        verbose_name=_("API Key"),
        orderable=False,
        attrs={
            "th": {"class": "text-start"},
            "td": {"class": "font-monospace"}
        }
    )
    
    is_active = tables.BooleanColumn(
        verbose_name=_("Status"),
        yesno=_("Active,Inactive"),
        attrs={
            "th": {"class": "text-center"},
            "td": {"class": "text-center"}
        }
    )
    
    valid_until = tables.DateTimeColumn(
        verbose_name=_("Valid Until"),
        format="Y-m-d H:i",
        attrs={
            "th": {"class": "text-center"},
            "td": {"class": "text-center"}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name=_("Created"),
        format="Y-m-d",
        attrs={
            "th": {"class": "text-center"},
            "td": {"class": "text-center text-muted"}
        }
    )
    
    actions = tables.Column(
        verbose_name=_("Actions"),
        empty_values=(),
        orderable=False,
        attrs={
            "th": {"class": "text-end"},
            "td": {"class": "text-end"}
        }
    )
    
    class Meta:
        model = APIKey
        template_name = "django_tables2/bootstrap5.html"
        fields = ("name", "key", "is_active", "valid_until", "created_at", "actions")
        attrs = {
            "class": "table table-sm table-responsive align-middle",
        }
        order_by = "-created_at"
    
    def render_key(self, value):
        """Render the API key with a masked format and copy button"""
        masked_key = f"{value[:8]}...{value[-8:]}" if len(value) > 16 else value
        return format_html(
            '<span class="api-key-masked">{}</span> '
            '<button class="btn btn-sm btn-outline-secondary copy-key-btn" '
            'data-to-copy="{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="{}"><i class="bi bi-clipboard"></i></button>',
            masked_key,
            value,
            _("Copy to clipboard")
        )
    
    def render_is_active(self, value, record):
        """Render status with colored badge"""
        if value:
            badge_class = "bg-success" if not record.is_expired else "bg-danger"
            status_text = _("Active") if not record.is_expired else _("Expired")
        else:
            badge_class = "bg-secondary"
            status_text = _("Inactive")
        
        return format_html(
            '<span class="badge {}">{}</span>',
            badge_class,
            status_text
        )
    
    def render_valid_until(self, value):
        """Render expiration date with indicator if expired"""
        if not value:
            return format_html('<span class="text-muted">{}</span>', _("Never"))
        
        if value < timezone.now():
            return format_html(
                '<span class="text-danger">{}</span>',
                value.strftime("%Y-%m-%d %H:%M")
            )
        
        return value.strftime("%Y-%m-%d %H:%M")
    
    def render_actions(self, record):
        """Render action buttons for each API key"""
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<a class="btn btn-outline-primary" href="{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="{}"><i class="bi bi-pencil"></i></a>'
            '<a class="btn btn-outline-warning" href="{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="{}"><i class="bi bi-arrow-clockwise"></i></a>'
            '<a class="btn btn-outline-{}" href="{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="{}"><i class="bi bi-{}"></i></a>'
            '<a class="btn btn-outline-danger" href="{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="{}"><i class="bi bi-trash"></i></a>'
            '</div>',
            reverse_lazy('users:api-key-update', kwargs={'pk': record.pk}), _("Edit this API key"),
            reverse_lazy('users:api-key-regenerate', kwargs={'pk': record.pk}), _("Regenerate this API key"),
            "success" if record.is_active else "secondary",
            reverse_lazy('users:api-key-toggle', kwargs={'pk': record.pk}), _("Toggle active status of this API key"),
            "toggle-off" if record.is_active else "toggle-on",
            reverse_lazy('users:api-key-delete', kwargs={'pk': record.pk}), _("Delete this API key")
        )
