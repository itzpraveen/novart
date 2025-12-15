from __future__ import annotations

import datetime as dt
from decimal import Decimal

from .models import RecurringTransactionRule, Transaction, User


def add_month(base: dt.date, months: int) -> dt.date:
    month = base.month - 1 + months
    year = base.year + month // 12
    month = month % 12 + 1
    day = min(base.day, 28)
    return dt.date(year, month, day)


def generate_recurring_transactions(*, today: dt.date, actor: User | None = None) -> int:
    created_count = 0
    rules = RecurringTransactionRule.objects.filter(is_active=True, next_run_date__lte=today).select_related(
        'account', 'related_project', 'related_vendor'
    )
    for rule in rules:
        run_date = rule.next_run_date
        while run_date and run_date <= today:
            txn, created = Transaction.objects.get_or_create(
                recurring_rule=rule,
                date=run_date,
                defaults={
                    'description': (rule.description or rule.name)[:255],
                    'category': rule.category,
                    'debit': rule.amount if rule.direction == RecurringTransactionRule.Direction.DEBIT else Decimal('0'),
                    'credit': rule.amount if rule.direction == RecurringTransactionRule.Direction.CREDIT else Decimal('0'),
                    'account': rule.account,
                    'related_project': rule.related_project,
                    'related_vendor': rule.related_vendor,
                    'recorded_by': actor,
                    'remarks': f"Recurring: {rule.name}"[:255],
                },
            )
            if created:
                created_count += 1
            run_date = add_month(run_date.replace(day=1), 1).replace(day=min(rule.day_of_month or 1, 28))
        if run_date and run_date != rule.next_run_date:
            rule.next_run_date = run_date
            rule.save(update_fields=['next_run_date'])
    return created_count

