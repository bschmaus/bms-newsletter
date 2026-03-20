"""Shared configuration and file paths for BMS Newsletter."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR             = Path(__file__).parent
DATA_DIR             = BASE_DIR / "data"

LEARNINGS_FILE       = DATA_DIR / "learnings.md"
NEWSLETTER_ARCHIVE   = DATA_DIR / "newsletter_archive.md"
RESEARCH_NOTES_FILE  = DATA_DIR / "research_notes.md"
VOICE_FILE           = DATA_DIR / "voice.md"
REDTEAM_NOTES_FILE   = DATA_DIR / "redteam_notes.md"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html, application/xhtml+xml, */*",
}

MODEL = "claude-sonnet-4-6"

# --- BMS school website ---
BMS_NEWS_URL    = "https://bilinguale-montessori-schule.de/de/aktuelles/news-de"
BMS_TERMINE_URL = "https://bilinguale-montessori-schule.de/de/aktuelles/termine"

# --- Montessori-Quellen (Schulen, Verbände, Organisationen) ---
RSS_FEEDS_MONTESSORI = [
    "https://www.montessori-deutschland.de/feed/",           # Montessori Bundesverband
    "https://montessori-europe.com/feed/",                   # Montessori Europe
]

EXTRA_MONTESSORI_SOURCES = [
    "https://montessori-ami.org/news",                       # AMI — international
    "https://www.namta.org/news",                            # NAMTA — North American Montessori
]

# --- Bildungspolitik-Quellen ---
RSS_FEEDS_BILDUNG = [
    "https://www.deutsches-schulportal.de/feed/",            # Schulportal — Robert Bosch Stiftung
    "https://bildungsklick.de/rss/bildungsklick.xml",        # bildungsklick — Bildungsnachrichten
]

EXTRA_BILDUNG_SOURCES = [
    "https://www.kmk.org",                                   # Kultusministerkonferenz
    "https://bm.rlp.de/de/startseite/",                     # Bildungsministerium RLP
]

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def read_file(path: Path) -> str:
    """Read a shared data file. Returns empty string if missing."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def ensure_data_dir() -> None:
    """Create data/ and initialise empty shared files if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    defaults = {
        LEARNINGS_FILE:      "# Learnings & Verbesserungen\n\n_Noch keine Learnings._\n",
        NEWSLETTER_ARCHIVE:  "# Newsletter-Archiv\n\n_Noch keine Newsletter._\n",
        RESEARCH_NOTES_FILE: "# Recherche-Notizen\n\n_Noch keine Recherche._\n",
    }
    for path, content in defaults.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
