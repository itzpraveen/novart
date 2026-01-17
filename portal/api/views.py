from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core.mail import send_mail
from django.db import transaction as db_transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from xhtml2pdf import pisa

from portal.activity import log_staff_activity
from portal.api.access import (
    can_view_all_projects,
    visible_issues_for_user,
    visible_projects_for_user,
    visible_site_visits_for_user,
    visible_tasks_for_user,
)
from portal.api.permissions import ModulePermission, RolePermission
from portal.api.serializers import (
    AccountSerializer,
    BankStatementImportSerializer,
    BankStatementLineSerializer,
    BillPaymentSerializer,
    BillSerializer,
    ClientAdvanceAllocationSerializer,
    ClientAdvanceSerializer,
    ClientSerializer,
    DocumentSerializer,
    ExpenseClaimAttachmentSerializer,
    ExpenseClaimPaymentSerializer,
    ExpenseClaimSerializer,
    FirmProfileSerializer,
    InvoiceSerializer,
    InvoiceUpsertSerializer,
    LeadSerializer,
    NotificationSerializer,
    PaymentSerializer,
    ProjectFinancePlanSerializer,
    ProjectMilestoneSerializer,
    ProjectSerializer,
    ProjectStageHistorySerializer,
    ReceiptSerializer,
    RecurringTransactionRuleSerializer,
    ReminderSettingSerializer,
    RolePermissionSerializer,
    SiteIssueAttachmentSerializer,
    SiteIssueSerializer,
    SiteVisitAttachmentSerializer,
    SiteVisitSerializer,
    StaffActivitySerializer,
    TaskCommentAttachmentSerializer,
    TaskCommentSerializer,
    TaskSerializer,
    TaskTemplateSerializer,
    TeamMemberSerializer,
    TransactionSerializer,
    UserSerializer,
    VendorSerializer,
    WhatsAppConfigSerializer,
)
from portal.finance_utils import generate_recurring_transactions
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
from portal.notifications.tasks import notify_task_change
from portal.notifications.whatsapp import send_text as send_whatsapp_text
from portal.permissions import get_permissions_for_user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username = attrs.get(self.username_field)
        if username and '@' in username:
            user = User.objects.filter(email__iexact=username).first()
            if user:
                attrs[self.username_field] = user.get_username()
        return super().validate(attrs)


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)


class MeView(APIView):
    def get(self, request):
        perms = get_permissions_for_user(request.user)
        return Response({
            'user': UserSerializer(request.user).data,
            'permissions': perms,
        })


class DashboardView(APIView):
    def get(self, request):
        user = request.user
        today = timezone.localdate()
        start_month = today.replace(day=1)
        perms = get_permissions_for_user(user)
        show_finance = user.is_superuser or perms.get('finance') or perms.get('invoices')
        show_stage_summary = user.is_superuser or perms.get('leads')
        can_create_projects_flag = user.is_superuser or user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)

        projects = Project.objects.select_related('client')
        if not show_finance:
            projects = projects.filter(
                Q(project_manager=user) | Q(site_engineer=user) | Q(tasks__assigned_to=user)
            ).distinct()

        total_active = projects.exclude(current_stage=Project.Stage.CLOSED).count()
        stage_counts = []
        if show_stage_summary:
            stage_counts = list(
                projects.values('current_stage').annotate(total=Count('id')).order_by('current_stage')
            )

        site_visits_scope = SiteVisit.objects.filter(visit_date__gte=start_month)
        if not show_finance:
            site_visits_scope = site_visits_scope.filter(
                Q(visited_by=user) | Q(project__project_manager=user) | Q(project__site_engineer=user)
            )
        site_visits_this_month = site_visits_scope.count()

        tasks_scope = visible_tasks_for_user(
            user,
            Task.objects.select_related('project', 'project__client').filter(
                status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]
            ),
        )
        task_limit = 5 if show_stage_summary else 10
        upcoming_tasks = tasks_scope.order_by(F('due_date').asc(nulls_last=True), '-created_at')[:task_limit]
        my_open_tasks_count = tasks_scope.count()

        upcoming_handover = projects.filter(
            expected_handover__gte=today,
            expected_handover__lte=today + timedelta(days=30),
        )

        response = {
            'total_projects': projects.count(),
            'active_projects': total_active,
            'stage_counts': stage_counts,
            'site_visits_this_month': site_visits_this_month,
            'upcoming_tasks': TaskSerializer(upcoming_tasks, many=True).data,
            'upcoming_handover': ProjectSerializer(upcoming_handover, many=True).data,
            'show_finance': show_finance,
            'show_stage_summary': show_stage_summary,
            'can_create_projects': can_create_projects_flag,
            'my_open_tasks_count': my_open_tasks_count,
        }

        if show_finance:
            invoices_this_month = Invoice.objects.filter(invoice_date__gte=start_month).prefetch_related('lines')
            total_invoiced = sum((invoice.total_with_tax for invoice in invoices_this_month), Decimal('0'))
            payments_this_month = Payment.objects.filter(payment_date__gte=start_month)
            total_received = payments_this_month.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            top_projects = (
                projects.annotate(revenue=Sum('invoices__amount'))
                .order_by('-revenue')[:5]
                .select_related('client')
            )
            response.update({
                'total_invoiced_month': total_invoiced,
                'total_received_month': total_received,
                'cash_gap': (total_invoiced or Decimal('0')) - (total_received or Decimal('0')),
                'top_projects': ProjectSerializer(top_projects, many=True).data,
            })

        return Response(response)


