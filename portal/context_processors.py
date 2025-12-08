def notifications(request):
    if request.user.is_authenticated:
        return {'unread_notifications': request.user.notifications.filter(is_read=False).count()}
    return {}


def module_perms(request):
    from .permissions import ensure_role_permissions, get_permissions_for_user

    ensure_role_permissions()
    return {'module_perms': get_permissions_for_user(request.user)}
