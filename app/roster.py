"""Student roster: SID sign-in and the log of who used the site.

The site used to have a single shared password. That told us nobody: any
student could type the same password, and there was no way to say which
Form 6 class had actually used the site.

Now each student signs in with their own SID. The roster lives in
data/roster.json, which holds the allowed SIDs and, for each one, a
password hash. The roster is a plain file so the teacher can edit it in
Obsidian or in a text editor without touching the code.

Two things are deliberately kept apart:

  * The roster (data/roster.json) says WHO may sign in. It is safe to
    commit: it holds a salted hash, never a password.

  * The activity log (data/activity_log.jsonl) says WHO DID WHAT. It is
    never committed - it grows with every sign-in and every question,
    and it carries the students' names.

Passwords are hashed with PBKDF2-HMAC-SHA256 and a per-student random
salt. There is no password to recover: a forgotten password is reset by
running scripts/set_student_password.py, which writes a new hash.

The teacher keeps their own door open with MAKGEO_TEACHER_KEY, a
separate secret that is never part of the roster. The teacher can sign in
as "teacher" and see the activity log; students cannot.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROSTER_PATH = DATA_DIR / "roster.json"
ACTIVITY_LOG = DATA_DIR / "activity_log.jsonl"

# On a deployed server the roster is not in the repository - it holds the
# students' names, so it is never committed. It is mounted as a file, or
# passed in as an environment variable, instead.
#
# MAKGEO_ROSTER_PATH: the path of a roster.json on the server.
# MAKGEO_ROSTER_JSON: the roster itself, inline, for a server where
#                     setting a file is awkward. It can be large, so
#                     MAKGEO_ROSTER_PATH is preferred.
ROSTER_PATH_ENV = "MAKGEO_ROSTER_PATH"
ROSTER_JSON_ENV = "MAKGEO_ROSTER_JSON"

PBKDF2_ROUNDS = 120_000
SID_RE = re.compile(r"^\d{8}$")


# ---------------------------------------------------------------------------
# The roster file
# ---------------------------------------------------------------------------

def _roster_path() -> Path:
    """Where the roster lives, on this machine or on the server."""
    override = os.environ.get(ROSTER_PATH_ENV, "").strip()
    return Path(override) if override else ROSTER_PATH


def _roster_from_env() -> dict | None:
    """The roster passed inline as an environment variable."""
    raw = os.environ.get(ROSTER_JSON_ENV, "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("students", {})
    return data


def load_roster() -> dict:
    """Read the roster, or an empty one if it is missing.

    An empty roster means no student may sign in, and the site falls back
    to the teacher key alone. That is the safe default: a site that has
    just been deployed but not yet given a roster is closed, not open.
    """
    inline = _roster_from_env()
    if inline is not None:
        return inline

    path = _roster_path()
    if not path.is_file():
        return {"students": {}, "note": "no roster file yet"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"students": {}, "note": "roster file could not be read"}
    if not isinstance(data, dict):
        return {"students": {}, "note": "roster file is not an object"}
    data.setdefault("students", {})
    return data


def save_roster(roster: dict) -> None:
    path = _roster_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(roster, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: str | None = None) -> dict:
    """Hash a password with PBKDF2. Returns the record to store."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return {
        "salt": salt,
        "hash": dk.hex(),
        "rounds": PBKDF2_ROUNDS,
        "algo": "pbkdf2_sha256",
    }


def verify_password(password: str, record: dict) -> bool:
    """Check a password against a stored hash, in constant time."""
    if not isinstance(record, dict):
        return False
    salt = record.get("salt")
    expected = record.get("hash")
    if not salt or not expected:
        return False
    rounds = int(record.get("rounds") or PBKDF2_ROUNDS)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
    return hmac.compare_digest(dk.hex(), expected)


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------

def teacher_key() -> str:
    """The teacher's own key, from the environment only."""
    return os.environ.get("MAKGEO_TEACHER_KEY", "").strip()


def sign_in(identifier: str, password: str) -> dict | None:
    """Try to sign in. Returns the identity on success, or None.

    The identifier is a SID (eight digits) or the word "teacher".
    """
    ident = (identifier or "").strip()

    if ident.lower() == "teacher":
        key = teacher_key()
        if key and hmac.compare_digest(password or "", key):
            return {
                "role": "teacher",
                "sid": "teacher",
                "name": "Teacher",
                "name_zh": "老師",
                "class": "",
            }
        return None

    if not SID_RE.match(ident):
        return None

    roster = load_roster()
    entry = roster.get("students", {}).get(ident)
    if not entry:
        return None
    if not verify_password(password or "", entry.get("password") or {}):
        return None

    return {
        "role": "student",
        "sid": ident,
        "name": entry.get("name_en", ""),
        "name_zh": entry.get("name_zh", ""),
        "class": entry.get("class", ""),
        "house": entry.get("house", ""),
    }