class GlobalSearchView(APIView):
    def get(self, request):
        query = (request.GET.get('q') or '').strip()
        perms = get_permissions_for_user(request.user)
        clients = Client.objects.none()
        leads = Lead.objects.none()
        projects = Project.objects.none()
        tasks = Task.objects.none()
        invoices = Invoice.objects.none()

        if query:
            if perms.get('clients'):
                clients = Client.objects.filter(
                    Q(name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
                ).order_by('name')[:10]
            if perms.get('leads'):
                leads = Lead.objects.select_related('client').filter(
                    Q(title__icontains=query)
                    | Q(client__name__icontains=query)
                    | Q(lead_source__icontains=query)
                ).order_by('-created_at')[:10]
            if perms.get('projects'):
                projects = visible_projects_for_user(
                    request.user,
                    Project.objects.select_related('client', 'project_manager'),
                ).filter(
                    Q(name__icontains=query) | Q(code__icontains=query) | Q(client__name__icontains=query)
                ).order_by('-updated_at')[:10]
                tasks = visible_tasks_for_user(
                    request.user,
                    Task.objects.select_related('project', 'assigned_to'),
                ).filter(
                    Q(title__icontains=query)
                    | Q(project__code__icontains=query)
                    | Q(project__name__icontains=query)
                ).order_by('due_date')[:10]
            if perms.get('invoices') or perms.get('finance'):
                invoice_filters = (
                    Q(invoice_number__icontains=query)
                    | Q(project__code__icontains=query)
                    | Q(project__name__icontains=query)
                    | Q(lead__title__icontains=query)
                    | Q(lead__client__name__icontains=query)
                )
                if '/' in query:
                    tail = query.split('/')[-1].strip()
                    if tail.isdigit():
                        invoice_filters |= Q(invoice_number__icontains=tail)
                invoices = Invoice.objects.select_related('project__client', 'lead__client').filter(
                    invoice_filters
                ).order_by('-invoice_date')[:10]

        return Response({
            'query': query,
            'clients': ClientSerializer(clients, many=True).data,
            'leads': LeadSerializer(leads, many=True).data,
            'projects': ProjectSerializer(projects, many=True).data,
            'tasks': TaskSerializer(tasks, many=True).data,
            'invoices': InvoiceSerializer(invoices, many=True).data,
        })


class BaseModelViewSet(viewsets.ModelViewSet):
    permission_classes = (ModulePermission, RolePermission)
    module_permission: str | None = None
    role_map: dict[str, tuple[str, ...] | None] | None = None

    def get_permissions(self):
        if self.role_map:
            roles = self.role_map.get(self.action)
            self.allowed_roles = roles
        return super().get_permissions()


class ClientViewSet(BaseModelViewSet):
    queryset = Client.objects.all().order_by('name')
    serializer_class = ClientSerializer
    module_permission = 'clients'
    search_fields = ('name', 'phone', 'email')
    ordering_fields = ('name', 'created_at', 'updated_at')
    filterset_fields = ('city', 'state')


class LeadViewSet(BaseModelViewSet):
    queryset = Lead.objects.select_related('client', 'created_by', 'converted_by').order_by('-created_at')
    serializer_class = LeadSerializer
    module_permission = 'leads'
    search_fields = ('title', 'client__name', 'lead_source')
    ordering_fields = ('created_at', 'status', 'estimated_value')
    filterset_fields = ('status', 'client')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'partial_update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'destroy': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'convert': (User.Roles.ADMIN, User.Roles.ARCHITECT),
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        lead = self.get_object()
        if lead.status == Lead.Status.LOST:
            return Response({'detail': 'Lost leads cannot be converted.'}, status=status.HTTP_400_BAD_REQUEST)
        if lead.is_converted:
            project = lead.projects.first()
            return Response({
                'detail': 'Lead already converted.',
                'project_id': project.pk if project else None,
            })
        project_data = request.data.get('project') or {}
        project_data.setdefault('client', lead.client_id)
        project_data.setdefault('lead', lead.pk)
        if not project_data.get('name'):
            project_data['name'] = lead.title
        if lead.planning_details and not project_data.get('description'):
            project_data['description'] = lead.planning_details
        project_serializer = ProjectSerializer(data=project_data)
        project_serializer.is_valid(raise_exception=True)
        project = project_serializer.save(client=lead.client, lead=lead)
        ProjectStageHistory.objects.create(project=project, stage=project.current_stage, changed_by=request.user)
        lead.status = Lead.Status.WON
        lead.converted_at = timezone.now()
        lead.converted_by = request.user
        lead.save(update_fields=['status', 'converted_at', 'converted_by'])
        log_staff_activity(
            actor=request.user,
            category=StaffActivity.Category.PROJECTS,
            message=f"Converted lead {lead.title} to project {project.code}.",
            related_url=f"/projects/{project.pk}/",
        )
        return Response({'project_id': project.pk}, status=status.HTTP_201_CREATED)


class ProjectViewSet(BaseModelViewSet):
    serializer_class = ProjectSerializer
    module_permission = 'projects'
    search_fields = ('name', 'code', 'client__name')
    ordering_fields = ('code', 'name', 'updated_at', 'expected_handover')
    filterset_fields = ('current_stage', 'health_status', 'project_type', 'client')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'partial_update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'destroy': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'stage_update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
    }

    def get_queryset(self):
        qs = Project.objects.select_related('client', 'project_manager', 'site_engineer')
        return visible_projects_for_user(self.request.user, qs)

    def perform_create(self, serializer):
        project = serializer.save()
        ProjectStageHistory.objects.create(project=project, stage=project.current_stage, changed_by=self.request.user)
        log_staff_activity(
            actor=self.request.user,
            category=StaffActivity.Category.PROJECTS,
            message=f"Created project {project.code}.",
            related_url=f"/projects/{project.pk}/",
        )

    @action(detail=True, methods=['post'])
    def stage_update(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectStageHistorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        history = serializer.save(project=project, changed_by=request.user)
        project.current_stage = history.stage
        project.save(update_fields=['current_stage'])
        log_staff_activity(
            actor=request.user,
            category=StaffActivity.Category.PROJECTS,
            message=f"Updated stage for {project.code} -> {history.stage}.",
            related_url=f"/projects/{project.pk}/",
        )
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        project = self.get_object()
        history = list(project.stage_history.order_by('changed_on', 'created_at'))
        phases = []
        if history:
            for idx, change in enumerate(history):
                start = change.changed_on
                end = history[idx + 1].changed_on - timedelta(days=1) if idx + 1 < len(history) else timezone.localdate()
                phases.append({
                    'stage': change.stage,
                    'start': start,
                    'end': end,
                    'duration_days': (end - start).days + 1 if start and end else None,
                    'changed_by': change.changed_by_id,
                    'notes': change.notes,
                })
        elif project.start_date:
            phases.append({
                'stage': project.current_stage,
                'start': project.start_date,
                'end': timezone.localdate(),
                'duration_days': (timezone.localdate() - project.start_date).days + 1,
                'changed_by': None,
                'notes': '',
            })
        return Response({'project_id': project.pk, 'phases': phases})

    @action(detail=True, methods=['get'])
    def finance(self, request, pk=None):
        project = self.get_object()
        plan, _ = ProjectFinancePlan.objects.get_or_create(project=project)
        milestones = ProjectMilestone.objects.filter(project=project).select_related('invoice').order_by('due_date', 'created_at')
        return Response({
            'plan': ProjectFinancePlanSerializer(plan).data,
            'milestones': ProjectMilestoneSerializer(milestones, many=True).data,
        })

    @action(detail=True, methods=['post'])
    def milestone_invoice(self, request, pk=None):
        project = self.get_object()
        milestone_id = request.data.get('milestone_id')
        milestone = ProjectMilestone.objects.filter(pk=milestone_id, project=project).first()
        if not milestone:
            return Response({'detail': 'Milestone not found.'}, status=status.HTTP_404_NOT_FOUND)
        if milestone.invoice_id:
            return Response({'detail': 'Invoice already exists.', 'invoice_id': milestone.invoice_id})
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
        return Response({'invoice_id': invoice.pk}, status=status.HTTP_201_CREATED)


class ProjectStageHistoryViewSet(BaseModelViewSet):
    queryset = ProjectStageHistory.objects.select_related('project', 'changed_by').order_by('-changed_on', '-created_at')
    serializer_class = ProjectStageHistorySerializer
    module_permission = 'projects'
    filterset_fields = ('project', 'stage')


class ProjectFinancePlanViewSet(BaseModelViewSet):
    queryset = ProjectFinancePlan.objects.select_related('project')
    serializer_class = ProjectFinancePlanSerializer
    module_permission = 'finance'
    filterset_fields = ('project',)


class ProjectMilestoneViewSet(BaseModelViewSet):
    queryset = ProjectMilestone.objects.select_related('project', 'invoice')
    serializer_class = ProjectMilestoneSerializer
    module_permission = 'finance'
    filterset_fields = ('project', 'status', 'invoice')


class TaskViewSet(BaseModelViewSet):
    serializer_class = TaskSerializer
    module_permission = 'projects'
    search_fields = ('title', 'project__code', 'project__name')
    ordering_fields = ('due_date', 'priority', 'created_at')
    filterset_fields = ('status', 'priority', 'project', 'assigned_to')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'partial_update': (User.Roles.ADMIN, User.Roles.ARCHITECT),
        'destroy': (User.Roles.ADMIN, User.Roles.ARCHITECT),
    }

    def get_queryset(self):
        qs = Task.objects.select_related('project', 'assigned_to').prefetch_related('watchers')
        return visible_tasks_for_user(self.request.user, qs)

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project') if hasattr(serializer, 'validated_data') else None
        if project and not visible_projects_for_user(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied('You do not have permission to add tasks to that project.')
        task = serializer.save()
        if task.assigned_to_id:
            task.watchers.add(task.assigned_to)
        notify_task_change(
            task,
            actor=self.request.user,
            message=f"{self.request.user} created task \"{task.title}\".",
            category='task_created',
        )
        log_staff_activity(
            actor=self.request.user,
            category=StaffActivity.Category.TASKS,
            message=f"Created task \"{task.title}\" ({task.project.code}).",
            related_url=f"/tasks/{task.pk}/",
        )

    def perform_update(self, serializer):
        project = serializer.validated_data.get('project') if hasattr(serializer, 'validated_data') else None
        if project and not visible_projects_for_user(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied('You do not have permission to move this task to that project.')
        serializer.save()

    @action(detail=True, methods=['post'])
    def quick_update(self, request, pk=None):
        task = self.get_object()
        can_manage_tasks = request.user.is_superuser or request.user.has_any_role(User.Roles.ADMIN, User.Roles.ARCHITECT)
        can_self_update = task.assigned_to_id == request.user.id
        if not (can_manage_tasks or can_self_update):
            return Response({'detail': 'You do not have permission to update this task.'}, status=status.HTTP_403_FORBIDDEN)
        new_status = request.data.get('status')
        if new_status not in Task.Status.values:
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
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
                message=f"{request.user} moved task \"{task.title}\" to {task.get_status_display()}.",
                category='task_status_changed',
            )
            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.TASKS,
                message=f"Moved task \"{task.title}\" -> {task.get_status_display()} ({task.project.code}).",
                related_url=f"/tasks/{task.pk}/",
            )
        return Response({'status': task.status})


