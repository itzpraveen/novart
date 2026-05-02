from decimal import Decimal
import os
import shutil
import tempfile
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
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
    FirmProfile,
    StaffActivity,
    Task,
    Transaction,
    Lead,
    PublicProcessStep,
    PublicProjectHighlight,
    PublicService,
    PublicSiteSettings,
    Vendor,
)
from .permissions import get_permissions_for_user

User = get_user_model()


def _tiny_gif(name='tiny.gif'):
    return SimpleUploadedFile(
        name,
        (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00'
            b'\x00\x00\x00\xff\xff\xff!\xf9\x04\x01'
            b'\x00\x00\x00\x00,\x00\x00\x00\x00\x01'
            b'\x00\x01\x00\x00\x02\x02D\x01\x00;'
        ),
        content_type='image/gif',
    )


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


class InvoiceNumberSeedTests(TestCase):
    def test_invoice_sequence_after_env_seeds_next_number(self):
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='530-NVRT')
        with patch.dict(
            os.environ,
            {'INVOICE_PREFIX': 'NVRT', 'INVOICE_SEQUENCE_AFTER': 'NVRT/530/584'},
            clear=False,
        ):
            invoice = Invoice.objects.create(
                project=project,
                invoice_date=timezone.localdate(),
                due_date=timezone.localdate(),
                amount=Decimal('1000.00'),
            )
        self.assertEqual(invoice.invoice_number, 'NVRT/530/585')

    def test_invoice_sequence_after_uses_max_of_firm_and_env(self):
        FirmProfile.objects.create(singleton=True, invoice_sequence_after=584)
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='530-NVRT')
        with patch.dict(os.environ, {'INVOICE_PREFIX': 'NVRT', 'INVOICE_SEQUENCE_AFTER': '1000'}, clear=False):
            invoice = Invoice.objects.create(
                project=project,
                invoice_date=timezone.localdate(),
                due_date=timezone.localdate(),
                amount=Decimal('1000.00'),
            )
        self.assertEqual(invoice.invoice_number, 'NVRT/530/1001')


class DashboardUpcomingTasksTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'
        self.user = User.objects.create_user(
            username='arch',
            password=self.password,
            role=User.Roles.ARCHITECT,
        )
        self.client.login(username='arch', password=self.password)

    def test_dashboard_shows_tasks_without_due_date(self):
        client = Client.objects.create(name='Test Client')
        project = Project.objects.create(client=client, name='Test Project', code='530-NVRT')
        Task.objects.create(
            project=project,
            title='No due date task',
            status=Task.Status.TODO,
            assigned_to=self.user,
        )

        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, 'No due date task')


