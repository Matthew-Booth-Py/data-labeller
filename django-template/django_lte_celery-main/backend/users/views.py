from django.middleware.csrf import get_token
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView, UpdateView, TemplateView, CreateView, DeleteView, ListView
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from django_tables2 import SingleTableView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin


from backend.users.models import User, APIKey, Notification
from backend.users.forms import (
    UserAccountForm,
    UserNotificationsForm,
    UserLanguageForm,
    UserSecurityForm,
    APIKeyForm
)
from backend.users.tables import APIKeyTable
from django.db.models.functions import TruncDate

class UserAccountOverviewView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserAccountForm
    template_name = "app/users/user_form.html"
    success_message = _("Your account information has been updated successfully.")

    def get_object(self, queryset: QuerySet | None = None) -> User:
        return self.request.user
    
    def get_success_url(self) -> str:
        return reverse("users:settings-account")
    

class UserNotificationsUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView,):
    model = User
    form_class = UserNotificationsForm
    template_name = "app/users/user_form.html"
    success_message = _("Your notification settings have been updated.")

    def get_object(self, queryset: QuerySet | None = None) -> User:
        return self.request.user
    
    def get_success_url(self) -> str:
        return reverse("users:settings-notifications")


class UserLanguageUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView,):
    model = User
    form_class = UserLanguageForm
    template_name = "app/users/user_form.html"
    success_message = _("Your language and timezone settings have been updated.")

    def get_object(self, queryset: QuerySet | None = None) -> User:
        return self.request.user

    def get_success_url(self) -> str:
        return reverse("users:settings-language")


class UserSecurityUpdateView(LoginRequiredMixin, SuccessMessageMixin, TemplateView,):
    template_name = "app/users/user_form.html"
    success_message = _("Your security settings have been updated.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = UserSecurityForm(user=self.request.user)
        return context
    
    def post(self, request, *args, **kwargs):
        form = UserSecurityForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = request.user
            
            # Update password if provided
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)
                user.save()
                messages.success(request, _('Your password has been changed successfully.'))
            
            # Update email if provided
            new_email = form.cleaned_data.get('new_email')
            if new_email:
                user.email = new_email
                user.save()
                # Here you would typically send a verification email
                messages.success(request, _('Your email has been updated. Please check your inbox to verify.'))
            
            return HttpResponseRedirect(reverse("users:settings-security"))
        
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)



class UserAPIManagementView(LoginRequiredMixin, SuccessMessageMixin, SingleTableView):
    template_name = "app/users/api_management.html"
    table_class = APIKeyTable
    success_message = _("API Key has been created successfully.")

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)
    


class APIKeyCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = APIKey
    form_class = APIKeyForm
    template_name = "app/users/api_management_form.html"
    success_message = _("API Key has been created successfully.")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return reverse("users:settings-api-management")
    
    
class APIKeyDeleteView(LoginRequiredMixin, DeleteView):
    model = APIKey
    template_name = "app/users/api_management_confirm.html"
    success_url = reverse_lazy("users:settings-api-management")

    def get_queryset(self) -> QuerySet:
        return APIKey.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'delete'
        context['action_title'] = _('Delete API Key')
        context['action_message'] = _('Are you sure you want to delete this API key? This action cannot be undone.')
        context['action_button'] = _('Delete')
        context['action_class'] = 'btn-danger'
        return context
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _("API Key has been deleted successfully."))
        return super().delete(request, *args, **kwargs)
    

class APIKeyUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = APIKey
    form_class = APIKeyForm
    template_name = "app/users/api_management_form.html"
    success_message = _("API Key has been updated successfully.")

    def get_queryset(self) -> QuerySet:
        return APIKey.objects.filter(user=self.request.user)
    
    def get_success_url(self) -> str:
        return reverse("users:settings-api-management")
    
    
class APIKeyRegenerateView(LoginRequiredMixin, TemplateView):
    template_name = "app/users/api_management_confirm.html"
    
    def get_object(self):
        return APIKey.objects.filter(user=self.request.user).get(pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        context['action'] = 'regenerate'
        context['action_title'] = _('Regenerate API Key')
        context['action_message'] = _('Are you sure you want to regenerate this API key? The old key will stop working immediately.')
        context['action_button'] = _('Regenerate')
        context['action_class'] = 'btn-warning'
        return context
    
    def post(self, request, *args, **kwargs):
        api_key = self.get_object()
        api_key.key = api_key.generate_api_key()
        api_key.save()
        messages.success(request, _("API Key has been regenerated successfully."))
        return HttpResponseRedirect(reverse("users:settings-api-management"))
    

class APIKeyToggleView(LoginRequiredMixin, TemplateView):
    template_name = "app/users/api_management_confirm.html"
    
    def get_object(self):
        return APIKey.objects.filter(user=self.request.user).get(pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        api_key = self.get_object()
        context['object'] = api_key
        
        if api_key.is_active:
            context['action'] = 'deactivate'
            context['action_title'] = _('Deactivate API Key')
            context['action_message'] = _('Are you sure you want to deactivate this API key? It will stop working until you reactivate it.')
            context['action_button'] = _('Deactivate')
            context['action_class'] = 'btn-warning'
        else:
            context['action'] = 'activate'
            context['action_title'] = _('Activate API Key')
            context['action_message'] = _('Are you sure you want to activate this API key?')
            context['action_button'] = _('Activate')
            context['action_class'] = 'btn-success'
        
        return context
    
    def post(self, request, *args, **kwargs):
        api_key = self.get_object()
        api_key.is_active = not api_key.is_active
        api_key.save()
        status = _("activated") if api_key.is_active else _("deactivated")
        messages.success(request, _(f"API Key has been {status} successfully."))
        return HttpResponseRedirect(reverse("users:settings-api-management"))
    


class UserNotificationsListView(LoginRequiredMixin, SuccessMessageMixin, ListView):
    model = Notification
    template_name = "app/notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Notifications")
        context['breadcrumbs'] = [
            {'title': _('Home'), 'url': reverse('core:dashboard')},
            {'title': _('Notifications'), 'url': ''},
        ]
        context['csrf_token'] = get_token(self.request)
        return context

    def get_queryset(self) -> QuerySet:
        return Notification.objects.filter(user=self.request.user).annotate(date=TruncDate('created_at')).order_by('-date', '-created_at')


class MarkNotificationReadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.is_read = True
            notification.save()
            messages.success(request, _('Notification marked as read.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('users:notifications')))
        except Notification.DoesNotExist:
            messages.error(request, _('Notification not found.'))
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('users:notifications')))


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def get(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, _('All notifications marked as read.'))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('users:notifications')))
