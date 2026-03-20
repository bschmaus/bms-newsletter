"""
Red Team Agent — BMS Newsletter
--------------------------------
Quality check before the newsletter goes out:

  1. Faktencheck — stimmen die Inhalte mit den Quellen überein?
  2. Leser-Perspektive — liest sich das gut für Eltern, Alumni und Mitarbeitende?

Iterates with newsletter_writer up to 2 times until approved.

Reads  : data/newsletter_archive.md  (current draft)
         data/research_notes.md      (original research)
         data/learnings.md           (accumulated feedback)
         data/voice.md               (BMS voice)
Writes : data/redteam_notes.md       (iteration history)

Run standalone:
    python -m agents.red_team
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
    NEWSLETTER_ARCHIVE,
    RESEARCH_NOTES_FILE,
    LEARNINGS_FILE,
    VOICE_FILE,
    REDTEAM_NOTES_FILE,
    read_file,
    ensure_data_dir,
)
from agents.utils import extract_latest_newsletter, stream_claude

MAX_ITERATIONS = 2


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Du bist Qualitätsprüfer für den Newsletter einer Montessori-Schule.
Deine Leser sind Eltern, Alumni und Mitarbeitende — intelligente, engagierte
Menschen, die wenig Zeit haben und keinen Marketing-Sprech mögen.

## Ziel des Newsletters
Vertrauen und Motivation in die pädagogische Arbeit nach Montessori steigern.
Eltern begeistern, bei der Schule zu bleiben und alle Bildungswege als gleichwertig
zu sehen. Jeder Beitrag soll die Qualität der Montessori-Pädagogik erlebbar machen.

## Prüfung 1 — Fakten & Quellen
- Stimmen die Inhalte mit den Recherche-Notizen überein?
- Werden Quellen korrekt wiedergegeben?
- Werden keine Behauptungen aufgestellt, die nicht belegt sind?

## Prüfung 2 — Roter Faden & Struktur
- Gibt es ein verbindendes Thema, das sich durch den Newsletter zieht?
- Setzt die Begrüßung diesen roten Faden?
- Ist "Aus der Montessori-Welt" EIN Beitrag mit ausreichend Tiefe?
  (Nicht 2-3 oberflächliche Meldungen!)
- Geht "Bildungspolitik" tief genug? Wird erläutert, wie die BMS damit umgeht?
- Werden externe Personen/Konzepte (z.B. Hattie, Clara Grünwald) kurz eingeordnet?

## Prüfung 3 — Sprache & Ton
- Sprachlich anspruchsvoll, persönlich, warm — aber KEINE Floskeln?
- SOFORT beanstanden: "war einiges los", "lässt uns nicht los", "spannende Zeiten",
  "es bleibt spannend" und vergleichbare Phrasen. Das ist zu platt.
- Wird pädagogisch argumentiert statt nur organisatorisch berichtet?
  (Nicht: "Bus macht Ausflüge einfacher" sondern: "Bus ermöglicht außerschulische
  Lernorte und steigert Selbständigkeit der Lerngruppen")
- Ist die Schule als inklusiv dargestellt? Werden alle Bildungswege gleichwertig
  behandelt (Ausbildung, Fachabi, Abitur)?
- Passt ein Montessori-Zitat zum Inhalt?
- Sind sinnvolle Links zu Quellen und BMS-Artikeln vorhanden?

## Prüfung 4 — Leser-Perspektive
Lies als Elternteil/Mitarbeiter:in, das/die 5 Minuten hat:
- Ist der Newsletter interessant genug, um bis zum Ende zu lesen?
- Klingt er authentisch — wie die Schule, die ich kenne?
- Oder klingt er wie eine PR-Abteilung?
- Steigert er Vertrauen in die pädagogische Arbeit?
- Ist die Länge angemessen (max 2 Seiten)?
- Wird durchgehend die Sie-Form verwendet?
- Sind die Termine korrekt aufgelistet?

## Ausgabeformat
Nutze GENAU diese Struktur:

### Fakten-Check
[Bullet Points — oder "Keine Probleme gefunden." wenn sauber]

### Leser-Perspektive
[Bullet Points — oder "Liest sich gut." wenn ok]

### Urteil
FREIGEGEBEN oder ÜBERARBEITEN

### Überarbeitungshinweise
[Konkrete Bullet Points wenn ÜBERARBEITEN — "Ersetze X mit Y", "Kürze Absatz 3"
Leer lassen wenn FREIGEGEBEN]
"""


