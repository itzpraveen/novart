from base64 import b64encode
from datetime import timedelta
from decimal import Decimal
import logging
import mimetypes
import os
from io import BytesIO
from django.contrib.staticfiles import finders

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

from .decorators import role_required
from .filters import InvoiceFilter, ProjectFilter, SiteIssueFilter, SiteVisitFilter, TaskFilter, TransactionFilter
from .forms import (
    ClientForm,
    DocumentForm,
    FirmProfileForm,
    InvoiceForm,
    InvoiceLineFormSet,
    LeadForm,
    PaymentForm,
    ProjectForm,
    SiteIssueForm,
    SiteVisitAttachmentForm,
    SiteVisitForm,
    StageUpdateForm,
    TaskForm,
    TransactionForm,
    ReminderSettingForm,
    UserForm,
)
from .models import (
    Client,
    Document,
    FirmProfile,
    Invoice,
    Lead,
    Notification,
    Payment,
    Project,
    ProjectStageHistory,
    ReminderSetting,
    SiteIssue,
    SiteVisit,
    Task,
    TaskTemplate,
    Transaction,
    User,
)


def _get_default_context():
    return {'currency': '₹'}


def _task_template_data():
    return list(
        TaskTemplate.objects.order_by('title').values(
            'id', 'title', 'description', 'status', 'priority', 'due_in_days'
        )
    )


def _refresh_invoice_status(invoice: Invoice) -> Invoice:
    today = timezone.localdate()
    outstanding = invoice.outstanding
    new_status = invoice.status
    if outstanding <= 0:
        new_status = Invoice.Status.PAID
    elif invoice.due_date < today:
        new_status = Invoice.Status.OVERDUE
    elif invoice.status == Invoice.Status.DRAFT:
        new_status = Invoice.Status.SENT
    if new_status != invoice.status:
        invoice.status = new_status
        invoice.save(update_fields=['status'])
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
    projects = Project.objects.select_related('client')
    total_active = projects.exclude(current_stage=Project.Stage.CLOSED).count()
    stage_counts = projects.values('current_stage').annotate(total=Count('id')).order_by('current_stage')

    site_visits_this_month = SiteVisit.objects.filter(visit_date__gte=start_month).count()
    upcoming_tasks = Task.objects.filter(status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]).order_by('due_date')[:5]
    upcoming_handover = projects.filter(expected_handover__gte=today, expected_handover__lte=today + timedelta(days=30))

    invoices_this_month = Invoice.objects.filter(invoice_date__gte=start_month).prefetch_related('lines')
    total_invoiced = sum((invoice.total_with_tax for invoice in invoices_this_month), Decimal('0'))
    payments_this_month = Payment.objects.filter(payment_date__gte=start_month)
    total_received = payments_this_month.aggregate(total=Sum('amount'))['total'] or 0

    top_projects = (
        projects.annotate(revenue=Sum('invoices__amount'))
        .order_by('-revenue')[:5]
        .select_related('client')
    )

    context = _get_default_context() | {
        'total_projects': projects.count(),
        'active_projects': total_active,
        'stage_counts': stage_counts,
        'site_visits_this_month': site_visits_this_month,
        'upcoming_tasks': upcoming_tasks,
        'upcoming_handover': upcoming_handover,
        'total_invoiced_month': total_invoiced,
        'total_received_month': total_received,
        'cash_gap': (total_invoiced or 0) - (total_received or 0),
        'top_projects': top_projects,
    }
    return render(request, 'portal/dashboard.html', context)


@login_required
def client_list(request):
    clients = Client.objects.all().order_by('name')
    search = request.GET.get('q')
    if search:
        clients = clients.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search))

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client saved.')
            return redirect('client_list')
    else:
        form = ClientForm()
    return render(request, 'portal/clients.html', {'clients': clients, 'form': form})


@login_required
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
def lead_list(request):
    leads = Lead.objects.select_related('client').annotate(project_count=Count('projects')).order_by('-created_at')
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)
    return render(request, 'portal/leads.html', {'leads': leads, 'statuses': Lead.Status.choices, 'selected_status': status})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
