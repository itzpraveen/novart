from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


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
        return Payment.objects.filter(invoice__project=self).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def total_expenses(self) -> Decimal:
        expenses = self.transactions.aggregate(total=models.Sum('debit'))['total'] or Decimal('0')
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

    class Meta:
        ordering = ['due_date', 'priority']

    def __str__(self) -> str:
        return self.title


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

    def __str__(self) -> str:
        return self.title


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, related_name='invoices', null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-invoice_date']

    def __str__(self) -> str:
        return f"Invoice {self.invoice_number}"

    def clean(self):
        super().clean()
        if not self.project and not self.lead:
            raise ValidationError('Select a project or a lead to bill.')

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
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def outstanding(self) -> Decimal:
        return max(self.total_with_tax - self.amount_received, Decimal('0'))


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
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_received'
    )

    class Meta:
        ordering = ['-payment_date']

    def __str__(self) -> str:
        return f"Payment {self.amount} on {self.payment_date}"


class Transaction(TimeStampedModel):
    date = models.DateField()
    description = models.CharField(max_length=255)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    related_project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    related_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    related_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

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


class Notification(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    category = models.CharField(max_length=50, blank=True)
    related_url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['is_read', '-created_at']

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
