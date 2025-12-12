from __future__ import annotations

from typing import Iterable, Optional, Set

from django.urls import reverse

from portal.models import Notification, Task, User
from portal.notifications.whatsapp import send_text as send_whatsapp_text


def notify_task_change(
    task: Task,
    *,
    actor: Optional[User] = None,
    message: str,
    category: str = 'task_update',
    recipients: Optional[Iterable[User]] = None,
) -> None:
    """Send in-app + WhatsApp notifications for task changes."""
    recips: Set[User] = set(recipients or [])
    if task.assigned_to_id:
        recips.add(task.assigned_to)
    if task.project and task.project.project_manager_id:
        recips.add(task.project.project_manager)
    if hasattr(task, 'watchers'):
        recips.update(task.watchers.all())
    if actor:
        recips.discard(actor)

    if not recips:
        return

    url = reverse('task_detail', args=[task.pk])
    for user in recips:
        Notification.objects.create(user=user, message=message[:500], category=category, related_url=url)
        if getattr(user, 'phone', None):
            send_whatsapp_text(user.phone, message)

