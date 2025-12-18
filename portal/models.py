from decimal import Decimal
import os
import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import connection
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        ARCHITECT = 'architect', 'Architect'
        SENIOR_ARCHITECT = 'senior_architect', 'Senior Architect'
        JUNIOR_ARCHITECT = 'junior_architect', 'Junior Architect'
        MANAGING_DIRECTOR = 'managing_director', 'Managing Director'
        SITE_ENGINEER = 'site_engineer', 'Site Engineer'
        SENIOR_CIVIL_ENGINEER = 'senior_civil_engineer', 'Senior Civil Engineer'
        JUNIOR_CIVIL_ENGINEER = 'junior_civil_engineer', 'Junior Civil Engineer'
        FINANCE = 'finance', 'Finance'
        ACCOUNTANT = 'accountant', 'Accountant'
        PROJECT_MANAGER = 'project_manager', 'Project Manager'
        DESIGNER = 'designer', 'Designer'
        SENIOR_INTERIOR_DESIGNER = 'senior_interior_designer', 'Senior Interior Designer'
        JUNIOR_INTERIOR_DESIGNER = 'junior_interior_designer', 'Junior Interior Designer'
        DRAUGHTSMAN = 'draughtsman', 'Draughtsman'
        VISUALISER_3D = 'visualiser_3d', '3D Visualiser'
        QS = 'qs', 'QS / Estimator'
        PROCUREMENT = 'procurement', 'Procurement'
        CLIENT_LIAISON = 'client_liaison', 'Client Liaison'
        INTERN = 'intern', 'Intern / Trainee'
        VIEWER = 'viewer', 'Viewer (read-only)'

    phone = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=32, choices=Roles.choices, default=Roles.ARCHITECT)
    monthly_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        blank=True,
        help_text='Optional: used for payroll tracking (monthly amount).',
    )

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def has_any_role(self, *roles: str) -> bool:
        """Role-aware helper that also considers equivalent/specialised titles."""
        role_groups = {
            self.Roles.ADMIN: {self.Roles.ADMIN},
            self.Roles.ARCHITECT: {
                self.Roles.ARCHITECT,
                self.Roles.SENIOR_ARCHITECT,
                self.Roles.JUNIOR_ARCHITECT,
                self.Roles.MANAGING_DIRECTOR,
            },
            self.Roles.SITE_ENGINEER: {
                self.Roles.SITE_ENGINEER,
                self.Roles.SENIOR_CIVIL_ENGINEER,
                self.Roles.JUNIOR_CIVIL_ENGINEER,
            },
            self.Roles.FINANCE: {self.Roles.FINANCE, self.Roles.ACCOUNTANT},
            self.Roles.PROJECT_MANAGER: {self.Roles.PROJECT_MANAGER},
            self.Roles.DESIGNER: {
                self.Roles.DESIGNER,
                self.Roles.SENIOR_INTERIOR_DESIGNER,
                self.Roles.JUNIOR_INTERIOR_DESIGNER,
                self.Roles.DRAUGHTSMAN,
                self.Roles.VISUALISER_3D,
            },
            self.Roles.QS: {self.Roles.QS},
            self.Roles.PROCUREMENT: {self.Roles.PROCUREMENT},
            self.Roles.CLIENT_LIAISON: {self.Roles.CLIENT_LIAISON},
            self.Roles.INTERN: {self.Roles.INTERN},
            self.Roles.VIEWER: {self.Roles.VIEWER},
        }
        for requested in roles:
            if self.role in role_groups.get(requested, {requested}):
                return True
        return False


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Client(TimeStampedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class Lead(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        DISCUSSION = 'discussion', 'In Discussion'
        WON = 'won', 'Won'
        LOST = 'lost', 'Lost'

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='leads')
    title = models.CharField(max_length=255)
    lead_source = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    planning_details = models.TextField(blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_leads'
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    @property
    def is_converted(self) -> bool:
        project_count = getattr(self, 'project_count', None)
        if project_count is not None:
            return bool(self.converted_at or project_count)
        return bool(self.converted_at or self.projects.exists())


class Project(TimeStampedModel):
    class ProjectType(models.TextChoices):
        RESIDENTIAL = 'residential', 'Residential'
        COMMERCIAL = 'commercial', 'Commercial'
        OTHER = 'other', 'Other'

    class Stage(models.TextChoices):
        ENQUIRY = 'Enquiry', 'Enquiry'
        CONCEPT = 'Concept', 'Concept'
        DESIGN_DEVELOPMENT = 'Design Development', 'Design Development'
        APPROVALS = 'Approvals', 'Approvals'
        WORKING_DRAWINGS = 'Working Drawings', 'Working Drawings'
        SITE_EXECUTION = 'Site Execution', 'Site Execution'
        HANDOVER = 'Handover', 'Handover'
        CLOSED = 'Closed', 'Closed'

    class Health(models.TextChoices):
        ON_TRACK = 'on_track', 'On Track'
        AT_RISK = 'at_risk', 'At Risk'
        DELAYED = 'delayed', 'Delayed'

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    project_type = models.CharField(max_length=32, choices=ProjectType.choices, default=ProjectType.RESIDENTIAL)
    location = models.CharField(max_length=255, blank=True)
    built_up_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    expected_handover = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    current_stage = models.CharField(max_length=50, choices=Stage.choices, default=Stage.ENQUIRY)
    health_status = models.CharField(max_length=32, choices=Health.choices, default=Health.ON_TRACK)
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects'
    )
    site_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='engineered_projects'
    )

    class Meta:
        indexes = [
            models.Index(fields=['current_stage']),
            models.Index(fields=['health_status']),
            models.Index(fields=['project_type']),
            models.Index(fields=['start_date']),
            models.Index(fields=['expected_handover']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    @property
    def total_tasks(self) -> int:
        return self.tasks.count()

    @property
    def open_tasks(self) -> int:
        return self.tasks.exclude(status=Task.Status.DONE).count()

    @property
    def total_invoiced(self) -> Decimal:
        invoices = self.invoices.prefetch_related('lines')
        return sum((invoice.total_with_tax for invoice in invoices), Decimal('0'))

    @property
    def total_received(self) -> Decimal:
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}
        if 'transactions' in prefetched:
            return sum((txn.credit for txn in self.transactions.all()), Decimal('0'))
        return self.transactions.aggregate(total=models.Sum('credit'))['total'] or Decimal('0')

    @property
    def total_expenses(self) -> Decimal:
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}

        if 'transactions' in prefetched:
            expenses = sum((txn.debit for txn in self.transactions.all()), Decimal('0'))
        else:
            expenses = self.transactions.aggregate(total=models.Sum('debit'))['total'] or Decimal('0')

        if 'site_visits' in prefetched:
            visit_expenses = sum((visit.expenses for visit in self.site_visits.all()), Decimal('0'))
        else:
            visit_expenses = self.site_visits.aggregate(total=models.Sum('expenses'))['total'] or Decimal('0')

        return expenses + visit_expenses

    @property
    def net_position(self) -> Decimal:
        return self.total_received - self.total_expenses


