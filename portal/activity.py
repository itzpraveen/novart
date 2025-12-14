from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from portal.models import StaffActivity

User = get_user_model()


def log_staff_activity(
    *,
    actor: Optional[User],
    category: str,
    message: str,
    related_url: str = '',
) -> None:
    if not actor or not getattr(actor, 'is_authenticated', False):
        return
    StaffActivity.objects.create(
        actor=actor,
        category=category,
        message=(message or '')[:500],
        related_url=(related_url or '')[:255],
    )

