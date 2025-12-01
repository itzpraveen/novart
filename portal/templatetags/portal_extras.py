from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rupee(value):
    try:
        amount = Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{amount:,.2f}"
    return f"₹ {formatted}"


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