def allowed_sids() -> list[str]:
    """Every SID on the roster, sorted.

    This is the list of SIDs the site recognises, not the list of
    students who can sign in. Those are different questions: a student
    with no password set yet is still on the roster, and the roster
    being present is what turns the sign-in gate on.

    Getting this wrong is silent and dangerous. It once returned only
    the students who had a password, so a freshly built roster - where
    no student has a password yet - looked like no roster at all, and
    the gate silently opened the site to anyone.
    """
    roster = load_roster()
    return sorted(k for k, v in roster.get("students", {}).items()
                  if isinstance(v, dict))


def roster_stats() -> dict:
    """A short summary for the teacher dashboard.

    Two counts, because they answer different questions: how many
    students are on the roster, and how many can actually sign in.
    """
    roster = load_roster()
    students = roster.get("students", {})
    with_password = [k for k, v in students.items()
                      if isinstance(v, dict) and v.get("password")]

    def by_class(keys: list[str]) -> dict:
        out: dict[str, int] = {}
        for sid in keys:
            cls = (students[sid].get("class") or "?").strip() or "?"
            out[cls] = out.get(cls, 0) + 1
        return dict(sorted(out.items()))

    return {
        "total": len(students),
        "with_password": len(with_password),
        "classes": by_class(list(students)),
        "classes_with_password": by_class(with_password),
        "updated": roster.get("updated", ""),
    }


# ---------------------------------------------------------------------------
# The activity log
# ---------------------------------------------------------------------------

def _activity_path() -> Path:
    """Where the activity log lives.

    A deployed server may have a read-only filesystem, so the log can be
    pointed somewhere writable. MAKGEO_ACTIVITY_LOG is that path.
    """
    override = os.environ.get("MAKGEO_ACTIVITY_LOG", "").strip()
    return Path(override) if override else ACTIVITY_LOG


def log_event(identity: dict, action: str, detail: str = "") -> None:
    """Append one line to the activity log.

    One JSON object per line, so the file can be read while it is being
    written and truncated safely. The log is never committed: it holds
    the students' names and what they did.
    """
    if not identity:
        return
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sid": identity.get("sid", ""),
        "name": identity.get("name", ""),
        "name_zh": identity.get("name_zh", ""),
        "class": identity.get("class", ""),
        "role": identity.get("role", ""),
        "action": action,
        "detail": (detail or "")[:300],
    }
    try:
        path = _activity_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # A logging failure must never break the site.
        pass


def read_log(limit: int = 500) -> list[dict]:
    """The most recent entries, newest first."""
    path = _activity_path()
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    out.reverse()
    return out


def summarise_log(days: int = 7) -> dict:
    """Who used the site, and how much, over the last N days."""
    entries = read_log(limit=20000)
    cutoff = time.time() - days * 86400
    recent = []
    for e in entries:
        ts = e.get("ts", "")
        try:
            when = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        if when >= cutoff:
            recent.append(e)

    per_student: dict[str, dict] = {}
    for e in recent:
        sid = e.get("sid", "")
        if not sid or e.get("role") == "teacher":
            continue
        rec = per_student.setdefault(sid, {
            "sid": sid, "name": e.get("name", ""), "class": e.get("class", ""),
            "logins": 0, "asks": 0, "essays": 0, "last": "",
        })
        action = e.get("action", "")
        if action == "login":
            rec["logins"] += 1
        elif action == "ask":
            rec["asks"] += 1
        elif action == "essay":
            rec["essays"] += 1
        if e.get("ts", "") > rec["last"]:
            rec["last"] = e.get("ts", "")

    by_class: dict[str, int] = {}
    for rec in per_student.values():
        cls = rec.get("class") or "?"
        by_class[cls] = by_class.get(cls, 0) + 1

    return {
        "days": days,
        "active_students": len(per_student),
        "by_class": dict(sorted(by_class.items())),
        "students": sorted(per_student.values(), key=lambda r: r["last"], reverse=True),
        "total_logins": sum(r["logins"] for r in per_student.values()),
        "total_asks": sum(r["asks"] for r in per_student.values()),
        "total_essays": sum(r["essays"] for r in per_student.values()),
    }
