from base64 import b64encode
from collections import defaultdict
import csv
from datetime import timedelta
import datetime as dt
from decimal import Decimal
from functools import lru_cache
import json
import logging
import mimetypes
import os
import re
from io import BytesIO, TextIOWrapper
from django.conf import settings as dj_settings
from django.contrib.staticfiles import finders

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
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

def _file_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


@lru_cache(maxsize=32)
def _data_uri_cached(path: str, mtime: float) -> str:
    mime, _ = mimetypes.guess_type(path)
    with open(path, 'rb') as f:
        encoded = b64encode(f.read()).decode('utf-8')
    return f"data:{mime or 'image/png'};base64,{encoded}"


def _data_uri(path: str | None) -> str | None:
    if not path:
        return None
    mtime = _file_mtime(path)
    if mtime is None:
        return None
    try:
        return _data_uri_cached(path, mtime)
    except Exception:
        return None


@lru_cache(maxsize=4)
def _dejavu_font_bundle_cached(font_path: str, mtime: float) -> tuple[str | None, str | None]:
    try:
        registered = set(pdfmetrics.getRegisteredFontNames())
        if 'DejaVuSans' not in registered:
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
        return font_path, font_data_b64
    except Exception:
        logger.exception("Failed to register PDF font at %s", font_path)
        return None, None


