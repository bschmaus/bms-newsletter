"""
Scanning Agent — BMS Newsletter
--------------------------------
Pulls news from the BMS school website and Montessori/Bildung sources,
then uses Claude to structure the raw content into newsletter-ready material.

Reads  : data/learnings.md           (feedback from past newsletters)
         data/newsletter_archive.md  (history — avoid repeating topics)
Writes : data/research_notes.md      (structured content for the Writer)

Run standalone:
    python -m agents.scanning
"""

import sys
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic
import feedparser
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    BMS_NEWS_URL,
    RSS_FEEDS,
    EXTRA_SOURCES,
    LEARNINGS_FILE,
    NEWSLETTER_ARCHIVE,
    RESEARCH_NOTES_FILE,
    BROWSER_HEADERS,
    read_file,
    ensure_data_dir,
)
from agents.utils import strip_html

# Scanning uses Sonnet to keep costs down
MODEL = "claude-sonnet-4-6"

MAX_FEED_CHARS = 28_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_bms_news(url: str) -> str:
    """Scrape the BMS news page and extract article titles + summaries."""
    try:
        print(f"  🏫 Scraping BMS news: {url}")
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        text = strip_html(resp.text)
        return text[:8000]
    except Exception as exc:
        print(f"  ⚠️  Could not fetch BMS news: {exc}")
        return ""


def fetch_feed(url: str) -> list[dict]:
    """Fetch a single RSS feed. Returns list of entry dicts."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        entries = []
        for entry in feed.entries[:10]:
            title   = entry.get("title", "").strip()
            summary = strip_html(entry.get("summary", entry.get("description", "")))[:500]
            link    = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            if title:
                entries.append({
                    "title":     title,
                    "summary":   summary,
                    "link":      link,
                    "published": published,
                })
        return entries
    except Exception as exc:
        print(f"  ⚠️  Could not fetch {url}: {exc}")
        return []


def fetch_extra_source(url: str) -> str:
    """Fetch a non-RSS page and return its visible text."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
        text = strip_html(resp.text)
        return text[:3000]
    except Exception as exc:
        print(f"  ⚠️  Could not scrape {url}: {exc}")
        return ""


def fetch_all_content() -> tuple[str, str]:
    """
    Fetch BMS news + external Montessori sources.
    Returns (bms_content, external_content).
    """
    # --- BMS school news ---
    bms_content = fetch_bms_news(BMS_NEWS_URL)

    # --- External Montessori / Bildung sources ---
    sections = []

    for url in RSS_FEEDS:
        print(f"  📡 RSS: {url}")
        entries = fetch_feed(url)
        if not entries:
            continue
        source_domain = url.split("/")[2]
        block = [f"### Quelle: {source_domain}"]
        for e in entries:
            block.append(f"**{e['title']}**")
            if e["published"]:
                block.append(f"_Veröffentlicht: {e['published']}_")
            if e["link"]:
                block.append(f"URL: {e['link']}")
            if e["summary"]:
                block.append(e["summary"])
            block.append("")
        sections.append("\n".join(block))

    for url in EXTRA_SOURCES:
        print(f"  🌐 Scraping: {url}")
        text = fetch_extra_source(url)
        if text.strip():
            domain = url.split("/")[2]
            sections.append(f"### Quelle: {domain}\nURL: {url}\n{text}")

    external_content = "\n\n".join(sections)[:MAX_FEED_CHARS]
    return bms_content, external_content


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du bist ein Redakteur für den Newsletter einer Montessori-Schule.
Deine Aufgabe ist es, aus Rohinhalten strukturierte Newsletter-Bausteine zu erstellen.

Der Newsletter hat zwei Sektionen:

## Sektion 1: "News aus der BMS"
- Extrahiere die 2-4 aktuellsten und interessantesten Neuigkeiten von der Schulwebsite
- Fasse jede News in 2-3 Sätzen zusammen — warm, persönlich, auf Augenhöhe
- Wenn keine aktuellen News gefunden werden, notiere das ehrlich

## Sektion 2: "Spannendes aus der Montessori- & Bildungsszene"
- Finde genau 2 Geschichten:
  1. Ein Montessori-Beispiel aus Deutschland
  2. Ein Montessori-Beispiel international (weltweit)
- Fokus auf positive, inspirierende Geschichten — was funktioniert, was ist innovativ
- Immer mit Quellenangabe (Titel + URL)

## Richtlinien
- Schreibe auf Deutsch
- Tone: warm, einladend, für Eltern und Alumni
- Vermeide Behördendeutsch und PR-Sprache
- Bevorzuge konkrete Geschichten vor abstrakten Trends
- Integriere Feedback aus vergangenen Newslettern (Learnings)
- Vermeide Themen, die kürzlich schon im Newsletter waren
- Output NUR strukturiertes Markdown — keine Einleitung, kein Kommentar
"""


def build_user_message(bms_content: str, external_content: str,
                       learnings: str, archive: str) -> str:
    today = datetime.now().strftime("%A, %d. %B %Y")
    return textwrap.dedent(f"""
        Heute ist {today}.

        ## Vergangene Learnings & Feedback
        {learnings or "_Noch keine._"}

        ## Bisherige Newsletter (Themen nicht wiederholen)
        {archive or "_Noch kein Archiv._"}

        ## BMS-Website-Inhalte (Schulnews)
        {bms_content or "_Keine BMS-News gefunden._"}

        ## Externe Montessori- & Bildungsquellen
        {external_content or "_Keine externen Inhalte gefunden._"}

        ---

        Erstelle jetzt die Newsletter-Bausteine. Nutze diese Struktur:

        ## Sektion 1: News aus der BMS

        ### [News-Titel 1]
        [2-3 Sätze Zusammenfassung]

        ### [News-Titel 2]
        [2-3 Sätze Zusammenfassung]

        (weitere News falls vorhanden)

        ## Sektion 2: Spannendes aus der Montessori- & Bildungsszene

        ### 🇩🇪 [Titel Deutschland-Beispiel]
        **Quelle:** [Titel + URL]
        [3-4 Sätze — was ist passiert, warum ist es spannend]

        ### 🌍 [Titel Internationales Beispiel]
        **Quelle:** [Titel + URL]
        [3-4 Sätze — was ist passiert, warum ist es spannend]
    """).strip()


def run(client: anthropic.Anthropic | None = None) -> str:
    """
    Run the scanning agent. Returns the research notes as a string.
    """
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("🔍 Scanning Agent startet...")

    learnings = read_file(LEARNINGS_FILE)
    archive   = read_file(NEWSLETTER_ARCHIVE)

    print("\n  Inhalte abrufen...")
    bms_content, external_content = fetch_all_content()

    if not bms_content.strip() and not external_content.strip():
        print("  ⚠️  Keine Inhalte abgerufen — Claude nutzt Allgemeinwissen.")

    print("\n  Analysiere mit Claude...\n")
    user_message = build_user_message(bms_content, external_content, learnings, archive)

    collected = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)

    print("\n")
    research_output = "".join(collected)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    notes = f"# Recherche-Notizen — {timestamp}\n\n{research_output}\n"
    RESEARCH_NOTES_FILE.write_text(notes, encoding="utf-8")
    print(f"  ✅ Recherche-Notizen geschrieben: {RESEARCH_NOTES_FILE}")

    return research_output


if __name__ == "__main__":
    run()
