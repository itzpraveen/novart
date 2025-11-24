from django import forms
from django.forms import inlineformset_factory

from .models import (
    Client,
    Document,
    FirmProfile,
    Invoice,
    InvoiceLine,
    Lead,
    Payment,
    Project,
    ProjectStageHistory,
    ReminderSetting,
    SiteIssue,
    SiteVisit,
    SiteVisitAttachment,
    Task,
    TaskTemplate,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Client name'
        placeholders = {
            'name': 'Full name or company',
            'phone': 'Primary contact number',
            'email': 'name@example.com',
            'address': 'Street and number',
            'city': 'City',
            'state': 'State/Region',
            'postal_code': 'Postal/ZIP code',
            'notes': 'Any extra context about the client',
        }
        for field, text in placeholders.items():
            self.fields[field].widget.attrs.setdefault('placeholder', text)


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['client', 'title', 'lead_source', 'status', 'estimated_value', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Lead title'
        placeholders = {
            'title': 'Short summary (e.g., Kitchen remodel)',
            'lead_source': 'How they found us (referral, ad, web, etc.)',
            'estimated_value': 'Estimated contract value',
            'notes': 'Next steps or extra details',
        }
        for field, text in placeholders.items():
            self.fields[field].widget.attrs.setdefault('placeholder', text)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'name' in self.fields:
            self.fields['name'].label = 'Project name'
        if 'code' in self.fields:
            self.fields['code'].label = 'Project code'
        placeholders = {
            'name': 'Project name (client-facing)',
            'code': 'Internal code or job number (optional)',
            'location': 'Site address or city',
            'built_up_area': 'e.g., 3500 sq ft',
            'description': 'Scope, goals, milestones',
            'current_stage': 'e.g., Enquiry, Proposal, Execution',
            'health_status': 'On Track, At Risk, etc.',
        }
        for field, text in placeholders.items():
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('placeholder', text)
        # Date inputs render as type=date; keep a hint for non-supporting browsers.
        for date_field in ['start_date', 'expected_handover']:
            if date_field in self.fields:
                self.fields[date_field].widget.attrs.setdefault('placeholder', 'mm/dd/yyyy')


class StageUpdateForm(forms.ModelForm):
    class Meta:
        model = ProjectStageHistory
        fields = ['stage', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class TaskForm(forms.ModelForm):
    template = forms.ModelChoiceField(
        queryset=TaskTemplate.objects.none(), required=False, empty_label='Select a template (optional)'
    )

    class Meta:
        model = Task
        fields = [
            'template',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].queryset = TaskTemplate.objects.order_by('title')
        placeholders = {
            'title': 'Task title',
            'description': 'Details or acceptance criteria',
        }
        for field, text in placeholders.items():
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('placeholder', text)

    def clean(self):
        cleaned = super().clean()
        template = cleaned.get('template')
        if template:
            cleaned.setdefault('title', template.title)
            cleaned.setdefault('description', template.description)
            if template.status and not cleaned.get('status'):
                cleaned['status'] = template.status
            if template.priority and not cleaned.get('priority'):
                cleaned['priority'] = template.priority
            if template.due_in_days is not None and not cleaned.get('due_date'):
                date_widget = self.fields['due_date']
                from datetime import date, timedelta
                cleaned['due_date'] = date.today() + timedelta(days=template.due_in_days or 0)
        return cleaned


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
        fields = [
            'project',
            'invoice_number',
            'invoice_date',
            'due_date',
            'amount',
            'discount_percent',
            'tax_percent',
            'status',
            'description',
        ]
        widgets = {
            'invoice_date': DateInput(),
            'due_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ['description', 'quantity', 'unit_price']
        widgets = {'description': forms.TextInput(attrs={'placeholder': 'Describe work delivered'})}


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=3,
    can_delete=False,
)


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


class FirmProfileForm(forms.ModelForm):
    class Meta:
        model = FirmProfile
        fields = [
            'name',
            'address',
            'email',
            'phone',
            'tax_id',
            'bank_name',
            'bank_account_name',
            'bank_account_number',
            'bank_ifsc',
            'upi_id',
            'terms',
            'logo',
        ]
        widgets = {'address': forms.Textarea(attrs={'rows': 2}), 'terms': forms.Textarea(attrs={'rows': 3})}
