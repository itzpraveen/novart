from datetime import date, timedelta

from django.core.management.base import BaseCommand

from portal.models import (
    Account,
    Bill,
    BillPayment,
    Client,
    ClientAdvance,
    ClientAdvanceAllocation,
    Vendor,
    Invoice,
    Lead,
    Payment,
    Project,
    ProjectStageHistory,
    RecurringTransactionRule,
    ReminderSetting,
    SiteVisit,
    Task,
    Transaction,
    User,
)


class Command(BaseCommand):
    help = "Seed the database with sample data for demos."

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("Create at least one user before seeding."))
            return
        if getattr(user, 'monthly_salary', 0) in (None, 0):
            user.monthly_salary = 35000
            user.save(update_fields=['monthly_salary'])

        cash_account, _ = Account.objects.get_or_create(
            name='Cash',
            defaults={'account_type': Account.Type.CASH, 'opening_balance': 0},
        )

        client, _ = Client.objects.get_or_create(
            name="Mathew Residence",
            defaults={'phone': '98950 00000', 'city': 'Kochi', 'state': 'Kerala'},
        )
        lead, _ = Lead.objects.get_or_create(
            client=client,
            title="Mathew Residence",
            defaults={'lead_source': 'Referral', 'status': Lead.Status.WON, 'created_by': user},
        )
        project, created = Project.objects.get_or_create(
            code="MR-01",
            defaults={
                'client': client,
                'lead': lead,
                'name': "Mathew Residence",
                'project_type': Project.ProjectType.RESIDENTIAL,
                'location': 'Kakkanad',
                'built_up_area': 3200,
                'start_date': date.today() - timedelta(days=30),
                'expected_handover': date.today() + timedelta(days=120),
                'project_manager': user,
            },
        )
        if created:
            ProjectStageHistory.objects.create(project=project, stage=project.current_stage, changed_by=user)

        Task.objects.get_or_create(
            project=project,
            title="Finalize concept drawings",
            defaults={'assigned_to': user, 'due_date': date.today() + timedelta(days=7)},
        )

        SiteVisit.objects.get_or_create(
            project=project,
            visit_date=date.today() - timedelta(days=3),
            defaults={'visited_by': user, 'notes': 'Excavation review', 'expenses': 850},
        )

        invoice, _ = Invoice.objects.get_or_create(
            project=project,
            invoice_number="MR-INV-001",
            defaults={'invoice_date': date.today(), 'due_date': date.today() + timedelta(days=15), 'amount': 150000},
        )
        Payment.objects.get_or_create(
            invoice=invoice,
            payment_date=date.today(),
            defaults={'amount': 50000, 'received_by': user, 'method': 'Bank Transfer', 'account': cash_account},
        )

        Transaction.objects.get_or_create(
            description="Site soil testing",
            date=date.today() - timedelta(days=10),
            defaults={
                'debit': 12000,
                'related_project': project,
                'category': Transaction.Category.PROJECT_EXPENSE,
                'account': cash_account,
            },
        )

        vendor, _ = Vendor.objects.get_or_create(name='Geo Labs', defaults={'phone': '98950 11111'})
        bill, _ = Bill.objects.get_or_create(
            vendor=vendor,
            bill_number='GL-001',
            bill_date=date.today() - timedelta(days=12),
            defaults={
                'project': project,
                'amount': 12000,
                'category': 'project_expense',
                'created_by': user,
            },
        )
        BillPayment.objects.get_or_create(
            bill=bill,
            payment_date=date.today() - timedelta(days=11),
            defaults={'amount': 12000, 'account': cash_account, 'method': 'Cash', 'recorded_by': user},
        )

        advance, _ = ClientAdvance.objects.get_or_create(
            project=project,
            client=client,
            received_date=date.today() - timedelta(days=20),
            defaults={'amount': 25000, 'account': cash_account, 'method': 'Cash', 'received_by': user, 'recorded_by': user},
        )
        ClientAdvanceAllocation.objects.get_or_create(
            advance=advance,
            invoice=invoice,
            defaults={'amount': 10000, 'allocated_by': user},
        )

        RecurringTransactionRule.objects.get_or_create(
            name='Office Rent',
            defaults={
                'is_active': True,
                'direction': RecurringTransactionRule.Direction.DEBIT,
                'category': Transaction.Category.MISC,
                'description': 'Office rent',
                'amount': 25000,
                'account': cash_account,
                'day_of_month': 5,
                'next_run_date': date.today().replace(day=5),
            },
        )

        for category in ReminderSetting.Category.values:
            ReminderSetting.objects.get_or_create(category=category)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
