"""
MakGeography — DSE Geography study site.

Four sections:
  1. News Corner      — geography news tagged by elective
  2. Notes            — CP1–CP7 + EP1, scaffolded by curriculum sub-questions
  3. MC Drilling      — practice questions with a mistake report
  4. Chatbot          — answers grounded in the MakGeography notes

The whole site is behind a sign-in. Students sign in with their own SID
and password (see app/roster.py); the teacher signs in with a separate
key. The roster also records who used the site.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .kb import KnowledgeBase
from .curriculum import CurriculumMatcher
from . import essay, llm, roster as roster_mod

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

    This is the FALLBACK gate, used when no roster exists. Once
    data/roster.json is present, students sign in with their own SID
    instead (see app/roster.py) and this shared password is only the
    teacher's own door.

    Resolved lazily and cached, so importing the module (CI, tooling) does
    not require a password to be configured.
    """
    global _password_cache
    if _password_cache:
        return _password_cache
    p = os.environ.get("MAKGEO_PASSWORD", "").strip()
    if p:
        _password_cache = p
        return p
    # On the teacher's Mac the password lives in ~/.hermes/.env; on a
    # deployed server it comes from the environment and the file is not
    # there. A missing file is normal, not an error.
    for candidate in (Path.home() / ".hermes" / ".env",
                       BASE_DIR / ".env"):
        try:
            if not candidate.is_file():
                continue
            import re
            m = re.search(r"^MAKGEO_PASSWORD=(.+)$",
                          candidate.read_text(), re.M)
        except OSError:
            continue
        if m:
            _password_cache = m.group(1).strip().strip("'\"")
            return _password_cache
    # No password configured means no gate. The site is open to everyone.
    # Set MAKGEO_PASSWORD to turn the gate back on.
    _password_cache = ""
    return ""


# The password is resolved lazily, on first use. Importing the module must not
# require a password — CI and tooling need to import the app without one.
#
# The gate is OPTIONAL. With no MAKGEO_PASSWORD set the site is open: every
# page and API works without signing in. Set a password to require one.
SESSION_COOKIE = "makgeo_session"
SESSION_TTL = 60 * 60 * 12  # 12 hours

# ---------------------------------------------------------------------------
# Session store (in-process; single-worker deployment)
# ---------------------------------------------------------------------------

# token -> (created_at, identity)
#
# The identity is who signed in: the SID, the name, the class, the role.
# It is kept in the session so every request knows who is asking - that is
# what makes the activity log possible.
_sessions: dict[str, tuple[float, dict]] = {}

# Rate limit: max N requests per client per minute, to protect the API key.
#
# The limit is per BUCKET as well as per client. The chatbot and the
# essay generator are different operations with different costs, and one
# must not spend the other's budget.
RATE_LIMIT = 12
RATE_WINDOW = 60
_rate: dict[str, list[float]] = {}


def new_session(identity: dict | None = None) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = (time.time(), identity or {})
    return token


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    entry = _sessions.get(token)
    if not entry:
        return False
    created = entry[0]
    if time.time() - created > SESSION_TTL:
        _sessions.pop(token, None)
        return False
    return True


def current_identity(request: Request) -> dict:
    """Who is making this request. Empty dict if nobody is signed in."""
    entry = _sessions.get(request.cookies.get(SESSION_COOKIE) or "")
    if not entry:
        return {}
    identity = entry[1]
    return identity if isinstance(identity, dict) else {}


def check_rate(session: str, limit: int = RATE_LIMIT, bucket: str = "ask") -> bool:
    """Rate limit per client, per bucket.

    The client key is the session token when there is one. With the
    password gate off, a visitor is not asked to log in, so there is no
    session token - and keying on None would put every visitor in the
    same bucket, where one person's 12 questions would lock out everyone
    else. The home page therefore hands every visitor a session token,
    so the limit is per browser.
    """
    now = time.time()
    key = f"{bucket}:{session or 'anonymous'}"
    hits = [t for t in _rate.get(key, []) if now - t < RATE_WINDOW]
    if len(hits) >= limit:
        _rate[key] = hits
        return False
    hits.append(now)
    _rate[key] = hits
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


