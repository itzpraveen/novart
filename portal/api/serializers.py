from __future__ import annotations

from typing import Any
import os

from django.core.exceptions import ValidationError
from rest_framework import serializers

from portal.models import (
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
    InvoiceLine,
    Lead,
    Notification,
    Payment,
    Project,
    ProjectFinancePlan,
    ProjectMilestone,
    ProjectStageHistory,
    Receipt,
    RecurringTransactionRule,
    ReminderSetting,
    RolePermission,
    SiteIssue,
    SiteIssueAttachment,
    SiteVisit,
    SiteVisitAttachment,
    StaffActivity,
    Task,
    TaskComment,
    TaskCommentAttachment,
    TaskTemplate,
    Transaction,
    User,
    Vendor,
    WhatsAppConfig,
)


ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ALLOWED_PDF_EXTENSIONS = {'.pdf'}


def validate_media_file(value, *, allow_images: bool = True, allow_pdf: bool = True):
    if not value:
        return value
    ext = os.path.splitext(value.name or '')[1].lower()
    allowed = set()
    if allow_images:
        allowed.update(ALLOWED_IMAGE_EXTENSIONS)
    if allow_pdf:
        allowed.update(ALLOWED_PDF_EXTENSIONS)
    if ext not in allowed:
        raise serializers.ValidationError('Only JPG, PNG, or PDF files are allowed.')
    content_type = getattr(value, 'content_type', '') or ''
    if content_type:
        if ext == '.pdf' and content_type not in ('application/pdf', 'application/x-pdf'):
            raise serializers.ValidationError('Only PDF files are allowed.')
        if ext in ALLOWED_IMAGE_EXTENSIONS and not content_type.startswith('image/'):
            raise serializers.ValidationError('Only image files are allowed.')
    return value


class CleanModelSerializer(serializers.ModelSerializer):
    """ModelSerializer that runs full_clean before saving."""

    def _perform_full_clean(self, instance):
        try:
            instance.full_clean()
        except ValidationError as exc:
            if hasattr(exc, 'message_dict'):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError({'detail': exc.messages}) from exc

    def create(self, validated_data, **kwargs):
        validated_data.update(kwargs)
        instance = self.Meta.model(**validated_data)
        self._perform_full_clean(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data, **kwargs):
        validated_data.update(kwargs)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._perform_full_clean(instance)
        instance.save()
        return instance


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'full_name', 'email', 'role')

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class TeamMemberSerializer(UserSummarySerializer):
    open_tasks_count = serializers.IntegerField(read_only=True)
    overdue_tasks_count = serializers.IntegerField(read_only=True)
    due_soon_tasks_count = serializers.IntegerField(read_only=True)
    managed_projects_count = serializers.IntegerField(read_only=True)
    visits_count = serializers.IntegerField(read_only=True)

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + (
            'open_tasks_count',
            'overdue_tasks_count',
            'due_soon_tasks_count',
            'managed_projects_count',
            'visits_count',
        )


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone',
            'role',
            'monthly_salary',
            'is_active',
            'is_superuser',
            'password',
        )

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user


class ClientSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ('id', 'name', 'phone', 'email')


class LeadSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ('id', 'title', 'status', 'estimated_value')


class ProjectSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ('id', 'code', 'name', 'current_stage', 'health_status')


class AccountSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ('id', 'name', 'account_type')


class VendorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ('id', 'name')


class ClientSerializer(CleanModelSerializer):
    class Meta:
        model = Client
        fields = (
            'id',
            'name',
            'phone',
            'email',
            'address',
            'city',
            'state',
            'postal_code',
            'notes',
            'created_at',
            'updated_at',
        )


class LeadSerializer(CleanModelSerializer):
    client_detail = ClientSummarySerializer(source='client', read_only=True)
    converted_by_detail = UserSummarySerializer(source='converted_by', read_only=True)
    created_by_detail = UserSummarySerializer(source='created_by', read_only=True)
    is_converted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lead
        fields = (
            'id',
            'client',
            'client_detail',
            'title',
            'lead_source',
            'status',
            'estimated_value',
            'notes',
            'planning_details',
            'converted_at',
            'converted_by',
            'converted_by_detail',
            'created_by',
            'created_by_detail',
            'is_converted',
            'created_at',
            'updated_at',
        )