def lead_create(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.created_by = request.user
            lead.save()
            messages.success(request, 'Lead created.')
            return redirect('lead_list')
    else:
        form = LeadForm()
    return render(request, 'portal/lead_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
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
def lead_convert(request, pk):
    lead = get_object_or_404(Lead.objects.select_related('client'), pk=pk)
    if lead.status == Lead.Status.LOST:
        messages.warning(request, 'Lost leads cannot be converted. Please reopen the lead first.')
        return redirect('lead_list')
    if lead.status == Lead.Status.WON and not lead.is_converted:
        messages.info(request, 'This lead is already marked as won. Link or view the project directly.')
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
def project_list(request):
    project_filter = ProjectFilter(
        request.GET, queryset=Project.objects.select_related('client', 'project_manager', 'site_engineer')
    )
    context = {'filter': project_filter}
    return render(request, 'portal/projects.html', context)


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
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
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
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
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related('client', 'lead', 'lead__client', 'project_manager', 'site_engineer'), pk=pk
    )
    tasks = project.tasks.exclude(status=Task.Status.DONE).select_related('assigned_to')
    site_visits = project.site_visits.order_by('-visit_date')[:5]
    issues = project.issues.order_by('-raised_on')[:5]
    documents = project.documents.all()[:5]
    stage_history = project.stage_history.all()
    stage_form = StageUpdateForm(initial={'stage': project.current_stage})
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
            'currency': '₹',
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
def project_stage_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
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
def project_tasks(request, pk):
    project = get_object_or_404(Project, pk=pk)
    task_list = list(project.tasks.select_related('assigned_to'))
    columns = {code: [] for code, _ in Task.Status.choices}
    for task in task_list:
        columns.setdefault(task.status, []).append(task)
    form = TaskForm(initial={'project': project})
    if request.method == 'POST':
        if request.user.role not in [User.Roles.ADMIN, User.Roles.ARCHITECT]:
            return HttpResponseForbidden("You do not have permission to add tasks.")
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, 'Task added.')
            return redirect('project_tasks', pk=pk)
    return render(
        request,
        'portal/project_tasks.html',
        {
            'project': project,
            'columns': columns,
            'form': form,
            'statuses': Task.Status.choices,
            'task_templates_json': _task_template_data(),
        },
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
def task_create(request):
    project_id = request.GET.get('project')
    project = None
    if project_id:
        project = get_object_or_404(Project, pk=project_id)
    initial = {'project': project} if project else None
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, 'Task created.')
            return redirect('project_detail', pk=task.project.pk)
    else:
        form = TaskForm(initial=initial)
    return render(
        request,
        'portal/task_form.html',
        {'form': form, 'project': project, 'task_templates_json': _task_template_data()},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT)
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated.')
            return redirect('project_detail', pk=task.project.pk)
    else:
        form = TaskForm(instance=task)
    return render(
        request,
        'portal/task_form.html',
        {'form': form, 'task': task, 'project': task.project, 'task_templates_json': _task_template_data()},
    )


@login_required
def my_tasks(request):
    task_filter = TaskFilter(request.GET, queryset=Task.objects.filter(assigned_to=request.user))
    return render(request, 'portal/my_tasks.html', {'filter': task_filter})


@login_required
def site_visit_list(request):
    visit_filter = SiteVisitFilter(request.GET, queryset=SiteVisit.objects.select_related('project', 'visited_by'))
    return render(request, 'portal/site_visits.html', {'filter': visit_filter})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
