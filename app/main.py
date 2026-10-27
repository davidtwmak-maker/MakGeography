"""
MakGeography — DSE Geography study site.

Four sections:
  1. News Corner      — geography news tagged by elective
  2. Notes            — CP1–CP7 + EP1, scaffolded by curriculum sub-questions
  3. MC Drilling      — practice questions with a mistake report
  4. Chatbot          — answers grounded in the MakGeography notes

The whole site is behind a shared password.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .kb import KnowledgeBase
from . import llm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="MakGeography", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_password_cache: str | None = None


def _load_password() -> str:
    """The site password.

    Read from MAKGEO_PASSWORD in the environment, or from MAKGEO_PASSWORD in
    ~/.hermes/.env. There is deliberately NO built-in default: a password
    committed to a public repository is not a password.

    Resolved lazily and cached, so importing the module (CI, tooling) does not
    require a password to be configured.
    """
    global _password_cache
    if _password_cache:
        return _password_cache
    p = os.environ.get("MAKGEO_PASSWORD", "").strip()
    if p:
        _password_cache = p
        return p
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        import re
        m = re.search(r"^MAKGEO_PASSWORD=(.+)$", env.read_text(), re.M)
        if m:
            _password_cache = m.group(1).strip().strip("'\"")
            return _password_cache
    raise RuntimeError(
        "MAKGEO_PASSWORD is not set. Export it, or add it to ~/.hermes/.env. "
        "There is no default password on purpose."
    )


# The password is resolved lazily, on first use. Importing the module must not
# require a password — CI and tooling need to import the app without one.
SESSION_COOKIE = "makgeo_session"
SESSION_TTL = 60 * 60 * 12  # 12 hours

# ---------------------------------------------------------------------------
# Session store (in-process; single-worker deployment)
# ---------------------------------------------------------------------------

_sessions: dict[str, float] = {}

# Rate limit: max N questions per session per minute, to protect the API key.
RATE_LIMIT = 12
RATE_WINDOW = 60
_rate: dict[str, list[float]] = {}


def new_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time()
    return token


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    created = _sessions.get(token)
    if not created:
        return False
    if time.time() - created > SESSION_TTL:
        _sessions.pop(token, None)
        return False
    return True


def check_rate(session: str) -> bool:
    now = time.time()
    hits = [t for t in _rate.get(session, []) if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        _rate[session] = hits
        return False
    hits.append(now)
    _rate[session] = hits
    return True


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase(DATA_DIR / "kb.json")
    return _kb


def load_json(name: str, default):
    p = DATA_DIR / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def require_auth(request: Request):
    if not session_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="Not signed in.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not session_valid(request.cookies.get(SESSION_COOKIE)):
        return templates.TemplateResponse(request, "login.html")
    return templates.TemplateResponse(request, "index.html")


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if hmac.compare_digest(password.strip(), _load_password()):
        token = new_session()
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax",
            max_age=SESSION_TTL, secure=False,
        )
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": "Wrong password."}, status_code=401
    )


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _sessions.pop(token, None)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ------------------------------- API ---------------------------------------

class AskPayload(BaseModel):
    question: str
    topic: str | None = None
    history: list[dict] | None = None


@app.post("/api/ask")
def api_ask(request: Request, payload: AskPayload):
    require_auth(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not check_rate(token):
        raise HTTPException(status_code=429, detail="Too many questions — wait a minute.")

    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty question.")
    if len(q) > 1200:
        raise HTTPException(status_code=400, detail="Question too long (max 1200 characters).")

    kb = get_kb()
    results = kb.search(q, k=7, topic=payload.topic)
    if not results:
        return {
            "answer": "I could not find anything on that in the MakGeography notes. "
                      "Try naming the elective (CP1–CP7, EP1) or a syllabus term.",
            "sources": [],
            "grounded": False,
        }

    context = llm.build_context(results)
    messages = [{"role": "system", "content": llm.SYSTEM_PROMPT.format(context=context)}]
    for h in (payload.history or [])[-6:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": q})

    res = llm.chat(messages)
    if not res["ok"]:
        return {"answer": None, "error": res["error"], "sources": [], "grounded": False}

    sources = [
        {
            "title": c.title,
            "heading": c.heading,
            "topic": c.topic,
            "path": c.path,
            "score": round(s, 2),
        }
        for c, s in results
    ]
    return {"answer": res["content"], "sources": sources, "grounded": True}


@app.get("/api/kb/status")
def kb_status(request: Request):
    require_auth(request)
    kb = get_kb()
    return {
        "docs": kb.meta.get("n_docs"),
        "chunks": kb.meta.get("n_chunks"),
        "built_at": kb.meta.get("built_at"),
        "topics": kb.topics,
    }


@app.get("/api/notes")
def api_notes(request: Request, topic: str | None = None):
    """Curriculum-scaffolded notes.

    Returns the official elective/sub-question/leaf structure, with the real
    MakGeography note content matched into each leaf via its source hints.
    """
    require_auth(request)
    kb = get_kb()
    curriculum = load_json("curriculum.json", {"electives": []})
    want = (topic or "ALL").upper()

    # Index the KB by note title (lowercased) and by section heading, so a
    # hint can point at either a whole note or one section inside it.
    by_title: dict[str, list] = {}
    by_heading: dict[str, list] = {}
    for c in kb.chunks:
        by_title.setdefault(c.title.lower(), []).append(c)
        h = (c.heading or "").lower().strip()
        if h:
            by_heading.setdefault(h, []).append(c)

    def match(hints: list[str]) -> list[dict]:
        found: dict[str, dict] = {}
        for hint in hints:
            hl = hint.lower()
            for c in by_title.get(hl, []):
                found[c.doc_id + "#" + str(c.n)] = {
                    "title": c.title, "heading": c.heading, "text": c.text,
                    "n": c.n, "path": c.path,
                }
            # section heading inside a note (fuzzy: exact, then contains)
            for head, chunks in by_heading.items():
                if head == hl or hl in head or head in hl:
                    for c in chunks:
                        found[c.doc_id + "#" + str(c.n)] = {
                            "title": c.title, "heading": c.heading, "text": c.text,
                            "n": c.n, "path": c.path,
                        }
        return sorted(found.values(), key=lambda s: (s["title"], s["n"]))

    electives = []
    for el in curriculum.get("electives", []):
        code = el.get("code", "")
        if want != "ALL" and code.upper() != want:
            continue
        subqs = []
        for sq in el.get("subquestions", []):
            leaves = []
            for leaf in sq.get("leaves", []):
                content = match(leaf.get("source_hints", []))
                leaves.append({
                    "id": leaf.get("id"),
                    "title": leaf.get("title"),
                    "summary": leaf.get("summary"),
                    "content": content,
                })
            subqs.append({
                "number": sq.get("number"),
                "title": sq.get("title"),
                "leaves": leaves,
            })
        electives.append({
            "code": code,
            "title": el.get("title"),
            "module": el.get("module"),
            "question": el.get("question"),
            "subquestions": subqs,
        })

    return {
        "electives": electives,
        "topics": kb.topics,
        "kb_topics": kb.topics,
    }


@app.get("/api/news")
def api_news(request: Request, topic: str | None = None):
    require_auth(request)
    items = load_json("news.json", [])
    want = (topic or "ALL").upper()
    if want != "ALL":
        items = [i for i in items if want in [t.upper() for t in i.get("topics", [])]]
    items.sort(key=lambda i: i.get("published", ""), reverse=True)
    return {"items": items, "updated_at": load_json("news_meta.json", {}).get("updated_at")}


@app.get("/api/mc")
def api_mc(request: Request, topic: str | None = None, limit: int = 20,
           subtopic: str | None = None):
    require_auth(request)
    bank = load_json("mc_bank.json", {"questions": []})
    qs = bank.get("questions", [])
    want = (topic or "ALL").upper()
    if want != "ALL":
        qs = [q for q in qs if want in [t.upper() for t in q.get("topics", [])]]
    if subtopic:
        qs = [q for q in qs if q.get("subtopic") == subtopic]
    # A stable id per question lets the browser remember which ones were wrong.
    # Older banks may not carry one, so derive it here rather than trust the file.
    for q in qs:
        if not q.get("id"):
            q["id"] = f"{q.get('subtopic', 'gen')}-" + hashlib.sha1(
                q.get("stem", "").encode()).hexdigest()[:8]
    return {"questions": qs[:limit], "total": len(qs)}


# --------------------------- static + error -------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    return JSONResponse({"error": "Not signed in."}, status_code=401)
