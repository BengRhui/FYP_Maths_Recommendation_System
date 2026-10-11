"""
This file provides a template tag that allows the website to load modified CSS without hard refresh.
"""

from django import template
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from pathlib import Path

# Let the HTML discover this tag
register = template.Library()


# A function to support cache busting
@register.simple_tag
def static_v(path):

    # Obtain the URL of the static file and check if it exists
    url = staticfiles_storage.url(path)
    found = finders.find(path)

    # If it is not found, do nothing
    if not found:
        return url

    # If it is found, modify the URL to include a timestamp for cache busting
    try:
        stamp = int(Path(found).stat().st_mtime)
    except OSError:
        return url
    return f"{url}{'&' if '?' in url else '?'}v={stamp}"