class TaskCommentViewSet(BaseModelViewSet):
    queryset = TaskComment.objects.select_related('task', 'author').prefetch_related('attachments')
    serializer_class = TaskCommentSerializer
    module_permission = 'projects'
    filterset_fields = ('task',)

    def get_queryset(self):
        qs = TaskComment.objects.select_related('task', 'author').prefetch_related('attachments')
        visible_tasks = visible_tasks_for_user(self.request.user, Task.objects.all())
        return qs.filter(task__in=visible_tasks)

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        task = comment.task
        if task.watchers.filter(pk=self.request.user.pk).exists() is False:
            task.watchers.add(self.request.user)


class TaskCommentAttachmentViewSet(BaseModelViewSet):
    queryset = TaskCommentAttachment.objects.select_related('comment')
    serializer_class = TaskCommentAttachmentSerializer
    module_permission = 'projects'
    filterset_fields = ('comment',)

    def get_queryset(self):
        qs = TaskCommentAttachment.objects.select_related('comment', 'comment__task')
        visible_tasks = visible_tasks_for_user(self.request.user, Task.objects.all())
        return qs.filter(comment__task__in=visible_tasks)


class TaskTemplateViewSet(BaseModelViewSet):
    queryset = TaskTemplate.objects.all().order_by('title')
    serializer_class = TaskTemplateSerializer
    module_permission = 'projects'