@override_settings(
    ALLOWED_HOSTS=[
        'testserver',
        'localhost',
        '127.0.0.1',
        'novartarchitects.com',
        'www.novartarchitects.com',
        'erp.novartarchitects.com',
    ],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PUBLIC_SITE_HOSTS=['novartarchitects.com', 'www.novartarchitects.com', 'localhost', '127.0.0.1'],
    ERP_HOSTS=['erp.novartarchitects.com'],
    ERP_BASE_URL='https://erp.novartarchitects.com',
)
class PublicSiteRoutingTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'

    def test_public_host_root_renders_public_homepage(self):
        response = self.client.get('/', HTTP_HOST='novartarchitects.com')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public/home.html')
        self.assertContains(response, 'Architecture, interiors, planning, and project management')

    def test_erp_host_root_still_renders_dashboard(self):
        user = User.objects.create_user(
            username='erp-admin',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.client.force_login(user)

        response = self.client.get('/', HTTP_HOST='erp.novartarchitects.com')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/dashboard.html')

    def test_public_host_login_redirects_to_erp_host(self):
        response = self.client.get(reverse('login'), HTTP_HOST='novartarchitects.com')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://erp.novartarchitects.com/accounts/login/')


@override_settings(
    ALLOWED_HOSTS=[
        'testserver',
        'localhost',
        '127.0.0.1',
        'novartarchitects.com',
        'www.novartarchitects.com',
        'erp.novartarchitects.com',
    ],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PUBLIC_SITE_HOSTS=['novartarchitects.com', 'www.novartarchitects.com', 'localhost', '127.0.0.1'],
    ERP_HOSTS=['erp.novartarchitects.com'],
    ERP_BASE_URL='https://erp.novartarchitects.com',
)
class PublicSiteContentModelTests(TestCase):
    def _model(self, name):
        try:
            return apps.get_model('portal', name)
        except LookupError:
            self.fail(f'{name} model is missing')

    def test_default_public_site_content_is_seeded(self):
        PublicSiteSettings = self._model('PublicSiteSettings')
        PublicService = self._model('PublicService')
        PublicProcessStep = self._model('PublicProcessStep')
        PublicProjectHighlight = self._model('PublicProjectHighlight')

        site_settings = PublicSiteSettings.objects.get(singleton=True)

        self.assertEqual(site_settings.brand_name, 'Novart')
        self.assertGreaterEqual(PublicService.objects.count(), 4)
        self.assertGreaterEqual(PublicProcessStep.objects.count(), 4)
        self.assertGreaterEqual(PublicProjectHighlight.objects.count(), 3)

    def test_project_highlights_ship_with_known_fallback_art(self):
        PublicProjectHighlight = self._model('PublicProjectHighlight')
        valid_keys = {'courtyard-house', 'atelier-interior', 'horizon-masterplan'}

        art_keys = set(PublicProjectHighlight.objects.values_list('art_key', flat=True))

        self.assertTrue(art_keys)
        self.assertTrue(art_keys.issubset(valid_keys))


@override_settings(
    ALLOWED_HOSTS=[
        'testserver',
        'localhost',
        '127.0.0.1',
        'novartarchitects.com',
        'www.novartarchitects.com',
        'erp.novartarchitects.com',
    ],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PUBLIC_SITE_HOSTS=['novartarchitects.com', 'www.novartarchitects.com', 'localhost', '127.0.0.1'],
    ERP_HOSTS=['erp.novartarchitects.com'],
    ERP_BASE_URL='https://erp.novartarchitects.com',
)
class PublicHomepageRenderTests(TestCase):
    def test_public_homepage_renders_all_sections(self):
        response = self.client.get('/', HTTP_HOST='novartarchitects.com')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public/home.html')
        self.assertContains(response, 'Services')
        self.assertContains(response, 'Process')
        self.assertContains(response, 'Selected Work')
        self.assertContains(response, 'Studio')
        self.assertContains(response, 'Contact')

    def test_public_homepage_uses_fallback_artwork_when_uploads_are_missing(self):
        response = self.client.get('/', HTTP_HOST='novartarchitects.com')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/img/public/courtyard-house.svg')

    def test_public_homepage_falls_back_to_static_logo_when_uploaded_logo_is_missing(self):
        FirmProfile.objects.create(singleton=True, logo='firm/novart_logo.png')

        response = self.client.get('/', HTTP_HOST='novartarchitects.com')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/img/novart.png')
        self.assertNotContains(response, '/media/firm/novart_logo.png')


class WebsiteSettingsAccessTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'

    def test_admin_can_open_website_settings(self):
        user = User.objects.create_user(
            username='website-admin',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('website_settings'))

        self.assertEqual(response.status_code, 200)

    def test_non_admin_gets_forbidden_even_with_settings_permission(self):
        user = User.objects.create_user(
            username='website-architect',
            password=self.password,
            role=User.Roles.ARCHITECT,
        )
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'settings': True})
        self.client.force_login(user)

        response = self.client.get(reverse('website_settings'))

        self.assertEqual(response.status_code, 403)

    def test_admin_without_settings_module_redirects_to_dashboard(self):
        user = User.objects.create_user(
            username='locked-admin',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        RolePermission.objects.update_or_create(role=User.Roles.ADMIN, defaults={'settings': False})
        self.client.force_login(user)

        response = self.client.get(reverse('website_settings'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))


class WebsiteSettingsSaveTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media = tempfile.mkdtemp(prefix='website-settings-tests-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.password = 'test-pass-123'
        self.user = User.objects.create_user(
            username='website-admin-save',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.client.force_login(self.user)
        self.site = PublicSiteSettings.objects.get(singleton=True)
        self.site.services.all().delete()
        self.site.process_steps.all().delete()
        self.site.project_highlights.all().delete()
        self.service = PublicService.objects.create(site=self.site, title='Old Service', description='Old description', sort_order=0)
        self.process_step = PublicProcessStep.objects.create(site=self.site, step_label='01', title='Old Step', description='Old step description', sort_order=0)
        self.project = PublicProjectHighlight.objects.create(
            site=self.site,
            title='Old Project',
            project_type='Architecture',
            location='Old Location',
            description='Old project description',
            art_key='courtyard-house',
            sort_order=0,
        )
        self.profile, _ = FirmProfile.objects.get_or_create(singleton=True, defaults={'name': 'Novart Architects'})

    def test_post_updates_website_settings_and_related_content(self):
        response = self.client.post(
            reverse('website_settings'),
            data={
                'profile-logo': _tiny_gif('brand.gif'),
                'site-brand_name': 'Novart',
                'site-brand_suffix': 'Architects',
                'site-phone_display': '+91 98765 43210',
                'site-whatsapp_number': '919876543210',
                'site-email': 'hello@novartarchitects.com',
                'site-address': 'Calicut, Kerala',
                'site-hero_heading': 'Designed around how people live.',
                'site-hero_supporting_text': 'Architecture, interiors, planning, and project management in one clear process.',
                'site-hero_cta_phone_label': 'Call Novart',
                'site-hero_cta_whatsapp_label': 'WhatsApp Novart',
                'site-hero_art_key': 'atelier-interior',
                'site-hero_image_alt': 'Hero image',
                'site-hero_image': _tiny_gif('hero.gif'),
                'site-services_heading': 'What We Do',
                'site-services_intro': 'Tailored design services.',
                'site-process_heading': 'How We Work',
                'site-process_intro': 'From brief to handover.',
                'site-work_heading': 'Featured Projects',
                'site-work_intro': 'A selection of recent work.',
                'site-studio_heading': 'About the Studio',
                'site-studio_body': 'Sustainability and clarity guide every decision.',
                'site-studio_art_key': 'horizon-masterplan',
                'site-studio_image_alt': 'Studio image',
                'site-contact_heading': 'Start a Conversation',
                'site-contact_intro': 'Share your site or brief.',
                'site-meta_title': 'Novart Architects',
                'site-meta_description': 'Novart public site',
                'services-TOTAL_FORMS': '2',
                'services-INITIAL_FORMS': '1',
                'services-MIN_NUM_FORMS': '0',
                'services-MAX_NUM_FORMS': '1000',
                'services-0-id': str(self.service.id),
                'services-0-title': 'Architectural Design',
                'services-0-description': 'Homes, campuses, and workplaces.',
                'services-0-sort_order': '0',
                'services-1-id': '',
                'services-1-title': 'Interior Design',
                'services-1-description': 'Spatial detailing and atmosphere.',
                'services-1-sort_order': '1',
                'process_steps-TOTAL_FORMS': '2',
                'process_steps-INITIAL_FORMS': '1',
                'process_steps-MIN_NUM_FORMS': '0',
                'process_steps-MAX_NUM_FORMS': '1000',
                'process_steps-0-id': str(self.process_step.id),
                'process_steps-0-step_label': '01',
                'process_steps-0-title': 'Discover',
                'process_steps-0-description': 'We understand the brief and site.',
                'process_steps-0-sort_order': '0',
                'process_steps-1-id': '',
                'process_steps-1-step_label': '02',
                'process_steps-1-title': 'Develop',
                'process_steps-1-description': 'We refine design and delivery.',
                'process_steps-1-sort_order': '1',
                'projects-TOTAL_FORMS': '2',
                'projects-INITIAL_FORMS': '1',
                'projects-MIN_NUM_FORMS': '0',
                'projects-MAX_NUM_FORMS': '1000',
                'projects-0-id': str(self.project.id),
                'projects-0-title': 'Courtyard Residence',
                'projects-0-project_type': 'Architecture',
                'projects-0-location': 'Kerala',
                'projects-0-description': 'A shaded residence built around a planted court.',
                'projects-0-image': _tiny_gif('project.gif'),
                'projects-0-image_alt': 'Courtyard residence',
                'projects-0-image_secondary': _tiny_gif('project-detail.gif'),
                'projects-0-image_secondary_alt': 'Courtyard residence detail',
                'projects-0-image_tertiary_alt': 'Courtyard residence interior',
                'projects-0-art_key': 'courtyard-house',
                'projects-0-sort_order': '0',
                'projects-1-id': '',
                'projects-1-title': 'Atelier Apartment',
                'projects-1-project_type': 'Interiors',
                'projects-1-location': 'Kozhikode',
                'projects-1-description': 'Calm interiors with warm natural materials.',
                'projects-1-image_alt': 'Atelier apartment',
                'projects-1-art_key': 'atelier-interior',
                'projects-1-sort_order': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('website_settings'))

        self.site.refresh_from_db()
        self.profile.refresh_from_db()
        self.project.refresh_from_db()

        self.assertEqual(self.site.hero_heading, 'Designed around how people live.')
        self.assertEqual(self.site.services_heading, 'What We Do')
        self.assertEqual(self.site.contact_heading, 'Start a Conversation')
        self.assertTrue(self.profile.logo.name.startswith('firm/'))
        self.assertTrue(self.site.hero_image.name.startswith('public_site/'))
        self.assertEqual(self.site.services.count(), 2)
        self.assertEqual(self.site.process_steps.count(), 2)
        self.assertEqual(self.site.project_highlights.count(), 2)
        self.assertEqual(self.project.title, 'Courtyard Residence')
        self.assertTrue(self.project.image.name.startswith('public_site/'))
        self.assertTrue(self.project.image_secondary.name.startswith('public_site/'))
        self.assertEqual(self.project.image_secondary_alt, 'Courtyard residence detail')


class WebsiteSettingsRenderTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'
        self.admin = User.objects.create_user(
            username='website-admin-render',
            password=self.password,
            role=User.Roles.ADMIN,
        )
        self.architect = User.objects.create_user(
            username='website-architect-render',
            password=self.password,
            role=User.Roles.ARCHITECT,
        )

    def test_website_settings_page_renders_expected_sections(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('website_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Brand & Contact')
        self.assertContains(response, 'Hero')
        self.assertContains(response, 'Selected Work')
        self.assertContains(response, 'Second project image')
        self.assertContains(response, 'SEO')

    def test_admin_navigation_contains_website_settings_link(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('website_settings'))

    def test_non_admin_navigation_does_not_show_website_settings_link(self):
        self.client.force_login(self.architect)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('website_settings'))
