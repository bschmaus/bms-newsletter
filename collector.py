"""
Content Collector — BMS Newsletter
------------------------------------
Runs every 14 days (via cron or manually) to collect Montessori and education
news from worldwide sources. Accumulates content in data/content_pool.md for
the next newsletter edition.

Sends an email notification when new content is found.

Usage:
    python collector.py                  # run once, send email if new content

Cron setup (every 14 days at 8:00 AM):
    0 8 */14 * * cd /path/to/bms-newsletter && python collector.py >> /tmp/bms-collector.log 2>&1
"""

import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    MODEL,
    BMS_NEWS_URL,
    EXTRA_MONTESSORI_SOURCES,
    RSS_FEEDS_BILDUNG,
    EXTRA_BILDUNG_SOURCES,
    CONTENT_POOL_FILE,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    NOTIFY_EMAIL,
    read_file,
    ensure_data_dir,
)
from agents.scanning import fetch_bms_articles, fetch_feed, fetch_page, format_feed_entries
from agents.utils import stream_claude


# ---------------------------------------------------------------------------
# Collect content from all sources
# ---------------------------------------------------------------------------

def collect_raw() -> str:
    """Fetch all sources and return combined raw content as markdown."""
    sections = []

    print("  🏫 BMS News...")
    bms = fetch_bms_articles(BMS_NEWS_URL)
    if bms.strip():
        sections.append(f"## BMS News\n{bms}")

    print("  🌍 Montessori-Quellen...")
    for url in EXTRA_MONTESSORI_SOURCES:
        print(f"    🌐 {url}")
        text = fetch_page(url, max_chars=3000)
        if text.strip():
            domain = url.split("/")[2]
            sections.append(f"## {domain}\nURL: {url}\n{text}")

    print("  📰 Bildungspolitik RSS...")
    for url in RSS_FEEDS_BILDUNG:
        print(f"    📡 {url}")
        entries = fetch_feed(url)
        if entries:
            sections.append(format_feed_entries(entries, url.split("/")[2]))

    print("  🏛️  Bildungspolitik Websites...")
    for url in EXTRA_BILDUNG_SOURCES:
        print(f"    🌐 {url}")
        text = fetch_page(url, max_chars=2000)
        if text.strip():
            domain = url.split("/")[2]
            sections.append(f"## {domain}\nURL: {url}\n{text}")

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Deduplicate against existing pool
# ---------------------------------------------------------------------------

def deduplicate(new_content: str, existing_pool: str,
                client: anthropic.Anthropic) -> str:
    """Use Claude to identify genuinely new items not already in the pool."""
    if not existing_pool.strip() or "_Noch kein Content._" in existing_pool:
        return new_content

    system = (
        "Du bist ein Redaktionsassistent. Vergleiche die NEUEN Inhalte mit dem "
        "BESTEHENDEN Pool. Extrahiere NUR die Inhalte, die wirklich NEU sind "
        "(nicht bereits im Pool enthalten oder sehr ähnlich). "
        "Ausgabe: Nur die neuen Inhalte als Markdown. Wenn nichts neu ist: "
        "'Keine neuen Inhalte gefunden.'"
    )
    user_msg = (
        f"## Bestehender Content Pool\n{existing_pool[:6000]}\n\n"
        f"---\n\n"
        f"## Neue Inhalte (prüfen)\n{new_content[:8000]}"
    )
    return stream_claude(
        client, model=MODEL, system=system,
        user_message=user_msg, max_tokens=3000,
    )


# ---------------------------------------------------------------------------
# Email notification
# ---------------------------------------------------------------------------

def send_notification(digest: str) -> None:
    """Send email digest via SMTP."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        print("  ⚠️  SMTP nicht konfiguriert — keine Email gesendet.")
        print("     Bitte SMTP_HOST, SMTP_USER, SMTP_PASSWORD und NOTIFY_EMAIL in .env setzen.")
        return

    today = datetime.now().strftime("%d.%m.%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BMS Newsletter — Neue Inhalte gesammelt ({today})"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(digest, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"  📧 Email gesendet an {NOTIFY_EMAIL}")
    except Exception as exc:
        print(f"  ❌ Email-Versand fehlgeschlagen: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ensure_data_dir()
    client = anthropic.Anthropic()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"📥 Content Collector startet — {timestamp}")
    print()

    raw = collect_raw()
    if not raw.strip():
        print("\n  ⚠️  Keine Inhalte gefunden.")
        return

    existing_pool = read_file(CONTENT_POOL_FILE)

    print("\n  🔍 Dedupliziere gegen bestehenden Pool...")
    new_items = deduplicate(raw, existing_pool, client)

    if "keine neuen inhalte" in new_items.lower():
        print("\n  ℹ️  Keine neuen Inhalte seit letztem Lauf.")
        return

    # Append to pool
    entry = f"\n\n---\n\n## Gesammelt: {timestamp}\n\n{new_items}\n"
    if not CONTENT_POOL_FILE.exists() or "_Noch kein Content._" in existing_pool:
        CONTENT_POOL_FILE.write_text(
            f"# Content Pool — BMS Newsletter\n{entry}",
            encoding="utf-8",
        )
    else:
        with open(CONTENT_POOL_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    print(f"\n  ✅ Content Pool aktualisiert: {CONTENT_POOL_FILE}")

    # Build email digest
    digest = (
        f"BMS Newsletter Content Collector — {timestamp}\n"
        f"{'=' * 50}\n\n"
        f"Neue Inhalte gefunden:\n\n"
        f"{new_items}\n\n"
        f"{'=' * 50}\n"
        f"Der vollständige Pool liegt in: data/content_pool.md\n"
        f"Newsletter erstellen: python orchestrator.py\n"
    )
    send_notification(digest)

    print("\n📥 Content Collector fertig.")


if __name__ == "__main__":
    main()
