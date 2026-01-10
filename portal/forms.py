from decimal import Decimal

import re
from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Account,
    BankStatementImport,
    Bill,
    BillPayment,
    Client,
    ClientAdvance,
    ClientAdvanceAllocation,
    Document,
    ExpenseClaim,
    ExpenseClaimPayment,
    FirmProfile,
    Invoice,
    InvoiceLine,
    Lead,
    Payment,
    ProjectFinancePlan,
    ProjectMilestone,
    Receipt,
    RecurringTransactionRule,
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
    Vendor,
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

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault('attrs', {})
        existing = attrs.get('class', '')
        attrs['class'] = (existing + ' form-control').strip()
        super().__init__(*args, **kwargs)


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
            self.fields['watchers'].help_text = (
                'Optional: people to notify about task updates. Hold Ctrl/Cmd to select multiple; deselect to remove.'
            )
            self.fields['watchers'].widget.attrs.setdefault('size', 6)

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
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'monthly_salary', 'role', 'is_staff', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['first_name'].widget.attrs.setdefault('autocomplete', 'given-name')
        self.fields['last_name'].widget.attrs.setdefault('autocomplete', 'family-name')
        self.fields['email'].widget.attrs.setdefault('autocomplete', 'email')
        self.fields['phone'].widget.attrs.setdefault('autocomplete', 'tel')
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self.instance, 'pk', None):
            today = timezone.localdate()
            self.initial.setdefault('invoice_date', today)
            self.initial.setdefault('due_date', today + timedelta(days=7))

    class Meta:
        model = Invoice
        fields = [
            'project',
            'lead',
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
        fields = ['payment_date', 'amount', 'account', 'method', 'reference', 'notes', 'received_by']
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
            'category',
            'subcategory',
            'account',
            'debit',
            'credit',
            'related_project',
            'related_client',
            'related_vendor',
            'related_person',
            'remarks',
        ]
        widgets = {'date': DateInput(), 'remarks': forms.Textarea(attrs={'rows': 3})}

    def clean(self):
        cleaned = super().clean()
        category = (cleaned.get('category') or '').strip()
        debit = cleaned.get('debit') or Decimal('0')
        credit = cleaned.get('credit') or Decimal('0')

        if debit < 0:
            self.add_error('debit', 'Debit cannot be negative.')
        if credit < 0:
            self.add_error('credit', 'Credit cannot be negative.')

        has_debit = debit > 0
        has_credit = credit > 0
        if has_debit and has_credit:
            msg = 'Enter either a debit OR a credit amount, not both.'
            self.add_error('debit', msg)
            self.add_error('credit', msg)
        elif not has_debit and not has_credit:
            msg = 'Enter a debit or credit amount.'
            self.add_error('debit', msg)
            self.add_error('credit', msg)
        if has_debit and not category:
            self.add_error('category', 'Select a category for debit transactions.')
        return cleaned


class PersonalExpenseForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'date',
            'description',
            'category',
            'account',
            'debit',
            'related_project',
            'remarks',
        ]
        labels = {'debit': 'Amount'}
        widgets = {'date': DateInput(), 'remarks': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expense_categories = {
            Transaction.Category.MISC,
            Transaction.Category.PROJECT_EXPENSE,
            Transaction.Category.OTHER_EXPENSE,
        }
        self.fields['category'].choices = [
            choice for choice in self.fields['category'].choices if choice[0] in expense_categories
        ]
        self.fields['category'].required = True

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('debit') or Decimal('0')
        if amount <= 0:
            self.add_error('debit', 'Amount must be greater than zero.')
        return cleaned

    def save(self, commit=True):
        txn = super().save(commit=False)
        txn.credit = Decimal('0')
        if commit:
            txn.save()
        return txn


class SalaryPaymentForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['date', 'related_person', 'debit', 'account', 'remarks']
        labels = {'related_person': 'Employee', 'debit': 'Amount'}
        widgets = {'date': DateInput(), 'remarks': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get('related_person')
        amount = cleaned.get('debit') or Decimal('0')
        if not employee:
            self.add_error('related_person', 'Select an employee.')
        if amount <= 0:
            self.add_error('debit', 'Amount must be greater than zero.')
        return cleaned

    def save(self, commit=True):
        txn = super().save(commit=False)
        txn.category = Transaction.Category.SALARY
        txn.credit = 0
        employee = txn.related_person
        employee_name = employee.get_full_name() if employee else ''
        employee_name = employee_name.strip() if employee_name else (employee.username if employee else '')
        txn.description = f"Salary paid · {employee_name or 'Employee'}"[:255]
        if commit:
            txn.save()
        return txn


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'opening_balance', 'is_active', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'phone', 'email', 'address', 'tax_id', 'notes']
        widgets = {'address': forms.Textarea(attrs={'rows': 2}), 'notes': forms.Textarea(attrs={'rows': 2})}


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = [
            'vendor',
            'project',
            'bill_number',
            'bill_date',
            'due_date',
            'amount',
            'category',
            'description',
            'attachment',
        ]
        widgets = {
            'bill_date': DateInput(),
            'due_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        bill_date = cleaned.get('bill_date')
        due_date = cleaned.get('due_date')
        if bill_date and due_date and due_date < bill_date:
            self.add_error('due_date', 'Due date cannot be earlier than the bill date.')
        return cleaned


class BillPaymentForm(forms.ModelForm):
    def __init__(self, *args, bill=None, **kwargs):
        self.bill = bill
        super().__init__(*args, **kwargs)

    class Meta:
        model = BillPayment
        fields = ['payment_date', 'amount', 'account', 'method', 'reference', 'notes']
        widgets = {'payment_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        if self.bill:
            outstanding = self.bill.outstanding
            if outstanding <= 0:
                raise forms.ValidationError('This bill is already settled.')
            if amount > outstanding:
                raise forms.ValidationError(f'Cannot pay more than the outstanding amount ({outstanding}).')
        return amount


class ClientAdvanceForm(forms.ModelForm):
    def __init__(self, *args, project_queryset=None, client_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project_queryset is not None:
            self.fields['project'].queryset = project_queryset
        if client_queryset is not None:
            self.fields['client'].queryset = client_queryset

    class Meta:
        model = ClientAdvance
        fields = [
            'project',
            'client',
            'received_date',
            'amount',
            'account',
            'method',
            'reference',
            'notes',
            'received_by',
        ]
        widgets = {'received_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get('project')
        client = cleaned.get('client')
        if not project and not client:
            self.add_error('project', 'Select a project or a client.')
            self.add_error('client', 'Select a project or a client.')
        if project and not client and getattr(project, 'client', None):
            cleaned['client'] = project.client
        amount = cleaned.get('amount') or Decimal('0')
        if amount <= 0:
            self.add_error('amount', 'Amount must be greater than zero.')
        return cleaned


class ClientAdvanceAllocationForm(forms.ModelForm):
    def __init__(self, *args, invoice=None, advance=None, **kwargs):
        self.invoice = invoice
        self.advance = advance
        super().__init__(*args, **kwargs)
        if invoice is not None:
            self.fields['invoice'].queryset = Invoice.objects.filter(pk=invoice.pk)
            self.initial.setdefault('invoice', invoice)
        if advance is not None:
            self.fields['advance'].queryset = ClientAdvance.objects.filter(pk=advance.pk)
            self.initial.setdefault('advance', advance)

    class Meta:
        model = ClientAdvanceAllocation
        fields = ['advance', 'invoice', 'amount', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        invoice = self.cleaned_data.get('invoice') or self.invoice
        advance = self.cleaned_data.get('advance') or self.advance
        prior_amount = self.instance.amount if getattr(self.instance, 'pk', None) else Decimal('0')
        if invoice:
            allowed = (invoice.outstanding or Decimal('0')) + prior_amount
            if amount > allowed:
                raise forms.ValidationError(f'Cannot apply more than invoice balance ({allowed}).')
        if advance:
            allowed = (advance.available_amount or Decimal('0')) + prior_amount
            if amount > allowed:
                raise forms.ValidationError(f'Cannot apply more than available advance ({allowed}).')
        return amount

    def clean(self):
        cleaned = super().clean()
        invoice = cleaned.get('invoice') or self.invoice
        advance = cleaned.get('advance') or self.advance
        if invoice and advance:
            if invoice.project_id and advance.project_id and invoice.project_id != advance.project_id:
                self.add_error('advance', 'Advance must belong to the same project as the invoice.')
            if invoice.lead_id and advance.client_id and invoice.lead and invoice.lead.client_id != advance.client_id:
                self.add_error('advance', 'Advance must belong to the same client as the invoice.')
        return cleaned


class ProjectFinancePlanForm(forms.ModelForm):
    class Meta:
        model = ProjectFinancePlan
        fields = ['planned_fee', 'planned_cost', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class ProjectMilestoneForm(forms.ModelForm):
    class Meta:
        model = ProjectMilestone
        fields = ['title', 'due_date', 'amount', 'status', 'notes']
        widgets = {'due_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}


class ExpenseClaimForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)

    class Meta:
        model = ExpenseClaim
        fields = ['project', 'expense_date', 'amount', 'category', 'description']
        widgets = {
            'expense_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class ExpenseClaimPaymentForm(forms.ModelForm):
    def __init__(self, *args, claim=None, **kwargs):
        self.claim = claim
        super().__init__(*args, **kwargs)

    class Meta:
        model = ExpenseClaimPayment
        fields = ['payment_date', 'amount', 'account', 'method', 'reference', 'notes']
        widgets = {'payment_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        if self.claim:
            claim_amount = self.claim.amount or Decimal('0')
            if amount > claim_amount:
                raise forms.ValidationError(f'Cannot pay more than the claim amount ({claim_amount}).')
        return amount


class RecurringTransactionRuleForm(forms.ModelForm):
    class Meta:
        model = RecurringTransactionRule
        fields = [
            'name',
            'is_active',
            'direction',
            'category',
            'description',
            'amount',
            'account',
            'related_project',
            'related_vendor',
            'day_of_month',
            'next_run_date',
            'notes',
        ]
        widgets = {'next_run_date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 2})}

    def clean_day_of_month(self):
        value = self.cleaned_data.get('day_of_month') or 1
        if value < 1 or value > 28:
            raise forms.ValidationError('Use a day between 1 and 28 for reliable monthly scheduling.')
        return value

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or Decimal('0')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class BankStatementImportForm(forms.ModelForm):
    class Meta:
        model = BankStatementImport
        fields = ['account', 'file', 'source_name']


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
    invoice_sequence_after = forms.CharField(
        required=False,
        label='Start invoice numbering after',
        widget=forms.TextInput(attrs={'placeholder': '584 or NVRT/530/584'}),
    )

    class Meta:
        model = FirmProfile
        fields = [
            'name',
            'address',
            'email',
            'phone',
            'tax_id',
            'invoice_sequence_after',
            'bank_name',
            'bank_account_name',
            'bank_account_number',
            'bank_ifsc',
            'upi_id',
            'terms',
            'logo',
        ]
        widgets = {'address': forms.Textarea(attrs={'rows': 2}), 'terms': forms.Textarea(attrs={'rows': 3})}

    def clean_invoice_sequence_after(self):
        raw = (self.cleaned_data.get('invoice_sequence_after') or '').strip()
        if not raw:
            return None
        match = re.search(r'(\d+)\s*$', raw)
        if not match:
            raise forms.ValidationError('Enter a number like 584 or an invoice like NVRT/530/584.')
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            raise forms.ValidationError('Enter a valid invoice number suffix (e.g. 584).')
