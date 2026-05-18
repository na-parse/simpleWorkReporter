'''Display formatting helpers.'''

from __future__ import annotations

import re

from markupsafe import Markup, escape

_NEWLINE_RUN = re.compile(r'(?:\r\n|\r|\n)+')


def description_html(description: str) -> Markup:
    '''Render description text with compact line breaks.'''
    escaped = escape(description)
    compact = _NEWLINE_RUN.sub('<br />', str(escaped))
    return Markup(compact)
