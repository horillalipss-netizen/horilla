"""
Template tags for the Knowledge Base ("База знань").
"""

from django import template
from django.utils.html import urlize
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="kb_richtext")
def kb_richtext(value):
    """
    Render plain text with clickable links (opening in a new tab) and
    preserved line breaks. Input is autoescaped by urlize, so the result
    is safe to mark as HTML.
    """
    if not value:
        return ""
    html = urlize(value, autoescape=True)
    html = html.replace("<a ", '<a target="_blank" rel="noopener noreferrer" ')
    html = html.replace("\r\n", "\n").replace("\n", "<br>")
    return mark_safe(html)
