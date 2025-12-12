from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import Payment, ReminderSetting


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
