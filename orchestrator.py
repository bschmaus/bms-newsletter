"""
BMS Newsletter Pipeline
-----------------------
Automated newsletter generation for the Bilinguale Montessori Schule Ingelheim.

  1. Scanning       — scrape BMS website + Montessori sources
  2. Writer         — compose the newsletter draft
  3. Red Team       — quality & tone check for parents
  4. Assessment     — learn from the edition for next time
  5. HTML Formatter — convert newsletter to styled HTML email

Human steps (outside this pipeline):
  • Review the HTML in data/newsletter.html
  • Copy-paste into Outlook and send

Usage:
    python orchestrator.py                     # full pipeline
    python orchestrator.py --from scan         # restart from scanning
    python orchestrator.py --from write        # restart from writer
    python orchestrator.py --only html         # re-run HTML formatter only
    python orchestrator.py --only assess       # re-run assessment only

Available agent names: scan, write, redteam, assess, html
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))

from agents import scanning, newsletter_writer, red_team, assessment, html_formatter

AGENTS = [
    ("scan",     "Scanning",           scanning.run),
    ("write",    "Newsletter Writer",  newsletter_writer.run),
    ("redteam",  "Red Team",           red_team.run),
    ("assess",   "Assessment",         assessment.run),
    ("html",     "HTML Formatter",     html_formatter.run),
]

AGENT_NAMES = [name for name, _, _ in AGENTS]


def _notify(title: str, message: str) -> None:
    """Send a macOS notification."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}" sound name "Glass"'],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


def banner(text: str, width: int = 68) -> None:
    print("\n" + "═" * width)
    print(f"  {text}")
    print("═" * width)


def run_pipeline(start_from: str | None = None, only: str | None = None) -> None:
    client = anthropic.Anthropic()

    if only:
        match = [(n, label, fn) for n, label, fn in AGENTS if n == only]
        if not match:
            print(f"Unbekannter Agent '{only}'. Verfügbar: {', '.join(AGENT_NAMES)}")
            sys.exit(1)
        name, label, fn = match[0]
        banner(f"Starte: {label}")
        t0 = time.time()
        fn(client)
        banner(f"✅ {label} fertig ({time.time() - t0:.1f}s)")
        return

    start_idx = 0
    if start_from:
        indices = [i for i, (n, _, _) in enumerate(AGENTS) if n == start_from]
        if not indices:
            print(f"Unbekannter Agent '{start_from}'. Verfügbar: {', '.join(AGENT_NAMES)}")
            sys.exit(1)
        start_idx = indices[0]

    banner("BMS Newsletter Pipeline — Start")
    total_start = time.time()

    for i, (name, label, fn) in enumerate(AGENTS):
        if i < start_idx:
            print(f"  ⏭  Überspringe {label}")
            continue

        banner(f"Schritt {i + 1}/{len(AGENTS)}: {label}")
        t0 = time.time()
        try:
            fn(client)
        except Exception as exc:
            print(f"\n  ❌ {label} fehlgeschlagen: {exc}")
            print(f"     Fortsetzen mit: python orchestrator.py --from {name}")
            sys.exit(1)
        print(f"\n  ✅ {label} fertig ({time.time() - t0:.1f}s)")

    elapsed = time.time() - total_start
    banner(f"🎉 Pipeline fertig! Gesamtzeit: {elapsed:.0f}s")
    _notify("BMS Newsletter ✍️", "Newsletter ist fertig — HTML prüfen und versenden.")
    print("  Nächste Schritte:")
    print("  1. Prüfen  : data/newsletter.html (im Browser öffnen)")
    print("  2. HTML in Outlook einfügen und versenden")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BMS Newsletter Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Agent-Namen: {', '.join(AGENT_NAMES)}",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--from", dest="start_from", metavar="AGENT",
        help="Pipeline ab diesem Agent starten",
    )
    group.add_argument(
        "--only", metavar="AGENT",
        help="Nur diesen einen Agent ausführen",
    )
    args = parser.parse_args()
    run_pipeline(start_from=args.start_from, only=args.only)


if __name__ == "__main__":
    main()
