import django_filters
from django.contrib.auth import get_user_model

from .models import Invoice, Lead, Project, SiteIssue, SiteVisit, Task, Transaction

User = get_user_model()


class ProjectFilter(django_filters.FilterSet):
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

    class Meta:
        model = Transaction
        fields = ['related_project', 'related_client']
