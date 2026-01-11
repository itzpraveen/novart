from decimal import Decimal, InvalidOperation
from django.utils.safestring import mark_safe
from django.urls import reverse

from django import template

register = template.Library()

def _qs_set(request, **kwargs) -> str:
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else ""


@register.filter
def rupee(value):
    try:
        amount = Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{amount:,.2f}"
    return mark_safe(f"Rs. {formatted}")


@register.filter
def status_badge(status):
    colors = {'todo': 'secondary', 'in_progress': 'info', 'done': 'success', 'open': 'danger', 'resolved': 'success'}
    return colors.get(status, 'secondary')


@register.filter
def add_class(field, css):
    return field.as_widget(attrs={**field.field.widget.attrs, 'class': f"{field.field.widget.attrs.get('class', '')} {css}".strip()})


@register.filter
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'):
        return dictionary.get(key, [])
    return []


@register.filter
def make_url(pk, view_name: str) -> str:
    """Build a URL for the given view using the primary key as the positional arg."""
    if pk is None:
        return ""
    try:
        return reverse(view_name, args=[pk])
    except Exception:
        return ""


@register.simple_tag
def qs_set(request, **kwargs) -> str:
    return _qs_set(request, **kwargs)


@register.simple_tag
def sort_url(request, field: str) -> str:
    current = (request.GET.get('ordering', '') or '').strip()
    if current.lstrip('-') == field:
        next_value = field if current.startswith('-') else f"-{field}"
    else:
        next_value = field
    return _qs_set(request, ordering=next_value)


@register.simple_tag
def sort_indicator(request, field: str) -> str:
    current = (request.GET.get('ordering', '') or '').strip()
    if current.lstrip('-') != field:
        return mark_safe('<span class="sort-indicator" aria-hidden="true">↕</span>')
    arrow = '▼' if current.startswith('-') else '▲'
    return mark_safe(f'<span class="sort-indicator active" aria-hidden="true">{arrow}</span>')