class ProjectStageHistory(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='stage_history')
    stage = models.CharField(max_length=50, choices=Project.Stage.choices)
    changed_on = models.DateField(auto_now_add=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_on', '-created_at']

    def __str__(self) -> str:
        return f"{self.project} -> {self.stage}"


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks'
    )
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    objective = models.TextField(blank=True, help_text='What is the goal of this task?')
    expected_output = models.TextField(help_text='What should be delivered/decided?')
    deliverables = models.TextField(blank=True, help_text='Checklist or bullet deliverables (one per line).')
    references = models.TextField(blank=True, help_text='Links or references (one per line).')
    constraints = models.TextField(blank=True, help_text='Any constraints, budgets, or rules to follow.')
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='watched_tasks', help_text='Users watching this task.'
    )

    class Meta:
        ordering = ['due_date', 'priority']
        indexes = [
            models.Index(fields=['assigned_to', 'status', 'due_date']),
            models.Index(fields=['project', 'status', 'due_date']),
        ]

    def __str__(self) -> str:
        return self.title


class TaskComment(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_comments'
    )
    body = models.TextField()
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Comment on {self.task}"


class TaskCommentAttachment(TimeStampedModel):
    comment = models.ForeignKey(TaskComment, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_comments/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Attachment for {self.comment}"


class TaskTemplate(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Task.Status.choices, default=Task.Status.TODO)
    priority = models.CharField(max_length=32, choices=Task.Priority.choices, default=Task.Priority.MEDIUM)
    due_in_days = models.PositiveIntegerField(
        null=True, blank=True, help_text='If set, due date will default to today + this many days.'
    )

    class Meta:
        ordering = ['title']

    def __str__(self) -> str:
        return self.title


class SiteVisit(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='site_visits')
    visit_date = models.DateField()
    visited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='site_visits'
    )
    notes = models.TextField(blank=True)
    expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'visit_date']),
            models.Index(fields=['visited_by', 'visit_date']),
        ]

    def save(self, *args, **kwargs):
        if not self.location and self.project:
            self.location = self.project.location
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.project} visit on {self.visit_date}"