class ProjectSerializer(CleanModelSerializer):
    client_detail = ClientSummarySerializer(source='client', read_only=True)
    lead_detail = LeadSummarySerializer(source='lead', read_only=True)
    project_manager_detail = UserSummarySerializer(source='project_manager', read_only=True)
    site_engineer_detail = UserSummarySerializer(source='site_engineer', read_only=True)
    total_tasks = serializers.IntegerField(read_only=True)
    open_tasks = serializers.IntegerField(read_only=True)
    total_invoiced = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_received = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_position = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        fields = (
            'id',
            'client',
            'client_detail',
            'lead',
            'lead_detail',
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
            'project_manager_detail',
            'site_engineer',
            'site_engineer_detail',
            'total_tasks',
            'open_tasks',
            'total_invoiced',
            'total_received',
            'total_expenses',
            'net_position',
            'created_at',
            'updated_at',
        )


class ProjectStageHistorySerializer(CleanModelSerializer):
    changed_by_detail = UserSummarySerializer(source='changed_by', read_only=True)

    class Meta:
        model = ProjectStageHistory
        fields = (
            'id',
            'project',
            'stage',
            'changed_on',
            'changed_by',
            'changed_by_detail',
            'notes',
            'created_at',
            'updated_at',
        )


class ProjectFinancePlanSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)

    class Meta:
        model = ProjectFinancePlan
        fields = (
            'id',
            'project',
            'project_detail',
            'planned_fee',
            'planned_cost',
            'notes',
            'created_at',
            'updated_at',
        )


class ProjectMilestoneSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    invoice_detail = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMilestone
        fields = (
            'id',
            'project',
            'project_detail',
            'title',
            'due_date',
            'amount',
            'status',
            'invoice',
            'invoice_detail',
            'notes',
            'created_at',
            'updated_at',
        )

    def get_invoice_detail(self, obj):
        invoice = getattr(obj, 'invoice', None)
        if not invoice:
            return None
        return {
            'id': invoice.id,
            'display_invoice_number': invoice.display_invoice_number,
            'status': invoice.status,
            'total_with_tax': invoice.total_with_tax,
        }


class TaskSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    assigned_to_detail = UserSummarySerializer(source='assigned_to', read_only=True)
    watchers_detail = UserSummarySerializer(source='watchers', many=True, read_only=True)

    class Meta:
        model = Task
        fields = (
            'id',
            'project',
            'project_detail',
            'title',
            'description',
            'status',
            'priority',
            'due_date',
            'assigned_to',
            'assigned_to_detail',
            'estimated_hours',
            'actual_hours',
            'objective',
            'expected_output',
            'deliverables',
            'references',
            'constraints',
            'watchers',
            'watchers_detail',
            'created_at',
            'updated_at',
        )


class TaskCommentAttachmentSerializer(CleanModelSerializer):
    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = TaskCommentAttachment
        fields = ('id', 'comment', 'file', 'caption', 'created_at', 'updated_at')


class TaskCommentSerializer(CleanModelSerializer):
    author_detail = UserSummarySerializer(source='author', read_only=True)
    attachments = TaskCommentAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TaskComment
        fields = (
            'id',
            'task',
            'author',
            'author_detail',
            'body',
            'is_system',
            'attachments',
            'created_at',
            'updated_at',
        )


