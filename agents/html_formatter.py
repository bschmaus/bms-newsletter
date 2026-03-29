"""
HTML Formatter Agent — BMS Newsletter
--------------------------------------
Converts the finished newsletter from Markdown to a styled HTML email layout
that can be copy-pasted into Outlook.

Reads  : data/newsletter_archive.md  (the finished newsletter)
         data/voice.md               (for tone context)
Writes : data/newsletter.html        (ready-to-paste HTML email)

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
    VOICE_FILE,
    read_file,
    ensure_data_dir,
)
from agents.utils import extract_latest_newsletter, stream_claude


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

BMS_LOGO_URL = "http://bilinguale-montessori-schule.de/images/Logo_BMS.png"


# ---------------------------------------------------------------------------
# HTML template & CSS
# ---------------------------------------------------------------------------

# The agent receives this as context so it can produce consistent output.
HTML_STYLE_GUIDE = """
## Design-Vorgaben für das HTML-Email-Layout

### Farbpalette (BMS)
- Primärfarbe (Überschriften, Akzente): #2B5B84 (ruhiges Dunkelblau)
- Sekundärfarbe (Termine-Highlights): #3A7CA5 (mittleres Blau)
- Hintergrund Body: #f5f5f0 (warmes Hellgrau)
- Hintergrund Content: #ffffff
- Text: #333333
- Zitat-Hintergrund: #f0f4f8 (zartes Blau)
- Zitat-Rand: #2B5B84
- Termine-Box: #f8f4e8 (warmes Creme)
- Footer-Hintergrund: #2B5B84
- Footer-Text: #ffffff

### Struktur
1. **Logo** — zentriert, oben, max 160px breit
2. **Montessori-Eröffnungszitat** — großes zentriertes Pull-Quote-Element mit linkem Farbrand
3. **Begrüßung** — normaler Fließtext
4. **Sektionen** (BMS-News, Montessori-Welt, Bildungspolitik) — je mit farbiger Überschrift, Trennlinie zwischen Sektionen
5. **Termine** — hervorgehobene Box/Tabelle mit Datum, Ort, Aktion
6. **Abschluss-Zitat** — visuell hervorgehoben (Pull-Quote-Stil)
7. **Footer** — kompakt: Schulname, Adresse, Website

### Typografie
- Font-Stack: 'Georgia', 'Times New Roman', serif (für Fließtext — passt zum redaktionellen Ton)
- Überschriften: 'Helvetica Neue', Arial, sans-serif
- Zeilenabstand: 1.6
- Max-Breite Content: 640px

### Technische Regeln
- HTML mit <style>-Block im <head>
- Alle URLs im Text werden zu klickbaren <a href>-Links (Farbe: #2B5B84)
- Bilder: nur das Logo (externe URL)
- Kein JavaScript
- UTF-8 Encoding
"""

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    Du bist ein erfahrener Email-Designer, der Newsletter-Text in ein
    ansprechendes HTML-Email-Layout konvertiert.

    Dein Output ist AUSSCHLIESSLICH der vollständige HTML-Code — kein
    Markdown, keine Erklärungen, keine Kommentare davor oder danach.
    Beginne mit <!DOCTYPE html> und ende mit </html>.

    Regeln:
    - Der Text des Newsletters wird NICHT verändert, gekürzt oder umgeschrieben.
    - Du darfst Überschriften, Absätze, Listen und andere HTML-Strukturelemente
      einsetzen, um die Lesbarkeit zu verbessern.
    - Du darfst Abschnitte visuell zusammenfassen oder umordnen, wenn es das
      Layout verbessert, aber der Inhalt muss vollständig erhalten bleiben.
    - Alle URLs im Text werden zu klickbaren Links.
    - Termine werden als visuell hervorgehobene Box dargestellt.
    - Das Montessori-Eröffnungszitat wird als großes zentriertes Pull-Quote gestaltet.
    - Am Ende: Abschluss-Zitat visuell hervorgehoben + kompakter Footer mit
      Schulname, Adresse (Carolinenstraße 2, 55218 Ingelheim), Website.
""")


def build_prompt(newsletter: str, subject: str) -> str:
    return textwrap.dedent(f"""\
        {HTML_STYLE_GUIDE}

        ## Logo-URL
        {BMS_LOGO_URL}

        ## Newsletter-Betreff
        {subject}

        ## Newsletter-Text (vollständig übernehmen)

        {newsletter}

        ---

        Erstelle jetzt das vollständige HTML-Email-Layout.
        Beginne mit <!DOCTYPE html> und ende mit </html>.
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

    print(f"\n  Formatiere: {subject}\n")
    print("-" * 60)

    prompt = build_prompt(newsletter, subject)
    html = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=prompt, max_tokens=8000,
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
