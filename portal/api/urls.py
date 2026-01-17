from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from portal.api import views

router = DefaultRouter()
router.register('clients', views.ClientViewSet, basename='client')
router.register('leads', views.LeadViewSet, basename='lead')
router.register('projects', views.ProjectViewSet, basename='project')
router.register('project-stage-history', views.ProjectStageHistoryViewSet, basename='project-stage-history')
router.register('project-finance-plans', views.ProjectFinancePlanViewSet, basename='project-finance-plan')
router.register('project-milestones', views.ProjectMilestoneViewSet, basename='project-milestone')
router.register('tasks', views.TaskViewSet, basename='task')
router.register('task-comments', views.TaskCommentViewSet, basename='task-comment')
router.register('task-comment-attachments', views.TaskCommentAttachmentViewSet, basename='task-comment-attachment')
router.register('task-templates', views.TaskTemplateViewSet, basename='task-template')
router.register('site-visits', views.SiteVisitViewSet, basename='site-visit')
router.register('site-visit-attachments', views.SiteVisitAttachmentViewSet, basename='site-visit-attachment')
router.register('site-issues', views.SiteIssueViewSet, basename='site-issue')
router.register('site-issue-attachments', views.SiteIssueAttachmentViewSet, basename='site-issue-attachment')
router.register('invoices', views.InvoiceViewSet, basename='invoice')
router.register('payments', views.PaymentViewSet, basename='payment')
router.register('receipts', views.ReceiptViewSet, basename='receipt')
router.register('accounts', views.AccountViewSet, basename='account')
router.register('vendors', views.VendorViewSet, basename='vendor')
router.register('bills', views.BillViewSet, basename='bill')
router.register('bill-payments', views.BillPaymentViewSet, basename='bill-payment')
router.register('client-advances', views.ClientAdvanceViewSet, basename='client-advance')
router.register('client-advance-allocations', views.ClientAdvanceAllocationViewSet, basename='client-advance-allocation')
router.register('expense-claims', views.ExpenseClaimViewSet, basename='expense-claim')
router.register('expense-claim-attachments', views.ExpenseClaimAttachmentViewSet, basename='expense-claim-attachment')
router.register('expense-claim-payments', views.ExpenseClaimPaymentViewSet, basename='expense-claim-payment')
router.register('recurring-rules', views.RecurringTransactionRuleViewSet, basename='recurring-rule')
router.register('transactions', views.TransactionViewSet, basename='transaction')
router.register('bank-statements', views.BankStatementImportViewSet, basename='bank-statement')
router.register('bank-statement-lines', views.BankStatementLineViewSet, basename='bank-statement-line')
router.register('documents', views.DocumentViewSet, basename='document')
router.register('firm-profiles', views.FirmProfileViewSet, basename='firm-profile')
router.register('role-permissions', views.RolePermissionViewSet, basename='role-permission')
router.register('reminder-settings', views.ReminderSettingViewSet, basename='reminder-setting')
router.register('whatsapp-configs', views.WhatsAppConfigViewSet, basename='whatsapp-config')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('staff-activity', views.StaffActivityViewSet, basename='staff-activity')
router.register('team', views.TeamViewSet, basename='team')
router.register('users', views.UserViewSet, basename='user')

urlpatterns = [
    path('auth/token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', views.CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('search/', views.GlobalSearchView.as_view(), name='global_search'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('', include(router.urls)),
]
