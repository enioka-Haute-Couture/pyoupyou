from django import template
from django.utils.safestring import mark_safe

from markdown_it import MarkdownIt

register = template.Library()
md = MarkdownIt()


@register.filter(is_safe=True)
def commonmark(value):
    return mark_safe(md.render(value))
