from django.shortcuts import render
from django.views.generic import TemplateView
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'app/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Dashboard')
        context['breadcrumbs'] = [
            {'url': reverse_lazy('core:dashboard'), 'title': _('Home')},
            {'url': reverse_lazy('core:dashboard'), 'title': _('Dashboard')},
        ]
        return context
