"""
Shared utilities used across BMS Newsletter agents.
"""

import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Newsletter parsing
# ---------------------------------------------------------------------------

def extract_latest_newsletter(archive: str) -> tuple[str, str]:
    """Return (subject, newsletter_text) for the most recent entry in newsletter_archive.md.

    Entries are delimited by '## YYYY-MM-DD — ...' headers. We find the last one
    and return everything after the metadata line as the newsletter body.
    This correctly handles '---' horizontal rules within the newsletter content.
    """
    # Find all entry headers and their positions
    headers = list(re.finditer(r"^## (\d{4}-\d{2}-\d{2}) — (.+)$", archive, re.MULTILINE))
    if not headers:
        return "Newsletter", ""

    last = headers[-1]
    title = last.group(2).strip()
    # Extract everything after this header
    body = archive[last.end():]
    # Strip the metadata line (_Erstellt: ..._)
    lines = body.splitlines()
    content_lines = [
        l for l in lines
        if not l.startswith("_Erstellt:")
    ]
    return title, "\n".join(content_lines).strip()


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

class _StripHTML(HTMLParser):
    _SKIP = {"script", "style", "nav", "header", "footer", "aside", "noscript"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(html: str) -> str:
    """Strip HTML tags and return readable text. Skips script/style/nav content."""
    parser = _StripHTML()
    parser.feed(html)
    return parser.get_text()