def site_visit_create(request):
    if request.method == 'POST':
        form = SiteVisitForm(request.POST, request.FILES)
        if form.is_valid():
            visit = form.save()
            messages.success(request, 'Site visit logged.')
            return redirect('site_visit_list')
    else:
        form = SiteVisitForm(initial={'visited_by': request.user})
    return render(request, 'portal/site_visit_form.html', {'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
def site_visit_edit(request, pk):
    visit = get_object_or_404(SiteVisit, pk=pk)
    if request.method == 'POST':
        form = SiteVisitForm(request.POST, instance=visit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Site visit updated.')
            return redirect('site_visit_list')
    else:
        form = SiteVisitForm(instance=visit)
    return render(request, 'portal/site_visit_form.html', {'form': form, 'visit': visit})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.ARCHITECT, User.Roles.SITE_ENGINEER)
def site_visit_detail(request, pk):
    visit = get_object_or_404(SiteVisit, pk=pk)
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
def issue_list(request):
    issue_filter = SiteIssueFilter(request.GET, queryset=SiteIssue.objects.select_related('project', 'site_visit'))
    if request.method == 'POST':
        form = SiteIssueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Issue logged.')
            return redirect('issue_list')
    else:
        form = SiteIssueForm()
    return render(request, 'portal/issues.html', {'filter': issue_filter, 'form': form})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
def invoice_list(request):
    invoice_qs = Invoice.objects.select_related('project', 'project__client', 'lead', 'lead__client').prefetch_related(
        'lines', 'payments'
    )
    invoice_filter = InvoiceFilter(request.GET, queryset=invoice_qs)
    invoices = list(invoice_filter.qs)
    for invoice in invoices:
        _refresh_invoice_status(invoice)
    # Re-apply filter to reflect any status changes after refresh.
    invoice_filter = InvoiceFilter(request.GET, queryset=invoice_qs)
    invoices = list(invoice_filter.qs)
    return render(request, 'portal/invoices.html', {'filter': invoice_filter, 'invoices': invoices})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
def invoice_pdf(request, invoice_pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'project__client', 'project__project_manager', 'lead', 'lead__client'
        ).prefetch_related('lines', 'payments'),
        pk=invoice_pk,
    )
    invoice = _refresh_invoice_status(invoice)
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
        invoice = _refresh_invoice_status(invoice)
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
            payment.save()
            _refresh_invoice_status(invoice)
            messages.success(request, 'Payment recorded.')
            return redirect('invoice_list')
    else:
        form = PaymentForm(initial={'received_by': request.user}, invoice=invoice)
    return render(request, 'portal/payment_form.html', {'form': form, 'invoice': invoice})


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
def transaction_list(request):
    txn_filter = TransactionFilter(request.GET, queryset=Transaction.objects.select_related('related_project'))
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction saved.')
            return redirect('transaction_list')
    else:
        form = TransactionForm()
    return render(request, 'portal/transactions.html', {'filter': txn_filter, 'form': form, 'currency': '₹'})


@login_required
def document_list(request):
    documents = Document.objects.select_related('project').order_by('-created_at')
    doc_type = request.GET.get('file_type')
    project_id = request.GET.get('project')
    if doc_type:
        documents = documents.filter(file_type=doc_type)
    if project_id:
        documents = documents.filter(project_id=project_id)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            document.save()
            messages.success(request, 'Document added.')
            return redirect('document_list')
    else:
        form = DocumentForm()
    projects = Project.objects.order_by('name')
    return render(
        request,
        'portal/documents.html',
        {'documents': documents, 'form': form, 'projects': projects, 'file_types': Document.FileType.choices},
    )


@login_required
@role_required(User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT)
def finance_dashboard(request):
    projects = Project.objects.all()
    total_invoiced = sum((invoice.total_with_tax for invoice in Invoice.objects.prefetch_related('lines')), Decimal('0'))
    total_received = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
    ledger_expenses = Transaction.objects.aggregate(total=Sum('debit'))['total'] or 0
    site_expenses = SiteVisit.objects.aggregate(total=Sum('expenses'))['total'] or 0
    totals = {
        'invoiced': total_invoiced,
        'received': total_received,
        'expenses': (ledger_expenses or 0) + (site_expenses or 0),
    }
    return render(
        request,
        'portal/finance.html',
        {
            'projects': projects,
            'totals': totals,
            'currency': '₹',
        },
    )


@login_required
@role_required(User.Roles.ADMIN)
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
    if notification.related_url:
        return redirect(notification.related_url)
    return redirect('notification_list')


@login_required
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
def user_admin_list(request):
    users = User.objects.order_by('role', 'first_name', 'last_name')
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created.')
            return redirect('user_admin_list')
    else:
        form = UserForm()
    return render(request, 'portal/user_admin.html', {'users': users, 'form': form})


@login_required
@role_required(User.Roles.ADMIN)
def user_admin_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated.')
            return redirect('user_admin_list')
    else:
        form = UserForm(instance=user)
    return render(request, 'portal/user_admin.html', {'users': User.objects.order_by('role', 'first_name'), 'form': form, 'editing': user})