_matcher: CurriculumMatcher | None = None


def get_matcher() -> CurriculumMatcher:
    """The curriculum-to-notes matcher, built once and reused."""
    global _matcher
    if _matcher is None:
        _matcher = CurriculumMatcher(get_kb())
    return _matcher


def load_json(name: str, default):
    p = DATA_DIR / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def password_required() -> bool:
    """True when the site is gated.

    The site is gated when a roster exists (students sign in with their
    SID) or when a shared password is configured (the fallback gate).
    With neither, the site is open, which is what the local copy on the
    teacher's Mac does.
    """
    if roster_mod.allowed_sids():
        return True
    try:
        return bool(_load_password())
    except Exception:
        return False


def require_auth(request: Request):
    """Require a signed-in session, unless the site is open.

    With no roster and no password configured there is nothing to check,
    so every route works for anyone. Both are honoured when set, so
    turning the gate on is a one-line change in the environment.
    """
    if not password_required():
        return
    if not session_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="Not signed in.")


def require_teacher(request: Request):
    """Only the teacher may use this route."""
    identity = current_identity(request)
    if identity.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Teacher only.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    """A health check for the hosting platform.

    Deliberately does nothing: no knowledge base, no language model, no
    session, no authentication. The platform polls this to decide whether
    the container is up, and a check that could fail for a reason
    unrelated to the container being alive would take the site down.
    """
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if password_required() and not session_valid(request.cookies.get(SESSION_COOKIE)):
        return templates.TemplateResponse(request, "login.html", {
            "use_roster": bool(roster_mod.allowed_sids()),
        })

    # Hand out a session token even when the gate is off.
    #
    # The token is what the rate limit is keyed on. With the gate off a
    # visitor never logs in, so without this every anonymous visitor
    # shares one bucket and one person's questions lock out everyone.
    # It is not an access token - it grants nothing - it just identifies
    # the browser.
    resp = templates.TemplateResponse(
        request, "index.html", {
            "password_required": password_required(),
            "is_teacher": current_identity(request).get("role") == "teacher",
        }
    )
    if not session_valid(request.cookies.get(SESSION_COOKIE)):
        resp.set_cookie(
            SESSION_COOKIE, new_session(current_identity(request)),
            httponly=True, samesite="lax",
            max_age=SESSION_TTL, secure=False,
        )
    return resp