class SiteVisitAttachment(TimeStampedModel):
    site_visit = models.ForeignKey(SiteVisit, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='site_visits/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"Attachment for {self.site_visit}"


class SiteIssue(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        RESOLVED = 'resolved', 'Resolved'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='issues')
    site_visit = models.ForeignKey(SiteVisit, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    raised_on = models.DateField()
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues_raised'
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)
    resolved_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['status', '-raised_on']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['status', 'raised_on']),
        ]

    def __str__(self) -> str:
        return self.title


class SiteIssueAttachment(TimeStampedModel):
    issue = models.ForeignKey(SiteIssue, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='site_issues/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Attachment for {self.issue}"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, related_name='invoices', null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['invoice_date']),
        ]

    def __str__(self) -> str:
        return f"Invoice {self.display_invoice_number}"

    def clean(self):
        super().clean()
        if self.invoice_date and self.due_date and self.due_date < self.invoice_date:
            raise ValidationError({'due_date': 'Due date cannot be earlier than the invoice date.'})
        if not self.project and not self.lead:
            raise ValidationError('Select a project or a lead to bill.')

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self) -> str:
        prefix = (os.environ.get('INVOICE_PREFIX') or 'NVRT').strip() or 'NVRT'
        project_part = 'GEN'
        if self.project and getattr(self.project, 'code', None):
            code = str(self.project.code)
            match = re.match(r'^(\d+)', code)
            if match:
                project_part = match.group(1)
            else:
                project_part = code.split('-')[0] or code
        elif self.lead and self.lead.client_id:
            project_part = str(self.lead.client_id)

        max_seq: int | None = None
        if connection.vendor == 'postgresql':
            try:
                table = connection.ops.quote_name(Invoice._meta.db_table)
                scheme_regex = rf'^{re.escape(prefix)}/[^/]+/[0-9]+$'
                digits_regex = r'^[0-9]+$'
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT MAX(CAST(split_part(invoice_number, '/', 3) AS integer)) "
                        f"FROM {table} WHERE invoice_number ~ %s",
                        [scheme_regex],
                    )
                    max_scheme = cursor.fetchone()[0] or 0
                    cursor.execute(
                        f"SELECT MAX(CAST(invoice_number AS integer)) "
                        f"FROM {table} WHERE invoice_number ~ %s",
                        [digits_regex],
                    )
                    max_digits = cursor.fetchone()[0] or 0
                max_seq = max(int(max_scheme or 0), int(max_digits or 0))
            except Exception:
                max_seq = None

        if max_seq is None:
            pattern = re.compile(rf'^{re.escape(prefix)}/[^/]+/(\d+)$')
            max_seq = 0
            for existing in Invoice.objects.values_list('invoice_number', flat=True):
                existing_value = (existing or '').strip()
                m = pattern.match(existing_value)
                if m:
                    seq_str = m.group(1)
                elif re.fullmatch(r'\d+', existing_value):
                    seq_str = existing_value
                else:
                    continue
                try:
                    max_seq = max(max_seq, int(seq_str))
                except ValueError:
                    continue

        def parse_seed_after(raw_value: str | None) -> int | None:
            value = (raw_value or '').strip()
            if not value:
                return None
            match = re.search(r'(\d+)\s*$', value)
            if not match:
                return None
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                return None

        seed_after = None
        try:
            firm = FirmProfile.objects.only('invoice_sequence_after').first()
        except Exception:
            firm = None
        firm_seed_after = getattr(firm, 'invoice_sequence_after', None) if firm else None
        env_seed_after = parse_seed_after(os.environ.get('INVOICE_SEQUENCE_AFTER'))
        candidates = [value for value in (firm_seed_after, env_seed_after) if value is not None]
        if candidates:
            seed_after = max(candidates)
            max_seq = max(max_seq, seed_after)

        seq = max_seq + 1
        candidate = f"{prefix}/{project_part}/{seq}"
        while Invoice.objects.filter(invoice_number=candidate).exists():
            seq += 1
            candidate = f"{prefix}/{project_part}/{seq}"
        return candidate

    @property
    def display_invoice_number(self) -> str:
        """Human-friendly invoice number that follows firm scheme."""
        raw = (self.invoice_number or '').strip()
        if not raw:
            return ''
        if '/' in raw:
            return raw
        if not re.fullmatch(r'\d+', raw):
            return raw

        prefix = (os.environ.get('INVOICE_PREFIX') or 'NVRT').strip() or 'NVRT'
        project_part = 'GEN'
        if self.project and getattr(self.project, 'code', None):
            code = str(self.project.code)
            match = re.match(r'^(\d+)', code)
            if match:
                project_part = match.group(1)
            else:
                project_part = code.split('-')[0] or code
        elif self.lead and self.lead.client_id:
            project_part = str(self.lead.client_id)

        return f"{prefix}/{project_part}/{raw}"

    def refresh_status(self, *, save: bool = True, today=None) -> str:
        """Update invoice.status based on due date and payments."""
        today = today or timezone.localdate()
        outstanding = self.outstanding
        new_status = self.status
        if outstanding <= 0:
            new_status = self.Status.PAID
        elif self.due_date < today:
            new_status = self.Status.OVERDUE
        elif self.status == self.Status.DRAFT:
            new_status = self.Status.SENT
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=['status'])
        return new_status

    @property
    def subtotal(self) -> Decimal:
        lines_total = sum((line.line_total for line in self.lines.all()), Decimal('0'))
        return lines_total or self.amount

    @property
    def discount_amount(self) -> Decimal:
        base = self.subtotal
        discount_value = (base * (self.discount_percent or 0)) / Decimal('100')
        discount_value = max(discount_value, Decimal('0'))
        return min(discount_value, base)

    @property
    def taxable_amount(self) -> Decimal:
        return max(self.subtotal - self.discount_amount, Decimal('0'))

    @property
    def total_with_tax(self) -> Decimal:
        tax_value = (self.taxable_amount * (self.tax_percent or 0)) / Decimal('100')
        return self.taxable_amount + tax_value

    @property
    def amount_received(self) -> Decimal:
        """Cash payments recorded against this invoice."""
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}
        if 'payments' in prefetched:
            return sum((payment.amount for payment in self.payments.all()), Decimal('0'))
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def advance_applied(self) -> Decimal:
        """Non-cash allocations from client advances that settle this invoice."""
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}
        if 'advance_allocations' in prefetched:
            return sum((alloc.amount for alloc in self.advance_allocations.all()), Decimal('0'))
        return self.advance_allocations.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def amount_settled(self) -> Decimal:
        """Payments + advance allocations."""
        return (self.amount_received or Decimal('0')) + (self.advance_applied or Decimal('0'))

    @property
    def outstanding(self) -> Decimal:
        return max(self.total_with_tax - self.amount_settled, Decimal('0'))


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return f"{self.description} x {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return (self.quantity or Decimal('0')) * (self.unit_price or Decimal('0'))


