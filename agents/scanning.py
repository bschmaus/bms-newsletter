"""
Scanning Agent — BMS Newsletter
--------------------------------
Pulls content from three source categories:
  1. BMS website — school news + upcoming events (next 8 weeks)
  2. Montessori world — other schools, AMI, NAMTA, Montessori Europe/Deutschland
  3. Bildungspolitik — policy news (Schulbarometer, PISA, KMK, BM RLP, WEF, UN)

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
    BMS_TERMINE_URL,
    EXTRA_MONTESSORI_SOURCES,
    RSS_FEEDS_BILDUNG,
    EXTRA_BILDUNG_SOURCES,
    LEARNINGS_FILE,
    NEWSLETTER_ARCHIVE,
    RESEARCH_NOTES_FILE,
    BROWSER_HEADERS,
    read_file,
    ensure_data_dir,
)
from agents.utils import strip_html, stream_claude

# Scanning uses Sonnet to keep costs down
MODEL = "claude-sonnet-4-6"

MAX_FEED_CHARS = 28_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, max_chars: int = 8000) -> str:
    """Scrape a web page and return readable text."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return strip_html(resp.text)[:max_chars]
    except Exception as exc:
        print(f"  ⚠️  Konnte {url} nicht abrufen: {exc}")
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
        print(f"  ⚠️  Konnte {url} nicht abrufen: {exc}")
        return []


def format_feed_entries(entries: list[dict], source_domain: str) -> str:
    """Format feed entries into a markdown block."""
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
    return "\n".join(block)


