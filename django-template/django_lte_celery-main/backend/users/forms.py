from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, Field, HTML, Row, Column
from crispy_forms.bootstrap import FormActions
from bootstrap_datepicker_plus.widgets import DateTimePickerInput

from .models import User, APIKey


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class UserAccountForm(forms.ModelForm):
    """
    Form for updating user account information including personal details and profile.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'date_of_birth', 
            'gender',
            'phone_number', 
            'bio', 
            'website',
            'profile_image'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': _('Enter your first name'),
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': _('Enter your last name'),
                'class': 'form-control'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'placeholder': _('YYYY-MM-DD'),
                'class': 'form-control'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': _('+1 (555) 123-4567'),
                'class': 'form-control'
            }),
            'bio': forms.Textarea(attrs={
                'placeholder': _('Tell us about yourself...'),
                'rows': 4,
                'class': 'form-control'
            }),
            'website': forms.URLInput(attrs={
                'placeholder': _('https://yourwebsite.com'),
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        
        self.helper.field_class = ''
        
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Personal Information</h5>'),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-6 mb-3'),
                Column('gender', css_class='form-group col-md-6 mb-3'),
            ),
            Div('phone_number', css_class='form-group mb-3'),
            
            HTML('<h5 class="mt-4 mb-3">Profile Information</h5>'),
            Div('bio', css_class='form-group mb-3'),
            Div('website', css_class='form-group mb-3'),
            
            FormActions(
                Submit('submit', _('Save Changes'), css_class='btn btn-primary'),
                css_class='mt-4'
            )
        )


class UserNotificationsForm(forms.ModelForm):
    """
    Form for managing notification preferences.
    """
    class Meta:
        model = User
        fields = [
            'email_notifications',
            'push_notifications',
            'marketing_emails',
            'security_alerts'
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'marketing_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'security_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set help text for fields
        self.fields['email_notifications'].label = _('Email Notifications')
        self.fields['email_notifications'].help_text = _('Receive notifications via email')
        self.fields['email_notifications'].required = False
        
        self.fields['push_notifications'].label = _('Push Notifications')
        self.fields['push_notifications'].help_text = _('Receive push notifications in your browser')
        self.fields['push_notifications'].required = False
        
        self.fields['marketing_emails'].label = _('Marketing Emails')
        self.fields['marketing_emails'].help_text = _('Receive promotional and marketing emails')
        self.fields['marketing_emails'].required = False
        
        self.fields['security_alerts'].label = _('Security Alerts')
        self.fields['security_alerts'].help_text = _('Important security and account alerts')
        self.fields['security_alerts'].required = False
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Notification Preferences</h5>'),
            HTML('<p class="text-muted mb-4">Choose how you want to receive notifications</p>'),
            
            Div(
                Div('email_notifications', css_class='form-check form-switch mb-3'),
                Div('push_notifications', css_class='form-check form-switch mb-3'),
                Div('marketing_emails', css_class='form-check form-switch mb-3'),
                Div('security_alerts', css_class='form-check form-switch mb-3'),
                css_class='mb-4'
            ),
            
            FormActions(
                Submit('submit', _('Save Preferences'), css_class='btn btn-primary'),
            )
        )


class UserLanguageForm(forms.ModelForm):
    """
    Form for updating language and timezone preferences.
    """
    
    class Meta:
        model = User
        fields = ['platform_language', 'timezone']
        widgets = {
            'platform_language': forms.Select(attrs={
                'class': 'form-select'
            }),
            'timezone': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Common timezones
        timezone_choices = [
            ('America/New_York', 'Eastern Time (US & Canada)'),
            ('America/Chicago', 'Central Time (US & Canada)'),
            ('America/Denver', 'Mountain Time (US & Canada)'),
            ('America/Los_Angeles', 'Pacific Time (US & Canada)'),
            ('Europe/London', 'London'),
            ('Europe/Paris', 'Paris'),
            ('Europe/Berlin', 'Berlin'),
            ('Asia/Tokyo', 'Tokyo'),
            ('Asia/Shanghai', 'Beijing'),
            ('Asia/Dubai', 'Dubai'),
            ('Australia/Sydney', 'Sydney'),
        ]
        
        self.fields['timezone'].widget = forms.Select(
            choices=timezone_choices,
            attrs={'class': 'form-select'}
        )
        
        self.fields['platform_language'].help_text = _('Select your preferred language for the interface')
        self.fields['timezone'].help_text = _('Select your timezone for displaying dates and times')
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Language & Region</h5>'),
            HTML('<p class="text-muted mb-4">Customize your language and timezone settings</p>'),
            
            Div('platform_language', css_class='form-group mb-3'),
            Div('timezone', css_class='form-group mb-3'),
            
            FormActions(
                Submit('submit', _('Save Settings'), css_class='btn btn-primary'),
                css_class='mt-4'
            )
        )


class UserSecurityForm(forms.Form):
    """
    Form for updating password and email.
    """
    current_password = forms.CharField(
        label=_('Current Password'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('Enter your current password'),
            'class': 'form-control',
            'autocomplete': 'current-password'
        }),
        help_text=_('Required to make changes to your account'),
        required=True
    )
    
    new_password = forms.CharField(
        label=_('New Password'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('Enter a new password'),
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        help_text=_('Must be at least 8 characters long'),
        required=False
    )
    
    confirm_password = forms.CharField(
        label=_('Confirm New Password'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('Confirm your new password'),
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        required=False
    )
    
    new_email = forms.EmailField(
        label=_('New Email Address'),
        widget=forms.EmailInput(attrs={
            'placeholder': _('Enter a new email address'),
            'class': 'form-control'
        }),
        help_text=_('We will send a verification email to this address'),
        required=False
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        
        
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Change Password</h5>'),
            HTML('<p class="text-muted mb-4">Update your password to keep your account secure</p>'),
            
            Div('current_password', css_class='form-group mb-3'),
            Row(
                Column('new_password', css_class='form-group col-md-6 mb-3'),
                Column('confirm_password', css_class='form-group col-md-6 mb-3'),
            ),
            
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Change Email Address</h5>'),
            HTML('<p class="text-muted mb-4">Update the email address associated with your account</p>'),
            
            Div('new_email', css_class='form-group mb-3'),
            
            FormActions(
                Submit('submit', _('Update Security Settings'), css_class='btn btn-primary'),
                css_class='mt-4'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        new_email = cleaned_data.get('new_email')
        
        # Verify current password
        if current_password and not self.user.check_password(current_password):
            raise forms.ValidationError(_('Current password is incorrect'))
        
        # If changing password, validate new password
        if new_password or confirm_password:
            if not new_password:
                raise forms.ValidationError(_('Please enter a new password'))
            if new_password != confirm_password:
                raise forms.ValidationError(_('New passwords do not match'))
            if len(new_password) < 8:
                raise forms.ValidationError(_('New password must be at least 8 characters long'))
        
        # If changing email, validate new email
        if new_email:
            if new_email == self.user.email:
                raise forms.ValidationError(_('New email must be different from current email'))
            if User.objects.filter(email=new_email).exists():
                raise forms.ValidationError(_('This email address is already in use'))
        
        # At least one field must be filled
        if not new_password and not new_email:
            raise forms.ValidationError(_('Please provide a new password or email address to update'))
        
        return cleaned_data


class APIKeyForm(forms.ModelForm):
    """
    Form for creating and editing API keys.
    """
    
    class Meta:
        model = APIKey
        fields = ['name', 'valid_until']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': _('e.g., Production API, Development Key'),
                'class': 'form-control'
            }),
            'valid_until': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['name'].help_text = _('A descriptive name to identify this API key')
        self.fields['valid_until'].help_text = _('Leave blank for no expiration')
        self.fields['valid_until'].required = False
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_id = 'apiKeyForm'
        
        self.helper.layout = Layout(
            Div('name', css_class='form-group mb-3'),
            Div('valid_until', css_class='form-group mb-3'),
            FormActions(
                Submit('submit', _('Save API Key'), css_class='btn btn-primary'),
                css_class='mt-3'
            )
        )
