"""
HTML Formatter Agent — BMS Newsletter
--------------------------------------
Converts the finished newsletter from Markdown to a styled HTML email layout
that can be copy-pasted into Outlook.

Reads  : data/newsletter_archive.md   (the finished newsletter)
         data/corporate_design.md     (colors, fonts, layout rules, Outlook constraints)
Writes : data/newsletter.html         (ready-to-paste HTML email)

Technical output requirements:
- ALL styles as inline style="..." attributes (no <style> block — Outlook strips it)
- Table-based layout throughout (no <div> for structure — Outlook ignores max-width/overflow)
- No box-shadow, border-radius, rgba(), :hover, @media, flexbox, grid

Run standalone:
    python -m agents.html_formatter
"""

import sys
import textwrap
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MODEL,
    NEWSLETTER_ARCHIVE,
    NEWSLETTER_HTML,
    NEWSLETTER_ENGLISH,
    CORPORATE_DESIGN_FILE,
    read_file,
    ensure_data_dir,
)
from agents.utils import extract_latest_newsletter, stream_claude


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    Du bist ein erfahrener HTML-Email-Designer, der Newsletter-Text in ein
    Outlook-kompatibles HTML-Email-Layout konvertiert.

    Dein Output ist AUSSCHLIESSLICH der vollständige HTML-Code — kein
    Markdown, keine Erklärungen, keine Kommentare davor oder danach.
    Beginne mit <!DOCTYPE html> und ende mit </html>.

    OUTLOOK-KOMPATIBILITÄT (absolut verpflichtend, keine Ausnahmen):
    - ALLE Styles als inline style="..." Attribute direkt auf jedem HTML-Element
    - KEIN <style>-Block im <head> — Outlook Desktop ignoriert ihn komplett
    - Strukturelles Layout AUSSCHLIESSLICH mit <table>, <tr>, <td>
    - Keine <div>-Elemente für Layout-Struktur
    - Breite über width-Attribut auf <table>, nicht per CSS
    - VERBOTEN: box-shadow, border-radius, overflow, max-width, rgba(), :hover,
      @media, display:flex, display:grid, display:inline-block, CSS-Klassen

    Inhaltliche Regeln:
    - Der Newsletter-Text wird NICHT verändert, gekürzt oder umgeschrieben.
    - Überschriften, Absätze und Listen darf ich HTML-gerecht strukturieren.
    - Alle URLs im Text werden zu klickbaren <a href>-Links.
    - Die BMS-Website ist https://bilinguale-montessori-schule.de
      (niemals bms-ingelheim.de oder andere Domains).
    - Artikel-Links: Wenn ein Artikel eine spezifische URL hat
      (z.B. https://bilinguale-montessori-schule.de/de/aktuelles/news-de/bmsbus),
      diese URL als Link verwenden — NICHT die Übersichtsseite.
    - Termine werden als hervorgehobene Box mit Datum-/Event-Spalten dargestellt.
    - Das Eröffnungszitat aus dem Newsletter-Text wird als Pull-Quote gestaltet.
    - Das Abschluss-Zitat MUSS ein echtes, verifizierbares Maria-Montessori-Zitat
      sein — mit Quellenangabe (Werk, Jahr). Es darf KEIN Satz aus dem
      Newsletter-Text sein. Es soll thematisch zum roten Faden der Ausgabe passen.

    BILINGUALES LAYOUT (wenn englische Version vorhanden):
    - Ganz oben nach dem Logo: ein Hinweis-Link
      "Read in English ↓" der zum Anchor #english springt
    - Dann der vollständige DEUTSCHE Newsletter
    - Dann ein visueller Trenner (Linie + Anchor <a name="english"></a>)
      mit Überschrift "English Version"
    - Dann der vollständige ENGLISCHE Newsletter (gleiche Gestaltung)
    - Oben im englischen Teil: Link "Deutsche Version ↑" der zu #top springt
    - Wenn KEINE englische Version mitgegeben wird: nur den deutschen Teil,
      ohne Sprachlinks (rückwärtskompatibel)
""")


def build_prompt(newsletter: str, subject: str, design_guide: str,
                 english: str = "") -> str:
    english_section = ""
    if english.strip():
        english_section = textwrap.dedent(f"""

        ---

        ## Englische Version (gleiche Gestaltung, nach dem deutschen Teil)

        {english}

        ---

        WICHTIG: Baue BEIDE Versionen in ein einziges HTML-Dokument ein.
        Oben: "Read in English ↓" Link. Unten: englische Version mit Anchor.
        """)

    return textwrap.dedent(f"""\
        ## Corporate Design & technische Vorgaben

        {design_guide}

        ---

        ## Newsletter-Betreff
        {subject}

        ## Newsletter-Text (DEUTSCH — vollständig und unverändert übernehmen)

        {newsletter}
        {english_section}

        ---

        Erstelle jetzt das vollständige, Outlook-kompatible HTML-Email-Layout.
        Beginne mit <!DOCTYPE html> und ende mit </html>.
        Alle Styles inline. Alle Struktur-Elemente als <table>.
        Das Abschluss-Zitat muss ein echtes Montessori-Zitat sein.
    """)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def run(client: anthropic.Anthropic | None = None) -> str:
    """Run the HTML formatter agent. Returns the path to the generated file."""
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("🎨 HTML Formatter startet...")

    archive = read_file(NEWSLETTER_ARCHIVE)
    subject, newsletter = extract_latest_newsletter(archive)

    if not newsletter:
        print("  ⚠️  Kein Newsletter gefunden. Zuerst die Pipeline starten.")
        return ""

    design_guide = read_file(CORPORATE_DESIGN_FILE)
    if not design_guide:
        print("  ⚠️  corporate_design.md nicht gefunden — ohne Design-Vorgaben fortfahren.")

    english = read_file(NEWSLETTER_ENGLISH)
    if english.strip():
        print("  🌐 Englische Version gefunden — bilinguales Layout")
    else:
        print("  ℹ️  Keine englische Version — nur Deutsch")

    print(f"\n  Formatiere: {subject}\n")
    print("-" * 60)

    prompt = build_prompt(newsletter, subject, design_guide, english)
    html = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=prompt, max_tokens=32000,
    )
    print("-" * 60 + "\n")

    # Strip any accidental markdown fences
    if html.startswith("```"):
        lines = html.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        html = "\n".join(lines)

    NEWSLETTER_HTML.write_text(html, encoding="utf-8")
    print(f"  ✅ HTML gespeichert: {NEWSLETTER_HTML}")

    return str(NEWSLETTER_HTML)


if __name__ == "__main__":
    run()
