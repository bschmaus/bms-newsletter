"""
Shared utilities used across BMS Newsletter agents.
"""

import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Newsletter parsing
# ---------------------------------------------------------------------------

def extract_latest_newsletter(archive: str) -> tuple[str, str]:
    """Return (subject, newsletter_text) for the most recent entry in newsletter_archive.md."""
    blocks = re.split(r"\n---\n", archive)
    for block in reversed(blocks):
        block = block.strip()
        if not block or block.startswith("# Newsletter"):
            continue
        title_match = re.search(r"^## \d{4}-\d{2}-\d{2} — (.+)$", block, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Newsletter"
        lines = [
            l for l in block.splitlines()
            if not l.startswith("## ") and not l.startswith("_Erstellt:")
        ]
        return title, "\n".join(lines).strip()
    return "Newsletter", ""


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
