"""
BMS Newsletter Pipeline
-----------------------
Automated newsletter generation for the Bilinguale Montessori Schule Ingelheim.

  1. Scanning       — scrape BMS website + Montessori sources
  2. Writer         — compose the newsletter draft (German)
  3. Red Team       — quality & tone check for parents
  4. Assessment     — learn from the edition for next time
  5. Translator     — translate newsletter to English
  6. HTML Formatter — convert bilingual newsletter to styled HTML email

Human steps (outside this pipeline):
  • Review the HTML in data/newsletter.html
  • Copy-paste into Outlook and send

Usage:
    python orchestrator.py                     # full pipeline
    python orchestrator.py --from scan         # restart from scanning
    python orchestrator.py --from write        # restart from writer
    python orchestrator.py --only html         # re-run HTML formatter only
    python orchestrator.py --only assess       # re-run assessment only

Available agent names: scan, write, redteam, assess, translate, html
"""

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))

from agents import scanning, newsletter_writer, red_team, assessment, translator, html_formatter
from config import CONTENT_POOL_FILE

AGENT_NAMES = ["scan", "write", "redteam", "assess", "translate", "html"]


def _notify(title: str, message: str) -> None:
    """Send a macOS notification (no-op on Linux)."""
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


def _make_emit(label: str, emit):
    """Wrap an emit callback to prefix tokens with the agent label."""
    if emit is None:
        return None
    def _emit(text: str):
        emit(f"[{label}]{text}")
    return _emit


def run_pipeline(
    start_from: str | None = None,
    only: str | None = None,
    *,
    # Web-UI parameters
    scan_from: str | None = None,
    extra_urls: list[str] | None = None,
    red_thread: str = "",
    review_feedback: str = "",
    emit=None,
    # Pause between scan and write (web UI review step)
    pause_after_scan: threading.Event | None = None,
) -> None:
    """
    Run the newsletter pipeline.

    scan_from:        Date string "YYYY-MM-DD" — only consider content from this date.
    extra_urls:       Additional URLs to scan.
    red_thread:       Editorial direction injected into the writer.
    review_feedback:  Structured topic decisions from the web UI review step.
    emit:             Token callback for SSE streaming.
    pause_after_scan: threading.Event — if given, pipeline blocks after scan
                      until event is set (used by web server for review step).
    """
    client = anthropic.Anthropic()

    if only:
        match = [(n, label, fn) for n, label, fn in _build_agents() if n == only]
        if not match:
            print(f"Unbekannter Agent '{only}'. Verfügbar: {', '.join(AGENT_NAMES)}")
            sys.exit(1)
        name, label, fn = match[0]
        banner(f"Starte: {label}")
        t0 = time.time()
        _call_agent(name, fn, client,
                    scan_from=scan_from, extra_urls=extra_urls,
                    red_thread=red_thread, review_feedback=review_feedback,
                    emit=_make_emit(name, emit))
        banner(f"✅ {label} fertig ({time.time() - t0:.1f}s)")
        return

    start_idx = 0
    if start_from:
        agents = _build_agents()
        indices = [i for i, (n, _, _) in enumerate(agents) if n == start_from]
        if not indices:
            print(f"Unbekannter Agent '{start_from}'. Verfügbar: {', '.join(AGENT_NAMES)}")
            sys.exit(1)
        start_idx = indices[0]

    banner("BMS Newsletter Pipeline — Start")
    total_start = time.time()

    agents = _build_agents()
    for i, (name, label, fn) in enumerate(agents):
        if i < start_idx:
            print(f"  ⏭  Überspringe {label}")
            continue

        banner(f"Schritt {i + 1}/{len(agents)}: {label}")
        t0 = time.time()
        try:
            _call_agent(name, fn, client,
                        scan_from=scan_from, extra_urls=extra_urls,
                        red_thread=red_thread, review_feedback=review_feedback,
                        emit=_make_emit(name, emit))
        except Exception as exc:
            print(f"\n  ❌ {label} fehlgeschlagen: {exc}")
            print(f"     Fortsetzen mit: python orchestrator.py --from {name}")
            if emit:
                emit(f"[error]{exc}")
            raise
        print(f"\n  ✅ {label} fertig ({time.time() - t0:.1f}s)")

        # Pause after scan if web UI review is requested
        if name == "scan" and pause_after_scan is not None:
            print("\n  ⏸  Warte auf Review-Freigabe...")
            if emit:
                emit("[review]__PAUSE__")
            pause_after_scan.wait()
            print("  ▶  Review abgeschlossen — Writing startet")

    # Auto-reset content pool after full pipeline run
    if CONTENT_POOL_FILE.exists():
        pool_text = CONTENT_POOL_FILE.read_text(encoding="utf-8").strip()
        if pool_text and "_Noch kein Content._" not in pool_text:
            CONTENT_POOL_FILE.write_text(
                "# Content Pool — BMS Newsletter\n\n_Noch kein Content._\n",
                encoding="utf-8",
            )
            print("  🗑️  Content Pool geleert (wurde in Newsletter verarbeitet)")

    elapsed = time.time() - total_start
    banner(f"🎉 Pipeline fertig! Gesamtzeit: {elapsed:.0f}s")
    _notify("BMS Newsletter ✍️", "Newsletter ist fertig — HTML prüfen und versenden.")
    if emit:
        emit("[done]__DONE__")
    print("  Nächste Schritte:")
    print("  1. Prüfen  : data/newsletter.html (im Browser öffnen)")
    print("  2. HTML in Outlook einfügen und versenden")
    print()


def _build_agents():
    """Return the agent list (deferred import to allow patching in tests)."""
    return [
        ("scan",      "Scanning",           scanning.run),
        ("write",     "Newsletter Writer",  newsletter_writer.run),
        ("redteam",   "Red Team",           red_team.run),
        ("assess",    "Assessment",         assessment.run),
        ("translate", "Translator",         translator.run),
        ("html",      "HTML Formatter",     html_formatter.run),
    ]


def _call_agent(name: str, fn, client, *,
                scan_from, extra_urls, red_thread, review_feedback, emit):
    """Call the right agent with the right kwargs."""
    if name == "scan":
        fn(client, scan_from=scan_from, extra_urls=extra_urls, emit=emit)
    elif name == "write":
        fn(client, red_thread=red_thread, review_feedback=review_feedback, emit=emit)
    else:
        fn(client, emit=emit)


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
