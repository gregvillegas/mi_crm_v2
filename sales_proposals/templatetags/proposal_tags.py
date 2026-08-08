from django import template

register = template.Library()


@register.filter
def dict_items(value):
    """
    Safely call .items() on a dict, avoiding Django's key-lookup priority.
    Usage: {% for key, val in mydict|dict_items %}
    """
    if isinstance(value, dict):
        return value.items()
    return []


@register.filter
def get_item(dictionary, key):
    """Get a specific key from a dict (useful when key is a variable or conflicts with methods)."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