class SiteVisitViewSet(BaseModelViewSet):
    serializer_class = SiteVisitSerializer
    module_permission = 'site_visits'
    ordering_fields = ('visit_date', 'created_at')
    filterset_fields = ('project', 'visited_by')

    def get_queryset(self):
        qs = SiteVisit.objects.select_related('project', 'visited_by')
        return visible_site_visits_for_user(self.request.user, qs)

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        if project and not visible_projects_for_user(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied('You do not have permission to log visits for that project.')
        serializer.save(visited_by=self.request.user)


class SiteVisitAttachmentViewSet(BaseModelViewSet):
    queryset = SiteVisitAttachment.objects.select_related('site_visit')
    serializer_class = SiteVisitAttachmentSerializer
    module_permission = 'site_visits'
    filterset_fields = ('site_visit',)

    def get_queryset(self):
        qs = SiteVisitAttachment.objects.select_related('site_visit')
        visits = visible_site_visits_for_user(self.request.user, SiteVisit.objects.all())
        return qs.filter(site_visit__in=visits)


class SiteIssueViewSet(BaseModelViewSet):
    serializer_class = SiteIssueSerializer
    module_permission = 'site_visits'
    ordering_fields = ('raised_on', 'status', 'created_at')
    filterset_fields = ('project', 'status', 'site_visit')

    def get_queryset(self):
        qs = SiteIssue.objects.select_related('project', 'site_visit', 'raised_by')
        return visible_issues_for_user(self.request.user, qs)

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        if project and not visible_projects_for_user(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied('You do not have permission to log issues for that project.')
        serializer.save(raised_by=self.request.user)


class SiteIssueAttachmentViewSet(BaseModelViewSet):
    queryset = SiteIssueAttachment.objects.select_related('issue')
    serializer_class = SiteIssueAttachmentSerializer
    module_permission = 'site_visits'
    filterset_fields = ('issue',)

    def get_queryset(self):
        qs = SiteIssueAttachment.objects.select_related('issue', 'issue__project')
        issues = visible_issues_for_user(self.request.user, SiteIssue.objects.all())
        return qs.filter(issue__in=issues)


class InvoiceViewSet(BaseModelViewSet):
    serializer_class = InvoiceSerializer
    module_permission = 'invoices'
    ordering_fields = ('invoice_date', 'due_date', 'status')
    filterset_fields = ('status', 'project', 'lead')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
    }

    def get_queryset(self):
        return Invoice.objects.select_related('project', 'project__client', 'lead', 'lead__client').prefetch_related(
            'lines', 'payments', 'advance_allocations'
        )

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InvoiceUpsertSerializer
        return InvoiceSerializer

    def perform_create(self, serializer):
        invoice = serializer.save()
        if invoice.status == Invoice.Status.DRAFT:
            invoice.status = Invoice.Status.SENT
            invoice.save(update_fields=['status'])
        log_staff_activity(
            actor=self.request.user,
            category=StaffActivity.Category.FINANCE,
            message=f"Created invoice {invoice.display_invoice_number}.",
            related_url=f"/invoices/{invoice.pk}/",
        )

    def perform_update(self, serializer):
        invoice = serializer.save()
        if invoice.status == Invoice.Status.DRAFT:
            invoice.status = Invoice.Status.SENT
            invoice.save(update_fields=['status'])
        log_staff_activity(
            actor=self.request.user,
            category=StaffActivity.Category.FINANCE,
            message=f"Updated invoice {invoice.display_invoice_number}.",
            related_url=f"/invoices/{invoice.pk}/",
        )

    @action(detail=True, methods=['post'])
    def payments(self, request, pk=None):
        invoice = self.get_object()
        if invoice.outstanding <= 0:
            return Response({'detail': 'Invoice already settled.'}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['invoice'] = invoice.pk
        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        with db_transaction.atomic():
            payment = serializer.save(invoice=invoice, recorded_by=request.user)
            invoice.refresh_status()
            receipt = Receipt(payment=payment, generated_by=request.user)
            receipt.save()

            log_staff_activity(
                actor=request.user,
                category=StaffActivity.Category.FINANCE,
                message=(
                    f"Recorded payment {payment.amount} for invoice {invoice.display_invoice_number} "
                    f"and created receipt {receipt.receipt_number}."
                ),
                related_url=f"/receipts/{receipt.pk}/",
            )

            client = receipt.client
            receipt_url = request.build_absolute_uri(f"/api/v1/receipts/{receipt.pk}/pdf/")
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
                    pass

            db_transaction.on_commit(_notify_client)

        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def aging(self, request):
        today = timezone.localdate()
        invoices = Invoice.objects.exclude(status=Invoice.Status.PAID).select_related(
            'project__client', 'lead', 'lead__client'
        ).prefetch_related('lines', 'payments', 'advance_allocations')
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
            buckets[bucket_key].append({
                'invoice': InvoiceSerializer(invoice).data,
                'days_overdue': days_overdue,
                'outstanding': outstanding,
            })
            totals[bucket_key] += outstanding
        grand_total = sum(totals.values(), Decimal('0'))
        return Response({'buckets': buckets, 'totals': totals, 'grand_total': grand_total})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        invoice.refresh_status(save=False)
        lines = list(invoice.lines.all())
        tax_value = max(invoice.total_with_tax - invoice.taxable_amount, Decimal('0'))
        client = invoice.project.client if invoice.project else (invoice.lead.client if invoice.lead else None)
        firm = FirmProfile.objects.first()
        logo_data = None

        if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
            logo_path = firm.logo.path
            logo_data = _data_uri(logo_path)
        if not logo_data:
            logo_data = _data_uri(_find_static('img/novart.png'))

        font_path, font_data_b64 = _resolve_dejavu_font_bundle()
        html = render_to_string(
            'portal/invoice_pdf.html',
            {
                'invoice': invoice,
                'lines': lines,
                'tax_value': tax_value,
                'client': client,
                'firm': firm,
                'logo_data': logo_data,
                'font_path': font_path,
                'font_data_b64': font_data_b64,
                'generated_on': timezone.localtime(),
            },
        )
        pdf_file = _render_pdf(html)
        display_number = invoice.display_invoice_number or invoice.invoice_number or str(invoice.pk)
        safe_number = _safe_filename(display_number)
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice-{safe_number}.pdf"'
        return response


class PaymentViewSet(BaseModelViewSet):
    queryset = Payment.objects.select_related('invoice', 'account', 'recorded_by', 'received_by')
    serializer_class = PaymentSerializer
    module_permission = 'invoices'
    filterset_fields = ('invoice',)
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ARCHITECT),
    }

    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        payment.invoice.refresh_status()
        Receipt.objects.get_or_create(payment=payment, defaults={'generated_by': self.request.user})


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.select_related('payment', 'invoice', 'project', 'client')
    serializer_class = ReceiptSerializer
    permission_classes = (ModulePermission, RolePermission)
    module_permission = 'finance'
    allowed_roles = (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT)
    filterset_fields = ('invoice', 'project', 'client')

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        receipt = self.get_object()
        firm = FirmProfile.objects.first()
        logo_data = None
        if firm and firm.logo and firm.logo.storage.exists(firm.logo.name):
            logo_data = _data_uri(firm.logo.path)
        if not logo_data:
            logo_data = _data_uri(_find_static('img/novart.png'))
        html = render_to_string(
            'portal/receipt_pdf.html',
            {
                'receipt': receipt,
                'firm': firm,
                'logo_data': logo_data,
                'generated_on': timezone.localtime(),
            },
        )
        pdf_file = _render_pdf(html)
        safe_number = _safe_filename(receipt.receipt_number or str(receipt.pk))
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt-{safe_number}.pdf"'
        return response