@app.post("/login")
def login(request: Request, identifier: str = Form(""), password: str = Form("")):
    """Sign in.

    The identifier is a student's SID (eight digits) or the word
    "teacher". A student must be on the roster; the teacher needs the
    MAKGEO_TEACHER_KEY, which is not in the roster and so cannot be
    guessed from it.

    When there is no roster the old shared password still works, so the
    teacher can lock the site down before the roster is set up.
    """
    ident = (identifier or "").strip()

    # A roster exists: sign in against it.
    if roster_mod.allowed_sids():
        identity = roster_mod.sign_in(ident, password)
        if identity is None:
            return templates.TemplateResponse(
                request, "login.html", {
                    "error": "That SID and password do not match.",
                    "use_roster": True,
                }, status_code=401,
            )
        roster_mod.log_event(identity, "login")
        token = new_session(identity)
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax",
            max_age=SESSION_TTL, secure=False,
        )
        return resp

    # No roster: the shared password is the gate.
    if not password_required():
        token = new_session({})
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax",
            max_age=SESSION_TTL, secure=False,
        )
        return resp
    if hmac.compare_digest(password.strip(), _load_password()):
        identity = {"role": "teacher", "sid": "teacher", "name": "Teacher"}
        token = new_session(identity)
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax",
            max_age=SESSION_TTL, secure=False,
        )
        return resp
    return templates.TemplateResponse(
        request, "login.html", {
            "error": "Wrong password.",
            "use_roster": False,
        }, status_code=401,
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

    # Record who asked what, so the teacher can see which students are
    # using the site and on what.
    roster_mod.log_event(current_identity(request), "ask", q)

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

    matcher = get_matcher()

    electives = []
    for el in curriculum.get("electives", []):
        code = el.get("code", "")
        if want != "ALL" and code.upper() != want:
            continue
        subqs = []
        for sq in el.get("subquestions", []):
            leaves = []
            for leaf in sq.get("leaves", []):
                content = matcher.match(matcher.hints_for(leaf),
                                              leaf.get("title", ""))
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


@app.get("/api/essay/tree")
def api_essay_tree(request: Request):
    """The sub-topics the essay generator can draw on.

    Only CP1-CP7 and EP1. F2 and F3 are a different course and are not
    offered here, so the picker cannot ask for them.
    """
    require_auth(request)
    curriculum = load_json("curriculum.json", {"electives": []})
    out = []
    for el in curriculum.get("electives", []):
        code = el.get("code", "").upper()
        if code not in essay.ESSAY_ELECTIVES:
            continue
        subqs = []
        for sq in el.get("subquestions", []):
            leaves = [
                {"id": l.get("id"), "title": l.get("title")}
                for l in sq.get("leaves", [])
                if l.get("id")
            ]
            if leaves:
                subqs.append({
                    "number": sq.get("number"),
                    "title": sq.get("title"),
                    "leaves": leaves,
                })
        out.append({
            "code": code,
            "title": el.get("title"),
            "subquestions": subqs,
        })
    return {
        "electives": out,
        "marks": list(essay.MARK_OPTIONS),
        # Two command lists, one per half of the essay. The Part (b) list
        # carries the judgement commands; the Part (a) list carries the
        # knowledge-and-mechanism commands.
        "commands_a": [
            {"key": k, "label": v} for k, v in essay.PART_A_COMMANDS.items()
        ],
        "commands_b": [
            {"key": k, "label": v} for k, v in essay.PART_B_COMMANDS.items()
        ],
    }


class EssayPayload(BaseModel):
    topic: str
    leaf_ids: list[str] | None = None
    marks: int = 12
    # The command word for each half of the essay. A DSE short essay is two
    # parts with two different command words, so they are set separately.
    command_a: str | None = None
    command_b: str | None = None


@app.post("/api/essay/generate")
def api_essay_generate(request: Request, payload: EssayPayload):
    """Generate one practice essay from the MakGeography notes."""
    require_auth(request)
    topic = (payload.topic or "").strip().upper()
    if not check_rate(request.cookies.get(SESSION_COOKIE),
                      limit=essay.ESSAY_RATE_LIMIT, bucket="essay"):
        raise HTTPException(
            status_code=429,
            detail="You have reached the essay limit for this minute. Wait a moment, then try again.",
        )
    if topic in essay.EXCLUDED_ELECTIVES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{topic} is not covered by the essay generator. It covers "
                f"CP1-CP7 and EP1 only."
            ),
        )
    if topic not in essay.ESSAY_ELECTIVES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Choose one of {', '.join(essay.ESSAY_ELECTIVES)}."
            ),
        )

    marks = payload.marks if payload.marks in essay.MARK_OPTIONS else 12
    curriculum = load_json("curriculum.json", {"electives": []})

    # Record the essay, so the teacher can see who is practising what.
    roster_mod.log_event(
        current_identity(request), "essay",
        f"{topic} {marks} marks ({payload.command_a or '-'}/{payload.command_b or '-'})",
    )
    res = essay.generate(
        get_matcher(), curriculum, topic,
        leaf_ids=payload.leaf_ids or None,
        marks=marks,
        command_a=payload.command_a,
        command_b=payload.command_b,
        topic_title="",
    )
    if not res["ok"]:
        return {"ok": False, "error": res["error"], "essay": None, "sources": []}
    return res


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
    # Report every topic present, so the drill filter can offer the ones
    # that only the official HKEAA questions use (e.g. MAP for map reading).
    topics = sorted({t for q in qs for t in (q.get("topics") or []) if t})
    official_total = sum(1 for q in qs if q.get("official"))
    # Official HKEAA questions first, then newest paper first, then question
    # number. The bank otherwise starts with 251 AI questions, so a student
    # drilling "All topics" would rarely see a real exam question.
    def sort_key(q):
        return (
            0 if q.get("official") else 1,
            -(q.get("year") or 0),
            q.get("q") or 0,
        )
    qs = sorted(qs, key=sort_key)

    # Record that this student started a drill, and on what topic.
    if limit >= 20:
        roster_mod.log_event(
            current_identity(request), "mc_drill",
            f"{want} — {len(qs)} questions available",
        )

    return {"questions": qs[:limit], "total": len(qs), "topics": topics,
            "official_total": official_total}


