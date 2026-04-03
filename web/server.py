"""
BMS Newsletter Web Server
--------------------------
FastAPI application exposing the newsletter pipeline via HTTP.

Endpoints:
  GET  /                    — Web UI
  POST /api/run             — Start pipeline (Phase A: scan + optional pause for review)
  GET  /api/stream          — SSE token stream for pipeline output
  GET  /api/status          — Pipeline status {running, phase}
  GET  /api/research-notes  — Current research notes (for review UI)
  POST /api/approve         — Submit review + start Phase B (write → html)
  GET  /api/newsletter-html — Final newsletter HTML
  POST /api/collect         — Trigger content collector
  GET  /api/collect/stream  — SSE stream for collector output

Run:
    uvicorn web.server:app --host 0.0.0.0 --port 8000 --workers 1
    (--workers 1 required: PipelineState lives in process memory)
"""

import asyncio
import json
import queue
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    WEB_USER, WEB_PASS,
    RESEARCH_NOTES_FILE, NEWSLETTER_HTML,
    read_file,
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

security = HTTPBasic()


def require_auth(creds: Annotated[HTTPBasicCredentials, Depends(security)]):
    if not WEB_PASS:
        raise HTTPException(
            status_code=500,
            detail="WEB_PASS nicht gesetzt — bitte .env konfigurieren.",
        )
    ok_user = secrets.compare_digest(creds.username.encode(), WEB_USER.encode())
    ok_pass = secrets.compare_digest(creds.password.encode(), WEB_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Basic"},
            detail="Ungültige Zugangsdaten",
        )


Auth = Annotated[None, Depends(require_auth)]

# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

_DONE_SENTINEL   = object()
_REVIEW_SENTINEL = object()
_ERROR_SENTINEL  = object()


class PipelineState:
    def __init__(self):
        self.lock         = threading.Lock()
        self.running      = False
        self.phase        = "idle"       # idle | scanning | review | writing | done | error
        self.token_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.review_event = threading.Event()
        self.review_data: dict = {}

    def acquire(self) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.phase   = "scanning"
            self.token_queue = queue.SimpleQueue()
            self.review_event.clear()
            self.review_data  = {}
            return True

    def release(self, phase: str = "done"):
        with self.lock:
            self.running = False
            self.phase   = phase

    def emit(self, text: str):
        """Called from pipeline thread for each token."""
        if text == "[review]__PAUSE__":
            with self.lock:
                self.phase = "review"
            self.token_queue.put(_REVIEW_SENTINEL)
        elif text == "[done]__DONE__":
            with self.lock:
                self.phase = "done"
            self.token_queue.put(_DONE_SENTINEL)
        elif text.startswith("[error]"):
            self.token_queue.put(_ERROR_SENTINEL)
        else:
            self.token_queue.put(text)


state = PipelineState()


class CollectorState:
    def __init__(self):
        self.lock    = threading.Lock()
        self.running = False
        self.token_queue: queue.SimpleQueue = queue.SimpleQueue()

    def acquire(self) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.token_queue = queue.SimpleQueue()
            return True

    def release(self):
        with self.lock:
            self.running = False
        self.token_queue.put(_DONE_SENTINEL)

    def emit(self, text: str):
        self.token_queue.put(text)


collector_state = CollectorState()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="BMS Newsletter", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _auth: Auth):
    from datetime import date, timedelta
    default_scan_from = (date.today() - timedelta(weeks=8)).isoformat()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "default_scan_from": default_scan_from,
            "pipeline_running":  state.running,
            "pipeline_phase":    state.phase,
        },
    )


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    scan_from:  str | None  = None
    extra_urls: list[str]   = []
    red_thread: str         = ""
    start_from: str | None  = None   # agent name to resume from


@app.post("/api/run")
async def start_run(req: RunRequest, _auth: Auth):
    if not state.acquire():
        raise HTTPException(status_code=409, detail="Pipeline läuft bereits.")

    pause_event = threading.Event()

    def _run():
        try:
            from orchestrator import run_pipeline
            run_pipeline(
                start_from      = req.start_from,
                scan_from       = req.scan_from,
                extra_urls      = req.extra_urls or [],
                red_thread      = req.red_thread,
                review_feedback = "",          # filled in after /api/approve
                emit            = state.emit,
                pause_after_scan= pause_event,
            )
        except Exception as exc:
            state.emit(f"[error]{exc}")
            state.release("error")

    # Store pause_event so /api/approve can set it
    state._pause_event = pause_event
    state._run_request  = req

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started"}


class ApproveRequest(BaseModel):
    topics:       list[dict] = []   # [{section, title, include, comment}]
    red_thread:   str        = ""
    extra_topics: list[dict] = []   # [{title, description}]


@app.post("/api/approve")
async def approve_review(req: ApproveRequest, _auth: Auth):
    if state.phase != "review":
        raise HTTPException(status_code=409, detail="Pipeline ist nicht im Review-Modus.")

    # Count included topics (scan + custom)
    included_count = sum(1 for t in req.topics if t.get("include", True))
    included_count += len([et for et in req.extra_topics if et.get("title", "").strip()])

    if included_count < 1:
        raise HTTPException(status_code=422, detail="Mindestens 1 Thema muss ausgewählt sein.")

    # Actually filter the research_notes.md — remove excluded topics, add custom ones
    _filter_research_notes(req.topics, req.red_thread, req.extra_topics)

    # Store for the writer and signal the pipeline to continue
    state.review_data = {
        "red_thread": req.red_thread or getattr(state._run_request, "red_thread", ""),
    }

    state._pause_event.set()

    with state.lock:
        state.phase = "writing"

    return {"status": "approved", "included": included_count}


