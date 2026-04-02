"""
Shared utilities used across BMS Newsletter agents.
"""

import re
from html.parser import HTMLParser

import anthropic


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


# ---------------------------------------------------------------------------
# BMS article link extraction
# ---------------------------------------------------------------------------

_BMS_BASE = "https://bilinguale-montessori-schule.de"
_BMS_NEWS_PREFIX = "/de/aktuelles/news-de/"


class _BMSArticleExtractor(HTMLParser):
    """Extract article cards from the BMS news overview page.

    BMS uses Joomla with this card structure:
      <div class="blog-item">
        <h2>Article Title</h2>
        <dd class="create"><time>Erstellt: ...</time></dd>
        <p>Snippet text...</p>
        <a href="/de/aktuelles/news-de/slug">Weiterlesen</a>
      </div>

    We collect the h2 title, snippet text, and URL from Weiterlesen links,
    then merge them per article card.
    """

    def __init__(self):
        super().__init__()
        self.articles: list[dict] = []
        self._in_h2 = False
        self._h2_texts: list[str] = []
        self._current_title = ""
        self._current_snippet_parts: list[str] = []
        self._skip_depth = 0
        self._SKIP = {"script", "style", "nav", "header", "footer", "noscript"}
        self._in_p = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        if tag == "h2":
            self._in_h2 = True
            self._h2_texts = []
        elif tag == "p":
            self._in_p = True
        elif tag == "a":
            href = dict(attrs).get("href", "")
            if (href.startswith(_BMS_NEWS_PREFIX)
                    and href != _BMS_NEWS_PREFIX
                    and href.rstrip("/") != _BMS_NEWS_PREFIX.rstrip("/")):
                url = _BMS_BASE + href if href.startswith("/") else href
                if not any(a["url"] == url for a in self.articles):
                    title = self._current_title or href.split("/")[-1]
                    snippet = " ".join(self._current_snippet_parts).strip()[:200]
                    self.articles.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    })
                # Reset for next article card
                self._current_title = ""
                self._current_snippet_parts = []

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag == "h2" and self._in_h2:
            self._current_title = " ".join(self._h2_texts).strip()
            self._in_h2 = False
        elif tag == "p":
            self._in_p = False

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_h2:
            self._h2_texts.append(text)
        elif self._in_p and text.lower() not in ("weiterlesen", "weiterlesen …"):
            self._current_snippet_parts.append(text)


def extract_bms_articles(html: str) -> list[dict]:
    """Extract individual article links from the BMS news overview page.

    Returns list of dicts with keys: title, url, snippet.
    """
    parser = _BMSArticleExtractor()
    parser.feed(html)
    return parser.articles


# ---------------------------------------------------------------------------
# Claude streaming helper
# ---------------------------------------------------------------------------

def stream_claude(client: anthropic.Anthropic, *, model: str, system: str,
                  user_message: str, max_tokens: int = 3000,
                  emit=None) -> str:
    """Stream a Claude response, printing tokens as they arrive. Returns full text.

    emit: optional callable(str) — called for each token, used by web server
          to forward tokens to SSE clients.
    """
    collected: list[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            if emit is not None:
                emit(text)
            collected.append(text)
    print("\n")
    return "".join(collected).strip()