# ---------------------------------------------------------------------------
# The teacher's own view: who is using the site
# ---------------------------------------------------------------------------

@app.get("/api/teacher/activity")
def api_teacher_activity(request: Request, days: int = 7):
    """Who used the site, and how much. Teacher only."""
    require_auth(request)
    require_teacher(request)
    return roster_mod.summarise_log(days=max(1, min(days, 90)))


@app.get("/api/teacher/roster")
def api_teacher_roster(request: Request):
    """The roster, and who has signed in at least once."""
    require_auth(request)
    require_teacher(request)
    stats = roster_mod.roster_stats()
    signed_in = {e.get("sid") for e in roster_mod.read_log(limit=5000)}
    return {
        "stats": stats,
        "students": [
            {
                "sid": sid,
                "name": rec.get("name_en", ""),
                "name_zh": rec.get("name_zh", ""),
                "class": rec.get("class", ""),
                "has_password": bool(rec.get("password")),
                "signed_in": sid in signed_in,
            }
            for sid, rec in sorted(roster_mod.load_roster()
                                   .get("students", {}).items())
        ],
    }


@app.get("/question-images/{name}")
def question_image(request: Request, name: str):
    """The official exam questions, rendered from the HKEAA decks.

    The question as it appeared in the exam paper: stem, figure and
    numbered statements. The response percentages, the answer marking
    and the HKEAA commentary are stripped out, because they give the
    answer away.
    """
    require_auth(request)
    path = (DATA_DIR / "question_images" / name).resolve()
    if not path.is_file() or path.parent != (DATA_DIR / "question_images").resolve():
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(path, media_type="image/png")


# --- HKEAA question images from the OQB platform ----------------------------
#
# The 765 official HKDSE/HKCEE Geography MC questions came from the OQB
# (網上試題學習平台) at oqb.edcity.hk. Each question is stored as images:
# one stem image and four option images, plus the paper's map extract.
#
# These are served from data/hkeaa_oqb/. The path is resolved and then
# checked to be inside that directory, so a crafted path cannot escape it.

OQB_DIR = (DATA_DIR / "hkeaa_oqb").resolve()
OQB_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


def _oqb_file(rel: str):
    """Resolve a path inside the OQB media directory, or raise 404."""
    root = OQB_DIR
    path = (root / rel).resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found.")
    # The resolved path must still be inside the media root.
    if root != path and root not in path.parents:
        raise HTTPException(status_code=404, detail="Not found.")
    return path


@app.get("/oqb-images/{rel_path:path}")
def oqb_image(request: Request, rel_path: str):
    """A stem, option or map-extract image for an official HKEAA question."""
    require_auth(request)
    path = _oqb_file(rel_path)
    media = OQB_MEDIA.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/oqb-attachments/{rel_path:path}")
def oqb_attachment(request: Request, rel_path: str):
    """The paper's map extract (PDF or JPG), served as a download."""
    require_auth(request)
    path = _oqb_file(rel_path)
    if path.suffix.lower() not in (".pdf", ".jpg", ".jpeg"):
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(path, media_type=OQB_MEDIA.get(path.suffix.lower()),
                        headers={"Content-Disposition": f'inline; filename="{path.name}"'})


# --------------------------- static + error -------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    return JSONResponse({"error": "Not signed in."}, status_code=401)
