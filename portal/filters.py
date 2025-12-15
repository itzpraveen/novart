import django_filters
from django.contrib.auth import get_user_model
from django import forms

from .models import Bill, ClientAdvance, ExpenseClaim, Invoice, Lead, Project, RecurringTransactionRule, SiteIssue, SiteVisit, StaffActivity, Task, Transaction, Vendor, Account

User = get_user_model()


class ProjectFilter(django_filters.FilterSet):
    ordering = django_filters.OrderingFilter(
        label='Sort',
        fields=(
            ('code', 'code'),
            ('client__name', 'client'),
            ('project_manager__first_name', 'manager'),
            ('site_engineer__first_name', 'site_engineer'),
            ('current_stage', 'stage'),
            ('health_status', 'health'),
            ('start_date', 'start_date'),
            ('expected_handover', 'expected_handover'),
            ('updated_at', 'updated_at'),
        ),
        field_labels={
            'code': 'Code',
            'client__name': 'Client',
            'project_manager__first_name': 'Manager',
            'site_engineer__first_name': 'Site engineer',
            'current_stage': 'Stage',
            'health_status': 'Health',
            'start_date': 'Start date',
            'expected_handover': 'Handover date',
            'updated_at': 'Last updated',
        },
    )
    current_stage = django_filters.ChoiceFilter(choices=Project.Stage.choices)
    health_status = django_filters.ChoiceFilter(choices=Project.Health.choices)
    project_type = django_filters.ChoiceFilter(choices=Project.ProjectType.choices)
    project_manager = django_filters.ModelChoiceFilter(queryset=User.objects.all(), label='Manager')
    site_engineer = django_filters.ModelChoiceFilter(queryset=User.objects.all(), label='Site engineer')

    class Meta:
        model = Project
        fields = ['client', 'project_manager', 'site_engineer', 'project_type', 'current_stage', 'health_status']


class TaskFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Task.Status.choices)
    priority = django_filters.ChoiceFilter(choices=Task.Priority.choices)
    due_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = Task
        fields = ['project', 'assigned_to', 'status', 'priority']


class SiteVisitFilter(django_filters.FilterSet):
    visit_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    visited_by = django_filters.ModelChoiceFilter(queryset=User.objects.all())

    class Meta:
        model = SiteVisit
        fields = ['project', 'visited_by']


class SiteIssueFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=SiteIssue.Status.choices)
    raised_on = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = SiteIssue
        fields = ['project', 'status']


class InvoiceFilter(django_filters.FilterSet):
    STATUS_CHOICES = [('unpaid', 'Unpaid (open)')] + list(Invoice.Status.choices)

    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, method='filter_status')
    invoice_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    lead = django_filters.ModelChoiceFilter(queryset=Invoice.objects.none(), label='Lead (PR)')

    def filter_status(self, queryset, name, value):
        if value == 'unpaid':
            return queryset.exclude(status=Invoice.Status.PAID)
        if value:
            return queryset.filter(**{name: value})
        return queryset

    class Meta:
        model = Invoice
        fields = ['project', 'lead', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'lead' in self.filters:
            self.filters['lead'].queryset = Lead.objects.all()
            self.filters['lead'].label = 'Lead (PR)'


class TransactionFilter(django_filters.FilterSet):
    date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    category = django_filters.ChoiceFilter(choices=Transaction.Category.choices)
    related_person = django_filters.ModelChoiceFilter(queryset=User.objects.all(), label='Person')
    related_vendor = django_filters.ModelChoiceFilter(queryset=Vendor.objects.all(), label='Vendor')
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all(), label='Account')

    class Meta:
        model = Transaction
        fields = ['date', 'category', 'account', 'related_project', 'related_client', 'related_vendor', 'related_person']


class BillFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Bill.Status.choices)
    bill_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    due_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = Bill
        fields = ['vendor', 'project', 'status']


class ClientAdvanceFilter(django_filters.FilterSet):
    received_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = ClientAdvance
        fields = ['project', 'client']


class ExpenseClaimFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ExpenseClaim.Status.choices)
    expense_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    employee = django_filters.ModelChoiceFilter(queryset=User.objects.all())

    class Meta:
        model = ExpenseClaim
        fields = ['status', 'employee', 'project']


class RecurringRuleFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = RecurringTransactionRule
        fields = ['is_active', 'category', 'account', 'related_project', 'related_vendor']


class StaffActivityFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_q', label='Search')
    actor = django_filters.ModelChoiceFilter(queryset=User.objects.all())
    category = django_filters.ChoiceFilter(choices=StaffActivity.Category.choices)
    from_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        label='From',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    to_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        label='To',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def filter_q(self, queryset, name, value):
        value = (value or '').strip()
        if not value:
            return queryset
        return queryset.filter(message__icontains=value)

    class Meta:
        model = StaffActivity
        fields = ['q', 'actor', 'category', 'from_date', 'to_date']