def build_critique_prompt(newsletter: str, research: str, learnings: str,
                          voice: str, iteration: int,
                          prior_feedback: str) -> str:
    prior_section = (
        f"\n## Vorheriges Feedback (prüfe ob umgesetzt)\n{prior_feedback}"
        if prior_feedback.strip() else ""
    )
    return textwrap.dedent(f"""
        Iteration {iteration} von {MAX_ITERATIONS}.

        ## Recherche-Material (Quelle)
        {research or "_Nicht verfügbar._"}

        ## Voice & Style Guide
        {voice or "_Nicht vorhanden._"}

        ## Learnings aus vergangenen Newslettern
        {learnings or "_Noch keine._"}
        {prior_section}

        ## Newsletter-Entwurf
        {newsletter}

        ---

        Prüfe den Newsletter jetzt. Sei konstruktiv aber ehrlich.
    """).strip()


# ---------------------------------------------------------------------------
# Parse critique
# ---------------------------------------------------------------------------

def _extract_section(text: str, heading: str) -> str:
    pattern = rf"### {re.escape(heading)}\s*\n(.*?)(?=\n###|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_verdict(critique: str) -> str:
    section = _extract_section(critique, "Urteil")
    return "FREIGEGEBEN" if "FREIGEGEBEN" in section.upper() else "ÜBERARBEITEN"


def parse_revision_instructions(critique: str) -> str:
    facts   = _extract_section(critique, "Fakten-Check")
    parent  = _extract_section(critique, "Leser-Perspektive")
    instruct = _extract_section(critique, "Überarbeitungshinweise")
    parts = []
    if facts and "keine probleme" not in facts.lower():
        parts.append(f"**Fakten-Probleme:**\n{facts}")
    if parent and "liest sich gut" not in parent.lower():
        parts.append(f"**Leser-Perspektive:**\n{parent}")
    if instruct:
        parts.append(f"**Konkrete Hinweise:**\n{instruct}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Persist notes
# ---------------------------------------------------------------------------

def save_redteam_notes(subject: str, entries: list[dict]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Red Team Notizen — {timestamp}", f"\n## Newsletter: {subject}\n"]
    for e in entries:
        lines += [f"---\n", f"### Iteration {e['iteration']}\n", f"\n{e['critique']}\n"]
    if entries:
        last = entries[-1]
        verdict = parse_verdict(last["critique"])
        if verdict == "FREIGEGEBEN":
            lines.append(f"\n✅ Freigegeben nach {len(entries)} Iteration(en).")
        else:
            lines.append(f"\n⚠️  Max Iterationen erreicht — beste Version wird verwendet.")
    REDTEAM_NOTES_FILE.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def run(client: anthropic.Anthropic | None = None) -> str:
    """Run the Red Team agent. Returns the final newsletter text."""
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("🔴 Red Team Agent startet...")

    archive   = read_file(NEWSLETTER_ARCHIVE)
    research  = read_file(RESEARCH_NOTES_FILE)
    learnings = read_file(LEARNINGS_FILE)
    voice     = read_file(VOICE_FILE)

    subject, newsletter = extract_latest_newsletter(archive)
    if not newsletter:
        print("  ⚠️  Kein Newsletter gefunden. Zuerst Newsletter Writer starten.")
        return ""

    entries: list[dict] = []
    prior_feedback = ""

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'─' * 60}")
        print(f"  Red Team — Iteration {iteration}/{MAX_ITERATIONS}")
        print(f"{'─' * 60}\n")

        if iteration > 1:
            archive = read_file(NEWSLETTER_ARCHIVE)
            _, newsletter = extract_latest_newsletter(archive)

        prompt = build_critique_prompt(
            newsletter, research, learnings, voice, iteration, prior_feedback,
        )

        critique = stream_claude(
            client, model=MODEL, system=SYSTEM_PROMPT,
            user_message=prompt, max_tokens=1500,
        )
        entries.append({"iteration": iteration, "critique": critique})
        save_redteam_notes(subject, entries)

        verdict = parse_verdict(critique)

        if verdict == "FREIGEGEBEN":
            print(f"  ✅ FREIGEGEBEN in Iteration {iteration}")
            break

        if iteration == MAX_ITERATIONS:
            print(f"  ⚠️  Max Iterationen — aktuelle Version wird verwendet")
            break

        revision_instructions = parse_revision_instructions(critique)
        prior_feedback = revision_instructions

        print(f"\n  ↩️  ÜBERARBEITEN — Newsletter Writer wird neu gestartet...")
        from agents.newsletter_writer import run as write_newsletter
        write_newsletter(client, redteam_feedback=revision_instructions, revision=True)

    print(f"\n  ✅ Red Team Notizen gespeichert: {REDTEAM_NOTES_FILE}")
    _, final = extract_latest_newsletter(read_file(NEWSLETTER_ARCHIVE))
    return final


if __name__ == "__main__":
    run()