def _resolve_dejavu_font_bundle() -> tuple[str | None, str | None]:
    font_candidates = [
        finders.find('fonts/DejaVuSans.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/opt/studioflow/static/fonts/DejaVuSans.ttf',
    ]
    font_path = next((p for p in font_candidates if p and os.path.exists(p)), None)
    if not font_path:
        return None, None
    mtime = _file_mtime(font_path)
    if mtime is None:
        return None, None
    return _dejavu_font_bundle_cached(font_path, mtime)


from .decorators import role_required, module_required
from .filters import (
    BillFilter,
    ClientAdvanceFilter,
    ExpenseClaimFilter,
    InvoiceFilter,
    ProjectFilter,
    SiteIssueFilter,
    SiteVisitFilter,
    StaffActivityFilter,
    TaskFilter,
    TransactionFilter,
    RecurringRuleFilter,
)
from .forms import (
    AccountForm,
    BankStatementImportForm,
    BillForm,
    BillPaymentForm,
    ClientForm,
    ClientAdvanceAllocationForm,
    ClientAdvanceForm,
    DocumentForm,
    ExpenseClaimForm,
    ExpenseClaimPaymentForm,
    FirmProfileForm,
    InvoiceForm,
    InvoiceLineFormSet,
    LeadForm,
    ReceiptForm,
    PaymentForm,
    ProjectForm,
    ProjectFinancePlanForm,
    ProjectMilestoneForm,
    RecurringTransactionRuleForm,
    SiteIssueForm,
    SiteIssueAttachmentForm,
    SiteVisitAttachmentForm,
    SiteVisitForm,
    StageUpdateForm,
    TaskForm,
    TaskCommentForm,
    TransactionForm,
    PersonalExpenseForm,
    SalaryPaymentForm,
    ReminderSettingForm,
    UserForm,
    VendorForm,
    RolePermissionForm,
)
from .models import (
    Account,
    BankStatementImport,
    BankStatementLine,
    Bill,
    BillPayment,
    Client,
    ClientAdvance,
    ClientAdvanceAllocation,
    Document,
    ExpenseClaim,
    ExpenseClaimAttachment,
    ExpenseClaimPayment,
    FirmProfile,
    Invoice,
    Lead,
    Notification,
    Payment,
    Receipt,
    Project,
    ProjectFinancePlan,
    ProjectStageHistory,
    ReminderSetting,
    StaffActivity,
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
    Vendor,
    ProjectMilestone,
    RecurringTransactionRule,
)
from .permissions import MODULE_LABELS, ensure_role_permissions, get_permissions_for_user
from .notifications.tasks import notify_task_change
from .notifications.whatsapp import send_text as send_whatsapp_text
from .activity import log_staff_activity
from .finance_utils import add_month, generate_recurring_transactions
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
    if not user or not user.is_authenticated:
        return qs.none()
    task_project_ids = Task.objects.filter(assigned_to=user).values('project_id')
    return qs.filter(
        Q(project_manager=user) | Q(site_engineer=user) | Q(pk__in=task_project_ids)
    )


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
    show_stage_summary = request.user.is_superuser or perms.get('leads')
    can_create_projects = request.user.is_superuser or request.user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)

    projects = Project.objects.select_related('client')
    if not show_finance:
        projects = projects.filter(
            Q(project_manager=request.user)
            | Q(site_engineer=request.user)
            | Q(tasks__assigned_to=request.user)
        ).distinct()

    total_active = projects.exclude(current_stage=Project.Stage.CLOSED).count()
    stage_counts = []
    if show_stage_summary:
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
    task_limit = 5 if show_stage_summary else 10
    upcoming_tasks = tasks_scope.order_by(F('due_date').asc(nulls_last=True), '-created_at')[:task_limit]
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
        'show_stage_summary': show_stage_summary,
        'can_create_projects': can_create_projects,
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
            invoice_filters = (
                Q(invoice_number__icontains=q)
                | Q(project__code__icontains=q)
                | Q(project__name__icontains=q)
                | Q(lead__title__icontains=q)
                | Q(lead__client__name__icontains=q)
            )
            if '/' in q:
                tail = q.split('/')[-1].strip()
                if tail.isdigit():
                    invoice_filters |= Q(invoice_number__icontains=tail)
            invoices = Invoice.objects.select_related(
                'project__client', 'lead__client'
            ).filter(
                invoice_filters
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
    invoices = Invoice.objects.select_related('project__client', 'lead__client').prefetch_related('payments', 'lines', 'advance_allocations')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Project', 'Lead', 'Client', 'Invoice Date', 'Due Date', 'Status', 'Subtotal', 'Tax %', 'Discount %', 'Total With Tax', 'Paid (cash)', 'Advance Applied', 'Settled', 'Outstanding'])
    for invoice in invoices.order_by('-invoice_date'):
        client = invoice.project.client if invoice.project else (invoice.lead.client if invoice.lead else None)
        writer.writerow([
            invoice.display_invoice_number,
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
            invoice.advance_applied,
            invoice.amount_settled,
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
    view = request.GET.get('view') or 'table'
    if view not in {'table', 'pipeline'}:
        view = 'table'
    if status:
        leads = leads.filter(status=status)

    if view == 'pipeline':
        columns = {value: [] for value, _ in Lead.Status.choices}
        for lead in leads:
            columns.setdefault(lead.status, []).append(lead)
        return render(request, 'portal/leads.html', {
            'leads': leads,
            'columns': columns,
            'statuses': Lead.Status.choices,
            'selected_status': status,
            'view': view,
        })

    # Pagination
    paginator = Paginator(leads, ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'portal/leads.html', {
        'leads': page_obj,
        'page_obj': page_obj,
        'statuses': Lead.Status.choices,
        'selected_status': status,
        'view': view,
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
    ).order_by('code')
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.PROJECTS,
                message=f"Created project {project.code}.",
                related_url=reverse('project_detail', args=[project.pk]),
            )
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.PROJECTS,
                message=f"Updated project {project.code}.",
                related_url=reverse('project_detail', args=[project.pk]),
            )
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.PROJECTS,
                message=f"Updated stage for {project.code} → {history.stage}.",
                related_url=reverse('project_detail', args=[project.pk]),
            )
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.TASKS,
                message=f"Created task “{task.title}” ({task.project.code}).",
                related_url=reverse('task_detail', args=[task.pk]),
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.TASKS,
                message=f"Updated task “{updated_task.title}” ({updated_task.project.code}).",
                related_url=reverse('task_detail', args=[updated_task.pk]),
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
        log_staff_activity(
            actor=request.user,
            category=StaffActivity.Category.TASKS,
            message=f"Moved task “{task.title}” → {task.get_status_display()} ({task.project.code}).",
            related_url=reverse('task_detail', args=[task.pk]),
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.SITE_VISITS,
                message=f"Logged site visit for {visit.project.code} ({visit.visit_date:%d %b %Y}).",
                related_url=reverse('site_visit_detail', args=[visit.pk]),
            )
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.SITE_VISITS,
                message=f"Updated site visit for {updated_visit.project.code} ({updated_visit.visit_date:%d %b %Y}).",
                related_url=reverse('site_visit_detail', args=[updated_visit.pk]),
            )
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.SITE_VISITS,
                message=f"Logged issue “{issue.title}” for {issue.project.code}.",
                related_url=reverse('issue_detail', args=[issue.pk]),
            )
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
        'lines', 'payments', 'advance_allocations'
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
        ).prefetch_related('lines', 'payments', 'advance_allocations'),
        pk=invoice_pk,
    )
    invoice.refresh_status(save=False)
    lines = list(invoice.lines.all())
    tax_value = max(invoice.total_with_tax - invoice.taxable_amount, Decimal('0'))
    client = invoice.project.client if invoice.project else (invoice.lead.client if invoice.lead else None)
    firm = FirmProfile.objects.first()
    logo_path = None
    logo_data = None

    if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
        logo_path = firm.logo.path
        logo_data = _data_uri(logo_path)

    if not logo_data:
        fallback_logo = finders.find('img/novart.png')
        logo_data = _data_uri(fallback_logo)

    font_path, font_data_b64 = _resolve_dejavu_font_bundle()
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
    display_number = invoice.display_invoice_number or invoice.invoice_number or str(invoice.pk)
    safe_number = re.sub(r'[^A-Za-z0-9._-]+', '-', display_number).strip('-') or str(invoice.pk)
    response['Content-Disposition'] = f'inline; filename=\"invoice-{safe_number}.pdf\"'
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
                log_staff_activity(
                    actor=request.user,
                    category=StaffActivity.Category.FINANCE,
                    message=f"Created invoice {invoice.display_invoice_number}.",
                    related_url=reverse('invoice_edit', args=[invoice.pk]),
                )
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
    invoice = get_object_or_404(Invoice.objects.prefetch_related('lines', 'payments', 'advance_allocations'), pk=invoice_pk)
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
                log_staff_activity(
                    actor=request.user,
                    category=StaffActivity.Category.FINANCE,
                    message=f"Updated invoice {invoice.display_invoice_number}.",
                    related_url=reverse('invoice_edit', args=[invoice.pk]),
                )
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
        .prefetch_related('lines', 'payments', 'advance_allocations')
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
            with db_transaction.atomic():
                payment = form.save(commit=False)
                payment.invoice = invoice
                payment.recorded_by = request.user
                payment.save()
                _refresh_invoice_status(invoice)

                receipt = Receipt(payment=payment, generated_by=request.user)
                receipt.save()

                log_staff_activity(
                    actor=request.user,
                    category=StaffActivity.Category.FINANCE,
                    message=(
                        f"Recorded payment {payment.amount} for invoice {invoice.display_invoice_number} "
                        f"and created receipt {receipt.receipt_number}."
                    ),
                    related_url=reverse('receipt_pdf', args=[receipt.pk]),
                )

                client = receipt.client
                receipt_url = request.build_absolute_uri(reverse('receipt_pdf', args=[receipt.pk]))
                message_body = (
                    f"Payment received for invoice {receipt.invoice.display_invoice_number}. "
                    f"Receipt {receipt.receipt_number}: {receipt_url}"
                )

                def _notify_client():
                    if not client:
                        return
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

                db_transaction.on_commit(_notify_client)

            messages.success(request, f"Payment recorded. Receipt {receipt.receipt_number} created.")
            return redirect('receipt_pdf', receipt_pk=receipt.pk)
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
        receipt_filters = (
            Q(receipt_number__icontains=q)
            | Q(invoice__invoice_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(project__code__icontains=q)
        )
        if '/' in q:
            tail = q.split('/')[-1].strip()
            if tail.isdigit():
                receipt_filters |= Q(invoice__invoice_number__icontains=tail)
        receipts = receipts.filter(
            receipt_filters
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
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Generated receipt {receipt.receipt_number} for invoice {receipt.invoice.display_invoice_number}.",
                related_url=reverse('receipt_pdf', args=[receipt.pk]),
            )
            client = receipt.client
            receipt_url = request.build_absolute_uri(reverse('receipt_pdf', args=[receipt.pk]))
            message_body = (
                f"Payment received for invoice {receipt.invoice.display_invoice_number}. "
                f"Receipt {receipt.receipt_number}: {receipt_url}"
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

    logo_data = None
    if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
        logo_data = _data_uri(firm.logo.path)
    if not logo_data:
        fallback_logo = finders.find('img/novart.png')
        logo_data = _data_uri(fallback_logo)

    font_path, font_data_b64 = _resolve_dejavu_font_bundle()

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
    txn_filter = TransactionFilter(
        request.GET,
        queryset=Transaction.objects.select_related(
            'account',
            'related_project',
            'related_client',
            'related_vendor',
            'related_person',
            'recorded_by',
        ),
    )
    filtered_totals = txn_filter.qs.aggregate(
        debit=Sum('debit'),
        credit=Sum('credit'),
    )
    debit_total = filtered_totals.get('debit') or Decimal('0')
    credit_total = filtered_totals.get('credit') or Decimal('0')
    net_total = credit_total - debit_total
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.recorded_by = request.user
            txn.save()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Added cashbook entry: {txn.description} (Dr {txn.debit} / Cr {txn.credit}).",
                related_url=reverse('transaction_list'),
            )
            messages.success(request, 'Transaction saved.')
            return redirect('transaction_list')
    else:
        form = TransactionForm()
    return render(
        request,
        'portal/transactions.html',
        {
            'filter': txn_filter,
            'form': form,
            'currency': '₹',
            'totals': {'debit': debit_total, 'credit': credit_total, 'net': net_total},
            'show_export': True,
        },
    )


@login_required
@role_required(User.Roles.MANAGING_DIRECTOR, User.Roles.ADMIN)
def transaction_my(request):
    project_qs = Project.objects.all()
    txn_filter = TransactionFilter(
        request.GET,
        queryset=Transaction.objects.filter(recorded_by=request.user).select_related(
            'account',
            'related_project',
            'related_client',
            'related_vendor',
            'related_person',
            'recorded_by',
        ),
    )
    if 'related_project' in txn_filter.form.fields:
        txn_filter.form.fields['related_project'].queryset = project_qs
    filtered_totals = txn_filter.qs.aggregate(
        debit=Sum('debit'),
        credit=Sum('credit'),
    )
    debit_total = filtered_totals.get('debit') or Decimal('0')
    credit_total = filtered_totals.get('credit') or Decimal('0')
    net_total = credit_total - debit_total
    if request.method == 'POST':
        form = PersonalExpenseForm(request.POST)
        if 'related_project' in form.fields:
            form.fields['related_project'].queryset = project_qs
        if form.is_valid():
            txn = form.save(commit=False)
            txn.recorded_by = request.user
            txn.related_person = request.user
            txn.save()
            txn_type = form.cleaned_data.get('txn_type', 'expense')
            if txn_type == 'income':
                log_msg = f"Added income: {txn.description} (Cr {txn.credit})."
                success_msg = 'Income saved.'
            else:
                log_msg = f"Added expense: {txn.description} (Dr {txn.debit})."
                success_msg = 'Expense saved.'
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=log_msg,
                related_url=reverse('transaction_my'),
            )
            messages.success(request, success_msg)
            return redirect('transaction_my')
    else:
        form = PersonalExpenseForm(initial={'date': timezone.localdate()})
        if 'related_project' in form.fields:
            form.fields['related_project'].queryset = project_qs
    return render(
        request,
        'portal/transactions.html',
        {
            'filter': txn_filter,
            'form': form,
            'currency': '₹',
            'totals': {'debit': debit_total, 'credit': credit_total, 'net': net_total},
            'page_title': 'My Cashbook',
            'show_export': False,
            'simple_view': True,
            'new_entry_label': 'New entry',
            'empty_state_title': 'No transactions yet',
            'empty_state_description': 'Add your first transaction to track your expenses and income.',
            'empty_state_colspan': 4,
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def payroll(request):
    today = timezone.localdate()
    month_str = (request.GET.get('month') or '').strip()
    if not month_str:
        month_start = today.replace(day=1)
        month_str = month_start.strftime('%Y-%m')
    else:
        try:
            month_start = dt.datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
        except ValueError:
            messages.error(request, 'Invalid month format. Use YYYY-MM.')
            return redirect('payroll')

    if month_start.month == 12:
        month_end = dt.date(month_start.year + 1, 1, 1)
    else:
        month_end = dt.date(month_start.year, month_start.month + 1, 1)

    staff_qs = User.objects.filter(is_active=True, monthly_salary__gt=0).order_by('first_name', 'last_name', 'username')
    paid_rows = (
        Transaction.objects.filter(
            category=Transaction.Category.SALARY,
            related_person__in=staff_qs,
            date__gte=month_start,
            date__lt=month_end,
        )
        .values('related_person_id')
        .annotate(total=Sum('debit'))
    )
    paid_by_person = {row['related_person_id']: row['total'] or Decimal('0') for row in paid_rows}

    staff_rows = []
    total_salary = Decimal('0')
    total_paid = Decimal('0')
    total_due = Decimal('0')
    for staff in staff_qs:
        salary = staff.monthly_salary or Decimal('0')
        paid = paid_by_person.get(staff.id, Decimal('0'))
        due = max(salary - paid, Decimal('0'))
        staff_rows.append({'staff': staff, 'salary': salary, 'paid': paid, 'due': due})
        total_salary += salary
        total_paid += paid
        total_due += due

    salary_txns = Transaction.objects.filter(
        category=Transaction.Category.SALARY,
        date__gte=month_start,
        date__lt=month_end,
    ).select_related('account', 'related_person', 'recorded_by')

    if request.method == 'POST':
        form = SalaryPaymentForm(request.POST)
        form.fields['related_person'].queryset = staff_qs
        if form.is_valid():
            txn = form.save(commit=False)
            txn.recorded_by = request.user
            txn.save()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Recorded salary payment: {txn.related_person} (₹{txn.debit}).",
                related_url=reverse('payroll'),
            )
            messages.success(request, 'Salary payment recorded.')
            return redirect(f"{reverse('payroll')}?month={month_str}")
    else:
        form = SalaryPaymentForm(initial={'date': today})
        form.fields['related_person'].queryset = staff_qs

    return render(
        request,
        'portal/payroll.html',
        {
            'month_str': month_str,
            'month_start': month_start,
            'staff_rows': staff_rows,
            'salary_txns': salary_txns,
            'totals': {'salary': total_salary, 'paid': total_paid, 'due': total_due},
            'form': form,
            'currency': '₹',
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def account_list(request):
    zero = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
    accounts = (
        Account.objects.order_by('name')
        .annotate(
            debit_total=Coalesce(Sum('transactions__debit'), zero),
            credit_total=Coalesce(Sum('transactions__credit'), zero),
        )
        .annotate(
            balance=ExpressionWrapper(
                F('opening_balance') + F('credit_total') - F('debit_total'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
    )
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Created account: {account.name}.",
                related_url=reverse('account_list'),
            )
            messages.success(request, 'Account saved.')
            return redirect('account_list')
    else:
        form = AccountForm()
    return render(request, 'portal/accounts.html', {'accounts': accounts, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def transfer_create(request):
    class TransferForm(forms.Form):
        date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
        from_account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True).order_by('name'))
        to_account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True).order_by('name'))
        amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
        notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

        def clean(self):
            cleaned = super().clean()
            from_account = cleaned.get('from_account')
            to_account = cleaned.get('to_account')
            if from_account and to_account and from_account.pk == to_account.pk:
                self.add_error('to_account', 'Choose a different destination account.')
            return cleaned

    if request.method == 'POST':
        form = TransferForm(request.POST)
        if form.is_valid():
            transfer_date = form.cleaned_data['date']
            from_account = form.cleaned_data['from_account']
            to_account = form.cleaned_data['to_account']
            amount = form.cleaned_data['amount']
            notes = (form.cleaned_data.get('notes') or '').strip()
            transfer_ref = f"TXFER-{timezone.localtime():%Y%m%d%H%M%S}-{request.user.pk}"
            remarks = f"{notes} | Ref: {transfer_ref}".strip(" |")

            Transaction.objects.create(
                date=transfer_date,
                description=f"Transfer to {to_account.name}"[:255],
                category=Transaction.Category.TRANSFER,
                subcategory=transfer_ref,
                debit=amount,
                credit=0,
                account=from_account,
                recorded_by=request.user,
                remarks=remarks,
            )
            Transaction.objects.create(
                date=transfer_date,
                description=f"Transfer from {from_account.name}"[:255],
                category=Transaction.Category.TRANSFER,
                subcategory=transfer_ref,
                debit=0,
                credit=amount,
                account=to_account,
                recorded_by=request.user,
                remarks=remarks,
            )
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Created transfer {amount} from {from_account} → {to_account}.",
                related_url=reverse('account_list'),
            )
            messages.success(request, 'Transfer recorded.')
            return redirect('account_list')
    else:
        form = TransferForm(initial={'date': timezone.localdate()})
    return render(request, 'portal/transfer_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def vendor_list(request):
    vendors = Vendor.objects.order_by('name')
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Added vendor: {vendor.name}.",
                related_url=reverse('vendor_list'),
            )
            messages.success(request, 'Vendor saved.')
            return redirect('vendor_list')
    else:
        form = VendorForm()
    return render(request, 'portal/vendors.html', {'vendors': vendors, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def bill_list(request):
    bills_qs = Bill.objects.select_related('vendor', 'project', 'project__client').prefetch_related('payments')
    bill_filter = BillFilter(request.GET, queryset=bills_qs)
    if request.method == 'POST':
        form = BillForm(request.POST, request.FILES)
        visible_projects = _visible_projects_for_user(request.user)
        form.fields['project'].queryset = visible_projects
        if form.is_valid():
            bill = form.save(commit=False)
            bill.created_by = request.user
            bill.save()
            bill.refresh_status()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Added bill for {bill.vendor}: ₹{bill.amount}.",
                related_url=reverse('bill_list'),
            )
            messages.success(request, 'Bill saved.')
            return redirect('bill_list')
    else:
        form = BillForm(initial={'bill_date': timezone.localdate()})
        form.fields['project'].queryset = _visible_projects_for_user(request.user)
    return render(request, 'portal/bills.html', {'filter': bill_filter, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def bill_payment_create(request, bill_pk):
    bill = get_object_or_404(Bill.objects.select_related('vendor', 'project'), pk=bill_pk)
    if bill.outstanding <= 0:
        messages.info(request, 'This bill is already settled.')
        return redirect('bill_list')
    if request.method == 'POST':
        form = BillPaymentForm(request.POST, bill=bill)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.bill = bill
            payment.recorded_by = request.user
            payment.save()
            messages.success(request, 'Bill payment recorded.')
            return redirect('bill_list')
    else:
        form = BillPaymentForm(
            bill=bill,
            initial={'payment_date': timezone.localdate(), 'amount': bill.outstanding},
        )
    return render(request, 'portal/bill_payment_form.html', {'bill': bill, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def bill_aging(request):
    today = timezone.localdate()
    bills = Bill.objects.exclude(status=Bill.Status.PAID).select_related('vendor', 'project').prefetch_related('payments')
    buckets = {'0-30': [], '31-60': [], '61-90': [], '90+': []}
    totals = {key: Decimal('0') for key in buckets}
    for bill in bills:
        bill.refresh_status(save=False, today=today)
        outstanding = bill.outstanding
        if outstanding <= 0:
            continue
        due = bill.due_date or bill.bill_date
        days_overdue = max((today - due).days, 0) if due else 0
        if days_overdue <= 30:
            bucket_key = '0-30'
        elif days_overdue <= 60:
            bucket_key = '31-60'
        elif days_overdue <= 90:
            bucket_key = '61-90'
        else:
            bucket_key = '90+'
        buckets[bucket_key].append({'bill': bill, 'days_overdue': days_overdue, 'outstanding': outstanding})
        totals[bucket_key] += outstanding
    grand_total = sum(totals.values(), Decimal('0'))
    return render(
        request,
        'portal/bill_aging.html',
        {'buckets': buckets, 'totals': totals, 'grand_total': grand_total, 'today': today},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def advance_list(request):
    advances_qs = ClientAdvance.objects.select_related('project', 'client', 'account', 'recorded_by', 'received_by').prefetch_related('allocations')
    advance_filter = ClientAdvanceFilter(request.GET, queryset=advances_qs)
    if request.method == 'POST':
        form = ClientAdvanceForm(request.POST, project_queryset=_visible_projects_for_user(request.user))
        if form.is_valid():
            advance = form.save(commit=False)
            advance.recorded_by = request.user
            advance.save()
            messages.success(request, 'Advance saved.')
            return redirect('advance_list')
    else:
        form = ClientAdvanceForm(initial={'received_date': timezone.localdate()}, project_queryset=_visible_projects_for_user(request.user))
    return render(request, 'portal/advances.html', {'filter': advance_filter, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def apply_advance_to_invoice(request, invoice_pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('project__client', 'lead__client').prefetch_related('payments', 'lines', 'advance_allocations'),
        pk=invoice_pk,
    )
    if invoice.outstanding <= 0:
        messages.info(request, 'This invoice is already settled.')
        return redirect('invoice_list')

    if invoice.project_id:
        eligible_advances = ClientAdvance.objects.filter(
            Q(project=invoice.project) | Q(client=invoice.project.client)
        )
    elif invoice.lead_id and invoice.lead and invoice.lead.client_id:
        eligible_advances = ClientAdvance.objects.filter(client=invoice.lead.client)
    else:
        eligible_advances = ClientAdvance.objects.none()

    eligible_advances = eligible_advances.order_by('-received_date', '-created_at')

    if request.method == 'POST':
        form = ClientAdvanceAllocationForm(request.POST, invoice=invoice)
        form.fields['advance'].queryset = eligible_advances
        if form.is_valid():
            allocation = form.save(commit=False)
            allocation.allocated_by = request.user
            allocation.save()
            messages.success(request, 'Advance applied to invoice.')
            return redirect('invoice_list')
    else:
        form = ClientAdvanceAllocationForm(invoice=invoice)
        form.fields['advance'].queryset = eligible_advances
    return render(
        request,
        'portal/apply_advance.html',
        {
            'invoice': invoice,
            'form': form,
            'eligible_advances': eligible_advances,
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def recurring_rule_list(request):
    rule_filter = RecurringRuleFilter(
        request.GET,
        queryset=RecurringTransactionRule.objects.select_related('account', 'related_project', 'related_vendor'),
    )
    if request.method == 'POST':
        form = RecurringTransactionRuleForm(request.POST)
        if form.is_valid():
            rule = form.save()
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=f"Saved recurring rule: {rule.name}.",
                related_url=reverse('recurring_rule_list'),
            )
            messages.success(request, 'Recurring rule saved.')
            return redirect('recurring_rule_list')
    else:
        form = RecurringTransactionRuleForm(initial={'next_run_date': timezone.localdate()})
    return render(request, 'portal/recurring_rules.html', {'filter': rule_filter, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def recurring_rule_run(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Run requires POST.')
    created = generate_recurring_transactions(today=timezone.localdate(), actor=request.user)
    messages.success(request, f'Generated {created} recurring transaction(s).')
    return redirect('recurring_rule_list')


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def bank_statement_list(request):
    statements = BankStatementImport.objects.select_related('account', 'uploaded_by').order_by('-created_at')
    if request.method == 'POST':
        form = BankStatementImportForm(request.POST, request.FILES)
        if form.is_valid():
            statement = form.save(commit=False)
            statement.uploaded_by = request.user
            statement.save()

            try:
                statement.file.open('rb')
                wrapper = TextIOWrapper(statement.file, encoding='utf-8-sig')
                reader = csv.DictReader(wrapper)
                created = 0
                for raw_row in reader:
                    row = {str(k or '').strip().lower(): (v or '').strip() for k, v in (raw_row or {}).items()}
                    date_str = row.get('date') or row.get('transaction date') or row.get('value date')
                    desc = row.get('description') or row.get('narration') or row.get('details') or row.get('particulars') or ''
                    amount_str = row.get('amount')
                    debit_str = row.get('debit') or row.get('withdrawal') or ''
                    credit_str = row.get('credit') or row.get('deposit') or ''
                    balance_str = row.get('balance') or row.get('running balance') or ''
                    if not date_str:
                        continue
                    try:
                        line_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            line_date = dt.datetime.strptime(date_str, '%d/%m/%Y').date()
                        except ValueError:
                            continue
                    amount = Decimal('0')
                    if amount_str:
                        try:
                            amount = Decimal(amount_str.replace(',', ''))
                        except Exception:
                            amount = Decimal('0')
                    elif credit_str or debit_str:
                        try:
                            credit_val = Decimal(credit_str.replace(',', '') or '0')
                        except Exception:
                            credit_val = Decimal('0')
                        try:
                            debit_val = Decimal(debit_str.replace(',', '') or '0')
                        except Exception:
                            debit_val = Decimal('0')
                        amount = credit_val if credit_val else -debit_val
                    balance = None
                    if balance_str:
                        try:
                            balance = Decimal(balance_str.replace(',', ''))
                        except Exception:
                            balance = None

                    if not desc:
                        desc = f"Statement line {line_date:%Y-%m-%d}"

                    line = BankStatementLine.objects.create(
                        statement=statement,
                        line_date=line_date,
                        description=desc[:255],
                        amount=amount,
                        balance=balance,
                    )
                    created += 1

                    candidates = Transaction.objects.filter(account=statement.account, date__gte=line_date - dt.timedelta(days=1), date__lte=line_date + dt.timedelta(days=1))
                    if amount > 0:
                        candidates = candidates.filter(credit=amount)
                    elif amount < 0:
                        candidates = candidates.filter(debit=abs(amount))
                    match = candidates.exclude(matched_statement_lines__isnull=False).order_by('date').first()
                    if match:
                        line.matched_transaction = match
                        line.save(update_fields=['matched_transaction'])

                messages.success(request, f'Statement uploaded. Imported {created} line(s).')
                return redirect('bank_statement_detail', statement_pk=statement.pk)
            finally:
                try:
                    statement.file.close()
                except Exception:
                    pass
    else:
        form = BankStatementImportForm()
    return render(request, 'portal/bank_statements.html', {'statements': statements, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def bank_statement_detail(request, statement_pk):
    statement = get_object_or_404(BankStatementImport.objects.select_related('account'), pk=statement_pk)
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        line_id = request.POST.get('line_id')
        line = statement.lines.filter(pk=line_id).first() if line_id else None
        if not line:
            return HttpResponseForbidden('Invalid line.')
        if action == 'create_txn' and not line.matched_transaction_id:
            amount = line.amount or Decimal('0')
            txn = Transaction.objects.create(
                date=line.line_date,
                description=line.description[:255],
                category=Transaction.Category.OTHER_INCOME if amount > 0 else Transaction.Category.OTHER_EXPENSE,
                debit=abs(amount) if amount < 0 else 0,
                credit=amount if amount > 0 else 0,
                account=statement.account,
                recorded_by=request.user,
                remarks='Created from bank statement.',
            )
            line.matched_transaction = txn
            line.save(update_fields=['matched_transaction'])
            messages.success(request, 'Transaction created and matched.')
            return redirect('bank_statement_detail', statement_pk=statement.pk)
    lines = statement.lines.select_related('matched_transaction').order_by('-line_date', '-created_at')
    return render(request, 'portal/bank_statement_detail.html', {'statement': statement, 'lines': lines})


@login_required
def expense_claim_my(request):
    claims = ExpenseClaim.objects.filter(employee=request.user).select_related('project').order_by('-expense_date', '-created_at')
    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.employee = request.user
            claim.status = ExpenseClaim.Status.SUBMITTED
            claim.save()
            for upload in form.cleaned_data.get('attachments') or []:
                ExpenseClaimAttachment.objects.create(claim=claim, file=upload)
            messages.success(request, 'Expense claim submitted.')
            return redirect('expense_claim_my')
    else:
        form = ExpenseClaimForm(initial={'expense_date': timezone.localdate()})
    return render(request, 'portal/expense_claims_my.html', {'claims': claims, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def expense_claim_admin(request):
    claim_filter = ExpenseClaimFilter(
        request.GET,
        queryset=ExpenseClaim.objects.select_related('employee', 'project', 'approved_by').prefetch_related('attachments', 'payment'),
    )
    return render(request, 'portal/expense_claims_admin.html', {'filter': claim_filter})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def expense_claim_approve(request, claim_pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Approve requires POST.')
    claim = get_object_or_404(ExpenseClaim, pk=claim_pk)
    if claim.status not in (ExpenseClaim.Status.SUBMITTED,):
        messages.info(request, 'Only submitted claims can be approved.')
        return redirect('expense_claim_admin')
    claim.status = ExpenseClaim.Status.APPROVED
    claim.approved_by = request.user
    claim.approved_at = timezone.now()
    claim.save(update_fields=['status', 'approved_by', 'approved_at'])
    messages.success(request, 'Claim approved.')
    return redirect('expense_claim_admin')


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def expense_claim_reject(request, claim_pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Reject requires POST.')
    claim = get_object_or_404(ExpenseClaim, pk=claim_pk)
    if claim.status in (ExpenseClaim.Status.PAID,):
        messages.error(request, 'Cannot reject a paid claim.')
        return redirect('expense_claim_admin')
    claim.status = ExpenseClaim.Status.REJECTED
    claim.save(update_fields=['status'])
    messages.success(request, 'Claim rejected.')
    return redirect('expense_claim_admin')


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def expense_claim_pay(request, claim_pk):
    claim = get_object_or_404(ExpenseClaim.objects.select_related('employee', 'project'), pk=claim_pk)
    if claim.status != ExpenseClaim.Status.APPROVED:
        messages.error(request, 'Only approved claims can be paid.')
        return redirect('expense_claim_admin')
    if getattr(claim, 'payment', None):
        messages.info(request, 'This claim is already paid.')
        return redirect('expense_claim_admin')
    if request.method == 'POST':
        form = ExpenseClaimPaymentForm(request.POST, claim=claim)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.claim = claim
            payment.recorded_by = request.user
            payment.save()
            messages.success(request, 'Claim payment recorded.')
            return redirect('expense_claim_admin')
    else:
        form = ExpenseClaimPaymentForm(
            claim=claim,
            initial={'payment_date': timezone.localdate(), 'amount': claim.amount},
        )
    return render(request, 'portal/expense_claim_payment_form.html', {'claim': claim, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def project_finance(request, pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    plan, _ = ProjectFinancePlan.objects.get_or_create(project=project)
    milestones = ProjectMilestone.objects.filter(project=project).select_related('invoice').order_by('due_date', 'created_at')

    plan_form = ProjectFinancePlanForm(instance=plan)
    milestone_form = ProjectMilestoneForm()

    if request.method == 'POST':
        form_type = (request.POST.get('form_type') or '').strip()
        if form_type == 'plan':
            plan_form = ProjectFinancePlanForm(request.POST, instance=plan)
            if plan_form.is_valid():
                plan_form.save()
                messages.success(request, 'Finance plan updated.')
                return redirect('project_finance', pk=project.pk)
        elif form_type == 'milestone':
            milestone_form = ProjectMilestoneForm(request.POST)
            if milestone_form.is_valid():
                milestone = milestone_form.save(commit=False)
                milestone.project = project
                milestone.save()
                messages.success(request, 'Milestone added.')
                return redirect('project_finance', pk=project.pk)
    return render(
        request,
        'portal/project_finance.html',
        {'project': project, 'plan_form': plan_form, 'milestones': milestones, 'milestone_form': milestone_form},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def project_milestone_invoice(request, pk, milestone_pk):
    project = get_object_or_404(_visible_projects_for_user(request.user), pk=pk)
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_pk, project=project)
    if milestone.invoice_id:
        messages.info(request, 'Invoice already exists for this milestone.')
        return redirect('invoice_edit', invoice_pk=milestone.invoice_id)
    today = timezone.localdate()
    due_date = milestone.due_date or (today + timedelta(days=7))
    invoice = Invoice.objects.create(
        project=project,
        invoice_date=today,
        due_date=due_date,
        amount=milestone.amount or Decimal('0'),
        tax_percent=Decimal('0'),
        discount_percent=Decimal('0'),
        status=Invoice.Status.DRAFT,
        description=f"Milestone: {milestone.title}",
    )
    milestone.invoice = invoice
    milestone.status = ProjectMilestone.Status.INVOICED
    milestone.save(update_fields=['invoice', 'status'])
    messages.success(request, f"Invoice created for milestone: {milestone.title}.")
    return redirect('invoice_edit', invoice_pk=invoice.pk)


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
@module_required('finance')
def export_transactions_csv(request):
    txn_filter = TransactionFilter(
        request.GET,
        queryset=Transaction.objects.select_related(
            'account',
            'related_project',
            'related_client',
            'related_vendor',
            'related_person',
            'recorded_by',
        ),
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="cashbook.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'Date',
            'Description',
            'Category',
            'Subcategory',
            'Account',
            'Debit',
            'Credit',
            'Project',
            'Client',
            'Vendor',
            'Person',
            'Recorded By',
            'Remarks',
        ]
    )
    for txn in txn_filter.qs.order_by('-date', '-created_at'):
        writer.writerow(
            [
                txn.date,
                txn.description,
                txn.get_category_display() if txn.category else '',
                txn.subcategory,
                txn.account.name if txn.account_id else '',
                txn.debit,
                txn.credit,
                txn.related_project.code if txn.related_project_id else '',
                txn.related_client.name if txn.related_client_id else '',
                txn.related_vendor.name if txn.related_vendor_id else '',
                str(txn.related_person) if txn.related_person_id else '',
                str(txn.recorded_by) if txn.recorded_by_id else '',
                txn.remarks,
            ]
        )
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def export_payroll_csv(request):
    today = timezone.localdate()
    month_str = (request.GET.get('month') or '').strip()
    if not month_str:
        month_start = today.replace(day=1)
        month_str = month_start.strftime('%Y-%m')
    else:
        try:
            month_start = dt.datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
        except ValueError:
            messages.error(request, 'Invalid month format. Use YYYY-MM.')
            return redirect('payroll')

    if month_start.month == 12:
        month_end = dt.date(month_start.year + 1, 1, 1)
    else:
        month_end = dt.date(month_start.year, month_start.month + 1, 1)

    salary_txns = Transaction.objects.filter(
        category=Transaction.Category.SALARY,
        date__gte=month_start,
        date__lt=month_end,
    ).select_related('account', 'related_person', 'recorded_by')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payroll-{month_str}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Employee', 'Account', 'Amount', 'Recorded By', 'Remarks'])
    for txn in salary_txns.order_by('date', 'created_at'):
        writer.writerow(
            [
                txn.date,
                str(txn.related_person) if txn.related_person_id else '',
                txn.account.name if txn.account_id else '',
                txn.debit,
                str(txn.recorded_by) if txn.recorded_by_id else '',
                txn.remarks,
            ]
        )
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def export_bills_csv(request):
    bill_filter = BillFilter(
        request.GET,
        queryset=Bill.objects.select_related('vendor', 'project', 'project__client').prefetch_related('payments'),
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bills.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'Vendor',
            'Project',
            'Client',
            'Bill #',
            'Bill Date',
            'Due Date',
            'Category',
            'Status',
            'Amount',
            'Paid',
            'Outstanding',
        ]
    )
    for bill in bill_filter.qs.order_by('-bill_date', '-created_at'):
        writer.writerow(
            [
                bill.vendor.name,
                bill.project.code if bill.project_id else '',
                bill.project.client.name if bill.project_id and bill.project.client_id else '',
                bill.bill_number,
                bill.bill_date,
                bill.due_date,
                bill.get_category_display() if hasattr(bill, 'get_category_display') else bill.category,
                bill.get_status_display(),
                bill.amount,
                bill.amount_paid,
                bill.outstanding,
            ]
        )
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def export_advances_csv(request):
    advance_filter = ClientAdvanceFilter(
        request.GET,
        queryset=ClientAdvance.objects.select_related('project', 'client', 'account', 'recorded_by', 'received_by').prefetch_related('allocations'),
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="advances.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'Date',
            'Client',
            'Project',
            'Account',
            'Amount',
            'Allocated',
            'Available',
            'Method',
            'Reference',
            'Recorded By',
            'Received By',
            'Notes',
        ]
    )
    for adv in advance_filter.qs.order_by('-received_date', '-created_at'):
        writer.writerow(
            [
                adv.received_date,
                adv.client.name if adv.client_id else '',
                adv.project.code if adv.project_id else '',
                adv.account.name if adv.account_id else '',
                adv.amount,
                adv.allocated_amount,
                adv.available_amount,
                adv.method,
                adv.reference,
                str(adv.recorded_by) if adv.recorded_by_id else '',
                str(adv.received_by) if adv.received_by_id else '',
                adv.notes,
            ]
        )
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def export_claims_csv(request):
    claim_filter = ExpenseClaimFilter(
        request.GET,
        queryset=ExpenseClaim.objects.select_related('employee', 'project', 'approved_by').prefetch_related('payment'),
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expense-claims.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'Expense Date',
            'Employee',
            'Project',
            'Category',
            'Description',
            'Amount',
            'Status',
            'Approved By',
            'Approved At',
            'Paid On',
            'Paid Amount',
            'Paid Account',
        ]
    )
    for claim in claim_filter.qs.order_by('-expense_date', '-created_at'):
        payment = getattr(claim, 'payment', None)
        writer.writerow(
            [
                claim.expense_date,
                str(claim.employee),
                claim.project.code if claim.project_id else '',
                claim.category,
                claim.description,
                claim.amount,
                claim.get_status_display(),
                str(claim.approved_by) if claim.approved_by_id else '',
                timezone.localtime(claim.approved_at).strftime('%Y-%m-%d %H:%M') if claim.approved_at else '',
                payment.payment_date if payment else '',
                payment.amount if payment else '',
                payment.account.name if payment and payment.account_id else '',
            ]
        )
    return response


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def finance_reports(request):
    return render(request, 'portal/finance_reports.html')


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def report_profit_and_loss(request):
    today = timezone.localdate()
    from_str = (request.GET.get('from') or '').strip()
    to_str = (request.GET.get('to') or '').strip()
    try:
        from_date = dt.datetime.strptime(from_str, '%Y-%m-%d').date() if from_str else today.replace(day=1)
    except ValueError:
        from_date = today.replace(day=1)
    try:
        to_date = dt.datetime.strptime(to_str, '%Y-%m-%d').date() if to_str else today
    except ValueError:
        to_date = today
    if to_date < from_date:
        from_date, to_date = to_date, from_date

    txns = Transaction.objects.filter(date__gte=from_date, date__lte=to_date).exclude(category=Transaction.Category.TRANSFER)
    income_rows = (
        txns.values('category')
        .annotate(total=Sum('credit'))
        .filter(total__gt=0)
        .order_by('-total')
    )
    expense_rows = (
        txns.values('category')
        .annotate(total=Sum('debit'))
        .filter(total__gt=0)
        .order_by('-total')
    )

    def _label_for_category(value: str) -> str:
        if not value:
            return 'Uncategorized'
        for key, label in Transaction.Category.choices:
            if key == value:
                return label
        return value

    income = [{'category': _label_for_category(row['category']), 'total': row['total'] or Decimal('0')} for row in income_rows]
    expenses = [{'category': _label_for_category(row['category']), 'total': row['total'] or Decimal('0')} for row in expense_rows]

    site_expenses = (
        SiteVisit.objects.filter(visit_date__gte=from_date, visit_date__lte=to_date).aggregate(total=Sum('expenses'))['total']
        or Decimal('0')
    )
    if site_expenses:
        expenses.append({'category': 'Site visit expenses', 'total': site_expenses})

    income_total = sum((row['total'] for row in income), Decimal('0'))
    expense_total = sum((row['total'] for row in expenses), Decimal('0'))
    net = income_total - expense_total

    if request.GET.get('export') == '1':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="pnl-{from_date}-to-{to_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Type', 'Category', 'Total'])
        for row in income:
            writer.writerow(['Income', row['category'], row['total']])
        for row in expenses:
            writer.writerow(['Expense', row['category'], row['total']])
        writer.writerow(['', 'Income total', income_total])
        writer.writerow(['', 'Expense total', expense_total])
        writer.writerow(['', 'Net', net])
        return response

    return render(
        request,
        'portal/report_profit_and_loss.html',
        {
            'from_date': from_date,
            'to_date': to_date,
            'income': income,
            'expenses': expenses,
            'income_total': income_total,
            'expense_total': expense_total,
            'net': net,
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def report_cashflow_forecast(request):
    today = timezone.localdate()
    try:
        horizon_days = int((request.GET.get('days') or '30').strip())
    except ValueError:
        horizon_days = 30
    horizon_days = max(7, min(horizon_days, 180))
    end_date = today + timedelta(days=horizon_days)

    invoices = (
        Invoice.objects.exclude(status=Invoice.Status.PAID)
        .prefetch_related('payments', 'advance_allocations', 'lines')
        .select_related('project__client', 'lead__client')
    )
    overdue_in = sum((inv.outstanding for inv in invoices if inv.due_date and inv.due_date < today), Decimal('0'))
    due_in = sum((inv.outstanding for inv in invoices if inv.due_date and today <= inv.due_date <= end_date), Decimal('0'))

    bills = Bill.objects.exclude(status=Bill.Status.PAID).prefetch_related('payments').select_related('vendor', 'project')
    overdue_out = sum((bill.outstanding for bill in bills if (bill.due_date or bill.bill_date) and (bill.due_date or bill.bill_date) < today), Decimal('0'))
    due_out = sum((bill.outstanding for bill in bills if (bill.due_date or bill.bill_date) and today <= (bill.due_date or bill.bill_date) <= end_date), Decimal('0'))

    recurring_in = Decimal('0')
    recurring_out = Decimal('0')
    recurring_items = []
    for rule in RecurringTransactionRule.objects.filter(is_active=True).select_related('account'):
        run_date = rule.next_run_date
        while run_date and run_date <= end_date:
            if rule.direction == RecurringTransactionRule.Direction.CREDIT:
                recurring_in += rule.amount
            else:
                recurring_out += rule.amount
            recurring_items.append({'date': run_date, 'name': rule.name, 'amount': rule.amount, 'direction': rule.direction})
            run_date = add_month(run_date.replace(day=1), 1).replace(day=min(rule.day_of_month or 1, 28))

    month_start = today.replace(day=1)
    month_end = add_month(month_start, 1)
    payroll_due = Decimal('0')
    if month_end <= end_date + timedelta(days=1):
        staff_qs = User.objects.filter(is_active=True, monthly_salary__gt=0)
        salary_total = staff_qs.aggregate(total=Sum('monthly_salary'))['total'] or Decimal('0')
        paid = (
            Transaction.objects.filter(category=Transaction.Category.SALARY, date__gte=month_start, date__lt=month_end)
            .aggregate(total=Sum('debit'))['total']
            or Decimal('0')
        )
        payroll_due = max(salary_total - paid, Decimal('0'))

    approved_claims_due = ExpenseClaim.objects.filter(status=ExpenseClaim.Status.APPROVED).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    zero = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
    account_balances = (
        Account.objects.filter(is_active=True)
        .annotate(
            debit_total=Coalesce(Sum('transactions__debit'), zero),
            credit_total=Coalesce(Sum('transactions__credit'), zero),
        )
        .annotate(
            balance=ExpressionWrapper(
                F('opening_balance') + F('credit_total') - F('debit_total'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .order_by('name')
    )
    starting_cash = sum((acc.balance for acc in account_balances), Decimal('0'))

    expected_in = overdue_in + due_in + recurring_in
    expected_out = overdue_out + due_out + recurring_out + payroll_due + approved_claims_due
    forecast_cash = starting_cash + expected_in - expected_out

    return render(
        request,
        'portal/report_cashflow_forecast.html',
        {
            'today': today,
            'end_date': end_date,
            'horizon_days': horizon_days,
            'starting_cash': starting_cash,
            'overdue_in': overdue_in,
            'due_in': due_in,
            'recurring_in': recurring_in,
            'overdue_out': overdue_out,
            'due_out': due_out,
            'recurring_out': recurring_out,
            'payroll_due': payroll_due,
            'approved_claims_due': approved_claims_due,
            'forecast_cash': forecast_cash,
            'account_balances': account_balances,
            'recurring_items': sorted(recurring_items, key=lambda x: x['date']),
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
@module_required('finance')
def report_project_profitability(request):
    projects = (
        Project.objects.select_related('client', 'finance_plan')
        .prefetch_related(
            'invoices__lines',
            'invoices__payments',
            'invoices__advance_allocations',
            'transactions',
            'site_visits',
            'bills__payments',
        )
        .order_by('code')
    )
    rows = []
    for project in projects:
        plan = getattr(project, 'finance_plan', None)
        planned_fee = plan.planned_fee if plan else Decimal('0')
        planned_cost = plan.planned_cost if plan else Decimal('0')
        invoiced = project.total_invoiced
        received = project.total_received
        expenses = project.total_expenses
        profit = received - expenses
        margin = (profit / received * 100) if received else Decimal('0')
        receivable = sum((inv.outstanding for inv in project.invoices.all()), Decimal('0'))
        payable = sum((bill.outstanding for bill in project.bills.all()), Decimal('0'))
        rows.append(
            {
                'project': project,
                'planned_fee': planned_fee,
                'planned_cost': planned_cost,
                'invoiced': invoiced,
                'received': received,
                'expenses': expenses,
                'profit': profit,
                'margin': margin,
                'receivable': receivable,
                'payable': payable,
            }
        )

    if request.GET.get('export') == '1':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="project-profitability.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                'Project Code',
                'Project Name',
                'Client',
                'Planned Fee',
                'Planned Cost',
                'Invoiced',
                'Received',
                'Expenses',
                'Profit',
                'Margin %',
                'Receivable',
                'Payable',
            ]
        )
        for row in rows:
            project = row['project']
            writer.writerow(
                [
                    project.code,
                    project.name,
                    project.client.name if project.client_id else '',
                    row['planned_fee'],
                    row['planned_cost'],
                    row['invoiced'],
                    row['received'],
                    row['expenses'],
                    row['profit'],
                    row['margin'],
                    row['receivable'],
                    row['payable'],
                ]
            )
        return response

    return render(request, 'portal/report_project_profitability.html', {'rows': rows})


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
    ledger_income = Transaction.objects.aggregate(total=Sum('credit'))['total'] or Decimal('0')
    salary_expenses = (
        Transaction.objects.filter(category=Transaction.Category.SALARY).aggregate(total=Sum('debit'))['total']
        or Decimal('0')
    )
    misc_expenses = (
        Transaction.objects.filter(category=Transaction.Category.MISC).aggregate(total=Sum('debit'))['total']
        or Decimal('0')
    )
    site_expenses = SiteVisit.objects.aggregate(total=Sum('expenses'))['total'] or Decimal('0')
    cash_balance = ledger_income - ledger_expenses - site_expenses
    totals = {
        'invoiced': total_invoiced,
        'received': total_received,
        'expenses': ledger_expenses + site_expenses,
        'salary': salary_expenses,
        'misc': misc_expenses,
        'cash_balance': cash_balance,
    }

    month_buckets = defaultdict(lambda: {'invoiced': Decimal('0'), 'received': Decimal('0'), 'expenses': Decimal('0')})

    for invoice in Invoice.objects.prefetch_related('lines'):
        month = invoice.invoice_date.replace(day=1)
        month_buckets[month]['invoiced'] += invoice.total_with_tax

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
@role_required(User.Roles.ADMIN)
def activity_overview(request):
    activity_filter = StaffActivityFilter(
        request.GET,
        queryset=StaffActivity.objects.select_related('actor').all()[:500],
    )
    return render(request, 'portal/activity.html', {'filter': activity_filter})


@login_required
@module_required('team')
def team_list(request):
    today = timezone.localdate()
    due_soon = today + timedelta(days=7)
    open_statuses = [Task.Status.TODO, Task.Status.IN_PROGRESS]
    team = (
        User.objects.order_by('role', 'first_name', 'last_name')
        .annotate(
            open_tasks_count=Count(
                'tasks', filter=Q(tasks__status__in=open_statuses), distinct=True
            ),
            overdue_tasks_count=Count(
                'tasks',
                filter=Q(tasks__status__in=open_statuses, tasks__due_date__lt=today),
                distinct=True,
            ),
            due_soon_tasks_count=Count(
                'tasks',
                filter=Q(tasks__status__in=open_statuses, tasks__due_date__gte=today, tasks__due_date__lte=due_soon),
                distinct=True,
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
