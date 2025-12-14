from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import Payment, ReminderSetting, Transaction


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
            'debit': 0,
            'credit': instance.amount,
            'related_project': project if project else None,
            'related_client': client,
            'related_person': instance.received_by if instance.received_by_id else None,
            'recorded_by': instance.recorded_by if instance.recorded_by_id else None,
            'remarks': remarks,
        },
    )
