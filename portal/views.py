from base64 import b64encode
from collections import defaultdict
import csv
from datetime import timedelta
import datetime as dt
from decimal import Decimal
import json
import logging
import mimetypes
import os
import re
from io import BytesIO
from django.conf import settings as dj_settings
from django.contrib.staticfiles import finders

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    Q,
    Sum,
    OuterRef,
    Subquery,
    Value,
    F,
    DecimalField,
    DateTimeField,
    ExpressionWrapper,
    Exists,
    Max,
    IntegerField,
    Case,
    When,
)
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models.functions import Coalesce, Greatest, Cast, TruncMonth

ITEMS_PER_PAGE = 25
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

from .decorators import role_required, module_required
from .filters import InvoiceFilter, ProjectFilter, SiteIssueFilter, SiteVisitFilter, TaskFilter, TransactionFilter
from .forms import (
    ClientForm,
    DocumentForm,
    FirmProfileForm,
    InvoiceForm,
    InvoiceLineFormSet,
    LeadForm,
    ReceiptForm,
    PaymentForm,
    ProjectForm,
    SiteIssueForm,
    SiteIssueAttachmentForm,
    SiteVisitAttachmentForm,
    SiteVisitForm,
    StageUpdateForm,
    TaskForm,
    TaskCommentForm,
    TransactionForm,
    ReminderSettingForm,
    UserForm,
    RolePermissionForm,
)
from .models import (
    Client,
    Document,
    FirmProfile,
    Invoice,
    Lead,
    Notification,
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
from .permissions import MODULE_LABELS, ensure_role_permissions, get_permissions_for_user
from .notifications.tasks import notify_task_change
from .notifications.whatsapp import send_text as send_whatsapp_text
from django.core.mail import send_mail


def _can_view_all_tasks(user) -> bool:
    """Admins and superusers can view every task; others are limited to their own."""
    return bool(user and (user.is_superuser or getattr(user, 'role', None) == User.Roles.ADMIN))


def _visible_tasks_for_user(user, queryset):
    return queryset if _can_view_all_tasks(user) else queryset.filter(assigned_to=user)


def _can_view_all_projects(user) -> bool:
    """Users with finance/invoice access can view all projects."""
    if not user or not user.is_authenticated:
        return False
    perms = get_permissions_for_user(user)
    return bool(user.is_superuser or perms.get('finance') or perms.get('invoices'))


def _visible_projects_for_user(user, queryset=None):
    qs = queryset or Project.objects.all()
    if _can_view_all_projects(user):
        return qs
    return qs.filter(
        Q(project_manager=user) | Q(site_engineer=user) | Q(tasks__assigned_to=user)
    ).distinct()


MENTION_RE = re.compile(r'@([\w.@+-]+)')


def _mentioned_users(text: str):
    usernames = {m.strip() for m in MENTION_RE.findall(text or '') if m.strip()}
    if not usernames:
        return User.objects.none()
    return User.objects.filter(username__in=usernames, is_active=True)


def _get_default_context():
    return {'currency': '₹'}


def _task_template_data():
    return list(
        TaskTemplate.objects.order_by('title').values(
            'id', 'title', 'description', 'status', 'priority', 'due_in_days'
        )
    )


def _refresh_invoice_status(invoice: Invoice) -> Invoice:
    invoice.refresh_status()
    return invoice


def _formset_line_total(formset) -> Decimal:
    total = Decimal('0')
    for form in formset:
        data = getattr(form, 'cleaned_data', None)
        if not data or data.get('DELETE'):
            continue
        if not any(data.get(field) for field in ('description', 'quantity', 'unit_price')):
            continue
        qty = data.get('quantity') or Decimal('0')
        unit_price = data.get('unit_price') or Decimal('0')
        total += qty * unit_price
    return total


@login_required
def dashboard(request):
    today = timezone.localdate()
    start_month = today.replace(day=1)
    perms = get_permissions_for_user(request.user)
    show_finance = request.user.is_superuser or perms.get('finance') or perms.get('invoices')

    projects = Project.objects.select_related('client')
    if not show_finance:
        projects = projects.filter(
            Q(project_manager=request.user)
            | Q(site_engineer=request.user)
            | Q(tasks__assigned_to=request.user)
        ).distinct()

    total_active = projects.exclude(current_stage=Project.Stage.CLOSED).count()
    stage_counts = projects.values('current_stage').annotate(total=Count('id')).order_by('current_stage')

    site_visits_scope = SiteVisit.objects.filter(visit_date__gte=start_month)
    if not show_finance:
        site_visits_scope = site_visits_scope.filter(
            Q(visited_by=request.user)
            | Q(project__project_manager=request.user)
            | Q(project__site_engineer=request.user)
        )
    site_visits_this_month = site_visits_scope.count()

    tasks_scope = _visible_tasks_for_user(
        request.user,
        Task.objects.select_related('project', 'project__client').filter(
            status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]
        ),
    )
    upcoming_tasks = tasks_scope.filter(due_date__isnull=False).order_by('due_date')[:5]
    my_open_tasks_count = tasks_scope.count()

    upcoming_handover = projects.filter(expected_handover__gte=today, expected_handover__lte=today + timedelta(days=30))

    financial_context = {}
    top_projects = Project.objects.none()
    if show_finance:
        invoices_this_month = Invoice.objects.filter(invoice_date__gte=start_month).prefetch_related('lines')
        total_invoiced = sum((invoice.total_with_tax for invoice in invoices_this_month), Decimal('0'))
        payments_this_month = Payment.objects.filter(payment_date__gte=start_month)
        total_received = payments_this_month.aggregate(total=Sum('amount'))['total'] or 0

        top_projects = (
            projects.annotate(revenue=Sum('invoices__amount'))
            .order_by('-revenue')[:5]
            .select_related('client')
        )

        cash_gap_value = (total_invoiced or 0) - (total_received or 0)
        financial_context = {
            'total_invoiced_month': total_invoiced,
            'total_received_month': total_received,
            'cash_gap': cash_gap_value,
            'cash_gap_rupee': f"Rs. {cash_gap_value:,.2f}",
            'top_projects': top_projects,
        }

    context = _get_default_context() | {
        'total_projects': projects.count(),
        'active_projects': total_active,
        'stage_counts': stage_counts,
        'site_visits_this_month': site_visits_this_month,
        'upcoming_tasks': upcoming_tasks,
        'upcoming_handover': upcoming_handover,
        'top_projects': top_projects,
        'show_finance': show_finance,
        'my_open_tasks_count': my_open_tasks_count,
    } | financial_context
    return render(request, 'portal/dashboard.html', context)