class AccountViewSet(BaseModelViewSet):
    queryset = Account.objects.all().order_by('name')
    serializer_class = AccountSerializer
    module_permission = 'finance'
    filterset_fields = ('account_type', 'is_active')


class VendorViewSet(BaseModelViewSet):
    queryset = Vendor.objects.all().order_by('name')
    serializer_class = VendorSerializer
    module_permission = 'finance'


class BillViewSet(BaseModelViewSet):
    queryset = Bill.objects.select_related('vendor', 'project', 'created_by').prefetch_related('payments')
    serializer_class = BillSerializer
    module_permission = 'finance'
    filterset_fields = ('status', 'vendor', 'project', 'category')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
    }

    def perform_create(self, serializer):
        bill = serializer.save(created_by=self.request.user)
        bill.refresh_status()
        log_staff_activity(
            actor=self.request.user,
            category=StaffActivity.Category.FINANCE,
            message=f"Added bill for {bill.vendor}: Rs. {bill.amount}.",
            related_url="/finance/bills/",
        )

    @action(detail=True, methods=['post'])
    def payments(self, request, pk=None):
        bill = self.get_object()
        if bill.outstanding <= 0:
            return Response({'detail': 'Bill already settled.'}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['bill'] = bill.pk
        serializer = BillPaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(bill=bill, recorded_by=request.user)
        bill.refresh_status()
        return Response(BillPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def aging(self, request):
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
            buckets[bucket_key].append({
                'bill': BillSerializer(bill).data,
                'days_overdue': days_overdue,
                'outstanding': outstanding,
            })
            totals[bucket_key] += outstanding
        grand_total = sum(totals.values(), Decimal('0'))
        return Response({'buckets': buckets, 'totals': totals, 'grand_total': grand_total})


class BillPaymentViewSet(BaseModelViewSet):
    queryset = BillPayment.objects.select_related('bill', 'account', 'recorded_by')
    serializer_class = BillPaymentSerializer
    module_permission = 'finance'
    filterset_fields = ('bill', 'account')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
    }

    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        payment.bill.refresh_status()


class ClientAdvanceViewSet(BaseModelViewSet):
    queryset = ClientAdvance.objects.select_related('project', 'client', 'account', 'recorded_by', 'received_by')
    serializer_class = ClientAdvanceSerializer
    module_permission = 'finance'
    filterset_fields = ('project', 'client', 'account')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
    }

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class ClientAdvanceAllocationViewSet(BaseModelViewSet):
    queryset = ClientAdvanceAllocation.objects.select_related('advance', 'invoice', 'allocated_by')
    serializer_class = ClientAdvanceAllocationSerializer
    module_permission = 'finance'
    filterset_fields = ('advance', 'invoice')
    role_map = {
        'create': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'partial_update': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'destroy': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
    }

    def perform_create(self, serializer):
        serializer.save(allocated_by=self.request.user)


