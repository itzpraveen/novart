from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Account,
    Bill,
    BillPayment,
    Client,
    ClientAdvance,
    ClientAdvanceAllocation,
    ExpenseClaim,
    Invoice,
    Payment,
    Project,
    Receipt,
    RecurringTransactionRule,
    RolePermission,
    StaffActivity,
    Transaction,
    Lead,
    Vendor,
)
from .permissions import get_permissions_for_user

User = get_user_model()


class PermissionGuardTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'

    def test_viewer_cannot_access_documents_module(self):
        user = User.objects.create_user(username='viewer', password=self.password, role=User.Roles.VIEWER)
        # Simulate legacy permission rows that incorrectly allowed docs for viewers
        RolePermission.objects.update_or_create(role=User.Roles.VIEWER, defaults={'docs': True})

        self.client.login(username='viewer', password=self.password)
        resp = self.client.get(reverse('document_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_architect_without_invoice_perm_is_redirected(self):
        user = User.objects.create_user(username='arch', password=self.password, role=User.Roles.ARCHITECT)
        # Explicitly disable invoices for this role
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'invoices': False})

        self.client.login(username='arch', password=self.password)
        resp = self.client.get(reverse('invoice_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_project_routes_enforce_module_permission(self):
        user = User.objects.create_user(username='viewer2', password=self.password, role=User.Roles.VIEWER)
        # Viewer has projects True by default; disable to confirm guard blocks access
        RolePermission.objects.update_or_create(role=User.Roles.VIEWER, defaults={'projects': False})
        self.client.login(username='viewer2', password=self.password)

        resp = self.client.get(reverse('project_detail', args=[1]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_lead_convert_requires_leads_permission(self):
        user = User.objects.create_user(username='leadless', password=self.password, role=User.Roles.ARCHITECT)
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'leads': False})
        client = Client.objects.create(name='Test Client')
        lead = Lead.objects.create(client=client, title='Test Lead', created_by=user)

        self.client.login(username='leadless', password=self.password)
        resp = self.client.get(reverse('lead_convert', args=[lead.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_won_lead_without_project_can_be_converted(self):
        user = User.objects.create_user(username='arch2', password=self.password, role=User.Roles.ARCHITECT)
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'leads': True})
        client = Client.objects.create(name='Test Client')
        lead = Lead.objects.create(
            client=client,
            title='Won Lead',
            status=Lead.Status.WON,
            created_by=user,
        )

        self.client.login(username='arch2', password=self.password)
        resp = self.client.get(reverse('lead_convert', args=[lead.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_alias_role_inherits_base_permissions_when_missing_row(self):
        RolePermission.objects.update_or_create(
            role=User.Roles.ARCHITECT,
            defaults={'clients': False, 'projects': True},
        )
        RolePermission.objects.filter(role=User.Roles.SENIOR_ARCHITECT).delete()
        user = User.objects.create_user(
            username='senior_arch',
            password=self.password,
            role=User.Roles.SENIOR_ARCHITECT,
        )

        perms = get_permissions_for_user(user)
        self.assertFalse(perms['clients'])
        self.assertTrue(perms['projects'])


class FinanceFlowTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'
        self.user = User.objects.create_user(
            username='admin',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.client.login(username='admin', password=self.password)

    def test_record_payment_auto_creates_receipt_and_cashbook(self):
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='100-NVRT')
        invoice = Invoice.objects.create(
            project=project,
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate(),
            amount=Decimal('1000.00'),
            tax_percent=Decimal('0'),
            discount_percent=Decimal('0'),
            status=Invoice.Status.SENT,
        )

        resp = self.client.post(
            reverse('payment_create', args=[invoice.pk]),
            data={
                'payment_date': timezone.localdate(),
                'amount': '250.00',
                'method': 'Cash',
                'reference': 'REF-1',
                'notes': '',
                'received_by': self.user.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)

        payment = Payment.objects.get(invoice=invoice)
        receipt = Receipt.objects.get(payment=payment)
        cashbook_entry = Transaction.objects.get(payment=payment)

        self.assertEqual(cashbook_entry.credit, payment.amount)
        self.assertEqual(cashbook_entry.debit, 0)
        self.assertEqual(cashbook_entry.category, Transaction.Category.CLIENT_PAYMENT)
        self.assertEqual(cashbook_entry.related_project_id, project.pk)
        self.assertEqual(cashbook_entry.related_client_id, client.pk)

        self.assertTrue(
            StaffActivity.objects.filter(
                category=StaffActivity.Category.FINANCE,
                related_url=reverse('receipt_pdf', args=[receipt.pk]),
            ).exists()
        )
        self.assertEqual(resp.url, reverse('receipt_pdf', args=[receipt.pk]))

    def test_bill_payment_creates_cashbook_entry(self):
        cash = Account.objects.create(name='Cash', account_type=Account.Type.CASH)
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='200-NVRT')
        vendor = Vendor.objects.create(name='Test Vendor')
        bill = Bill.objects.create(
            vendor=vendor,
            project=project,
            bill_number='B-1',
            bill_date=timezone.localdate(),
            due_date=timezone.localdate(),
            amount=Decimal('1000.00'),
            category='project_expense',
            created_by=self.user,
        )

        resp = self.client.post(
            reverse('bill_payment_create', args=[bill.pk]),
            data={
                'payment_date': timezone.localdate(),
                'amount': '1000.00',
                'account': cash.pk,
                'method': 'Cash',
                'reference': 'BILL-REF',
                'notes': '',
            },
        )
        self.assertEqual(resp.status_code, 302)

        payment = BillPayment.objects.get(bill=bill)
        txn = Transaction.objects.get(bill_payment=payment)
        self.assertEqual(txn.debit, Decimal('1000.00'))
        self.assertEqual(txn.credit, 0)
        self.assertEqual(txn.account_id, cash.pk)
        self.assertEqual(txn.related_vendor_id, vendor.pk)
        self.assertEqual(txn.related_project_id, project.pk)
        self.assertEqual(txn.category, 'project_expense')

    def test_advance_allocation_reduces_invoice_outstanding(self):
        cash = Account.objects.create(name='Cash', account_type=Account.Type.CASH)
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='300-NVRT')
        invoice = Invoice.objects.create(
            project=project,
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate(),
            amount=Decimal('1000.00'),
            tax_percent=Decimal('0'),
            discount_percent=Decimal('0'),
            status=Invoice.Status.SENT,
        )
        advance = ClientAdvance.objects.create(
            project=project,
            client=client,
            received_date=timezone.localdate(),
            amount=Decimal('1000.00'),
            account=cash,
            recorded_by=self.user,
            received_by=self.user,
        )
        ClientAdvanceAllocation.objects.create(advance=advance, invoice=invoice, amount=Decimal('250.00'), allocated_by=self.user)

        invoice.refresh_from_db()
        self.assertEqual(invoice.advance_applied, Decimal('250.00'))
        self.assertEqual(invoice.outstanding, Decimal('750.00'))

    def test_recurring_run_creates_transactions(self):
        cash = Account.objects.create(name='Cash', account_type=Account.Type.CASH)
        today = timezone.localdate()
        rule = RecurringTransactionRule.objects.create(
            name='Rent',
            is_active=True,
            direction=RecurringTransactionRule.Direction.DEBIT,
            category=Transaction.Category.MISC,
            description='Office rent',
            amount=Decimal('500.00'),
            account=cash,
            day_of_month=1,
            next_run_date=today.replace(day=1),
        )
        resp = self.client.post(reverse('recurring_rule_run'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Transaction.objects.filter(recurring_rule=rule).exists())

    def test_expense_claim_payment_sets_paid_and_cashbook(self):
        cash = Account.objects.create(name='Cash', account_type=Account.Type.CASH)
        employee = User.objects.create_user(username='employee2', password=self.password, role=User.Roles.ARCHITECT)
        claim = ExpenseClaim.objects.create(
            employee=employee,
            expense_date=timezone.localdate(),
            amount=Decimal('200.00'),
            category='Travel',
            status=ExpenseClaim.Status.APPROVED,
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        resp = self.client.post(
            reverse('expense_claim_pay', args=[claim.pk]),
            data={
                'payment_date': timezone.localdate(),
                'amount': '200.00',
                'account': cash.pk,
                'method': 'Cash',
                'reference': 'CLM-1',
                'notes': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ExpenseClaim.Status.PAID)
        txn = Transaction.objects.get(expense_claim_payment__claim=claim)
        self.assertEqual(txn.category, Transaction.Category.REIMBURSEMENT)
        self.assertEqual(txn.debit, Decimal('200.00'))
        self.assertEqual(txn.account_id, cash.pk)


class PayrollTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'
        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.employee = User.objects.create_user(
            username='employee',
            password=self.password,
            role=User.Roles.ARCHITECT,
            monthly_salary=Decimal('25000.00'),
        )
        self.client.login(username='admin', password=self.password)

    def test_payroll_post_creates_salary_transaction(self):
        resp = self.client.post(
            reverse('payroll'),
            data={
                'date': timezone.localdate(),
                'related_person': self.employee.pk,
                'debit': '5000.00',
                'remarks': 'Demo salary',
            },
        )
        self.assertEqual(resp.status_code, 302)
        txn = Transaction.objects.get(category=Transaction.Category.SALARY, related_person=self.employee)
        self.assertEqual(txn.credit, 0)
        self.assertEqual(txn.debit, Decimal('5000.00'))
