from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import BillPayment, ClientAdvance, ClientAdvanceAllocation, ExpenseClaimPayment, Payment, ReminderSetting, Transaction


@receiver(post_migrate)
def create_default_reminders(sender, **kwargs):
    if sender.name != 'portal':
        return
    for category in ReminderSetting.Category.values:
        ReminderSetting.objects.get_or_create(category=category)


@receiver(post_migrate)
def create_default_role_permissions(sender, **kwargs):
    if sender.name != 'portal':
        return
    from .permissions import ensure_role_permissions

    ensure_role_permissions()


@receiver(post_save, sender=Payment)
def refresh_invoice_status_on_payment(sender, instance: Payment, **kwargs):
    """Keep invoice status in sync when payments are recorded outside views."""
    if instance.invoice_id:
        instance.invoice.refresh_status()


@receiver(post_save, sender=Payment)
def sync_cashbook_entry_on_payment(sender, instance: Payment, created: bool, **kwargs):
    """Auto-create/update cashbook credit entry for every payment received."""
    if kwargs.get('raw'):
        return
    if not instance.invoice_id:
        return

    invoice = instance.invoice
    project = getattr(invoice, 'project', None)
    client = None
    if project and getattr(project, 'client_id', None):
        client = project.client
    elif getattr(invoice, 'lead_id', None) and getattr(invoice.lead, 'client_id', None):
        client = invoice.lead.client

    description = f"Payment received · Invoice {invoice.display_invoice_number}"
    if project and getattr(project, 'code', None):
        description = f"Payment received · {project.code} · Invoice {invoice.display_invoice_number}"

    remarks_parts = []
    if instance.method:
        remarks_parts.append(f"Method: {instance.method}")
    if instance.reference:
        remarks_parts.append(f"Ref: {instance.reference}")
    remarks = " | ".join(remarks_parts)

    Transaction.objects.update_or_create(
        payment=instance,
        defaults={
            'date': instance.payment_date,
            'description': description[:255],
            'category': Transaction.Category.CLIENT_PAYMENT,
            'debit': 0,
            'credit': instance.amount,
            'account': instance.account if getattr(instance, 'account_id', None) else None,
            'related_project': project if project else None,
            'related_client': client,
            'related_person': instance.received_by if instance.received_by_id else None,
            'recorded_by': instance.recorded_by if instance.recorded_by_id else None,
            'remarks': remarks,
        },
    )


@receiver(post_save, sender=BillPayment)
def sync_cashbook_entry_on_bill_payment(sender, instance: BillPayment, **kwargs):
    if kwargs.get('raw'):
        return
    if not instance.bill_id:
        return

    bill = instance.bill
    vendor = bill.vendor
    project = bill.project
    client = project.client if project and getattr(project, 'client_id', None) else None

    description = f"Vendor payment · {vendor.name}"
    if bill.bill_number:
        description = f"{description} · {bill.bill_number}"
    if project and getattr(project, 'code', None):
        description = f"{description} · {project.code}"

    remarks_parts = []
    if instance.method:
        remarks_parts.append(f"Method: {instance.method}")
    if instance.reference:
        remarks_parts.append(f"Ref: {instance.reference}")
    remarks = " | ".join(remarks_parts)

    Transaction.objects.update_or_create(
        bill_payment=instance,
        defaults={
            'date': instance.payment_date,
            'description': description[:255],
            'category': bill.category or Transaction.Category.OTHER_EXPENSE,
            'debit': instance.amount,
            'credit': 0,
            'account': instance.account if getattr(instance, 'account_id', None) else None,
            'related_project': project,
            'related_client': client,
            'related_vendor': vendor,
            'recorded_by': instance.recorded_by if instance.recorded_by_id else None,
            'remarks': remarks,
        },
    )
    bill.refresh_status()


@receiver(post_save, sender=ClientAdvance)
def sync_cashbook_entry_on_client_advance(sender, instance: ClientAdvance, **kwargs):
    if kwargs.get('raw'):
        return

    project = instance.project
    client = instance.client or (project.client if project and getattr(project, 'client_id', None) else None)

    description = "Advance received"
    if project and getattr(project, 'code', None):
        description = f"{description} · {project.code}"
    elif client:
        description = f"{description} · {client.name}"

    remarks_parts = []
    if instance.method:
        remarks_parts.append(f"Method: {instance.method}")
    if instance.reference:
        remarks_parts.append(f"Ref: {instance.reference}")
    remarks = " | ".join(remarks_parts)

    Transaction.objects.update_or_create(
        client_advance=instance,
        defaults={
            'date': instance.received_date,
            'description': description[:255],
            'category': Transaction.Category.CLIENT_ADVANCE,
            'debit': 0,
            'credit': instance.amount,
            'account': instance.account if getattr(instance, 'account_id', None) else None,
            'related_project': project,
            'related_client': client,
            'related_person': instance.received_by if instance.received_by_id else None,
            'recorded_by': instance.recorded_by if instance.recorded_by_id else None,
            'remarks': remarks,
        },
    )


@receiver(post_save, sender=ClientAdvanceAllocation)
def refresh_invoice_status_on_advance_allocation(sender, instance: ClientAdvanceAllocation, **kwargs):
    if kwargs.get('raw'):
        return
    if instance.invoice_id:
        instance.invoice.refresh_status()


@receiver(post_save, sender=ExpenseClaimPayment)
def sync_cashbook_entry_on_expense_claim_payment(sender, instance: ExpenseClaimPayment, **kwargs):
    if kwargs.get('raw'):
        return
    if not instance.claim_id:
        return

    claim = instance.claim
    employee = claim.employee
    project = claim.project
    client = project.client if project and getattr(project, 'client_id', None) else None

    description = f"Reimbursement · {employee.get_full_name() or employee.username}"
    if project and getattr(project, 'code', None):
        description = f"{description} · {project.code}"

    remarks_parts = []
    if instance.method:
        remarks_parts.append(f"Method: {instance.method}")
    if instance.reference:
        remarks_parts.append(f"Ref: {instance.reference}")
    remarks = " | ".join(remarks_parts)

    Transaction.objects.update_or_create(
        expense_claim_payment=instance,
        defaults={
            'date': instance.payment_date,
            'description': description[:255],
            'category': Transaction.Category.REIMBURSEMENT,
            'debit': instance.amount,
            'credit': 0,
            'account': instance.account if getattr(instance, 'account_id', None) else None,
            'related_project': project,
            'related_client': client,
            'related_person': employee,
            'recorded_by': instance.recorded_by if instance.recorded_by_id else None,
            'remarks': remarks,
        },
    )

    if claim.status != claim.Status.PAID:
        claim.status = claim.Status.PAID
        claim.save(update_fields=['status'])
