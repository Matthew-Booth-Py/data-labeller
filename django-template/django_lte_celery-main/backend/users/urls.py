from django.urls import path

from backend.users import views

app_name = "users"
urlpatterns = [
    # Notifications
    path("notifications/", views.UserNotificationsListView.as_view(), name="notifications"),
    path("notifications/<uuid:pk>/mark-read/", views.MarkNotificationReadView.as_view(), name="mark-notification-read"),
    path("notifications/mark-all-read/", views.MarkAllNotificationsReadView.as_view(), name="mark-all-notifications-read"),

    # User Settings
    path("settings/account/", views.UserAccountOverviewView.as_view(), name="settings-account"),
    path("settings/notifications/", views.UserNotificationsUpdateView.as_view(), name="settings-notifications"),
    path("settings/language/", views.UserLanguageUpdateView.as_view(), name="settings-language"),
    path("settings/security/", views.UserSecurityUpdateView.as_view(), name="settings-security"),
    path("settings/api-management/", views.UserAPIManagementView.as_view(), name="settings-api-management"),
    
    # API Key Management
    path("api-keys/create/", views.APIKeyCreateView.as_view(), name="api-key-create"),
    path("api-keys/<uuid:pk>/update/", views.APIKeyUpdateView.as_view(), name="api-key-update"),
    path("api-keys/<uuid:pk>/regenerate/", views.APIKeyRegenerateView.as_view(), name="api-key-regenerate"),
    path("api-keys/<uuid:pk>/toggle/", views.APIKeyToggleView.as_view(), name="api-key-toggle"),
    path("api-keys/<uuid:pk>/delete/", views.APIKeyDeleteView.as_view(), name="api-key-delete"),
]
