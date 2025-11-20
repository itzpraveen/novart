from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Client,
    Document,
    Invoice,
    Lead,
    Notification,
    Payment,
    Project,
    ProjectStageHistory,
    ReminderSetting,
    SiteIssue,
    SiteVisit,
    SiteVisitAttachment,
    Task,
    Transaction,
    User,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (('Role Info', {'fields': ('role', 'phone')}),)
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


@admin.register(SiteIssue)
class SiteIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'raised_on')
    list_filter = ('status',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'project', 'invoice_date', 'status', 'amount')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'payment_date', 'amount', 'method')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'debit', 'credit', 'related_project')


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
