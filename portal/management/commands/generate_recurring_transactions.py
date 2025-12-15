from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.finance_utils import generate_recurring_transactions


class Command(BaseCommand):
    help = "Generate due recurring transactions (run daily via cron/systemd)."

    def handle(self, *args, **options):
        created = generate_recurring_transactions(today=timezone.localdate(), actor=None)
        self.stdout.write(self.style.SUCCESS(f"Generated {created} recurring transaction(s)."))