def _filter_research_notes(topics: list[dict], red_thread: str, extra_topics: list[dict] | None = None):
    """Remove excluded topics from research_notes.md and add custom topics.

    This ensures the writer only sees the topics the editor approved.
    The original file is backed up as research_notes_unfiltered.md.
    """
    import re

    notes = read_file(RESEARCH_NOTES_FILE)

    # Backup original
    backup = RESEARCH_NOTES_FILE.parent / "research_notes_unfiltered.md"
    backup.write_text(notes, encoding="utf-8")

    # Collect titles of excluded topics
    excluded_titles = set()
    for t in topics:
        if not t.get("include", True):
            excluded_titles.add(t.get("title", "").strip())

    if excluded_titles:
        # Remove ### blocks for excluded topics
        # Each ### block runs until the next ### or ## or end of file
        filtered_lines = []
        skip = False
        for line in notes.split("\n"):
            # Check if this is a ### heading
            if line.startswith("### "):
                title = line[4:].strip()
                # Check if this title matches any excluded title
                skip = any(
                    excl.lower() in title.lower() or title.lower() in excl.lower()
                    for excl in excluded_titles
                )
                if skip:
                    continue
            # Stop skipping at next section boundary
            if skip and (line.startswith("## ") or line.startswith("### ")):
                skip = False
                if line.startswith("### "):
                    title = line[4:].strip()
                    skip = any(
                        excl.lower() in title.lower() or title.lower() in excl.lower()
                        for excl in excluded_titles
                    )
                    if skip:
                        continue
            if not skip:
                filtered_lines.append(line)

        notes = "\n".join(filtered_lines)

    # Remove empty sections (## Sektion with no ### underneath)
    notes = re.sub(
        r"(## Sektion \d+: [^\n]+\n---\n)\s*(?=## Sektion|\Z)",
        "",
        notes,
    )

    # Add editorial annotations
    annotation = "\n\n---\n\n## Redaktioneller Review\n"
    if red_thread.strip():
        annotation += f"\n**Roter Faden (manuell):** {red_thread.strip()}\n"

    # Include/exclude summary for writer context
    included = [t for t in topics if t.get("include", True)]
    excluded = [t for t in topics if not t.get("include", True)]
    if excluded:
        annotation += "\n**Vom Redakteur entfernte Themen (NICHT verwenden):**\n"
        for t in excluded:
            annotation += f"- ✗ {t.get('title', '?')}\n"
    for t in included:
        comment = t.get("comment", "").strip()
        if comment:
            annotation += f"\n**Hinweis zu »{t.get('title','')}«:** {comment}\n"

    # Add custom topics from editor
    if extra_topics:
        annotation += "\n\n## Zusätzliche Themen (vom Redakteur ergänzt)\n\n"
        for et in extra_topics:
            title = et.get("title", "").strip()
            desc = et.get("description", "").strip()
            if title:
                annotation += f"### {title}\n\n{desc}\n\n---\n\n"

    RESEARCH_NOTES_FILE.write_text(notes.rstrip() + annotation, encoding="utf-8")


@app.get("/api/status")
async def get_status(_auth: Auth):
    return {"running": state.running, "phase": state.phase}


@app.get("/api/research-notes")
async def get_research_notes(_auth: Auth):
    content = read_file(RESEARCH_NOTES_FILE)
    if not content.strip() or "_Noch keine Recherche._" in content:
        raise HTTPException(status_code=404, detail="Noch keine Research Notes vorhanden.")
    return {"content": content}


@app.get("/api/newsletter-html", response_class=HTMLResponse)
async def get_newsletter_html(_auth: Auth):
    if not NEWSLETTER_HTML.exists():
        raise HTTPException(status_code=404, detail="Noch kein Newsletter erstellt.")
    return HTMLResponse(NEWSLETTER_HTML.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# SSE stream — pipeline
# ---------------------------------------------------------------------------

@app.get("/api/stream")
async def stream_pipeline(_auth: Auth):
    async def _generator():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(
                    None, lambda: state.token_queue.get(timeout=0.1)
                )
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue

            if item is _DONE_SENTINEL:
                yield "event: done\ndata: {}\n\n"
                break
            if item is _REVIEW_SENTINEL:
                # Send current research notes with review event
                notes = read_file(RESEARCH_NOTES_FILE)
                payload = json.dumps({"notes": notes})
                yield f"event: review\ndata: {payload}\n\n"
                break
            if item is _ERROR_SENTINEL:
                yield "event: error\ndata: {}\n\n"
                break

            yield f"data: {json.dumps({'text': item})}\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Content collector
# ---------------------------------------------------------------------------

@app.post("/api/collect")
async def start_collector(_auth: Auth):
    if not collector_state.acquire():
        raise HTTPException(status_code=409, detail="Collector läuft bereits.")

    def _run():
        try:
            import collector as col
            # Patch collector's main to use our emit
            original_print = col.send_notification
            # Route output via emit
            import builtins
            original_builtins_print = builtins.print

            def _patched_print(*args, **kwargs):
                text = " ".join(str(a) for a in args)
                collector_state.emit(text + "\n")
                original_builtins_print(*args, **kwargs)

            builtins.print = _patched_print
            try:
                col.main()
            finally:
                builtins.print = original_builtins_print
        except Exception as exc:
            collector_state.emit(f"❌ Fehler: {exc}\n")
        finally:
            collector_state.release()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/api/collect/stream")
async def stream_collector(_auth: Auth):
    async def _generator():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(
                    None, lambda: collector_state.token_queue.get(timeout=0.1)
                )
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is _DONE_SENTINEL:
                yield "event: done\ndata: {}\n\n"
                break
            yield f"data: {json.dumps({'text': item})}\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
