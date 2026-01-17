from __future__ import annotations

from typing import Iterable

from rest_framework.permissions import BasePermission

from portal.permissions import get_permissions_for_user


class ModulePermission(BasePermission):
    module: str | None = None

    def has_permission(self, request, view) -> bool:
        module = getattr(view, 'module_permission', None) or self.module
        if not module:
            return True
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        perms = get_permissions_for_user(user)
        return bool(perms.get(module, False))


class RolePermission(BasePermission):
    allowed_roles: Iterable[str] | None = None

    def has_permission(self, request, view) -> bool:
        roles = getattr(view, 'allowed_roles', None) or self.allowed_roles
        if not roles:
            return True
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        has_any = getattr(user, 'has_any_role', None)
        if callable(has_any):
            return has_any(*roles)
        return getattr(user, 'role', None) in roles