class Payment(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(
        'Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, help_text='Internal notes about this payment.')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_recorded',
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_received'
    )

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['payment_date']),
            models.Index(fields=['invoice', 'payment_date']),
        ]

    def __str__(self) -> str:
        return f"Payment {self.amount} on {self.payment_date}"


class Receipt(TimeStampedModel):
    """
    Receipt = Proof of payment given to client.

    Correct flow: Invoice → Client pays → Record Payment → Generate Receipt (proof for client)
    Receipt is generated FROM a Payment, not the other way around.
    """
    receipt_number = models.CharField(max_length=64, unique=True)
    receipt_date = models.DateField(default=timezone.now)
    # Receipt is generated from a payment (required)
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name='receipt'
    )
    # Denormalized fields for easy access (auto-populated from payment)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='receipts')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts')
    # Receipt-specific fields
    notes = models.TextField(blank=True, help_text='Additional notes to print on receipt')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts_generated'
    )

    class Meta:
        ordering = ['-receipt_date', '-created_at']
        indexes = [
            models.Index(fields=['receipt_date']),
            models.Index(fields=['invoice', 'receipt_date']),
        ]

    def __str__(self) -> str:
        return self.receipt_number

    @property
    def amount(self):
        """Amount comes from the linked payment."""
        return self.payment.amount if self.payment else None

    @property
    def method(self):
        """Payment method comes from the linked payment."""
        return self.payment.method if self.payment else ''

    @property
    def reference(self):
        """Reference comes from the linked payment."""
        return self.payment.reference if self.payment else ''

    def save(self, *args, **kwargs):
        if not self.receipt_date:
            self.receipt_date = self.payment.payment_date if self.payment else timezone.now().date()
        # Auto-populate from payment
        if self.payment:
            if not self.invoice_id:
                self.invoice = self.payment.invoice
            if not self.project_id and self.payment.invoice.project:
                self.project = self.payment.invoice.project
            if not self.client_id:
                if self.payment.invoice.project and self.payment.invoice.project.client:
                    self.client = self.payment.invoice.project.client
                elif self.payment.invoice.lead:
                    self.client = self.payment.invoice.lead.client
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)

    def _generate_receipt_number(self) -> str:
        receipt_date = self.receipt_date or timezone.now().date()
        prefix_code = None
        if self.project and getattr(self.project, 'code', None):
            prefix_code = self.project.code
        elif self.payment and self.payment.invoice.project:
            prefix_code = self.payment.invoice.project.code
        prefix = f"{prefix_code or 'RCPT'}-{receipt_date:%Y%m%d}"
        base_qs = Receipt.objects.filter(receipt_number__startswith=prefix)
        seq = base_qs.count() + 1
        candidate = f"{prefix}-{seq:02d}"
        # ensure uniqueness if races or existing data
        while Receipt.objects.filter(receipt_number=candidate).exists():
            seq += 1
            candidate = f"{prefix}-{seq:02d}"
        return candidate


