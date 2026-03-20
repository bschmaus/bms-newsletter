"""
Newsletter Writer Agent — BMS Newsletter
-----------------------------------------
Takes the structured research notes and composes a complete newsletter
draft ready for email.

Reads  : data/research_notes.md      (content from Scanning agent)
         data/learnings.md           (accumulated style feedback)
         data/voice.md               (BMS voice & style guide)
Writes : data/newsletter_archive.md  (appends today's newsletter)

Run standalone:
    python -m agents.newsletter_writer
"""

import sys
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MODEL,
    RESEARCH_NOTES_FILE,
    LEARNINGS_FILE,
    NEWSLETTER_ARCHIVE,
    VOICE_FILE,
    read_file,
    ensure_data_dir,
)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du schreibst "News aus der BMS" — den Newsletter der Bilingualen Montessori
Schule (BMS) Ingelheim — für Eltern, Alumni und Mitarbeitende.

## Format & Struktur
Der Newsletter hat diese Struktur:
1. **Betreffzeile** — kurz, neugierig machend, max 60 Zeichen
2. **Begrüßung** — beginnt IMMER mit "Liebe Schulgemeinschaft," dann 1-2 warme Sätze
3. **News aus der BMS** — 2-4 kurze Meldungen aus dem Schulleben
4. **Aus der Montessori-Welt** — 2-3 inspirierende Geschichten von anderen
   Montessori-Schulen und -Verbänden (AMI, NAMTA, Montessori Europe etc.)
5. **Bildungspolitik — was bedeutet das für uns?** — genau EIN gut ausgewähltes
   Thema, kurz erklärt und eingeordnet: was heißt das für die BMS?
6. **Nächste Termine** — Termine der kommenden 8 Wochen als einfache Liste
7. **Abschluss** — herzlicher Gruß, max 2 Sätze

## Regeln
- Gesamtlänge: max 600-800 Wörter (max 2 Seiten in einer Email!)
- Sprache: Deutsch, Sie-Form
- Tonalität: warm, einladend, respektvoll
- Jede Sektion kurz und knapp — lieber weniger Text, dafür lesenswert
- Die Montessori-Geschichten sollen inspirieren — was kann man daraus lernen?
- Das Bildungspolitik-Thema soll einordnen, nicht belehren
- Termine einfach als Auflistung (Datum — Was)
- Quellenangaben bei externen Geschichten
- Keine PR-Sprache, kein Behördendeutsch
- Kein "In der heutigen Zeit..." oder ähnliche Floskeln
- Output NUR den Newsletter-Text — keine Meta-Kommentare
"""


def build_user_message(research: str, learnings: str, voice: str,
                       redteam_feedback: str = "") -> str:
    today = datetime.now().strftime("%A, %d. %B %Y")
    redteam_section = (
        f"\n        ## Red Team Feedback (bitte jeden Punkt adressieren)\n        {redteam_feedback}"
        if redteam_feedback.strip() else ""
    )
    return textwrap.dedent(f"""
        Heute ist {today}.

        ## Voice & Style Guide
        {voice or "_Kein Style Guide vorhanden._"}

        ## Feedback aus vergangenen Newslettern
        {learnings or "_Noch keins._"}
        {redteam_section}

        ## Recherche-Material (alle Sektionen vorbereitet)
        {research}

        ---

        Schreibe jetzt den kompletten Newsletter. Beginne mit der Betreffzeile
        (als "**Betreff:** ..."), dann der Newsletter-Text.

        WICHTIG: Maximal 2 Seiten! Lieber kürzer und knackiger als lang und langweilig.
        Sie-Form durchgehend. Termine als einfache Liste.
    """).strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _replace_latest_entry(newsletter: str, subject: str) -> None:
    """Overwrite the most recent newsletter entry — used during red team revisions."""
    import re
    content = read_file(NEWSLETTER_ARCHIVE)
    # Find the last entry header and replace everything after it
    headers = list(re.finditer(
        r"^## \d{4}-\d{2}-\d{2} — .+$", content, re.MULTILINE
    ))
    if headers:
        base = content[:headers[-1].start()]
    else:
        base = content
    today_str  = datetime.now().strftime("%Y-%m-%d")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"## {today_str} — {subject}\n\n"
        f"_Erstellt: {timestamp} | Status: Entwurf_\n\n"
        f"{newsletter}\n"
    )
    NEWSLETTER_ARCHIVE.write_text(base + entry, encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def run(client: anthropic.Anthropic | None = None,
        redteam_feedback: str = "",
        revision: bool = False) -> str:
    """
    Run the newsletter writer agent. Returns the finished newsletter as a string.
    """
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("✍️  Newsletter Writer startet...")

    research  = read_file(RESEARCH_NOTES_FILE)
    learnings = read_file(LEARNINGS_FILE)
    voice     = read_file(VOICE_FILE)

    if not research.strip() or "_Noch keine Recherche._" in research:
        print("  ⚠️  Keine Recherche-Notizen gefunden. Zuerst Scanning Agent starten.")
        return ""

    print("\n  Schreibe Newsletter mit Claude...\n")
    print("-" * 60)

    user_message = build_user_message(research, learnings, voice, redteam_feedback)
    collected = []

    with client.messages.stream(
        model=MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)

    print("\n" + "-" * 60 + "\n")
    newsletter = "".join(collected).strip()

    # Extract subject line for the archive header
    subject = "Newsletter"
    for line in newsletter.splitlines():
        if line.startswith("**Betreff:**"):
            subject = line.replace("**Betreff:**", "").strip()
            break

    if revision:
        _replace_latest_entry(newsletter, subject)
        print(f"  ✅ Newsletter überarbeitet in {NEWSLETTER_ARCHIVE}")
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = (
            f"\n---\n\n"
            f"## {today_str} — {subject}\n\n"
            f"_Erstellt: {timestamp} | Status: Entwurf_\n\n"
            f"{newsletter}\n"
        )
        with open(NEWSLETTER_ARCHIVE, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"  ✅ Newsletter archiviert in {NEWSLETTER_ARCHIVE}")

    return newsletter


if __name__ == "__main__":
    run()
