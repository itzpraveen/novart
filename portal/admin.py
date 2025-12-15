from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

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
    InvoiceLine,
    Lead,
    Notification,
    Payment,
    Project,
    ProjectFinancePlan,
    ProjectMilestone,
    ProjectStageHistory,
    RecurringTransactionRule,
    ReminderSetting,
    StaffActivity,
    SiteIssue,
    SiteIssueAttachment,
    SiteVisit,
    SiteVisitAttachment,
    Task,
    Transaction,
    User,
    Vendor,
    WhatsAppConfig,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (('Role Info', {'fields': ('role', 'phone', 'monthly_salary')}),)
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')


class StageHistoryInline(admin.TabularInline):
    model = ProjectStageHistory
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'client', 'project_type', 'current_stage', 'health_status')
    search_fields = ('name', 'code', 'client__name')
    list_filter = ('project_type', 'current_stage', 'health_status')
    inlines = [StageHistoryInline]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'city', 'state')
    search_fields = ('name', 'phone', 'email')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'status', 'lead_source', 'estimated_value')
    list_filter = ('status',)
    search_fields = ('title', 'client__name')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'priority', 'due_date', 'assigned_to')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'project__name')


@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = ('project', 'visit_date', 'visited_by', 'expenses')
    list_filter = ('visit_date',)


@admin.register(SiteVisitAttachment)
class SiteVisitAttachmentAdmin(admin.ModelAdmin):
    list_display = ('site_visit', 'caption')


class SiteIssueAttachmentInline(admin.TabularInline):
    model = SiteIssueAttachment
    extra = 0


@admin.register(SiteIssue)
class SiteIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'raised_on')
    list_filter = ('status',)
    inlines = [SiteIssueAttachmentInline]


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('display_invoice_number', 'project', 'invoice_date', 'status', 'total_display')
    list_filter = ('status',)
    inlines = [InvoiceLineInline]

    @admin.display(description='Invoice #')
    def display_invoice_number(self, obj):
        return obj.display_invoice_number

    @admin.display(description='Total (with tax)')
    def total_display(self, obj):
        return obj.total_with_tax


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'payment_date', 'amount', 'account', 'method', 'recorded_by')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'category', 'account', 'debit', 'credit', 'related_project', 'related_vendor', 'recorded_by')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'project', 'file_type', 'version')
    list_filter = ('file_type',)


@admin.register(ReminderSetting)
class ReminderSettingAdmin(admin.ModelAdmin):
    list_display = ('category', 'days_before', 'send_to_admins', 'send_to_assigned')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')


@admin.register(StaffActivity)
class StaffActivityAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'category', 'message')
    list_filter = ('category',)
    search_fields = ('message', 'actor__username', 'actor__first_name', 'actor__last_name')


@admin.register(FirmProfile)
class FirmProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'tax_id')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_type', 'opening_balance', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('name',)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'tax_id')
    search_fields = ('name', 'phone', 'email', 'tax_id')


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'project', 'bill_number', 'bill_date', 'due_date', 'amount', 'status', 'category')
    list_filter = ('status', 'category')
    search_fields = ('bill_number', 'vendor__name', 'project__code', 'project__name')


@admin.register(BillPayment)
class BillPaymentAdmin(admin.ModelAdmin):
    list_display = ('bill', 'payment_date', 'amount', 'account', 'method', 'recorded_by')
    list_filter = ('payment_date',)


@admin.register(ClientAdvance)
class ClientAdvanceAdmin(admin.ModelAdmin):
    list_display = ('project', 'client', 'received_date', 'amount', 'account', 'method', 'recorded_by')
    list_filter = ('received_date',)


@admin.register(ClientAdvanceAllocation)
class ClientAdvanceAllocationAdmin(admin.ModelAdmin):
    list_display = ('advance', 'invoice', 'amount', 'created_at', 'allocated_by')


@admin.register(ProjectFinancePlan)
class ProjectFinancePlanAdmin(admin.ModelAdmin):
    list_display = ('project', 'planned_fee', 'planned_cost', 'updated_at')


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ('project', 'title', 'due_date', 'amount', 'status', 'invoice')
    list_filter = ('status',)


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ('employee', 'project', 'expense_date', 'amount', 'status', 'approved_by')
    list_filter = ('status', 'expense_date')


@admin.register(ExpenseClaimAttachment)
class ExpenseClaimAttachmentAdmin(admin.ModelAdmin):
    list_display = ('claim', 'caption', 'created_at')


@admin.register(ExpenseClaimPayment)
class ExpenseClaimPaymentAdmin(admin.ModelAdmin):
    list_display = ('claim', 'payment_date', 'amount', 'account', 'method', 'recorded_by')


@admin.register(RecurringTransactionRule)
class RecurringTransactionRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'direction', 'category', 'amount', 'next_run_date')
    list_filter = ('is_active', 'direction', 'category')


@admin.register(BankStatementImport)
class BankStatementImportAdmin(admin.ModelAdmin):
    list_display = ('account', 'source_name', 'created_at', 'uploaded_by')


@admin.register(BankStatementLine)
class BankStatementLineAdmin(admin.ModelAdmin):
    list_display = ('statement', 'line_date', 'description', 'amount', 'matched_transaction')


@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ('enabled', 'from_number', 'phone_number_id', 'updated_at')
    list_display_links = ('from_number', 'phone_number_id')
    fields = ('enabled', 'from_number', 'phone_number_id', 'api_token', 'default_language')

    def has_add_permission(self, request):
        # Restrict to a single config entry
        if WhatsAppConfig.objects.exists():
            return False
        return super().has_add_permission(request)
