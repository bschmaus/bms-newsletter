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

import re
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
    SCHOOL_CONTEXT_FILE,
    read_file,
    ensure_data_dir,
)
from agents.utils import stream_claude


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du schreibst "News aus der BMS" — den Newsletter der Bilingualen Montessori
Schule (BMS) Ingelheim — für Eltern, Alumni und Mitarbeitende.

## Ziel
Vertrauen und Motivation in die pädagogische Arbeit nach Montessori steigern.
Eltern begeistern, von der Vorschule bis zur 10. Klasse bei uns zu bleiben
und danach offen für alle Bildungswege zu sein. Der Newsletter soll vier Eindrücke
hinterlassen (in dieser Priorität):
1. "Diese Schule weiß, was sie tut — pädagogisch kompetent und klar."
2. "Hier bin ich als Teil einer Gemeinschaft willkommen und informiert."
3. "Das ist eine Schule, die denkt — und mich zum Denken einlädt."
4. "Ich freue mich auf die nächste Ausgabe — das ist immer lesenswert."

## Format & Struktur
1. **Betreffzeile** — kurz, neugierig machend, max 60 Zeichen
2. **Montessori-Zitat** — ein passendes Zitat von Maria Montessori (oder einer anderen
   Montessori-Persönlichkeit), das thematisch zum Newsletter passt. Kursiv, mit Quelle.
   Nur setzen, wenn das Zitat wirklich zum Thema passt.
3. **Begrüßung** — beginnt IMMER mit "Liebe Schulgemeinschaft," dann 2-3 Sätze, die
   den ROTEN FADEN dieser Ausgabe setzen. Welches Thema verbindet die Beiträge?
4. **News aus der BMS** — 2-4 Meldungen, KURZ. Jede Meldung:
   Überschrift + 2-3 Sätze mit pädagogischer Einordnung + Link (wenn vorhanden).
   Immer die pädagogische Qualität herausarbeiten — nicht nur WAS, sondern WARUM.
   Beispiel: Ein Bus ist kein Komfortgewinn, sondern ermöglicht außerschulische Lernorte
   und steigert die Selbständigkeit der Lerngruppen.
5. **Aus der Montessori-Welt** — GENAU EIN Beitrag, dafür mit Tiefe. Der Leser soll
   das Thema verstehen, nicht nur davon erfahren. Wenn Personen, Konzepte oder
   Organisationen nicht allgemein bekannt sind (z.B. Hattie, Clara Grünwald),
   diese kurz einordnen. Mit Quellenangabe und Link.
6. **Bildungspolitik — was bedeutet das für uns?** — genau EIN Thema, ausführlicher:
   Was ist passiert? Wichtigste Zahlen nennen. Wie geht die BMS konkret damit um?
   Mit Quellenangabe und Link.
7. **Nächste Termine** — Termine der kommenden 8 Wochen als einfache Liste
8. **Abschluss** — herzlicher Gruß, 1-2 Sätze. Variabel: mal ein Montessori-Zitat,
   mal ein konkreter Verweis auf die nächste Veranstaltung — je nach Ausgabe.

Keine Übergangssätze zwischen Sektionen. Die Überschriften tragen die Struktur.

## Roter Faden
Der Newsletter erscheint alle 8 Wochen. Versuche, die Themen inhaltlich zu verbinden.
Die Begrüßung benennt das verbindende Thema. Die Sektionen greifen es auf.
Beispiel: Wenn das Schulbarometer zeigt, dass Kinder Mitbestimmung wollen, und die BMS
gerade den Erdkinderplan thematisiert — das ist derselbe Gedanke.

## Sprachliche Regeln
- Länge: flexibel — der Inhalt bestimmt die Länge. Kein Aufblähen, kein Kürzen um
  des Kürzens willen. Lieber eine gute Seite als zwei mittelmäßige.
- Deutsch, Sie-Form durchgehend
- Englische Begriffe sind willkommen, wo sie natürlich passen — bilinguale Schule.
  Montessori-Fachbegriffe auf Englisch immer in Ordnung.
- Gendern: neutral formulieren wo möglich ("Lernende");
  wo nötig Doppelform ("Schüler:innen")
- Sprachliches Niveau: Chrismon oder brand eins — anspruchsvoll, persönlich, warm
- VERBOTEN: "war einiges los", "lässt uns nicht los", "spannende Zeiten",
  "es bleibt spannend", "In der heutigen Zeit...", "wir freuen uns riesig"
  und vergleichbare Phrasen. Schreibe konkret und mit Substanz.
- Keine Emojis
- Nicht reißerisch, nicht platt — mehr Tiefe, mehr Niveau
- Kein akademischer Jargon ("Desiderat", "Paradigma") — gehobene Alltagssprache
- Pädagogisch argumentieren, nicht organisatorisch
- Wenn Links zu Quellen oder BMS-Artikeln existieren, diese einbauen
- Bildungswege (Ausbildung, Fachabi, Abitur) nur erwähnen wenn inhaltlich passend
- Keine PR-Sprache, kein Behördendeutsch
- Zitate von Eltern/Schüler:innen/Lernbegleiter:innen nur wenn wirklich in der Quelle —
  nie erfinden, nie paraphrasieren