class Account(TimeStampedModel):
    class Type(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK = 'bank', 'Bank'
        UPI = 'upi', 'UPI'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=16, choices=Type.choices, default=Type.CASH)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['account_type', 'name']),
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def current_balance(self) -> Decimal:
        totals = self.transactions.aggregate(
            debit=models.Sum('debit'),
            credit=models.Sum('credit'),
        )
        debit = totals.get('debit') or Decimal('0')
        credit = totals.get('credit') or Decimal('0')
        return (self.opening_balance or Decimal('0')) + credit - debit


class Vendor(TimeStampedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self) -> str:
        return self.name


class Bill(TimeStampedModel):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PARTIAL = 'partial', 'Partial'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='bills')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='bills')
    bill_number = models.CharField(max_length=100, blank=True)
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNPAID)
    category = models.CharField(
        max_length=32,
        choices=[
            ('project_expense', 'Project expense'),
            ('misc', 'Misc expense'),
            ('other_expense', 'Other expense'),
        ],
        default='project_expense',
    )
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to='bills/', blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills_created',
    )

    class Meta:
        ordering = ['-bill_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['bill_date']),
            models.Index(fields=['vendor', 'bill_date']),
        ]

    def __str__(self) -> str:
        label = self.bill_number or f"Bill #{self.pk}"
        return f"{self.vendor} · {label}"

    @property
    def amount_paid(self) -> Decimal:
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}
        if 'payments' in prefetched:
            return sum((payment.amount for payment in self.payments.all()), Decimal('0'))
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def outstanding(self) -> Decimal:
        return max((self.amount or Decimal('0')) - self.amount_paid, Decimal('0'))

    def refresh_status(self, *, save: bool = True, today=None) -> str:
        today = today or timezone.localdate()
        outstanding = self.outstanding
        new_status = self.status
        if outstanding <= 0:
            new_status = self.Status.PAID
        elif outstanding < (self.amount or Decimal('0')):
            new_status = self.Status.PARTIAL
        elif self.due_date and self.due_date < today:
            new_status = self.Status.OVERDUE
        else:
            new_status = self.Status.UNPAID
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=['status'])
        return new_status


