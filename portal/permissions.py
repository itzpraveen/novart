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

BASE_ROLE_PERMS: Dict[str, Dict[str, bool]] = {
    User.Roles.ADMIN: {key: True for key in MODULE_KEYS},
    User.Roles.MANAGING_DIRECTOR: {
        'clients': True,
        'leads': True,
        'projects': True,
        'site_visits': True,
        'docs': True,
        'team': True,
        'finance': True,
        'invoices': False,
        'users': False,
        'settings': False,
    },
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


ROLE_ALIASES: Dict[str, str] = {
    # Architect variants
    User.Roles.SENIOR_ARCHITECT: User.Roles.ARCHITECT,
    User.Roles.JUNIOR_ARCHITECT: User.Roles.ARCHITECT,
    # Site engineer variants
    User.Roles.SENIOR_CIVIL_ENGINEER: User.Roles.SITE_ENGINEER,
    User.Roles.JUNIOR_CIVIL_ENGINEER: User.Roles.SITE_ENGINEER,
    # Designer / drafting variants
    User.Roles.SENIOR_INTERIOR_DESIGNER: User.Roles.DESIGNER,
    User.Roles.JUNIOR_INTERIOR_DESIGNER: User.Roles.DESIGNER,
    User.Roles.VISUALISER_3D: User.Roles.DESIGNER,
    # Finance variants
    User.Roles.ACCOUNTANT: User.Roles.FINANCE,
}


def _default_perms_for_role(role: str) -> Dict[str, bool] | None:
    """Return default module permissions for a role, honoring aliases."""
    if role in BASE_ROLE_PERMS:
        return BASE_ROLE_PERMS[role]
    base_role = ROLE_ALIASES.get(role)
    if base_role and base_role in BASE_ROLE_PERMS:
        return BASE_ROLE_PERMS[base_role]
    return None


def ensure_role_permissions() -> None:
    for role in User.Roles.values:
        defaults = _default_perms_for_role(role)
        if defaults is None:
            continue
        RolePermission.objects.get_or_create(role=role, defaults=defaults)


def get_permissions_for_user(user: User) -> Dict[str, bool]:
    if not user.is_authenticated:
        return {key: False for key in MODULE_KEYS}
    if user.is_superuser:
        return {key: True for key in MODULE_KEYS}
    rp = RolePermission.objects.filter(role=user.role).first()
    if not rp:
        base_role = ROLE_ALIASES.get(user.role)
        if base_role:
            rp = RolePermission.objects.filter(role=base_role).first()
        if not rp:
            defaults = _default_perms_for_role(user.role)
            if defaults is None:
                return {key: False for key in MODULE_KEYS}
            return dict(defaults)
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
