"""
This file provides a template filter that renders student notes into a formatted HTML.
"""

import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

# Let HTML find this file
register = template.Library()

# Regex to recognise bullet points, lists, and bold text
_BULLET = re.compile(r"^(?:[-*•])\s+(.+)$")
_ORDERED = re.compile(r"^\d+[.)]\s+(.+)$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


# A function to escape text (turn special symbols into normal text) and apply bold markup
def _inline(text):
    escaped = conditional_escape(text)
    return _BOLD.sub(r"<strong>\1</strong>", escaped)


# A function to properly render notes into formatted HTML
@register.filter(is_safe=True)
def notes_markup(value):

    # Return empty string if there is no value
    if not value:
        return ""

    # The place to store the formatted blocks
    blocks = []

    # Split the input into lines, then process them one by one
    lines = str(value).strip().splitlines()
    index = 0
    while index < len(lines):

        # Clean empty lines
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        # Check if the line is a bullet point or a numbered list
        match = _BULLET.match(line)
        ordered = _ORDERED.match(line)
        if match or ordered:

            # Determine the tag to be attached
            tag = "ul" if match else "ol"
            items = []
            pattern = _BULLET if match else _ORDERED

            # Loop through each following lines to find all items in the list
            while index < len(lines):
                item = pattern.match(lines[index].strip())
                if not item:
                    break
                items.append(f"<li data-katex-text>{_inline(item.group(1))}</li>")
                index += 1

            # Once all items are found, wrap with an ending tag and add to the blocks
            blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        # If the line is a normal paragraph
        paragraph = [line]
        index += 1

        # Loop through the following lines to find text belonging to the paragraph
        while index < len(lines):
            next_line = lines[index].strip()
            if not next_line or _BULLET.match(next_line) or _ORDERED.match(next_line):
                break
            paragraph.append(next_line)
            index += 1

        # Only close when the text is no more paragraph type
        blocks.append(f"<p data-katex-text>{_inline(' '.join(paragraph))}</p>")

    # Lastly, return the notes rendered correctly as HTML
    return mark_safe("\n".join(blocks))
