from decimal import Decimal

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
    Receipt,
    Project,
    ProjectStageHistory,
    ReminderSetting,
    SiteIssue,
    SiteIssueAttachment,
    SiteVisit,
    SiteVisitAttachment,
    Task,
    TaskComment,
    TaskCommentAttachment,
    TaskTemplate,
    Transaction,
    User,
    RolePermission,
)

class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault('attrs', {})
        attrs.setdefault('type', 'date')  # ensure browsers render native picker
        attrs.setdefault('placeholder', 'YYYY-MM-DD')
        super().__init__(*args, **kwargs)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [super().clean(d, initial) for d in data]
        return [super().clean(data, initial)]


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
    # Option to create a new client inline
    new_client_name = forms.CharField(
        required=False,
        label='New client name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter new client name'}),
    )
    new_client_phone = forms.CharField(
        required=False,
        label='Phone',
        widget=forms.TextInput(attrs={'placeholder': 'Contact number'}),
    )
    new_client_email = forms.EmailField(
        required=False,
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'email@example.com'}),
    )

    class Meta:
        model = Lead
        fields = ['client', 'title', 'lead_source', 'status', 'estimated_value', 'notes', 'planning_details']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3}), 'planning_details': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].required = False
        self.fields['client'].help_text = 'Select an existing client OR create a new one below'
        self.fields['title'].label = 'Lead title'
        placeholders = {
            'title': 'Short summary (e.g., Kitchen remodel)',
            'lead_source': 'How they found us (referral, ad, web, etc.)',
            'estimated_value': 'Estimated contract value',
            'notes': 'Next steps or extra details',
            'planning_details': 'Planning details and confirmations captured in lead stage',
        }
        for field, text in placeholders.items():
            self.fields[field].widget.attrs.setdefault('placeholder', text)

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get('client')
        new_client_name = cleaned.get('new_client_name')

        # Must have either existing client or new client name
        if not client and not new_client_name:
            raise forms.ValidationError('Select an existing client or enter a new client name.')
        if client and new_client_name:
            raise forms.ValidationError('Either select an existing client OR enter a new client name, not both.')
        return cleaned


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


class RolePermissionForm(forms.ModelForm):
    class Meta:
        model = RolePermission
        fields = [
            'clients',
            'leads',
            'projects',
            'site_visits',
            'finance',
            'invoices',
            'docs',
            'team',
            'users',
            'settings',
        ]
        widgets = {field: forms.CheckboxInput(attrs={'class': 'form-check-input'}) for field in fields}


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
            'objective',
            'expected_output',
            'deliverables',
            'references',
            'constraints',
            'status',
            'priority',
            'due_date',
            'assigned_to',
            'watchers',
            'estimated_hours',
            'actual_hours',
        ]
        widgets = {
            'due_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
            'objective': forms.Textarea(attrs={'rows': 2}),
            'expected_output': forms.Textarea(attrs={'rows': 2}),
            'deliverables': forms.Textarea(attrs={'rows': 3}),
            'references': forms.Textarea(attrs={'rows': 2}),
            'constraints': forms.Textarea(attrs={'rows': 2}),
            'watchers': forms.SelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].queryset = TaskTemplate.objects.order_by('title')
        placeholders = {
            'title': 'Task title',
            'description': 'Details or acceptance criteria',
            'objective': 'What is this task trying to achieve?',
            'expected_output': 'Define the required output/result',
            'deliverables': 'One deliverable per line',
            'references': 'Links or notes, one per line',
            'constraints': 'Budgets, rules, or limitations',
        }
        for field, text in placeholders.items():
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('placeholder', text)
        if 'watchers' in self.fields:
            self.fields['watchers'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')

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


class TaskCommentForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text='Optional files, images, or notes to attach.',
    )

    class Meta:
        model = TaskComment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Add an update… Use @username to mention someone.',
                }
            )
        }


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
    attachments = MultipleFileField(
        required=False,
        help_text='Optional photos or files from the site visit.',
    )

    class Meta:
        model = SiteVisit
        fields = ['project', 'visit_date', 'visited_by', 'notes', 'expenses', 'location']
        widgets = {'visit_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 3})}


class SiteVisitAttachmentForm(forms.ModelForm):
    class Meta:
        model = SiteVisitAttachment
        fields = ['file', 'caption']


class SiteIssueForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text='Optional photos or files related to this issue.',
    )

    class Meta:
        model = SiteIssue
        fields = ['project', 'site_visit', 'title', 'description', 'raised_on', 'raised_by', 'status', 'resolved_on']
        widgets = {
            'raised_on': DateInput(),
            'resolved_on': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class SiteIssueAttachmentForm(forms.ModelForm):
    class Meta:
        model = SiteIssueAttachment
        fields = ['file', 'caption']


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'project',
            'lead',
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

    def clean(self):
        cleaned = super().clean()
        invoice_date = cleaned.get('invoice_date')
        due_date = cleaned.get('due_date')
        if invoice_date and due_date and due_date < invoice_date:
            self.add_error('due_date', 'Due date cannot be earlier than the invoice date.')
        project = cleaned.get('project')
        lead = cleaned.get('lead')
        if not project and not lead:
            self.add_error('project', 'Select a project or a lead to bill.')
            self.add_error('lead', 'Select a project or a lead to bill.')
        return cleaned


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
    can_delete=True,
)


class PaymentForm(forms.ModelForm):
    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice:
            outstanding = invoice.outstanding
            self.fields['amount'].widget.attrs.setdefault('max', str(outstanding))
            self.fields['amount'].widget.attrs.setdefault('min', '0.01')

    class Meta:
        model = Payment
        fields = ['payment_date', 'amount', 'method', 'reference', 'notes', 'received_by']
        widgets = {'payment_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        if self.invoice:
            outstanding = self.invoice.outstanding
            if outstanding <= 0:
                raise forms.ValidationError('This invoice is already settled.')
            if amount > outstanding:
                raise forms.ValidationError(f'Cannot record more than the outstanding balance ({outstanding}).')
        return amount


class ReceiptForm(forms.ModelForm):
    """
    Form for generating a receipt from a payment.
    Receipt is proof of payment - generated AFTER payment is recorded.
    """
    class Meta:
        model = Receipt
        fields = ['notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes to print on receipt'})}

    def __init__(self, *args, payment=None, **kwargs):
        self.payment = payment
        super().__init__(*args, **kwargs)


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