@login_required
def global_search(request):
    q = (request.GET.get('q') or '').strip()
    perms = get_permissions_for_user(request.user)

    clients = Client.objects.none()
    leads = Lead.objects.none()
    projects = Project.objects.none()
    tasks = Task.objects.none()
    invoices = Invoice.objects.none()

    if q:
        if perms.get('clients'):
            clients = Client.objects.filter(
                Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
            ).order_by('name')[:10]

        if perms.get('leads'):
            leads = Lead.objects.select_related('client').filter(
                Q(title__icontains=q) | Q(client__name__icontains=q) | Q(lead_source__icontains=q)
            ).order_by('-created_at')[:10]

        if perms.get('projects'):
            projects = _visible_projects_for_user(
                request.user,
                Project.objects.select_related('client', 'project_manager'),
            ).filter(
                Q(name__icontains=q) | Q(code__icontains=q) | Q(client__name__icontains=q)
            ).order_by('-updated_at')[:10]

            tasks = _visible_tasks_for_user(
                request.user,
                Task.objects.select_related('project', 'assigned_to'),
            ).filter(
                Q(title__icontains=q) | Q(project__code__icontains=q) | Q(project__name__icontains=q)
            ).order_by('due_date')[:10]

        if perms.get('invoices') or perms.get('finance'):
            invoices = Invoice.objects.select_related(
                'project__client', 'lead__client'
            ).filter(
                Q(invoice_number__icontains=q)
                | Q(project__code__icontains=q)
                | Q(project__name__icontains=q)
                | Q(lead__title__icontains=q)
                | Q(lead__client__name__icontains=q)
            ).order_by('-invoice_date')[:10]

    return render(
        request,
        'portal/search.html',
        {
            'query': q,
            'clients': clients,
            'leads': leads,
            'projects': projects,
            'tasks': tasks,
            'invoices': invoices,
            'perms': perms,
        },
    )


@login_required
@module_required('clients')
def export_clients_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clients.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Phone', 'Email', 'City', 'State', 'Address', 'Notes'])
    for client in Client.objects.order_by('name'):
        writer.writerow([
            client.name,
            client.phone,
            client.email,
            client.city,
            client.state,
            client.address,
            client.notes,
        ])
    return response


@login_required
@module_required('projects')
def export_projects_csv(request):
    projects = _visible_projects_for_user(request.user).select_related('client', 'project_manager', 'site_engineer')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="projects.csv"'
    writer = csv.writer(response)
    writer.writerow(['Code', 'Name', 'Client', 'Type', 'Stage', 'Health', 'Manager', 'Site Engineer', 'Start Date', 'Expected Handover', 'Location'])
    for project in projects.order_by('code'):
        writer.writerow([
            project.code,
            project.name,
            project.client.name if project.client else '',
            project.get_project_type_display(),
            project.current_stage,
            project.get_health_status_display(),
            project.project_manager.get_full_name() if project.project_manager else '',
            project.site_engineer.get_full_name() if project.site_engineer else '',
            project.start_date,
            project.expected_handover,
            project.location,
        ])
    return response


@login_required
@module_required('invoices')
def export_invoices_csv(request):
    invoices = Invoice.objects.select_related('project__client', 'lead__client').prefetch_related('payments', 'lines')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Project', 'Lead', 'Client', 'Invoice Date', 'Due Date', 'Status', 'Subtotal', 'Tax %', 'Discount %', 'Total With Tax', 'Amount Received', 'Outstanding'])
    for invoice in invoices.order_by('-invoice_date'):
        client = invoice.project.client if invoice.project else (invoice.lead.client if invoice.lead else None)
        writer.writerow([
            invoice.invoice_number,
            invoice.project.code if invoice.project else '',
            invoice.lead.title if invoice.lead else '',
            client.name if client else '',
            invoice.invoice_date,
            invoice.due_date,
            invoice.get_status_display(),
            invoice.subtotal,
            invoice.tax_percent,
            invoice.discount_percent,
            invoice.total_with_tax,
            invoice.amount_received,
            invoice.outstanding,
        ])
    return response


