from __future__ import annotations

from typing import Dict

from django.contrib import messages
from django.http import HttpRequest

from .models import RolePermission, User

MODULE_KEYS = [
    'clients',
    'leads',
    'projects',
    'site_visits',
    'finance',
    'invoices',
    'docs',
    'team',
    'users',
    'settings',
]

MODULE_LABELS: Dict[str, str] = {
    'clients': 'Clients',
    'leads': 'Leads',
    'projects': 'Projects',
    'site_visits': 'Site visits',
    'finance': 'Finance',
    'invoices': 'Invoices',
    'docs': 'Documents',
    'team': 'Team',
    'users': 'Users',
    'settings': 'Settings',
}

DEFAULT_ROLE_PERMS: Dict[str, Dict[str, bool]] = {
    User.Roles.ADMIN: {key: True for key in MODULE_KEYS},
    User.Roles.ARCHITECT: {
        'clients': True,
        'leads': True,
        'projects': True,
        'site_visits': True,
        'docs': True,
        'team': True,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
    User.Roles.SITE_ENGINEER: {
        'clients': False,
        'leads': False,
        'projects': True,
        'site_visits': True,
        'docs': False,
        'team': False,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
    User.Roles.FINANCE: {
        'clients': True,
        'leads': False,
        'projects': True,
        'site_visits': False,
        'docs': True,
        'team': False,
        'finance': True,
        'invoices': True,
        'users': False,
        'settings': False,
    },
    User.Roles.ACCOUNTANT: {
        'clients': True,
        'leads': False,
        'projects': True,
        'site_visits': False,
        'docs': True,
        'team': False,
        'finance': True,
        'invoices': True,
        'users': False,
        'settings': False,
    },
    User.Roles.PROJECT_MANAGER: {
        'clients': True,
        'leads': True,
        'projects': True,
        'site_visits': True,
        'docs': True,
        'team': True,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
    User.Roles.DESIGNER: {
        'clients': False,
        'leads': False,
        'projects': True,
        'site_visits': False,
        'docs': True,
        'team': False,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
    User.Roles.DRAUGHTSMAN: {
        'clients': False,
        'leads': False,
        'projects': True,
        'site_visits': False,
        'docs': True,
        'team': False,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
    User.Roles.VIEWER: {
        'clients': True,
        'leads': True,
        'projects': True,
        'site_visits': True,
        'docs': False,
        'team': False,
        'finance': False,
        'invoices': False,
        'users': False,
        'settings': False,
    },
}


def ensure_role_permissions() -> None:
    for role, defaults in DEFAULT_ROLE_PERMS.items():
        RolePermission.objects.get_or_create(role=role, defaults=defaults)


def get_permissions_for_user(user: User) -> Dict[str, bool]:
    if not user.is_authenticated:
        return {key: False for key in MODULE_KEYS}
    if user.is_superuser:
        return {key: True for key in MODULE_KEYS}
    ensure_role_permissions()
    rp = RolePermission.objects.filter(role=user.role).first()
    if not rp:
        return {key: False for key in MODULE_KEYS}
    perms = {key: bool(getattr(rp, key, False)) for key in MODULE_KEYS}
    if user.role == User.Roles.VIEWER:
        perms['docs'] = False
    return perms


def guard_module(request: HttpRequest, module: str) -> bool:
    if request.user.is_superuser:
        return True
    perms = get_permissions_for_user(request.user)
    allowed = perms.get(module, False)
    if not allowed:
        messages.error(request, "You don't have access to this area.")
    return allowed
