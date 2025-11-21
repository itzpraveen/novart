import django_filters
from django.contrib.auth import get_user_model

from .models import Invoice, Project, SiteIssue, SiteVisit, Task, Transaction

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
    status = django_filters.ChoiceFilter(choices=Invoice.Status.choices)
    invoice_date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = Invoice
        fields = ['project', 'status']


class TransactionFilter(django_filters.FilterSet):
    date = django_filters.DateFromToRangeFilter(widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    class Meta:
        model = Transaction
        fields = ['related_project', 'related_client']