def _fetch_category(label: str, rss_feeds: list[str], scrape_urls: list[str],
                    max_chars: int = MAX_FEED_CHARS // 2) -> str:
    """Fetch RSS feeds + scraped pages for a source category. Returns markdown."""
    sections: list[str] = []
    for url in rss_feeds:
        print(f"  📡 {label} RSS: {url}")
        entries = fetch_feed(url)
        if entries:
            sections.append(format_feed_entries(entries, url.split("/")[2]))
    for url in scrape_urls:
        print(f"  🌐 {label} Scrape: {url}")
        text = fetch_page(url, max_chars=3000)
        if text.strip():
            sections.append(f"### Quelle: {url.split('/')[2]}\nURL: {url}\n{text}")
    return "\n\n".join(sections)[:max_chars]


def fetch_all_content() -> tuple[str, str, str, str]:
    """
    Fetch all content sources.
    Returns (bms_news, bms_termine, montessori_content, bildung_content).
    """
    print(f"  🏫 BMS News: {BMS_NEWS_URL}")
    bms_news = fetch_page(BMS_NEWS_URL)

    print(f"  📅 BMS Termine: {BMS_TERMINE_URL}")
    bms_termine = fetch_page(BMS_TERMINE_URL, max_chars=5000)

    montessori_content = _fetch_category("Montessori", [], EXTRA_MONTESSORI_SOURCES)
    bildung_content = _fetch_category("Bildung", RSS_FEEDS_BILDUNG, EXTRA_BILDUNG_SOURCES)

    return bms_news, bms_termine, montessori_content, bildung_content


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du bist ein Redakteur für den Newsletter einer Montessori-Schule.
Deine Aufgabe ist es, aus Rohinhalten strukturierte Newsletter-Bausteine zu erstellen.

Der Newsletter hat diese Sektionen:

## Sektion 1: "News aus der BMS"
- Extrahiere die 2-4 aktuellsten und interessantesten Neuigkeiten von der Schulwebsite
- Fasse jede News KURZ zusammen (1-2 Sätze), aber arbeite die pädagogische Dimension
  heraus: nicht nur WAS passiert ist, sondern WARUM es pädagogisch wertvoll ist
- Wenn ein Link zum Originalartikel auf der BMS-Website existiert, diesen angeben
- Wenn keine aktuellen News gefunden werden, notiere das ehrlich

## Sektion 2: "Aus der Montessori-Welt"
- Wähle GENAU EINE Geschichte aus — die beste, tiefgründigste, relevanteste
- Diese eine Geschichte dafür mit TIEFE aufbereiten: Kontext erklären, Hintergrund
  liefern, Bezug zur BMS herstellen
- Wenn Personen, Organisationen oder Konzepte erwähnt werden, die nicht allgemein
  bekannt sind (z.B. John Hattie, Clara Grünwald, NAMTA), diese kurz einordnen
- Fokus: andere Montessori-Schulen, Verbände (AMI, NAMTA, Montessori Europe,
  Montessori Deutschland), Montessori Model United Nations
- Immer mit Quellenangabe (Titel + URL)

## Sektion 3: "Bildungspolitik — was bedeutet das für uns?"
- Wähle GENAU EIN aktuelles bildungspolitisches Thema aus
- Gute Themen: Schulbarometer (Robert Bosch Stiftung), Bildungsreport Telekom,
  PISA-Studie, Kultusministerkonferenz, Bildungsministerium RLP,
  World Economic Forum, United Nations Bildungsberichte
- Erkläre ausführlicher als bei anderen Sektionen: Was ist passiert? Was bedeutet das
  für eine Montessori-Schule wie die BMS? Wie gehen wir konkret damit um?
- Immer mit Quellenangabe und Link

## Sektion 4: "Nächste Termine an der BMS"
- Liste alle Termine der kommenden 8 Wochen aus dem Terminkalender
- Einfache Auflistung: Datum — Termin (ggf. kurze Ergänzung)

## Sektion 5: "Montessori-Zitat"
- Schlage ein passendes Zitat von Maria Montessori (oder einer anderen
  Montessori-Persönlichkeit) vor, das thematisch zu den Inhalten passt
- Mit Quellenangabe (Werk/Buch)

## Richtlinien
- Schreibe auf Deutsch, Sie-Form
- Tone: anspruchsvoll, warm, persönlich — aber KEINE Floskeln oder Phrasen
- Vermeide Behördendeutsch und PR-Sprache
- Bevorzuge konkrete Geschichten vor abstrakten Trends
- Denke über einen möglichen ROTEN FADEN nach: gibt es ein Thema, das mehrere
  Sektionen verbindet? Notiere diesen Vorschlag am Anfang.
- Integriere Feedback aus vergangenen Newslettern (Learnings)
- Vermeide Themen, die kürzlich schon im Newsletter waren
- Output NUR strukturiertes Markdown — keine Einleitung, kein Kommentar
"""


def build_user_message(bms_news: str, bms_termine: str,
                       montessori_content: str, bildung_content: str,
                       learnings: str, archive: str) -> str:
    today = datetime.now().strftime("%A, %d. %B %Y")
    return textwrap.dedent(f"""
        Heute ist {today}.

        ## Vergangene Learnings & Feedback
        {learnings or "_Noch keine._"}

        ## Bisherige Newsletter (Themen nicht wiederholen)
        {archive or "_Noch kein Archiv._"}

        ## BMS-Website: Schulnews
        {bms_news or "_Keine BMS-News gefunden._"}

        ## BMS-Website: Terminkalender
        {bms_termine or "_Keine Termine gefunden._"}

        ## Montessori-Quellen (Verbände, Schulen, Organisationen)
        {montessori_content or "_Keine Montessori-Inhalte gefunden._"}

        ## Bildungspolitik-Quellen
        {bildung_content or "_Keine Bildungspolitik-Inhalte gefunden._"}

        ---

        Erstelle jetzt die Newsletter-Bausteine. Nutze diese Struktur:

        ## Sektion 1: News aus der BMS

        ### [News-Titel 1]
        [2-3 Sätze Zusammenfassung]

        ### [News-Titel 2]
        [2-3 Sätze Zusammenfassung]

        ## Sektion 2: Aus der Montessori-Welt

        ### [Titel Geschichte 1]
        **Quelle:** [Titel + URL]
        [3-4 Sätze]

        ### [Titel Geschichte 2]
        **Quelle:** [Titel + URL]
        [3-4 Sätze]

        ## Sektion 3: Bildungspolitik — was bedeutet das für uns?

        ### [Titel des Themas]
        **Quelle:** [Titel + URL]
        [4-5 Sätze: Was ist passiert? Was bedeutet das für die BMS?]

        ## Sektion 4: Nächste Termine an der BMS
        - [Datum] — [Termin]
        - [Datum] — [Termin]
        - ...
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
    bms_news, bms_termine, montessori_content, bildung_content = fetch_all_content()

    if not any([bms_news.strip(), montessori_content.strip(), bildung_content.strip()]):
        print("  ⚠️  Wenig Inhalte abgerufen — Claude nutzt Allgemeinwissen.")

    print("\n  Analysiere mit Claude...\n")
    user_message = build_user_message(
        bms_news, bms_termine, montessori_content, bildung_content,
        learnings, archive,
    )

    research_output = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=user_message, max_tokens=4000,
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    notes = f"# Recherche-Notizen — {timestamp}\n\n{research_output}\n"
    RESEARCH_NOTES_FILE.write_text(notes, encoding="utf-8")
    print(f"  ✅ Recherche-Notizen geschrieben: {RESEARCH_NOTES_FILE}")

    return research_output


if __name__ == "__main__":
    run()
