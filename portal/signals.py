from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import ReminderSetting


@receiver(post_migrate)
def create_default_reminders(sender, **kwargs):
    if sender.name != 'portal':
        return
    for category in ReminderSetting.Category.values:
        ReminderSetting.objects.get_or_create(category=category)
