from functools import wraps

from django.http import HttpResponseForbidden


def role_required(*roles):
    """
    Enforce that request.user.role is within allowed roles.
    Superusers are always allowed.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user:
                return HttpResponseForbidden("You do not have permission to perform this action.")
            role_check = getattr(user, "has_any_role", None)
            has_role = False
            if callable(role_check):
                has_role = role_check(*roles)
            elif getattr(user, "role", None) in roles:
                has_role = True
            if user.is_superuser or has_role:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to perform this action.")

        return _wrapped

    return decorator