class TaskTemplateSerializer(CleanModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = (
            'id',
            'title',
            'description',
            'status',
            'priority',
            'due_in_days',
            'created_at',
            'updated_at',
        )


class SiteVisitSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    visited_by_detail = UserSummarySerializer(source='visited_by', read_only=True)

    class Meta:
        model = SiteVisit
        fields = (
            'id',
            'project',
            'project_detail',
            'visit_date',
            'visited_by',
            'visited_by_detail',
            'notes',
            'expenses',
            'location',
            'created_at',
            'updated_at',
        )


class SiteVisitAttachmentSerializer(CleanModelSerializer):
    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = SiteVisitAttachment
        fields = ('id', 'site_visit', 'file', 'caption', 'created_at', 'updated_at')


class SiteIssueSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    site_visit_detail = serializers.SerializerMethodField()
    raised_by_detail = UserSummarySerializer(source='raised_by', read_only=True)

    class Meta:
        model = SiteIssue
        fields = (
            'id',
            'project',
            'project_detail',
            'site_visit',
            'site_visit_detail',
            'title',
            'description',
            'raised_on',
            'raised_by',
            'raised_by_detail',
            'status',
            'resolved_on',
            'created_at',
            'updated_at',
        )

    def get_site_visit_detail(self, obj):
        visit = getattr(obj, 'site_visit', None)
        if not visit:
            return None
        return {
            'id': visit.id,
            'visit_date': visit.visit_date,
            'project_id': visit.project_id,
        }


class SiteIssueAttachmentSerializer(CleanModelSerializer):
    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = SiteIssueAttachment
        fields = ('id', 'issue', 'file', 'caption', 'created_at', 'updated_at')


class InvoiceLineSerializer(CleanModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ('id', 'invoice', 'description', 'quantity', 'unit_price', 'line_total')
        read_only_fields = ('line_total',)


class InvoiceSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    lead_detail = LeadSummarySerializer(source='lead', read_only=True)
    display_invoice_number = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    taxable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_with_tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_received = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    advance_applied = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_settled = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id',
            'project',
            'project_detail',
            'lead',
            'lead_detail',
            'invoice_number',
            'display_invoice_number',
            'invoice_date',
            'due_date',
            'amount',
            'tax_percent',
            'discount_percent',
            'status',
            'description',
            'subtotal',
            'discount_amount',
            'taxable_amount',
            'total_with_tax',
            'amount_received',
            'advance_applied',
            'amount_settled',
            'outstanding',
            'lines',
            'created_at',
            'updated_at',
        )


class InvoiceUpsertSerializer(InvoiceSerializer):
    lines = InvoiceLineSerializer(many=True, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        lines = attrs.get('lines')
        if lines:
            total = sum((line.get('quantity', 0) or 0) * (line.get('unit_price', 0) or 0) for line in lines)
            amount = attrs.get('amount')
            if amount is not None and total and amount != total:
                raise serializers.ValidationError({'amount': f'Total amount must match line items ({total}).'})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop('lines', [])
        invoice = super().create(validated_data)
        if lines:
            for line in lines:
                line.pop('invoice', None)
                InvoiceLine.objects.create(invoice=invoice, **line)
            invoice.refresh_status()
        return invoice

    def update(self, instance, validated_data):
        lines = validated_data.pop('lines', None)
        invoice = super().update(instance, validated_data)
        if lines is not None:
            invoice.lines.all().delete()
            for line in lines:
                line.pop('invoice', None)
                InvoiceLine.objects.create(invoice=invoice, **line)
        invoice.refresh_status()
        return invoice


class PaymentSerializer(CleanModelSerializer):
    invoice_detail = serializers.SerializerMethodField()
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    recorded_by_detail = UserSummarySerializer(source='recorded_by', read_only=True)
    received_by_detail = UserSummarySerializer(source='received_by', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id',
            'invoice',
            'invoice_detail',
            'payment_date',
            'amount',
            'account',
            'account_detail',
            'method',
            'reference',
            'notes',
            'recorded_by',
            'recorded_by_detail',
            'received_by',
            'received_by_detail',
            'created_at',
            'updated_at',
        )

    def get_invoice_detail(self, obj):
        invoice = getattr(obj, 'invoice', None)
        if not invoice:
            return None
        return {
            'id': invoice.id,
            'display_invoice_number': invoice.display_invoice_number,
            'status': invoice.status,
        }


class ReceiptSerializer(CleanModelSerializer):
    payment_detail = PaymentSerializer(source='payment', read_only=True)
    invoice_detail = InvoiceSerializer(source='invoice', read_only=True)
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    client_detail = ClientSummarySerializer(source='client', read_only=True)
    generated_by_detail = UserSummarySerializer(source='generated_by', read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    method = serializers.CharField(read_only=True)
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = Receipt
        fields = (
            'id',
            'receipt_number',
            'receipt_date',
            'payment',
            'payment_detail',
            'invoice',
            'invoice_detail',
            'project',
            'project_detail',
            'client',
            'client_detail',
            'notes',
            'generated_by',
            'generated_by_detail',
            'amount',
            'method',
            'reference',
            'created_at',
            'updated_at',
        )


class AccountSerializer(CleanModelSerializer):
    current_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = (
            'id',
            'name',
            'account_type',
            'opening_balance',
            'is_active',
            'notes',
            'current_balance',
            'created_at',
            'updated_at',
        )


class VendorSerializer(CleanModelSerializer):
    class Meta:
        model = Vendor
        fields = (
            'id',
            'name',
            'phone',
            'email',
            'address',
            'tax_id',
            'notes',
            'created_at',
            'updated_at',
        )


class BillSerializer(CleanModelSerializer):
    vendor_detail = VendorSummarySerializer(source='vendor', read_only=True)
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    created_by_detail = UserSummarySerializer(source='created_by', read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    def validate_attachment(self, value):
        return validate_media_file(value)

    class Meta:
        model = Bill
        fields = (
            'id',
            'vendor',
            'vendor_detail',
            'project',
            'project_detail',
            'bill_number',
            'bill_date',
            'due_date',
            'amount',
            'status',
            'category',
            'description',
            'attachment',
            'created_by',
            'created_by_detail',
            'amount_paid',
            'outstanding',
            'created_at',
            'updated_at',
        )


class BillPaymentSerializer(CleanModelSerializer):
    bill_detail = serializers.SerializerMethodField()
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    recorded_by_detail = UserSummarySerializer(source='recorded_by', read_only=True)

    class Meta:
        model = BillPayment
        fields = (
            'id',
            'bill',
            'bill_detail',
            'payment_date',
            'amount',
            'account',
            'account_detail',
            'method',
            'reference',
            'notes',
            'recorded_by',
            'recorded_by_detail',
            'created_at',
            'updated_at',
        )

    def get_bill_detail(self, obj):
        bill = getattr(obj, 'bill', None)
        if not bill:
            return None
        return {
            'id': bill.id,
            'bill_number': bill.bill_number,
            'status': bill.status,
        }


class ClientAdvanceSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    client_detail = ClientSummarySerializer(source='client', read_only=True)
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    recorded_by_detail = UserSummarySerializer(source='recorded_by', read_only=True)
    received_by_detail = UserSummarySerializer(source='received_by', read_only=True)
    allocated_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ClientAdvance
        fields = (
            'id',
            'project',
            'project_detail',
            'client',
            'client_detail',
            'received_date',
            'amount',
            'account',
            'account_detail',
            'method',
            'reference',
            'notes',
            'recorded_by',
            'recorded_by_detail',
            'received_by',
            'received_by_detail',
            'allocated_amount',
            'available_amount',
            'created_at',
            'updated_at',
        )


class ClientAdvanceAllocationSerializer(CleanModelSerializer):
    advance_detail = ClientAdvanceSerializer(source='advance', read_only=True)
    invoice_detail = InvoiceSerializer(source='invoice', read_only=True)
    allocated_by_detail = UserSummarySerializer(source='allocated_by', read_only=True)

    class Meta:
        model = ClientAdvanceAllocation
        fields = (
            'id',
            'advance',
            'advance_detail',
            'invoice',
            'invoice_detail',
            'amount',
            'allocated_by',
            'allocated_by_detail',
            'notes',
            'created_at',
            'updated_at',
        )


class ExpenseClaimSerializer(CleanModelSerializer):
    employee_detail = UserSummarySerializer(source='employee', read_only=True)
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    approved_by_detail = UserSummarySerializer(source='approved_by', read_only=True)

    class Meta:
        model = ExpenseClaim
        fields = (
            'id',
            'employee',
            'employee_detail',
            'project',
            'project_detail',
            'expense_date',
            'amount',
            'category',
            'description',
            'status',
            'approved_by',
            'approved_by_detail',
            'approved_at',
            'created_at',
            'updated_at',
        )


class ExpenseClaimAttachmentSerializer(CleanModelSerializer):
    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = ExpenseClaimAttachment
        fields = ('id', 'claim', 'file', 'caption', 'created_at', 'updated_at')


class ExpenseClaimPaymentSerializer(CleanModelSerializer):
    claim_detail = ExpenseClaimSerializer(source='claim', read_only=True)
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    recorded_by_detail = UserSummarySerializer(source='recorded_by', read_only=True)

    class Meta:
        model = ExpenseClaimPayment
        fields = (
            'id',
            'claim',
            'claim_detail',
            'payment_date',
            'amount',
            'account',
            'account_detail',
            'method',
            'reference',
            'notes',
            'recorded_by',
            'recorded_by_detail',
            'created_at',
            'updated_at',
        )


class RecurringTransactionRuleSerializer(CleanModelSerializer):
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    related_project_detail = ProjectSummarySerializer(source='related_project', read_only=True)
    related_vendor_detail = VendorSummarySerializer(source='related_vendor', read_only=True)

    class Meta:
        model = RecurringTransactionRule
        fields = (
            'id',
            'name',
            'is_active',
            'direction',
            'category',
            'description',
            'amount',
            'account',
            'account_detail',
            'related_project',
            'related_project_detail',
            'related_vendor',
            'related_vendor_detail',
            'day_of_month',
            'next_run_date',
            'notes',
            'created_at',
            'updated_at',
        )


class BankStatementImportSerializer(CleanModelSerializer):
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    uploaded_by_detail = UserSummarySerializer(source='uploaded_by', read_only=True)

    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = BankStatementImport
        fields = (
            'id',
            'account',
            'account_detail',
            'file',
            'uploaded_by',
            'uploaded_by_detail',
            'source_name',
            'created_at',
            'updated_at',
        )


class BankStatementLineSerializer(CleanModelSerializer):
    statement_detail = BankStatementImportSerializer(source='statement', read_only=True)
    matched_transaction_detail = serializers.SerializerMethodField()

    class Meta:
        model = BankStatementLine
        fields = (
            'id',
            'statement',
            'statement_detail',
            'line_date',
            'description',
            'amount',
            'balance',
            'matched_transaction',
            'matched_transaction_detail',
            'created_at',
            'updated_at',
        )

    def get_matched_transaction_detail(self, obj):
        txn = getattr(obj, 'matched_transaction', None)
        if not txn:
            return None
        return {
            'id': txn.id,
            'description': txn.description,
            'category': txn.category,
            'date': txn.date,
        }


class TransactionSerializer(CleanModelSerializer):
    account_detail = AccountSummarySerializer(source='account', read_only=True)
    related_project_detail = ProjectSummarySerializer(source='related_project', read_only=True)
    related_client_detail = ClientSummarySerializer(source='related_client', read_only=True)
    related_vendor_detail = VendorSummarySerializer(source='related_vendor', read_only=True)
    related_person_detail = UserSummarySerializer(source='related_person', read_only=True)
    recorded_by_detail = UserSummarySerializer(source='recorded_by', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id',
            'date',
            'description',
            'category',
            'subcategory',
            'debit',
            'credit',
            'account',
            'account_detail',
            'payment',
            'bill_payment',
            'client_advance',
            'expense_claim_payment',
            'recurring_rule',
            'related_project',
            'related_project_detail',
            'related_client',
            'related_client_detail',
            'related_vendor',
            'related_vendor_detail',
            'related_person',
            'related_person_detail',
            'recorded_by',
            'recorded_by_detail',
            'remarks',
            'created_at',
            'updated_at',
        )


class DocumentSerializer(CleanModelSerializer):
    project_detail = ProjectSummarySerializer(source='project', read_only=True)
    uploaded_by_detail = UserSummarySerializer(source='uploaded_by', read_only=True)

    def validate_file(self, value):
        return validate_media_file(value)

    class Meta:
        model = Document
        fields = (
            'id',
            'project',
            'project_detail',
            'uploaded_by',
            'uploaded_by_detail',
            'file',
            'file_name',
            'file_type',
            'version',
            'notes',
            'created_at',
            'updated_at',
        )


class FirmProfileSerializer(CleanModelSerializer):
    def validate_logo(self, value):
        return validate_media_file(value, allow_pdf=False)

    class Meta:
        model = FirmProfile
        fields = (
            'id',
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
            'invoice_sequence_after',
            'logo',
            'created_at',
            'updated_at',
        )


class RolePermissionSerializer(CleanModelSerializer):
    class Meta:
        model = RolePermission
        fields = (
            'id',
            'role',
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
        )


class ReminderSettingSerializer(CleanModelSerializer):
    class Meta:
        model = ReminderSetting
        fields = ('id', 'category', 'days_before', 'send_to_admins', 'send_to_assigned')


class StaffActivitySerializer(serializers.ModelSerializer):
    actor_detail = UserSummarySerializer(source='actor', read_only=True)

    class Meta:
        model = StaffActivity
        fields = ('id', 'actor', 'actor_detail', 'category', 'message', 'related_url', 'created_at')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'user', 'message', 'is_read', 'category', 'related_url', 'created_at')


class WhatsAppConfigSerializer(CleanModelSerializer):
    class Meta:
        model = WhatsAppConfig
        fields = ('id', 'enabled', 'phone_number_id', 'from_number', 'api_token', 'default_language')