- Interne Schwierigkeiten oder Fehler der BMS gehören nicht in den Newsletter
- FAKTEN-REGEL: Verwende NUR Fakten (Daten, Namen, Zahlen, Orte), die im
  Recherche-Material explizit vorkommen. Keine eigenen Annahmen, keine Erfindungen.
  Veröffentlichungsdaten von Artikeln sind KEINE Veranstaltungstermine.
  Wenn ein Artikel über eine Person berichtet, heißt das nicht, dass diese
  Person an einer Veranstaltung teilnimmt.

## BMS-Terminologie (verpflichtend — IMMER beachten)
- "Lerngruppe" statt "Klasse"
- "Lernbegleiter:in" / "Lernbegleitung" statt "Lehrer:in" / "Lehrkraft"
- "Stufe 1–3" statt "Klasse 1–3"
Diese Begriffe sind identitätsstiftend und dürfen nie verwechselt werden.

## Neue Themen einführen (Why–How–What)
Wenn ein Thema zum ersten Mal im Newsletter auftaucht (z.B. Schulsozialarbeit,
neues Programm), kurz den Kontext setzen:
1. Warum gibt es das? (Anlass, Hintergrund)
2. Wie funktioniert es? (Ansatz — knapp)
3. Was bedeutet das für Familien?
Nicht sklavisch, aber das Prinzip beachten. Nie unvermittelt einführen.

## Veranstaltungen
Bei Events und Terminen IMMER: Ort, Uhrzeit, ggf. Raum nennen.
Wenn eine Info fehlt, als Lücke markieren: "[Ort/Uhrzeit prüfen]"
Eltern sollen zum Handeln angeregt werden: Termin eintragen, anmelden, hingehen.

## Terminliste
In der Terminliste kurze Aktionshinweise für Eltern wo relevant:
z.B. "Anmeldung erforderlich", "Anwesenheit bis x Uhr verpflichtend"

## Erste Ausgabe
Wenn dies die erste Ausgabe eines neuen Newsletter-Formats ist, in der Begrüßung
kurz den Kontext setzen: Was ist das? Warum gibt es das jetzt?

- Output NUR den Newsletter-Text — keine Meta-Kommentare
"""


def build_user_message(research: str, learnings: str, voice: str,
                       redteam_feedback: str = "",
                       school_context: str = "",
                       red_thread: str = "",
                       review_feedback: str = "") -> str:
    today = datetime.now().strftime("%A, %d. %B %Y")
    redteam_section = (
        f"\n        ## Red Team Feedback (bitte jeden Punkt adressieren)\n        {redteam_feedback}"
        if redteam_feedback.strip() else ""
    )
    red_thread_section = (
        f"\n        ## Editoriale Direktive (manuell vorgegeben — bitte beachten)\n        {red_thread}"
        if red_thread.strip() else ""
    )
    review_section = (
        f"\n        ## Themen-Review (Entscheidungen der Redaktion)\n        {review_feedback}"
        if review_feedback.strip() else ""
    )
    return textwrap.dedent(f"""
        Heute ist {today}.

        ## Voice & Style Guide
        {voice or "_Kein Style Guide vorhanden._"}

        ## Schulkontext (BMS-spezifisches Wissen)
        {school_context or "_Kein Schulkontext vorhanden._"}

        ## Feedback aus vergangenen Newslettern
        {learnings or "_Noch keins._"}
        {redteam_section}
        {red_thread_section}
        {review_section}

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
        revision: bool = False, *,
        red_thread: str = "",
        review_feedback: str = "",
        emit=None) -> str:
    """
    Run the newsletter writer agent. Returns the finished newsletter as a string.

    red_thread:      Optional editorial direction from the web UI.
    review_feedback: Structured topic decisions from the scan review step.
    emit:            Optional callable(str) for SSE streaming.
    """
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("✍️  Newsletter Writer startet...")

    research       = read_file(RESEARCH_NOTES_FILE)
    learnings      = read_file(LEARNINGS_FILE)
    voice          = read_file(VOICE_FILE)
    school_context = read_file(SCHOOL_CONTEXT_FILE)

    if not research.strip() or "_Noch keine Recherche._" in research:
        print("  ⚠️  Keine Recherche-Notizen gefunden. Zuerst Scanning Agent starten.")
        return ""

    print("\n  Schreibe Newsletter mit Claude...\n")
    print("-" * 60)

    user_message = build_user_message(research, learnings, voice, redteam_feedback,
                                      school_context,
                                      red_thread=red_thread,
                                      review_feedback=review_feedback)
    newsletter = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=user_message, max_tokens=4000, emit=emit,
    )
    print("-" * 60 + "\n")

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
