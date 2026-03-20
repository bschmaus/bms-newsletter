"""
Assessment Agent — BMS Newsletter
-----------------------------------
Reflects on the completed newsletter and writes learnings for future issues.

Reads  : data/newsletter_archive.md  (the finished newsletter)
         data/research_notes.md      (the research it was based on)
         data/learnings.md           (existing learnings)
Writes : data/learnings.md           (appends new learnings)

Run standalone:
    python -m agents.assessment
"""

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
    read_file,
    ensure_data_dir,
)
from agents.utils import extract_latest_newsletter, stream_claude


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du bist ein erfahrener Newsletter-Redakteur, der den BMS-Newsletter
einer Montessori-Schule bewertet. Dein Ziel: konkrete, umsetzbare Tipps,
die den nächsten Newsletter besser machen.

Sei ehrlich und spezifisch. Vages Lob ist nutzlos. Vage Kritik auch.
Schreibe auf Deutsch. Ton: direkt, kollegial, konstruktiv."""


def build_prompt(newsletter: str, research: str, existing_learnings: str) -> str:
    return textwrap.dedent(f"""
        ## Das Recherche-Material (worauf der Newsletter basiert)
        {research or "_Nicht verfügbar._"}

        ## Der fertige Newsletter
        {newsletter or "_Kein Newsletter vorhanden._"}

        ## Bisherige Learnings (nicht wiederholen was schon erfasst ist)
        {existing_learnings or "_Noch keine._"}

        ---

        Bewerte den Newsletter. Nutze GENAU dieses Format:

        ### Was gut funktioniert hat
        - [konkreter Punkt]

        ### Was besser sein könnte
        - [konkreter Punkt]

        ### Tonalität & Sprache
        - [Beobachtung zu Ton, Wortwahl, Authentizität]

        ### Anweisungen für zukünftige Newsletter
        - [Umsetzbare Regel: "Immer...", "Nie...", "Wenn das Thema X ist, dann Y"]
    """).strip()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def run(client: anthropic.Anthropic | None = None) -> str:
    """Run the assessment agent. Returns the new learnings as a string."""
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("📝 Assessment Agent startet...")

    archive   = read_file(NEWSLETTER_ARCHIVE)
    research  = read_file(RESEARCH_NOTES_FILE)
    existing  = read_file(LEARNINGS_FILE)

    subject, newsletter = extract_latest_newsletter(archive)

    if not newsletter:
        print("  ⚠️  Kein Newsletter gefunden. Zuerst die Pipeline starten.")
        return ""

    print(f"\n  Bewerte: {subject}\n")
    print("-" * 60)

    prompt = build_prompt(newsletter, research, existing)
    assessment_body = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=prompt, max_tokens=2000,
    )
    print("-" * 60 + "\n")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n---\n\n## Bewertung: {subject}\n_Bewertet: {timestamp}_\n\n{assessment_body}\n"

    current = read_file(LEARNINGS_FILE)
    if "_Noch keine Learnings._" in current:
        updated = f"# Learnings & Verbesserungen\n{entry}"
    else:
        updated = current.rstrip() + "\n" + entry

    LEARNINGS_FILE.write_text(updated, encoding="utf-8")
    print(f"  ✅ Learnings aktualisiert: {LEARNINGS_FILE}")

    return assessment_body


if __name__ == "__main__":
    run()
