from django import forms

from .models import (
    Client,
    Document,
    Invoice,
    Lead,
    Payment,
    Project,
    ProjectStageHistory,
    ReminderSetting,
    SiteIssue,
    SiteVisit,
    SiteVisitAttachment,
    Task,
    Transaction,
    User,
)

class DateInput(forms.DateInput):
    input_type = 'date'


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'phone', 'email', 'address', 'city', 'state', 'postal_code', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['client', 'title', 'lead_source', 'status', 'estimated_value', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'client',
            'lead',
            'name',
            'code',
            'project_type',
            'location',
            'built_up_area',
            'start_date',
            'expected_handover',
            'description',
            'current_stage',
            'health_status',
            'project_manager',
            'site_engineer',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_date': DateInput(),
            'expected_handover': DateInput(),
        }


class StageUpdateForm(forms.ModelForm):
    class Meta:
        model = ProjectStageHistory
        fields = ['stage', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'project',
            'title',
            'description',
            'status',
            'priority',
            'due_date',
            'assigned_to',
            'estimated_hours',
            'actual_hours',
        ]
        widgets = {'due_date': DateInput(), 'description': forms.Textarea(attrs={'rows': 3})}


class UserForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'role', 'is_staff', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.initial['is_staff'] = True

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('password1')
        pw2 = cleaned.get('password2')
        if pw1 or pw2:
            if pw1 != pw2:
                self.add_error('password2', 'Passwords do not match.')
        elif not self.instance.pk:
            self.add_error('password1', 'Password is required.')
            self.add_error('password2', 'Password is required.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pw1 = self.cleaned_data.get('password1')
        if pw1:
            user.set_password(pw1)
        if commit:
            user.save()
        return user


class SiteVisitForm(forms.ModelForm):
    class Meta:
        model = SiteVisit
        fields = ['project', 'visit_date', 'visited_by', 'notes', 'expenses', 'location']
        widgets = {'visit_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 3})}


class SiteVisitAttachmentForm(forms.ModelForm):
    class Meta:
        model = SiteVisitAttachment
        fields = ['file', 'caption']


class SiteIssueForm(forms.ModelForm):
    class Meta:
        model = SiteIssue
        fields = ['project', 'site_visit', 'title', 'description', 'raised_on', 'raised_by', 'status', 'resolved_on']
        widgets = {
            'raised_on': DateInput(),
            'resolved_on': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['project', 'invoice_number', 'invoice_date', 'due_date', 'amount', 'tax_percent', 'status', 'description']
        widgets = {
            'invoice_date': DateInput(),
            'due_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_date', 'amount', 'method', 'reference', 'received_by']
        widgets = {'payment_date': DateInput()}


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'date',
            'description',
            'debit',
            'credit',
            'related_project',
            'related_client',
            'related_person',
            'remarks',
        ]
        widgets = {'date': DateInput(), 'remarks': forms.Textarea(attrs={'rows': 3})}


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['project', 'file', 'file_name', 'file_type', 'version', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('file_name') and cleaned.get('file'):
            cleaned['file_name'] = cleaned['file'].name
        return cleaned


class ReminderSettingForm(forms.ModelForm):
    class Meta:
        model = ReminderSetting
        fields = ['category', 'days_before', 'send_to_admins', 'send_to_assigned']
        widgets = {'category': forms.Select(attrs={'class': 'form-select'})}
