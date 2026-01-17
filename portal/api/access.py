from __future__ import annotations

from django.db.models import Q

from portal.models import Project, Task, User
from portal.permissions import get_permissions_for_user


def can_view_all_tasks(user: User | None) -> bool:
    return bool(user and (user.is_superuser or getattr(user, 'role', None) == User.Roles.ADMIN))


def visible_tasks_for_user(user: User | None, queryset):
    if can_view_all_tasks(user):
        return queryset
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(assigned_to=user)


def can_view_all_projects(user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    perms = get_permissions_for_user(user)
    return bool(user.is_superuser or perms.get('finance') or perms.get('invoices'))


def visible_projects_for_user(user: User | None, queryset=None):
    qs = queryset or Project.objects.all()
    if can_view_all_projects(user):
        return qs
    if not user or not user.is_authenticated:
        return qs.none()
    task_project_ids = Task.objects.filter(assigned_to=user).values('project_id')
    return qs.filter(Q(project_manager=user) | Q(site_engineer=user) | Q(pk__in=task_project_ids))


def visible_site_visits_for_user(user: User | None, queryset):
    if can_view_all_projects(user):
        return queryset
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(
        Q(visited_by=user) | Q(project__project_manager=user) | Q(project__site_engineer=user)
    )


def visible_issues_for_user(user: User | None, queryset):
    if can_view_all_projects(user):
        return queryset
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(
        Q(raised_by=user) | Q(project__project_manager=user) | Q(project__site_engineer=user)
    )
