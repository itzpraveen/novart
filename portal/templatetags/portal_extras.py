from django import template

register = template.Library()


@register.filter
def rupee(value):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return value
    return f"₹{amount:,.2f}"


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
