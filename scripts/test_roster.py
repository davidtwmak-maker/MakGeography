#!/usr/bin/env python3
"""Check the SID sign-in and the activity log.

The roster is the thing that tells the teacher which students are using
the site, so it has to be right in the ways that matter:

  * a student on the roster can sign in with their own password;
  * a student who is NOT on the roster cannot sign in;
  * the right password is required - a wrong one is refused;
  * one student's password does not open another's account;
  * the roster file holds a hash, never a password;
  * signing in is recorded, and the log says who it was;
  * only the teacher can read the activity log.

The test builds its own roster in a temp directory, so it never touches
the real one.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="makgeo_roster_"))
    from app import roster as r

    # Point the roster module at the temp directory.
    r.ROSTER_PATH = tmp / "roster.json"
    r.ACTIVITY_LOG = tmp / "activity_log.jsonl"

    students = {
        "20233004": {"name_en": "CAI XUEWEI", "name_zh": "蔡學為",
                     "class": "6A", "no": "1", "house": "Y"},
        "20211008": {"name_en": "CHAN CHUN HIN", "name_zh": "陳浚軒",
                     "class": "6A", "no": "2", "house": "B"},
        "20234011": {"name_en": "CHEN JIAKANGBO", "name_zh": "陳賈康愽",
                     "class": "6B", "no": "3", "house": "Y"},
    }
    for sid, rec in students.items():
        rec["password"] = r.hash_password(f"pw-{sid}")
    r.save_roster({"updated": "2026-10-28", "students": students})

    check("roster loads", len(r.load_roster().get("students", {})) == 3)
    check("allowed_sids lists all three", r.allowed_sids() == sorted(students))
    check("roster_stats counts by class",
          r.roster_stats()["classes"] == {"6A": 2, "6B": 1},
          str(r.roster_stats()["classes"]))

    # --- sign in -----------------------------------------------------
    ident = r.sign_in("20233004", "pw-20233004")
    check("a student on the roster signs in", ident is not None)
    check("the identity carries the name",
          bool(ident) and ident.get("name") == "CAI XUEWEI")
    check("the identity carries the class",
          bool(ident) and ident.get("class") == "6A")
    check("the identity carries the Chinese name",
          bool(ident) and ident.get("name_zh") == "蔡學為")
    check("the role is student", bool(ident) and ident.get("role") == "student")

    check("a wrong password is refused", r.sign_in("20233004", "wrong") is None)
    check("an empty password is refused", r.sign_in("20233004", "") is None)
    check("a SID not on the roster is refused",
          r.sign_in("20999999", "pw-20233004") is None)
    check("a malformed SID is refused", r.sign_in("abc", "x") is None)
    check("an empty identifier is refused", r.sign_in("", "x") is None)

    other = r.sign_in("20211008", "pw-20233004")
    check("one student's password does not open another's account", other is None)

    # --- the teacher -------------------------------------------------
    os.environ["MAKGEO_TEACHER_KEY"] = "teacher-secret"
    check("the teacher key signs in",
          (r.sign_in("20190901", "teacher-secret") or {}).get("role") == "teacher")
    check("a wrong teacher key is refused", r.sign_in("20190901", "nope") is None)
    check("the teacher is not in the roster", "20190901" not in r.allowed_sids())

    # --- the teacher's identifier looks like a Student ID ------------
    check("the teacher's identifier is eight digits",
          bool(re.fullmatch(r"\d{8}", r.TEACHER_IDENTIFIER)),
          r.TEACHER_IDENTIFIER)
    check("the teacher's identifier is not a student's",
          r.TEACHER_IDENTIFIER not in students, r.TEACHER_IDENTIFIER)
    check("the teacher signs in with the eight-digit identifier",
          r.sign_in(r.TEACHER_IDENTIFIER, "teacher-secret") is not None)
    check("the teacher signs in with leading or trailing spaces too",
          r.sign_in(f"  {r.TEACHER_IDENTIFIER}  ", "teacher-secret") is not None)
    check("the teacher's identifier is not in the allowed SIDs",
          r.TEACHER_IDENTIFIER not in r.allowed_sids())
    del os.environ["MAKGEO_TEACHER_KEY"]
    check("with no teacher key set the teacher cannot sign in",
          r.sign_in("20190901", "teacher-secret") is None)

    # --- a class list cannot take over the teacher's login -----------
    # The teacher's identifier is eight digits, so a class list that
    # happens to contain it must not turn into a student account.
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    build_roster = importlib.import_module("build_roster")
    check("the roster builder skips the teacher's identifier",
          getattr(build_roster.roster_mod, "TEACHER_IDENTIFIER", "") ==
          r.TEACHER_IDENTIFIER)

    # --- the roster file holds no password ---------------------------
    raw = r.ROSTER_PATH.read_text(encoding="utf-8")
    check("the roster file holds no plaintext password",
          "pw-20233004" not in raw and "teacher-secret" not in raw)
    check("the roster file holds a hash",
          '"hash"' in raw and '"salt"' in raw)

    # --- the activity log --------------------------------------------
    r.log_event(ident, "login")
    r.log_event(ident, "ask", "What is the capital of China?")
    r.log_event(r.sign_in("20234011", "pw-20234011"), "login")
    r.log_event(r.sign_in("20234011", "pw-20234011"), "mc_drill", "CP1")

    entries = r.read_log()
    check("four events were logged", len(entries) == 4, f"got {len(entries)}")
    check("the log names the student",
          any(e.get("name") == "CAI XUEWEI" for e in entries))
    check("the log records the class",
          any(e.get("class") == "6A" for e in entries))
    check("the log records the question asked",
          any("capital of China" in e.get("detail", "") for e in entries))

    summary = r.summarise_log(days=7)
    check("the summary counts two active students",
          summary["active_students"] == 2, str(summary["active_students"]))
    check("the summary counts the asks", summary["total_asks"] == 1)
    check("the summary counts the logins", summary["total_logins"] == 2)
    check("the summary groups by class",
          summary["by_class"] == {"6A": 1, "6B": 1},
          str(summary["by_class"]))

    # --- a roster with no passwords still closes the door ------------
    #
    # This is the bug worth guarding. allowed_sids() once returned only
    # the students who had a password, so a freshly built roster - where
    # no student has one yet - looked like no roster at all, and the
    # sign-in gate silently opened the site to anyone.
    r.save_roster({"students": {
        "20233004": {"name_en": "CAI XUEWEI", "class": "6A"},
        "20234011": {"name_en": "CHEN JIAKANGBO", "class": "6A"},
    }})
    check("a roster with no passwords still lists its SIDs",
          r.allowed_sids() == ["20233004", "20234011"],
          str(r.allowed_sids()))
    check("a student with no password cannot sign in",
          r.sign_in("20233004", "") is None)
    check("a student with no password cannot sign in with any password",
          r.sign_in("20233004", "anything") is None)
    check("a SID not on the roster cannot sign in",
          r.sign_in("99999999", "anything") is None)
    stats = r.roster_stats()
    check("the stats count every student on the roster",
          stats["total"] == 2, str(stats["total"]))
    check("the stats count separately who can sign in",
          stats["with_password"] == 0, str(stats["with_password"]))

    # --- an empty roster closes the door ------------------------------
    r.save_roster({"students": {}})
    check("an empty roster allows nobody", r.allowed_sids() == [])
    check("an empty roster refuses a student", r.sign_in("20233004", "pw-20233004") is None)

    # --- a missing roster file is safe -------------------------------
    r.ROSTER_PATH.unlink()
    check("a missing roster file allows nobody", r.allowed_sids() == [])
    check("a missing roster file refuses a student",
          r.sign_in("20233004", "pw-20233004") is None)
    check("a missing roster file does not crash the summary",
          isinstance(r.summarise_log(days=7), dict))

    # --- a corrupt roster file is safe -------------------------------
    r.ROSTER_PATH.write_text("{not json", encoding="utf-8")
    check("a corrupt roster file allows nobody", r.allowed_sids() == [])
    check("a corrupt roster file does not crash sign-in",
          r.sign_in("20233004", "x") is None)

    failed = [c for c in CHECKS if not c[1]]
    print()
    if failed:
        print(f"FAILED {len(failed)} of {len(CHECKS)} checks:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
        return 1
    print(f"ALL {len(CHECKS)} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