class BillPayment(TimeStampedModel):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bill_payments',
    )
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bill_payments_recorded',
    )

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['payment_date']),
            models.Index(fields=['bill', 'payment_date']),
        ]

    def __str__(self) -> str:
        return f"Bill payment {self.amount} on {self.payment_date}"


class ClientAdvance(TimeStampedModel):
    """Client advance / retainer received (not tied to an invoice)."""

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='advances')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='advances')
    received_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_advances',
    )
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advances_recorded',
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advances_received',
    )

    class Meta:
        ordering = ['-received_date', '-created_at']
        indexes = [
            models.Index(fields=['received_date']),
            models.Index(fields=['client', 'received_date']),
            models.Index(fields=['project', 'received_date']),
        ]

    def __str__(self) -> str:
        label = f"Advance {self.amount} on {self.received_date}"
        if self.project_id:
            return f"{self.project} · {label}"
        if self.client_id:
            return f"{self.client} · {label}"
        return label

    def clean(self):
        super().clean()
        if not self.project_id and not self.client_id:
            raise ValidationError('Select a project or a client.')
        if self.project_id and not self.client_id and self.project and self.project.client_id:
            self.client = self.project.client

    @property
    def allocated_amount(self) -> Decimal:
        prefetched = getattr(self, '_prefetched_objects_cache', {}) or {}
        if 'allocations' in prefetched:
            return sum((alloc.amount for alloc in self.allocations.all()), Decimal('0'))
        return self.allocations.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def available_amount(self) -> Decimal:
        return max((self.amount or Decimal('0')) - self.allocated_amount, Decimal('0'))


class ClientAdvanceAllocation(TimeStampedModel):
    advance = models.ForeignKey(ClientAdvance, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='advance_allocations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advance_allocations',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', 'created_at']),
            models.Index(fields=['advance', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.advance} -> {self.invoice.display_invoice_number} ({self.amount})"

    def clean(self):
        super().clean()
        amount = self.amount or Decimal('0')
        if amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than zero.'})
        if self.advance_id and self.invoice_id:
            if self.invoice.project_id and self.advance.project_id and self.invoice.project_id != self.advance.project_id:
                raise ValidationError('Advance and invoice must belong to the same project.')
            if self.invoice.lead_id and self.advance.client_id and self.invoice.lead and self.invoice.lead.client_id != self.advance.client_id:
                raise ValidationError('Advance and invoice must belong to the same client.')


class ProjectFinancePlan(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='finance_plan')
    planned_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    planned_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Finance plan · {self.project}"


class ProjectMilestone(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        INVOICED = 'invoiced', 'Invoiced'
        PAID = 'paid', 'Paid'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='milestones')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['due_date', 'created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self) -> str:
        return f"{self.project} · {self.title}"


class ExpenseClaim(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expense_claims')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='expense_claims')
    expense_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_claims_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'expense_date']),
            models.Index(fields=['employee', 'expense_date']),
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.amount} · {self.expense_date}"


class ExpenseClaimAttachment(TimeStampedModel):
    claim = models.ForeignKey(ExpenseClaim, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='expense_claims/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Attachment for {self.claim}"


class ExpenseClaimPayment(TimeStampedModel):
    claim = models.OneToOneField(ExpenseClaim, on_delete=models.CASCADE, related_name='payment')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_claim_payments',
    )
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_claim_payments_recorded',
    )

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['payment_date']),
        ]

    def __str__(self) -> str:
        return f"Claim payment {self.amount} on {self.payment_date}"


