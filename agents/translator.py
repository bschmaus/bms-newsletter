"""
Translator Agent — BMS Newsletter
-----------------------------------
Translates the finished German newsletter into natural-sounding English
for the bilingual school community.

Reads  : data/newsletter_archive.md   (the finished German newsletter)
Writes : data/newsletter_english.md   (English translation)

Run standalone:
    python -m agents.translator
"""

import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MODEL,
    NEWSLETTER_ARCHIVE,
    NEWSLETTER_ENGLISH,
    read_file,
    ensure_data_dir,
)
from agents.utils import extract_latest_newsletter, stream_claude


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are translating the German newsletter of the Bilinguale Montessori Schule
(BMS) Ingelheim into English for the bilingual school community. The translation
should feel as if it was originally written in English — natural, warm, and
articulate.

## Translation Rules
- Keep "BMS" as-is — it is the school's abbreviation
- Montessori terminology — use standard English equivalents:
  - Lerngruppe → learning group
  - Lernbegleiter:in → learning guide
  - Stufe 1–3 → Level 1–3
  - Erdkinderplan → Erdkinder plan (Maria Montessori's term, keep as-is)
- German event names: keep the German title, add English explanation in parentheses
  if not self-explanatory
- Maintain the same tone: sophisticated, personal, warm — like a quality magazine
- Preserve ALL links and URLs exactly as they are
- Do not add, remove, or reinterpret any content
- German "Sie-Form" → use "you" naturally
- Preserve the exact structure: subject line, sections, headings, bullet lists
- The subject line should be translated too (as "**Subject:** ...")
- Maria Montessori quotes: use the established English translation if one exists,
  otherwise translate faithfully and note the source

## Output
Output ONLY the translated newsletter text — no meta-comments, no explanations.
Begin with the translated subject line.
"""


def build_user_message(newsletter: str) -> str:
    return (
        "Translate the following German newsletter into English.\n\n"
        "---\n\n"
        f"{newsletter}\n\n"
        "---\n\n"
        "Translate now. Begin with the subject line."
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def run(client: anthropic.Anthropic | None = None, *, emit=None) -> str:
    """Run the translator agent. Returns the English newsletter text.

    emit: optional callable(str) forwarded to stream_claude for SSE streaming.
    """
    ensure_data_dir()

    if client is None:
        client = anthropic.Anthropic()

    print("🌐 Translator Agent startet...")

    archive = read_file(NEWSLETTER_ARCHIVE)
    subject, newsletter = extract_latest_newsletter(archive)

    if not newsletter:
        print("  ⚠️  Kein Newsletter gefunden. Zuerst die Pipeline starten.")
        return ""

    print(f"\n  Übersetze: {subject}\n")
    print("-" * 60)

    user_message = build_user_message(newsletter)
    english = stream_claude(
        client, model=MODEL, system=SYSTEM_PROMPT,
        user_message=user_message, max_tokens=4000, emit=emit,
    )
    print("-" * 60 + "\n")

    NEWSLETTER_ENGLISH.write_text(english, encoding="utf-8")
    print(f"  ✅ Englische Version gespeichert: {NEWSLETTER_ENGLISH}")

    return english


if __name__ == "__main__":
    run()