@login_required
@module_required('clients')
def client_list(request):
    base_clients = Client.objects.all()

    invoice_totals = (
        Invoice.objects.filter(project__client=OuterRef('pk'))
        .values('project__client')
        .annotate(
            total_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .values('total_amount')[:1]
    )
    payment_totals = (
        Payment.objects.filter(invoice__project__client=OuterRef('pk'))
        .values('invoice__project__client')
        .annotate(
            total_paid=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .values('total_paid')[:1]
    )
    overdue_exists = Invoice.objects.filter(
        project__client=OuterRef('pk'),
        status=Invoice.Status.OVERDUE,
    )

    fallback_dt = Value(
        timezone.make_aware(dt.datetime(2000, 1, 1)),
        output_field=DateTimeField(),
    )

    clients = (
        base_clients
        .annotate(
            project_count=Count('projects', distinct=True),
            invoice_count=Count('projects__invoices', distinct=True),
            first_project_id=Subquery(Project.objects.filter(client=OuterRef('pk')).values('pk')[:1]),
            invoice_total=Coalesce(
                Subquery(invoice_totals),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            payment_total=Coalesce(
                Subquery(payment_totals),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            last_project_update=Max('projects__updated_at'),
            last_invoice_date_dt=Cast(Max('projects__invoices__invoice_date'), output_field=DateTimeField()),
            has_overdue=Exists(overdue_exists),
        )
        .annotate(
            last_activity=Greatest(
                Coalesce('last_project_update', fallback_dt),
                Coalesce('last_invoice_date_dt', fallback_dt),
            ),
            outstanding_total=ExpressionWrapper(
                F('invoice_total') - F('payment_total'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .order_by('name')
    )

    search = request.GET.get('q')
    city_filter = request.GET.get('city')
    only_overdue = request.GET.get('overdue') == '1'
    has_contact = request.GET.get('contact') == '1'

    if search:
        clients = clients.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search))
    if city_filter:
        clients = clients.filter(city__iexact=city_filter)
    if only_overdue:
        clients = clients.filter(has_overdue=True)
    if has_contact:
        clients = clients.filter(Q(phone__isnull=False, phone__gt='') | Q(email__isnull=False, email__gt=''))

    cities = base_clients.exclude(city='').values_list('city', flat=True).distinct().order_by('city')

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, 'Client saved.')
            if request.POST.get('next') == 'project':
                return redirect(f"{reverse('project_create')}?client={client.pk}")
            return redirect('client_list')
    else:
        form = ClientForm()

    context = {
        'clients': clients,
        'form': form,
        'cities': cities,
        'summary': clients.aggregate(
            total_clients=Count('id'),
            overdue_clients=Sum(
                Case(
                    When(has_overdue=True, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            outstanding_sum=Sum(
                ExpressionWrapper(
                    F('invoice_total') - F('payment_total'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            ),
        ),
        'applied_filters': {
            'q': search or '',
            'city': city_filter or '',
            'overdue': only_overdue,
            'contact': has_contact,
        },
    }
    return render(request, 'portal/clients.html', context)


@login_required
@module_required('clients')
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client updated.')
            return redirect('client_list')
    else:
        form = ClientForm(instance=client)
    return render(request, 'portal/client_form.html', {'form': form, 'client': client})


@login_required
@module_required('leads')
def lead_list(request):
    leads = Lead.objects.select_related('client').annotate(project_count=Count('projects')).order_by('-created_at')
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    # Pagination
    paginator = Paginator(leads, ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'portal/leads.html', {
        'leads': page_obj,
        'page_obj': page_obj,
        'statuses': Lead.Status.choices,
        'selected_status': status,
    })


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('leads')
def lead_create(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.created_by = request.user

            # Handle inline client creation
            new_client_name = form.cleaned_data.get('new_client_name')
            if new_client_name:
                client = Client.objects.create(
                    name=new_client_name,
                    phone=form.cleaned_data.get('new_client_phone', ''),
                    email=form.cleaned_data.get('new_client_email', ''),
                )
                lead.client = client
                messages.success(request, f'Client "{client.name}" created.')

            lead.save()
            messages.success(request, 'Lead created.')
            return redirect('lead_list')
    else:
        form = LeadForm()
    return render(request, 'portal/lead_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('leads')
def lead_edit(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lead updated.')
            return redirect('lead_list')
    else:
        form = LeadForm(instance=lead)
    return render(request, 'portal/lead_form.html', {'form': form, 'lead': lead})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('leads')
def lead_convert(request, pk):
    lead = get_object_or_404(Lead.objects.select_related('client'), pk=pk)
    if lead.status == Lead.Status.LOST:
        messages.warning(request, 'Lost leads cannot be converted. Please reopen the lead first.')
        return redirect('lead_list')
    if lead.is_converted:
        project = lead.projects.first()
        messages.info(
            request,
            f'This lead is already converted{f" to project {project.code}" if project else ""}.',
        )
        if project:
            return redirect('project_detail', pk=project.pk)
        return redirect('lead_list')
    if request.method == 'POST':
        project_form = ProjectForm(request.POST)
        if project_form.is_valid():
            project = project_form.save(commit=False)
            project.client = lead.client
            project.lead = lead
            if not project.name:
                project.name = lead.title
            if lead.planning_details and not project.description:
                project.description = lead.planning_details
            project.save()
            ProjectStageHistory.objects.create(project=project, stage=project.current_stage, changed_by=request.user)
            lead.status = Lead.Status.WON
            lead.converted_at = timezone.now()
            lead.converted_by = request.user
            lead.save(update_fields=['status', 'converted_at', 'converted_by'])
            messages.success(request, 'Lead converted to project.')
            return redirect('project_detail', pk=project.pk)
    else:
        initial = {
            'client': lead.client,
            'lead': lead,
            'name': lead.title,
        }
        project_form = ProjectForm(initial=initial)
    return render(request, 'portal/lead_convert.html', {'lead': lead, 'form': project_form})


@login_required
@module_required('projects')
def project_list(request):
    base_qs = _visible_projects_for_user(
        request.user,
        Project.objects.select_related('client', 'project_manager', 'site_engineer'),
    )
    project_filter = ProjectFilter(request.GET, queryset=base_qs)
    qs = project_filter.qs
    context = {
        'filter': project_filter,
        'project_summary': {
            'total': qs.count(),
            'active': qs.exclude(current_stage=Project.Stage.CLOSED).count(),
            'at_risk': qs.filter(health_status=Project.Health.AT_RISK).count(),
            'delayed': qs.filter(health_status=Project.Health.DELAYED).count(),
        },
    }
    return render(request, 'portal/projects.html', context)


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('projects')
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            ProjectStageHistory.objects.create(project=project, stage=project.current_stage, changed_by=request.user)
            messages.success(request, 'Project created.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'portal/project_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('projects')
def project_edit(request, pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, 'Project updated.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'portal/project_form.html', {'form': form, 'project': project})


@login_required
@module_required('projects')
def project_detail(request, pk):
    project_qs = _visible_projects_for_user(
        request.user,
        Project.objects.select_related('client', 'lead', 'lead__client', 'project_manager', 'site_engineer'),
    )
    project = get_object_or_404(project_qs, pk=pk)
    visible_tasks = _visible_tasks_for_user(
        request.user, project.tasks.select_related('assigned_to')
    )
    open_tasks = visible_tasks.exclude(status=Task.Status.DONE)
    visible_open_tasks = open_tasks.count()
    visible_total_tasks = visible_tasks.count()
    tasks = open_tasks
    site_visits = project.site_visits.order_by('-visit_date')[:5]
    issues = project.issues.order_by('-raised_on')[:5]
    documents = project.documents.all()[:5]
    stage_history = project.stage_history.all()
    stage_form = StageUpdateForm(initial={'stage': project.current_stage})
    can_manage_tasks = request.user.is_superuser or request.user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)

    month_buckets = defaultdict(lambda: {'invoiced': Decimal('0'), 'expenses': Decimal('0')})
    for row in (
        Invoice.objects.filter(project=project)
        .annotate(month=TruncMonth('invoice_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['invoiced'] += row['total'] or Decimal('0')
    for row in (
        Transaction.objects.filter(related_project=project)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('debit'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['expenses'] += row['total'] or Decimal('0')
    for row in (
        SiteVisit.objects.filter(project=project)
        .annotate(month=TruncMonth('visit_date'))
        .values('month')
        .annotate(total=Sum('expenses'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['expenses'] += row['total'] or Decimal('0')

    months_sorted = sorted(month_buckets.keys())
    profit_chart_data = {
        'labels': [m.strftime('%b %Y') for m in months_sorted],
        'invoiced': [float(month_buckets[m]['invoiced']) for m in months_sorted],
        'expenses': [float(month_buckets[m]['expenses']) for m in months_sorted],
        'profit': [float(month_buckets[m]['invoiced'] - month_buckets[m]['expenses']) for m in months_sorted],
    }
    return render(
        request,
        'portal/project_detail.html',
        {
            'project': project,
            'tasks': tasks,
            'site_visits': site_visits,
            'issues': issues,
            'documents': documents,
            'stage_history': stage_history,
            'stage_form': stage_form,
            'visible_open_tasks': visible_open_tasks,
            'visible_total_tasks': visible_total_tasks,
            'currency': '₹',
            'can_manage_tasks': can_manage_tasks,
            'profit_chart_data': json.dumps(profit_chart_data),
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('projects')
def project_stage_update(request, pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    if request.method == 'POST':
        form = StageUpdateForm(request.POST)
        if form.is_valid():
            history = form.save(commit=False)
            history.project = project
            history.changed_by = request.user
            history.save()
            project.current_stage = history.stage
            project.save(update_fields=['current_stage'])
            messages.success(request, 'Stage updated.')
    return redirect('project_detail', pk=pk)


@login_required
@module_required('projects')
def project_timeline(request, pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    history = list(project.stage_history.order_by('changed_on', 'created_at'))
    phases = []
    if history:
        for idx, change in enumerate(history):
            start = change.changed_on
            end = history[idx + 1].changed_on - timedelta(days=1) if idx + 1 < len(history) else timezone.localdate()
            phases.append(
                {
                    'stage': change.stage,
                    'start': start,
                    'end': end,
                    'duration_days': (end - start).days + 1 if start and end else None,
                    'changed_by': change.changed_by,
                    'notes': change.notes,
                }
            )
    elif project.start_date:
        phases.append(
            {
                'stage': project.current_stage,
                'start': project.start_date,
                'end': timezone.localdate(),
                'duration_days': (timezone.localdate() - project.start_date).days + 1 if project.start_date else None,
                'changed_by': None,
                'notes': '',
            }
        )

    tasks = _visible_tasks_for_user(request.user, project.tasks.select_related('assigned_to')).order_by('due_date')
    return render(
        request,
        'portal/project_timeline.html',
        {
            'project': project,
            'phases': phases,
            'tasks': tasks,
            'today': timezone.localdate(),
        },
    )


@login_required
@module_required('projects')
def project_tasks(request, pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    today = timezone.localdate()
    visible_tasks_qs = _visible_tasks_for_user(request.user, project.tasks.select_related('assigned_to'))

    assigned_to_filter = request.GET.get('assigned_to') or ''
    priority_filter = request.GET.get('priority') or ''
    overdue_filter = request.GET.get('overdue') == '1'

    tasks_qs = visible_tasks_qs
    if assigned_to_filter:
        if assigned_to_filter == 'unassigned':
            tasks_qs = tasks_qs.filter(assigned_to__isnull=True)
        else:
            tasks_qs = tasks_qs.filter(assigned_to_id=assigned_to_filter)
    if priority_filter:
        tasks_qs = tasks_qs.filter(priority=priority_filter)
    if overdue_filter:
        tasks_qs = tasks_qs.filter(due_date__lt=today).exclude(status=Task.Status.DONE)

    columns = {code: [] for code, _ in Task.Status.choices}
    for task in tasks_qs:
        columns.setdefault(task.status, []).append(task)

    wip_limits = getattr(dj_settings, 'KANBAN_WIP_LIMITS', {}) or {}
    wip_counts = {code: visible_tasks_qs.filter(status=code).count() for code, _ in Task.Status.choices}
    can_manage_tasks = request.user.is_superuser or request.user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)
    form = TaskForm(initial={'project': project})
    if not _can_view_all_projects(request.user):
        form.fields['project'].queryset = _visible_projects_for_user(request.user)
    if request.method == 'POST':
        if not can_manage_tasks:
            return HttpResponseForbidden("You do not have permission to add tasks.")
        form = TaskForm(request.POST)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = _visible_projects_for_user(request.user)
        if form.is_valid():
            task = form.save(commit=False)
            if task.project_id != project.pk:
                return HttpResponseForbidden("You do not have permission to add tasks to this project.")
            task.save()
            form.save_m2m()
            if task.assigned_to_id:
                task.watchers.add(task.assigned_to)
            notify_task_change(
                task,
                actor=request.user,
                message=f"{request.user} created task “{task.title}”.",
                category='task_created',
            )
            messages.success(request, 'Task added.')
            return redirect('project_tasks', pk=pk)
    return render(
        request,
        'portal/project_tasks.html',
        {
            'project': project,
            'columns': columns,
            'form': form,
            'can_manage_tasks': can_manage_tasks,
            'statuses': Task.Status.choices,
            'task_templates_json': _task_template_data(),
            'today': today,
            'assignees': User.objects.filter(is_active=True).order_by('first_name', 'username'),
            'assigned_to_filter': assigned_to_filter,
            'priority_filter': priority_filter,
            'overdue_filter': overdue_filter,
            'priority_choices': Task.Priority.choices,
            'wip_limits': wip_limits,
            'wip_counts': wip_counts,
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('projects')
def task_create(request):
    project_id = request.GET.get('project')
    project = None
    if project_id:
        project = get_object_or_404(_visible_projects_for_user(request.user), pk=project_id)
    initial = {'project': project} if project else None
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = _visible_projects_for_user(request.user)
        if form.is_valid():
            task = form.save(commit=False)
            if not _visible_projects_for_user(request.user).filter(pk=task.project_id).exists():
                return HttpResponseForbidden("You do not have permission to add tasks to that project.")
            task.save()
            form.save_m2m()
            if task.assigned_to_id:
                task.watchers.add(task.assigned_to)
            notify_task_change(
                task,
                actor=request.user,
                message=f"{request.user} created task “{task.title}”.",
                category='task_created',
            )
            messages.success(request, 'Task created.')
            return redirect('project_detail', pk=task.project.pk)
    else:
        form = TaskForm(initial=initial)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = _visible_projects_for_user(request.user)
    return render(
        request,
        'portal/task_form.html',
        {'form': form, 'project': project, 'task_templates_json': _task_template_data()},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
@module_required('projects')
def task_edit(request, pk):
    visible_projects = _visible_projects_for_user(request.user)
    task_qs = Task.objects.select_related('project')
    if not _can_view_all_projects(request.user):
        task_qs = task_qs.filter(project__in=visible_projects)
    task = get_object_or_404(task_qs, pk=pk)
    if request.method == 'POST':
        old_status = task.status
        old_assigned_to = task.assigned_to
        old_assigned_to_id = task.assigned_to_id
        old_due_date = task.due_date
        old_priority = task.priority
        form = TaskForm(request.POST, instance=task)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
        if form.is_valid():
            updated_task = form.save(commit=False)
            if not visible_projects.filter(pk=updated_task.project_id).exists():
                return HttpResponseForbidden("You do not have permission to move this task to that project.")
            updated_task.save()
            form.save_m2m()
            changes = []
            if old_status != updated_task.status:
                changes.append(f"status {old_status} → {updated_task.status}")
            if old_priority != updated_task.priority:
                changes.append(f"priority {old_priority} → {updated_task.priority}")
            if old_due_date != updated_task.due_date:
                changes.append(f"due {old_due_date or '—'} → {updated_task.due_date or '—'}")
            if old_assigned_to_id != updated_task.assigned_to_id:
                changes.append(
                    f"assignee {old_assigned_to or 'Unassigned'} → {updated_task.assigned_to or 'Unassigned'}"
                )
                if updated_task.assigned_to_id:
                    updated_task.watchers.add(updated_task.assigned_to)
            if changes or form.changed_data:
                if changes:
                    message = f"{request.user} updated task “{updated_task.title}”: " + "; ".join(changes)
                else:
                    message = f"{request.user} updated task “{updated_task.title}”."
                notify_task_change(
                    updated_task,
                    actor=request.user,
                    message=message,
                    category='task_updated',
                )
            messages.success(request, 'Task updated.')
            return redirect('project_detail', pk=updated_task.project.pk)
    else:
        form = TaskForm(instance=task)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
    return render(
        request,
        'portal/task_form.html',
        {'form': form, 'task': task, 'project': task.project, 'task_templates_json': _task_template_data()},
    )


@login_required
@module_required('projects')
def task_detail(request, pk):
    visible_projects = _visible_projects_for_user(request.user)
    task_qs = Task.objects.select_related('project', 'assigned_to').prefetch_related('watchers')
    if not _can_view_all_projects(request.user):
        task_qs = task_qs.filter(project__in=visible_projects)
    task_qs = _visible_tasks_for_user(request.user, task_qs)
    task = get_object_or_404(task_qs, pk=pk)

    comments_qs = task.comments.select_related('author').prefetch_related('attachments')
    if request.method == 'POST':
        form = TaskCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            for uploaded in form.cleaned_data.get('attachments') or []:
                TaskCommentAttachment.objects.create(comment=comment, file=uploaded)

            # Auto-watch when commenting
            if task.watchers.filter(pk=request.user.pk).exists() is False:
                task.watchers.add(request.user)

            for user in _mentioned_users(comment.body):
                if user.pk == request.user.pk:
                    continue
                Notification.objects.create(
                    user=user,
                    message=f"{request.user} mentioned you on task “{task.title}”.",
                    category='task_mention',
                    related_url=reverse('task_detail', args=[task.pk]),
                )

            messages.success(request, 'Comment added.')
            return redirect('task_detail', pk=pk)
    else:
        form = TaskCommentForm()

    return render(
        request,
        'portal/task_detail.html',
        {
            'task': task,
            'project': task.project,
            'comments': comments_qs,
            'form': form,
        },
    )


@login_required
@module_required('projects')
def task_quick_update(request, pk):
    """Lightweight task update for kanban drag/drop and assignee self-updates."""
    if request.method != 'POST':
        return HttpResponseForbidden('Update requires POST.')

    visible_projects = _visible_projects_for_user(request.user)
    task_qs = Task.objects.select_related('project')
    if not _can_view_all_projects(request.user):
        task_qs = task_qs.filter(project__in=visible_projects)
    task = get_object_or_404(task_qs, pk=pk)

    can_manage_tasks = request.user.is_superuser or request.user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)
    can_self_update = task.assigned_to_id == request.user.id
    if not (can_manage_tasks or can_self_update):
        return HttpResponseForbidden('You do not have permission to update this task.')

    payload = {}
    if request.headers.get('Content-Type', '').startswith('application/json'):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except ValueError:
            payload = {}
    else:
        payload = request.POST

    new_status = payload.get('status')
    if new_status not in Task.Status.values:
        return JsonResponse({'ok': False, 'error': 'Invalid status'}, status=400)

    if new_status != task.status:
        old_status = task.status
        task.status = new_status
        task.save(update_fields=['status'])
        TaskComment.objects.create(
            task=task,
            author=request.user,
            body=f"Status changed from {old_status} to {new_status}.",
            is_system=True,
        )
        notify_task_change(
            task,
            actor=request.user,
            message=f"{request.user} moved task “{task.title}” to {task.get_status_display()}.",
            category='task_status_changed',
        )

    return JsonResponse({'ok': True, 'status': task.status})


@login_required
@module_required('projects')
def my_tasks(request):
    task_filter = TaskFilter(request.GET, queryset=Task.objects.filter(assigned_to=request.user))
    return render(request, 'portal/my_tasks.html', {'filter': task_filter})


@login_required
@module_required('site_visits')
def site_visit_list(request):
    visits_qs = SiteVisit.objects.select_related('project', 'visited_by')
    if not _can_view_all_projects(request.user):
        visits_qs = visits_qs.filter(project__in=_visible_projects_for_user(request.user))
    visit_filter = SiteVisitFilter(request.GET, queryset=visits_qs)
    return render(request, 'portal/site_visits.html', {'filter': visit_filter})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
@module_required('site_visits')
def site_visit_create(request):
    visible_projects = _visible_projects_for_user(request.user)
    if request.method == 'POST':
        form = SiteVisitForm(request.POST, request.FILES)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
        if form.is_valid():
            visit = form.save(commit=False)
            if not visible_projects.filter(pk=visit.project_id).exists():
                return HttpResponseForbidden("You do not have permission to log visits for that project.")
            visit.save()
            for file in request.FILES.getlist('attachments'):
                SiteVisitAttachment.objects.create(site_visit=visit, file=file)
            messages.success(request, 'Site visit logged.')
            return redirect('site_visit_list')
    else:
        initial = {'visited_by': request.user}
        project_id = request.GET.get('project')
        if project_id and visible_projects.filter(pk=project_id).exists():
            initial['project'] = project_id
        form = SiteVisitForm(initial=initial)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
    return render(request, 'portal/site_visit_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
@module_required('site_visits')
def site_visit_edit(request, pk):
    visible_projects = _visible_projects_for_user(request.user)
    visit_qs = SiteVisit.objects.select_related('project', 'visited_by')
    if not _can_view_all_projects(request.user):
        visit_qs = visit_qs.filter(project__in=visible_projects)
    visit = get_object_or_404(visit_qs, pk=pk)
    if request.method == 'POST':
        form = SiteVisitForm(request.POST, request.FILES, instance=visit)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
        if form.is_valid():
            updated_visit = form.save(commit=False)
            if not visible_projects.filter(pk=updated_visit.project_id).exists():
                return HttpResponseForbidden("You do not have permission to move this visit to that project.")
            updated_visit.save()
            for file in request.FILES.getlist('attachments'):
                SiteVisitAttachment.objects.create(site_visit=updated_visit, file=file)
            messages.success(request, 'Site visit updated.')
            return redirect('site_visit_list')
    else:
        form = SiteVisitForm(instance=visit)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
    return render(request, 'portal/site_visit_form.html', {'form': form, 'visit': visit})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
@module_required('site_visits')
def site_visit_detail(request, pk):
    visible_projects = _visible_projects_for_user(request.user)
    visit_qs = SiteVisit.objects.select_related('project', 'visited_by')
    if not _can_view_all_projects(request.user):
        visit_qs = visit_qs.filter(project__in=visible_projects)
    visit = get_object_or_404(visit_qs, pk=pk)
    attachment_form = SiteVisitAttachmentForm()
    if request.method == 'POST':
        attachment_form = SiteVisitAttachmentForm(request.POST, request.FILES)
        if attachment_form.is_valid():
            attachment = attachment_form.save(commit=False)
            attachment.site_visit = visit
            attachment.save()
            messages.success(request, 'Attachment added.')
            return redirect('site_visit_detail', pk=pk)
    return render(
        request,
        'portal/site_visit_detail.html',
        {'visit': visit, 'attachment_form': attachment_form, 'attachments': visit.attachments.all()},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
@module_required('site_visits')
def issue_list(request):
    visible_projects = _visible_projects_for_user(request.user)
    issues_qs = SiteIssue.objects.select_related('project', 'site_visit')
    if not _can_view_all_projects(request.user):
        issues_qs = issues_qs.filter(project__in=visible_projects)
    issue_filter = SiteIssueFilter(request.GET, queryset=issues_qs)
    if request.method == 'POST':
        form = SiteIssueForm(request.POST, request.FILES)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
            form.fields['site_visit'].queryset = SiteVisit.objects.filter(project__in=visible_projects)
        if form.is_valid():
            issue = form.save(commit=False)
            if not visible_projects.filter(pk=issue.project_id).exists():
                return HttpResponseForbidden("You do not have permission to log issues for that project.")
            if issue.site_visit_id and not SiteVisit.objects.filter(pk=issue.site_visit_id, project__in=visible_projects).exists():
                return HttpResponseForbidden("You do not have permission to link that site visit.")
            issue.save()
            for file in request.FILES.getlist('attachments'):
                SiteIssueAttachment.objects.create(issue=issue, file=file)
            messages.success(request, 'Issue logged.')
            return redirect('issue_list')
    else:
        initial = {}
        project_id = request.GET.get('project')
        if project_id and visible_projects.filter(pk=project_id).exists():
            initial['project'] = project_id
        form = SiteIssueForm(initial=initial)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
            form.fields['site_visit'].queryset = SiteVisit.objects.filter(project__in=visible_projects)
    return render(request, 'portal/issues.html', {'filter': issue_filter, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
@module_required('site_visits')
def issue_detail(request, pk):
    visible_projects = _visible_projects_for_user(request.user)
    issue_qs = SiteIssue.objects.select_related('project', 'site_visit')
    if not _can_view_all_projects(request.user):
        issue_qs = issue_qs.filter(project__in=visible_projects)
    issue = get_object_or_404(issue_qs, pk=pk)

    attachment_form = SiteIssueAttachmentForm()
    if request.method == 'POST':
        attachment_form = SiteIssueAttachmentForm(request.POST, request.FILES)
        if attachment_form.is_valid():
            attachment = attachment_form.save(commit=False)
            attachment.issue = issue
            attachment.save()
            messages.success(request, 'Attachment added.')
            return redirect('issue_detail', pk=pk)

    return render(
        request,
        'portal/issue_detail.html',
        {
            'issue': issue,
            'attachment_form': attachment_form,
            'attachments': issue.attachments.all(),
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_list(request):
    invoice_qs = Invoice.objects.select_related('project', 'project__client', 'lead', 'lead__client').prefetch_related(
        'lines', 'payments'
    )
    invoice_filter = InvoiceFilter(request.GET, queryset=invoice_qs)

    # Pagination
    paginator = Paginator(invoice_filter.qs, ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'portal/invoices.html', {
        'filter': invoice_filter,
        'invoices': page_obj,
        'page_obj': page_obj,
    })


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_pdf(request, invoice_pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'project__client', 'project__project_manager', 'lead', 'lead__client'
        ).prefetch_related('lines', 'payments'),
        pk=invoice_pk,
    )
    invoice.refresh_status(save=False)
    lines = list(invoice.lines.all())
    tax_value = max(invoice.total_with_tax - invoice.taxable_amount, Decimal('0'))
    client = invoice.project.client if invoice.project else (invoice.lead.client if invoice.lead else None)
    firm = FirmProfile.objects.first()
    logo_path = None
    logo_data = None

    def _encode_image(path: str | None) -> str | None:
        if not path:
            return None
        try:
            mime, _ = mimetypes.guess_type(path)
            with open(path, 'rb') as f:
                encoded = b64encode(f.read()).decode('utf-8')
                return f"data:{mime or 'image/png'};base64,{encoded}"
        except Exception:
            return None

    if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
        logo_path = firm.logo.path
        logo_data = _encode_image(logo_path)

    if not logo_data:
        fallback_logo = finders.find('img/novart.png')
        logo_data = _encode_image(fallback_logo)

    font_candidates = [
        finders.find('fonts/DejaVuSans.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/opt/studioflow/static/fonts/DejaVuSans.ttf',
    ]
    font_path = next((p for p in font_candidates if p and os.path.exists(p)), None)
    font_data_b64 = None
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            pdfmetrics.registerFontFamily(
                'DejaVuSans',
                normal='DejaVuSans',
                bold='DejaVuSans',
                italic='DejaVuSans',
                boldItalic='DejaVuSans',
            )
            with open(font_path, 'rb') as f:
                font_data_b64 = b64encode(f.read()).decode('utf-8')
        except Exception:
            logger.exception("Failed to register PDF font at %s", font_path)
            font_path = None
    html = render_to_string(
        'portal/invoice_pdf.html',
        {
            'invoice': invoice,
            'project': invoice.project,
            'lead': invoice.lead,
            'client': client,
            'lines': lines,
            'payments': invoice.payments.all(),
            'tax_amount': tax_value,
            'firm': firm,
            'firm_logo_path': logo_path,
            'firm_logo_data': logo_data,
            'font_path': font_path,
            'font_data': font_data_b64,
            'generated_on': timezone.localtime(),
        },
    )
    pdf_file = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_file, encoding='UTF-8')
    if result.err:
        logger.exception("Invoice PDF render failed for %s", invoice_pk)
        messages.error(request, 'Unable to generate PDF right now. Please try again.')
        return redirect('invoice_list')
    pdf_file.seek(0)
    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=\"invoice-{invoice.invoice_number}.pdf\"'
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            lines_total = _formset_line_total(formset)
            amount = form.cleaned_data.get('amount') or Decimal('0')
            if lines_total and amount != lines_total:
                form.add_error('amount', f'Total amount must match line items ({lines_total}).')
            else:
                invoice = form.save(commit=False)
                if lines_total:
                    invoice.amount = lines_total
                if invoice.status == Invoice.Status.DRAFT:
                    invoice.status = Invoice.Status.SENT
                invoice.save()
                formset.instance = invoice
                formset.save()
                _refresh_invoice_status(invoice)
                messages.success(request, 'Invoice created.')
                return redirect('invoice_list')
    else:
        form = InvoiceForm()
        formset = InvoiceLineFormSet()
    return render(request, 'portal/invoice_form.html', {'form': form, 'formset': formset})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_edit(request, invoice_pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related('lines', 'payments'), pk=invoice_pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            lines_total = _formset_line_total(formset)
            amount = form.cleaned_data.get('amount') or Decimal('0')
            if lines_total and amount != lines_total:
                form.add_error('amount', f'Total amount must match line items ({lines_total}).')
            else:
                invoice = form.save(commit=False)
                if lines_total:
                    invoice.amount = lines_total
                if invoice.status == Invoice.Status.DRAFT:
                    invoice.status = Invoice.Status.SENT
                invoice.save()
                formset.save()
                _refresh_invoice_status(invoice)
                messages.success(request, 'Invoice updated.')
                return redirect('invoice_list')
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceLineFormSet(instance=invoice)
    return render(request, 'portal/invoice_form.html', {'form': form, 'formset': formset, 'invoice': invoice})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_aging(request):
    today = timezone.localdate()
    invoices = (
        Invoice.objects.exclude(status=Invoice.Status.PAID)
        .select_related('project__client', 'lead', 'lead__client')
        .prefetch_related('lines', 'payments')
    )
    buckets = {'0-30': [], '31-60': [], '61-90': [], '90+': []}
    totals = {key: Decimal('0') for key in buckets}
    for invoice in invoices:
        invoice.refresh_status(save=False, today=today)
        outstanding = invoice.outstanding
        if outstanding <= 0:
            continue
        days_overdue = max((today - invoice.due_date).days, 0)
        if days_overdue <= 30:
            bucket_key = '0-30'
        elif days_overdue <= 60:
            bucket_key = '31-60'
        elif days_overdue <= 90:
            bucket_key = '61-90'
        else:
            bucket_key = '90+'
        buckets[bucket_key].append({'invoice': invoice, 'days_overdue': days_overdue, 'outstanding': outstanding})
        totals[bucket_key] += outstanding
    grand_total = sum(totals.values(), Decimal('0'))
    return render(
        request,
        'portal/invoice_aging.html',
        {'buckets': buckets, 'totals': totals, 'grand_total': grand_total, 'today': today},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def invoice_delete(request, invoice_pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related('payments'), pk=invoice_pk)
    if request.method != 'POST':
        return HttpResponseForbidden('Delete requires POST.')
    if invoice.payments.exists():
        messages.error(request, 'Cannot delete an invoice with recorded payments.')
        return redirect('invoice_list')
    invoice.delete()
    messages.success(request, 'Invoice deleted.')
    return redirect('invoice_list')


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('invoices')
def payment_create(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    if invoice.outstanding <= 0:
        messages.info(request, 'This invoice is already settled.')
        return redirect('invoice_list')
    if request.method == 'POST':
        form = PaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.recorded_by = request.user
            payment.save()
            _refresh_invoice_status(invoice)
            messages.success(request, 'Payment recorded.')
            # Offer to generate receipt
            if 'generate_receipt' in request.POST:
                return redirect('receipt_create', payment_pk=payment.pk)
            return redirect('invoice_list')
    else:
        form = PaymentForm(initial={'received_by': request.user, 'payment_date': timezone.now().date()}, invoice=invoice)
    return render(request, 'portal/payment_form.html', {'form': form, 'invoice': invoice})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def receipt_list(request):
    receipts = Receipt.objects.select_related('payment', 'invoice', 'project', 'client').order_by('-receipt_date', '-created_at')
    q = request.GET.get('q')
    if q:
        receipts = receipts.filter(
            Q(receipt_number__icontains=q)
            | Q(invoice__invoice_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(project__code__icontains=q)
        )
    total_amount = receipts.aggregate(total=Sum('payment__amount'))['total'] or Decimal('0')
    return render(
        request,
        'portal/receipts.html',
        {'receipts': receipts, 'query': q or '', 'total_amount': total_amount},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def receipt_create(request, payment_pk):
    """
    Generate a receipt for an existing payment.
    Receipt = proof of payment given to client.
    Flow: Invoice → Record Payment → Generate Receipt
    """
    payment = get_object_or_404(
        Payment.objects.select_related('invoice__project__client', 'invoice__lead__client'),
        pk=payment_pk
    )
    # Check if receipt already exists for this payment
    if hasattr(payment, 'receipt') and payment.receipt:
        messages.info(request, f'Receipt {payment.receipt.receipt_number} already exists for this payment.')
        return redirect('receipt_pdf', receipt_pk=payment.receipt.pk)

    if request.method == 'POST':
        form = ReceiptForm(request.POST, payment=payment)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.payment = payment
            receipt.generated_by = request.user
            receipt.save()
            client = receipt.client
            receipt_url = request.build_absolute_uri(reverse('receipt_pdf', args=[receipt.pk]))
            message_body = (
                f"Payment received for invoice #{receipt.invoice.invoice_number}. "
                f"Receipt #{receipt.receipt_number}: {receipt_url}"
            )
            if client:
                try:
                    if client.phone:
                        send_whatsapp_text(client.phone, message_body)
                    if client.email:
                        send_mail(
                            subject=f"Receipt #{receipt.receipt_number}",
                            message=message_body,
                            from_email=None,
                            recipient_list=[client.email],
                            fail_silently=True,
                        )
                except Exception:
                    logger.exception("Failed to send receipt notification to client %s", client.pk)
            messages.success(request, f"Receipt {receipt.receipt_number} generated.")
            return redirect('receipt_pdf', receipt_pk=receipt.pk)
    else:
        form = ReceiptForm(payment=payment)

    return render(request, 'portal/receipt_form.html', {
        'form': form,
        'payment': payment,
        'invoice': payment.invoice,
    })


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def receipt_pdf(request, receipt_pk):
    """Generate a PDF receipt to give to the client as proof of payment."""
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'payment__invoice__project__client',
            'payment__invoice__lead__client',
            'payment__received_by',
            'client',
            'project',
            'generated_by',
        ),
        pk=receipt_pk,
    )
    payment = receipt.payment
    invoice = payment.invoice
    client = receipt.client
    firm = FirmProfile.objects.first()

    def _encode_image(path: str | None) -> str | None:
        if not path:
            return None
        try:
            mime, _ = mimetypes.guess_type(path)
            with open(path, 'rb') as f:
                encoded = b64encode(f.read()).decode('utf-8')
                return f"data:{mime or 'image/png'};base64,{encoded}"
        except Exception:
            return None

    logo_data = None
    if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
        logo_data = _encode_image(firm.logo.path)
    if not logo_data:
        fallback_logo = finders.find('img/novart.png')
        logo_data = _encode_image(fallback_logo)

    font_candidates = [
        finders.find('fonts/DejaVuSans.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/opt/studioflow/static/fonts/DejaVuSans.ttf',
    ]
    font_path = next((p for p in font_candidates if p and os.path.exists(p)), None)
    font_data_b64 = None
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            with open(font_path, 'rb') as f:
                font_data_b64 = b64encode(f.read()).decode('utf-8')
        except Exception:
            logger.exception("Failed to register PDF font at %s", font_path)
            font_path = None

    html = render_to_string(
        'portal/receipt_pdf.html',
        {
            'receipt': receipt,
            'payment': payment,
            'invoice': invoice,
            'client': client,
            'project': receipt.project,
            'firm': firm,
            'firm_logo_data': logo_data,
            'font_path': font_path,
            'font_data': font_data_b64,
            'generated_on': timezone.localtime(),
        },
    )
    pdf_file = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_file, encoding='UTF-8')
    if result.err:
        logger.exception("Receipt PDF render failed for %s", receipt_pk)
        messages.error(request, 'Unable to generate PDF right now. Please try again.')
        return redirect('receipt_list')
    pdf_file.seek(0)
    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=\"receipt-{receipt.receipt_number}.pdf\"'
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('finance')
def transaction_list(request):
    txn_filter = TransactionFilter(request.GET, queryset=Transaction.objects.select_related('related_project'))
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.recorded_by = request.user
            txn.save()
            messages.success(request, 'Transaction saved.')
            return redirect('transaction_list')
    else:
        form = TransactionForm()
    return render(request, 'portal/transactions.html', {'filter': txn_filter, 'form': form, 'currency': '₹'})


@login_required
@module_required('docs')
def document_list(request):
    visible_projects = _visible_projects_for_user(request.user)
    documents = Document.objects.select_related('project').order_by('-created_at')
    if not _can_view_all_projects(request.user):
        documents = documents.filter(project__in=visible_projects)
    doc_type = request.GET.get('file_type')
    project_id = request.GET.get('project')
    if doc_type:
        documents = documents.filter(file_type=doc_type)
    if project_id:
        documents = documents.filter(project_id=project_id)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
        if form.is_valid():
            document = form.save(commit=False)
            if not visible_projects.filter(pk=document.project_id).exists():
                return HttpResponseForbidden("You do not have permission to upload documents to that project.")
            document.uploaded_by = request.user
            document.save()
            messages.success(request, 'Document added.')
            return redirect('document_list')
    else:
        form = DocumentForm()
        if not _can_view_all_projects(request.user):
            form.fields['project'].queryset = visible_projects
    projects = visible_projects.order_by('name') if not _can_view_all_projects(request.user) else Project.objects.order_by('name')
    return render(
        request,
        'portal/documents.html',
        {'documents': documents, 'form': form, 'projects': projects, 'file_types': Document.FileType.choices},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('finance')
def finance_dashboard(request):
    projects = Project.objects.select_related('client').prefetch_related(
        'invoices__lines',
        'invoices__payments',
        'transactions',
        'site_visits',
    )

    total_invoiced = sum((invoice.total_with_tax for invoice in Invoice.objects.prefetch_related('lines')), Decimal('0'))
    total_received = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    ledger_expenses = Transaction.objects.aggregate(total=Sum('debit'))['total'] or Decimal('0')
    site_expenses = SiteVisit.objects.aggregate(total=Sum('expenses'))['total'] or Decimal('0')
    totals = {
        'invoiced': total_invoiced,
        'received': total_received,
        'expenses': ledger_expenses + site_expenses,
    }

    month_buckets = defaultdict(lambda: {'invoiced': Decimal('0'), 'received': Decimal('0'), 'expenses': Decimal('0')})

    for row in (
        Invoice.objects.annotate(month=TruncMonth('invoice_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['invoiced'] += row['total'] or Decimal('0')

    for row in (
        Payment.objects.annotate(month=TruncMonth('payment_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['received'] += row['total'] or Decimal('0')

    for row in (
        Transaction.objects.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('debit'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['expenses'] += row['total'] or Decimal('0')

    for row in (
        SiteVisit.objects.annotate(month=TruncMonth('visit_date'))
        .values('month')
        .annotate(total=Sum('expenses'))
        .order_by('month')
    ):
        month = row['month']
        if month:
            if hasattr(month, 'date'):
                month = month.date()
            month_buckets[month]['expenses'] += row['total'] or Decimal('0')

    months_sorted = sorted(month_buckets.keys())
    chart_data = {
        'labels': [m.strftime('%b %Y') for m in months_sorted],
        'invoiced': [float(month_buckets[m]['invoiced']) for m in months_sorted],
        'received': [float(month_buckets[m]['received']) for m in months_sorted],
        'expenses': [float(month_buckets[m]['expenses']) for m in months_sorted],
    }
    return render(
        request,
        'portal/finance.html',
        {
            'projects': projects,
            'totals': totals,
            'currency': '₹',
            'chart_data': json.dumps(chart_data),
        },
    )


@login_required
@role_required(User.Roles.ADMIN)
@module_required('settings')
def firm_profile(request):
    profile, _ = FirmProfile.objects.get_or_create(singleton=True, defaults={'name': 'Your Architecture Studio'})
    if request.method == 'POST':
        form = FirmProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Firm profile updated.')
            return redirect('firm_profile')
    else:
        form = FirmProfileForm(instance=profile)
    logo_url = None
    if profile.logo and profile.logo.storage.exists(profile.logo.name):
        logo_url = profile.logo.url
    return render(request, 'portal/firm_profile.html', {'form': form, 'profile': profile, 'logo_url': logo_url})


@login_required
@role_required(User.Roles.ADMIN)
@module_required('settings')
def reminder_settings(request):
    if request.method == 'POST':
        instance_id = request.POST.get('instance_id')
        instance = ReminderSetting.objects.filter(pk=instance_id).first()
        form = ReminderSettingForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reminder setting saved.')
            return redirect('reminder_settings')
    else:
        form = ReminderSettingForm()
    forms = [ReminderSettingForm(instance=setting) for setting in ReminderSetting.objects.all()]
    return render(request, 'portal/reminders.html', {'forms': forms, 'form': form})


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    return render(request, 'portal/notifications.html', {'notifications': notifications})


@login_required
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    if notification.related_url and url_has_allowed_host_and_scheme(
        notification.related_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(notification.related_url)
    return redirect('notification_list')


@login_required
@module_required('team')
def team_list(request):
    team = (
        User.objects.order_by('role', 'first_name', 'last_name')
        .annotate(
            open_tasks_count=Count(
                'tasks', filter=Q(tasks__status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]), distinct=True
            ),
            managed_projects_count=Count('managed_projects', distinct=True),
            visits_count=Count('site_visits', distinct=True),
        )
    )
    return render(request, 'portal/team_list.html', {'team': team})


@login_required
@role_required(User.Roles.ADMIN)
@module_required('users')
def user_admin_list(request):
    users = User.objects.order_by('role', 'first_name', 'last_name')
    ensure_role_permissions()
    role_forms = {
        rp.role: RolePermissionForm(prefix=rp.role, instance=rp)
        for rp in RolePermission.objects.order_by('role')
    }
    if request.method == 'POST' and request.POST.get('perm_role'):
        role_key = request.POST.get('perm_role')
        rp = RolePermission.objects.filter(role=role_key).first()
        if rp:
            form = RolePermissionForm(request.POST, prefix=role_key, instance=rp)
            if form.is_valid():
                form.save()
                messages.success(request, f"Permissions updated for {rp.get_role_display()}.")
                return redirect('user_admin_list')
            role_forms[role_key] = form
    elif request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created.')
            return redirect('user_admin_list')
    else:
        form = UserForm()
    return render(
        request,
        'portal/user_admin.html',
        {
            'users': users,
            'form': form,
            'editing': None,
            'role_forms': role_forms,
            'module_labels': MODULE_LABELS,
            'editing_perms': None,
        },
    )


@login_required
@role_required(User.Roles.ADMIN)
@module_required('users')
def user_admin_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    ensure_role_permissions()
    role_forms = {
        rp.role: RolePermissionForm(prefix=rp.role, instance=rp)
        for rp in RolePermission.objects.order_by('role')
    }
    if request.method == 'POST' and request.POST.get('perm_role'):
        role_key = request.POST.get('perm_role')
        rp = RolePermission.objects.filter(role=role_key).first()
        if rp:
            form_perm = RolePermissionForm(request.POST, prefix=role_key, instance=rp)
            if form_perm.is_valid():
                form_perm.save()
                messages.success(request, f"Permissions updated for {rp.get_role_display()}.")
                return redirect('user_admin_edit', pk=user.pk)
            role_forms[role_key] = form_perm
    elif request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated.')
            return redirect('user_admin_list')
    else:
        form = UserForm(instance=user)
    user_perms = get_permissions_for_user(user)
    editing_perms = {
        'allowed': [(key, MODULE_LABELS.get(key, key.title())) for key, allowed in user_perms.items() if allowed],
        'blocked': [(key, MODULE_LABELS.get(key, key.title())) for key, allowed in user_perms.items() if not allowed],
    }
    return render(
        request,
        'portal/user_admin.html',
        {
            'users': User.objects.order_by('role', 'first_name'),
            'form': form,
            'editing': user,
            'role_forms': role_forms,
            'module_labels': MODULE_LABELS,
            'editing_perms': editing_perms,
        },
    )