class RecurringTransactionRule(TimeStampedModel):
    class Direction(models.TextChoices):
        DEBIT = 'debit', 'Debit (expense)'
        CREDIT = 'credit', 'Credit (income)'

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    direction = models.CharField(max_length=16, choices=Direction.choices, default=Direction.DEBIT)
    category = models.CharField(
        max_length=32,
        choices=[
            ('client_payment', 'Client payment'),
            ('client_advance', 'Client advance'),
            ('vendor_payment', 'Vendor payment'),
            ('salary', 'Salary'),
            ('reimbursement', 'Reimbursement'),
            ('transfer', 'Transfer'),
            ('misc', 'Misc expense'),
            ('project_expense', 'Project expense'),
            ('other_income', 'Other income'),
            ('other_expense', 'Other expense'),
        ],
        default='misc',
    )
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_rules')
    related_project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_rules')
    related_vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_rules')
    day_of_month = models.PositiveSmallIntegerField(default=1)
    next_run_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['next_run_date', 'name']
        indexes = [
            models.Index(fields=['is_active', 'next_run_date']),
        ]

    def __str__(self) -> str:
        return self.name


class BankStatementImport(TimeStampedModel):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='statement_imports')
    file = models.FileField(upload_to='bank_statements/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statement_uploads',
    )
    source_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.account} statement · {self.created_at:%Y-%m-%d}"


class BankStatementLine(TimeStampedModel):
    statement = models.ForeignKey(BankStatementImport, on_delete=models.CASCADE, related_name='lines')
    line_date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Positive = credit (money in). Negative = debit (money out).',
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    matched_transaction = models.ForeignKey(
        'Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_statement_lines',
    )

    class Meta:
        ordering = ['-line_date', '-created_at']
        indexes = [
            models.Index(fields=['statement', 'line_date']),
            models.Index(fields=['line_date']),
        ]

    def __str__(self) -> str:
        return f"{self.statement.account} · {self.line_date} · {self.amount}"


class Transaction(TimeStampedModel):
    class Category(models.TextChoices):
        CLIENT_PAYMENT = 'client_payment', 'Client payment'
        CLIENT_ADVANCE = 'client_advance', 'Client advance'
        VENDOR_PAYMENT = 'vendor_payment', 'Vendor payment'
        SALARY = 'salary', 'Salary'
        REIMBURSEMENT = 'reimbursement', 'Reimbursement'
        TRANSFER = 'transfer', 'Transfer'
        MISC = 'misc', 'Misc expense'
        PROJECT_EXPENSE = 'project_expense', 'Project expense'
        OTHER_INCOME = 'other_income', 'Other income'
        OTHER_EXPENSE = 'other_expense', 'Other expense'

    date = models.DateField()
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=Category.choices, blank=True, default='', db_index=True)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
    )
    payment = models.OneToOneField(
        'Payment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cashbook_entry',
        help_text='Auto-linked payment income entry (system generated).',
    )
    bill_payment = models.ForeignKey(
        'BillPayment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cashbook_entries',
        help_text='Auto-linked vendor payment entry (system generated).',
    )
    client_advance = models.ForeignKey(
        'ClientAdvance',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cashbook_entries',
        help_text='Auto-linked client advance entry (system generated).',
    )
    expense_claim_payment = models.ForeignKey(
        'ExpenseClaimPayment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cashbook_entries',
        help_text='Auto-linked reimbursement entry (system generated).',
    )
    recurring_rule = models.ForeignKey(
        RecurringTransactionRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
    )
    related_project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    related_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    related_vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    related_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions_recorded',
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category', 'date']),
            models.Index(fields=['account', 'date']),
            models.Index(fields=['related_vendor', 'date']),
            models.Index(fields=['related_person', 'date']),
            models.Index(fields=['related_project', 'date']),
            models.Index(fields=['related_client', 'date']),
        ]

    def __str__(self) -> str:
        return self.description


