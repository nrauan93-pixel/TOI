"""Небольшие помощники для шаблонов: иконки Lucide и формат цен в тенге."""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, size=20, css_class=""):
    """{% icon "heart" 18 %} → SVG-иконка из static/icons/lucide.svg."""
    return format_html(
        '<svg class="icon {}" width="{}" height="{}" aria-hidden="true" focusable="false">'
        '<use href="{}#{}"></use></svg>',
        css_class, size, size, static("icons/lucide.svg"), name,
    )


@register.filter
def tenge(value):
    """150000 → «150 000 ₸» (неразрывные пробелы, как принято в Казахстане)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return value
    return f"{number:,}".replace(",", " ") + " ₸"


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    """Ссылка на ту же страницу с изменёнными GET-параметрами (для пагинации)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return params.urlencode()


@register.filter
def ru_plural(value, forms):
    """3|ru_plural:"отзыв,отзыва,отзывов" → «3 отзыва» (русские окончания)."""
    try:
        number = abs(int(value))
    except (TypeError, ValueError):
        return value
    one, few, many = forms.split(",")
    if number % 10 == 1 and number % 100 != 11:
        word = one
    elif 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        word = few
    else:
        word = many
    return f"{value} {word}"
