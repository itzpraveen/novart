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
            if user and (user.is_superuser or getattr(user, "role", None) in roles):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to perform this action.")

        return _wrapped

    return decorator