class ExpenseClaimViewSet(BaseModelViewSet):
    serializer_class = ExpenseClaimSerializer
    module_permission = 'finance'
    permission_classes = (RolePermission,)
    role_map = {
        'approve': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'reject': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
        'pay': (User.Roles.ADMIN, User.Roles.FINANCE, User.Roles.ACCOUNTANT),
    }
    filterset_fields = ('status', 'employee', 'project')

    def get_queryset(self):
        qs = ExpenseClaim.objects.select_related('employee', 'project', 'approved_by').prefetch_related('attachments', 'payment')
        if can_view_all_projects(self.request.user) or self.request.user.has_any_role(
            User.Roles.ADMIN,
            User.Roles.FINANCE,
            User.Roles.ACCOUNTANT,
        ):
            return qs
        return qs.filter(employee=self.request.user)

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user, status=ExpenseClaim.Status.SUBMITTED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        claim = self.get_object()
        if claim.status != ExpenseClaim.Status.SUBMITTED:
            return Response({'detail': 'Only submitted claims can be approved.'}, status=status.HTTP_400_BAD_REQUEST)
        claim.status = ExpenseClaim.Status.APPROVED
        claim.approved_by = request.user
        claim.approved_at = timezone.now()
        claim.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response(ExpenseClaimSerializer(claim).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        claim = self.get_object()
        if claim.status == ExpenseClaim.Status.PAID:
            return Response({'detail': 'Cannot reject a paid claim.'}, status=status.HTTP_400_BAD_REQUEST)
        claim.status = ExpenseClaim.Status.REJECTED
        claim.save(update_fields=['status'])
        return Response(ExpenseClaimSerializer(claim).data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        claim = self.get_object()
        if claim.status != ExpenseClaim.Status.APPROVED:
            return Response({'detail': 'Only approved claims can be paid.'}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(claim, 'payment', None):
            return Response({'detail': 'This claim is already paid.'}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['claim'] = claim.pk
        serializer = ExpenseClaimPaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(claim=claim, recorded_by=request.user)
        claim.status = ExpenseClaim.Status.PAID
        claim.save(update_fields=['status'])
        return Response(ExpenseClaimPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class ExpenseClaimAttachmentViewSet(BaseModelViewSet):
    queryset = ExpenseClaimAttachment.objects.select_related('claim')
    serializer_class = ExpenseClaimAttachmentSerializer
    module_permission = 'finance'
    permission_classes = (RolePermission,)
    filterset_fields = ('claim',)

    def get_queryset(self):
        qs = ExpenseClaimAttachment.objects.select_related('claim')
        if can_view_all_projects(self.request.user) or self.request.user.has_any_role(
            User.Roles.ADMIN,
            User.Roles.FINANCE,
            User.Roles.ACCOUNTANT,
        ):
            return qs
        return qs.filter(claim__employee=self.request.user)


class ExpenseClaimPaymentViewSet(BaseModelViewSet):
    queryset = ExpenseClaimPayment.objects.select_related('claim', 'account', 'recorded_by')
    serializer_class = ExpenseClaimPaymentSerializer
    module_permission = 'finance'
    filterset_fields = ('claim', 'account')


class RecurringTransactionRuleViewSet(BaseModelViewSet):
    queryset = RecurringTransactionRule.objects.select_related('account', 'related_project', 'related_vendor')
    serializer_class = RecurringTransactionRuleSerializer
    module_permission = 'finance'
    filterset_fields = ('is_active', 'account', 'related_project', 'related_vendor', 'category')

    @action(detail=False, methods=['post'])
    def run(self, request):
        created = generate_recurring_transactions(today=timezone.localdate(), actor=request.user)
        return Response({'created': created})


class TransactionViewSet(BaseModelViewSet):
    queryset = Transaction.objects.select_related(
        'account',
        'related_project',
        'related_client',
        'related_vendor',
        'related_person',
        'recorded_by',
    )
    serializer_class = TransactionSerializer
    module_permission = 'finance'
    ordering_fields = ('date', 'category')
    filterset_fields = ('category', 'account', 'related_project', 'related_client', 'related_vendor', 'related_person')

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class BankStatementImportViewSet(BaseModelViewSet):
    queryset = BankStatementImport.objects.select_related('account', 'uploaded_by')
    serializer_class = BankStatementImportSerializer
    module_permission = 'finance'
    filterset_fields = ('account',)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class BankStatementLineViewSet(BaseModelViewSet):
    queryset = BankStatementLine.objects.select_related('statement', 'matched_transaction')
    serializer_class = BankStatementLineSerializer
    module_permission = 'finance'
    filterset_fields = ('statement', 'matched_transaction')

    @action(detail=True, methods=['post'])
    def create_transaction(self, request, pk=None):
        line = self.get_object()
        if line.matched_transaction_id:
            return Response({'detail': 'Line already matched.'}, status=status.HTTP_400_BAD_REQUEST)
        amount = line.amount or Decimal('0')
        txn = Transaction.objects.create(
            date=line.line_date,
            description=line.description[:255],
            category=Transaction.Category.OTHER_INCOME if amount > 0 else Transaction.Category.OTHER_EXPENSE,
            debit=abs(amount) if amount < 0 else 0,
            credit=amount if amount > 0 else 0,
            account=line.statement.account,
            recorded_by=request.user,
            remarks='Created from bank statement.',
        )
        line.matched_transaction = txn
        line.save(update_fields=['matched_transaction'])
        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


class DocumentViewSet(BaseModelViewSet):
    queryset = Document.objects.select_related('project', 'uploaded_by')
    serializer_class = DocumentSerializer
    module_permission = 'docs'
    filterset_fields = ('project', 'file_type')

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        if project and not visible_projects_for_user(self.request.user).filter(pk=project.pk).exists():
            raise PermissionDenied('You do not have permission to upload documents to that project.')
        serializer.save(uploaded_by=self.request.user)


class FirmProfileViewSet(BaseModelViewSet):
    queryset = FirmProfile.objects.all()
    serializer_class = FirmProfileSerializer
    module_permission = 'settings'


class RolePermissionViewSet(BaseModelViewSet):
    queryset = RolePermission.objects.all().order_by('role')
    serializer_class = RolePermissionSerializer
    module_permission = 'settings'


class ReminderSettingViewSet(BaseModelViewSet):
    queryset = ReminderSetting.objects.all().order_by('category')
    serializer_class = ReminderSettingSerializer
    module_permission = 'settings'


class WhatsAppConfigViewSet(BaseModelViewSet):
    queryset = WhatsAppConfig.objects.all().order_by('-updated_at')
    serializer_class = WhatsAppConfigSerializer
    module_permission = 'settings'


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    filterset_fields = ('is_read', 'category')

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('is_read', '-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)


class StaffActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StaffActivity.objects.select_related('actor').order_by('-created_at')
    serializer_class = StaffActivitySerializer
    permission_classes = (ModulePermission, RolePermission)
    module_permission = 'settings'
    allowed_roles = (User.Roles.ADMIN,)


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TeamMemberSerializer
    permission_classes = (ModulePermission,)
    module_permission = 'team'

    def get_queryset(self):
        today = timezone.localdate()
        due_soon = today + timedelta(days=7)
        open_statuses = [Task.Status.TODO, Task.Status.IN_PROGRESS]
        return (
            User.objects.order_by('role', 'first_name', 'last_name')
            .annotate(
                open_tasks_count=Count('tasks', filter=Q(tasks__status__in=open_statuses), distinct=True),
                overdue_tasks_count=Count(
                    'tasks',
                    filter=Q(tasks__status__in=open_statuses, tasks__due_date__lt=today),
                    distinct=True,
                ),
                due_soon_tasks_count=Count(
                    'tasks',
                    filter=Q(
                        tasks__status__in=open_statuses,
                        tasks__due_date__gte=today,
                        tasks__due_date__lte=due_soon,
                    ),
                    distinct=True,
                ),
                managed_projects_count=Count('managed_projects', distinct=True),
                visits_count=Count('site_visits', distinct=True),
            )
        )


class UserViewSet(BaseModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    module_permission = 'users'


class InvoiceReportView(APIView):
    def get(self, request):
        if not get_permissions_for_user(request.user).get('finance'):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        today = timezone.localdate()
        invoices = Invoice.objects.select_related('project__client', 'lead__client')
        data = {
            'total_count': invoices.count(),
            'total_outstanding': sum((invoice.outstanding for invoice in invoices), Decimal('0')),
            'overdue_count': invoices.filter(status=Invoice.Status.OVERDUE).count(),
            'as_of': today,
        }
        return Response(data)


def _render_pdf(html: str) -> bytes:
    pdf_file = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_file, encoding='UTF-8')
    if result.err:
        return b''
    pdf_file.seek(0)
    return pdf_file.read()


def _safe_filename(value: str) -> str:
    safe = ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in value)
    safe = safe.strip('-') or 'document'
    return safe


def _find_static(path: str) -> str | None:
    try:
        from django.contrib.staticfiles import finders

        return finders.find(path)
    except Exception:
        return None


_DATA_URI_CACHE: dict[str, tuple[float, str]] = {}


def _data_uri(path: str | None) -> str | None:
    if not path:
        return None
    try:
        import base64
        import os

        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        cached = _DATA_URI_CACHE.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(path, 'rb') as handle:
            encoded = base64.b64encode(handle.read()).decode('ascii')
        mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
        data_uri = f"data:{mime};base64,{encoded}"
        _DATA_URI_CACHE[path] = (mtime, data_uri)
        return data_uri
    except Exception:
        return None


_DEJAVU_CACHE: dict[str, tuple[float, tuple[str | None, str | None]]] = {}


def _resolve_dejavu_font_bundle() -> tuple[str | None, str | None]:
    try:
        import base64
        import os

        font_path = _find_static('fonts/DejaVuSans.ttf')
        if not font_path or not os.path.exists(font_path):
            return None, None
        mtime = os.path.getmtime(font_path)
        cached = _DEJAVU_CACHE.get(font_path)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(font_path, 'rb') as handle:
            font_data_b64 = base64.b64encode(handle.read()).decode('ascii')
        bundle = (font_path, font_data_b64)
        _DEJAVU_CACHE[font_path] = (mtime, bundle)
        return bundle
    except Exception:
        return None, None