class Document(TimeStampedModel):
    class FileType(models.TextChoices):
        DRAWING = 'drawing', 'Drawing'
        APPROVAL = 'approval', 'Approval'
        BOQ = 'boq', 'BOQ'
        PHOTO = 'photo', 'Photo'
        OTHER = 'other', 'Other'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents'
    )
    file = models.FileField(upload_to='documents/', blank=True, null=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50, choices=FileType.choices, default=FileType.OTHER)
    version = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'created_at']),
            models.Index(fields=['file_type']),
        ]


class FirmProfile(TimeStampedModel):
    name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    bank_ifsc = models.CharField(max_length=50, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    terms = models.TextField(blank=True)
    invoice_sequence_after = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Optional: next invoice will use the number after this value (e.g. 584 → 585).',
    )
    logo = models.ImageField(upload_to='firm/', blank=True, null=True)
    singleton = models.BooleanField(default=True, unique=True)

    class Meta:
        verbose_name = 'Firm Profile'

    def __str__(self) -> str:
        return self.name or "Firm Profile"


class RolePermission(TimeStampedModel):
    class Module(models.TextChoices):
        CLIENTS = 'clients', 'Clients'
        LEADS = 'leads', 'Leads'
        PROJECTS = 'projects', 'Projects'
        SITE_VISITS = 'site_visits', 'Site Visits'
        FINANCE = 'finance', 'Finance'
        INVOICES = 'invoices', 'Invoices'
        DOCS = 'docs', 'Docs'
        TEAM = 'team', 'Team'
        USERS = 'users', 'Users'
        SETTINGS = 'settings', 'Settings'

    role = models.CharField(max_length=32, choices=User.Roles.choices, unique=True)
    clients = models.BooleanField(default=False)
    leads = models.BooleanField(default=False)
    projects = models.BooleanField(default=False)
    site_visits = models.BooleanField(default=False)
    finance = models.BooleanField(default=False)
    invoices = models.BooleanField(default=False)
    docs = models.BooleanField(default=False)
    team = models.BooleanField(default=False)
    users = models.BooleanField(default=False)
    settings = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.get_role_display()} permissions"


class ReminderSetting(TimeStampedModel):
    class Category(models.TextChoices):
        TASK = 'task_due', 'Task Due'
        HANDOVER = 'handover', 'Upcoming Handover'
        INVOICE = 'invoice_due', 'Invoice Due'
        INVOICE_OVERDUE = 'invoice_overdue', 'Invoice Overdue'

    category = models.CharField(max_length=50, choices=Category.choices, unique=True)
    days_before = models.PositiveIntegerField(default=2)
    send_to_admins = models.BooleanField(default=True)
    send_to_assigned = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.get_category_display()} - {self.days_before} days"


class StaffActivity(TimeStampedModel):
    """Append-only audit trail for admin staff activity overview."""

    class Category(models.TextChoices):
        PROJECTS = 'projects', 'Projects'
        TASKS = 'tasks', 'Tasks'
        SITE_VISITS = 'site_visits', 'Site Visits'
        FINANCE = 'finance', 'Finance'
        DOCS = 'docs', 'Docs'
        TEAM = 'team', 'Team'
        USERS = 'users', 'Users'
        SETTINGS = 'settings', 'Settings'
        SYSTEM = 'system', 'System'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_activity',
    )
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.SYSTEM)
    message = models.CharField(max_length=500)
    related_url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['category', 'created_at']),
        ]

    def __str__(self) -> str:
        actor = self.actor.get_full_name() if self.actor else 'System'
        return f"{actor}: {self.message}"


class Notification(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    category = models.CharField(max_length=50, blank=True)
    related_url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['is_read', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.message}"


class WhatsAppConfig(TimeStampedModel):
    enabled = models.BooleanField(default=False)
    phone_number_id = models.CharField(max_length=64, blank=True)
    from_number = models.CharField(max_length=32, blank=True)
    api_token = models.TextField(blank=True)
    default_language = models.CharField(max_length=10, default='en', blank=True)

    class Meta:
        verbose_name = 'WhatsApp Configuration'

    def __str__(self) -> str:
        return self.from_number or self.phone_number_id or "WhatsApp Config"
