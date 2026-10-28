#!/usr/bin/env python3
"""Set or change a student's password.

    python scripts/set_student_password.py --sid 20233004 --password X
    python scripts/set_student_password.py --all --password X
    python scripts/set_student_password.py --sid 20233004          # random one
    python scripts/set_student_password.py --class 6A --password X

The password is hashed before it is written, so the roster file never
contains a password anyone could read. Running with --all and one
password gives every student the same password, which is convenient for
the first week and a bad idea afterwards - anyone who knows one can
sign in as anybody.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import roster as roster_mod  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", help="the student's SID")
    ap.add_argument("--class", dest="klass",
                    help="every student in this class")
    ap.add_argument("--all", action="store_true", help="every student")
    ap.add_argument("--password",
                    help="the password (omit for a random one)")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print the random password")
    args = ap.parse_args()

    if not (args.sid or args.klass or args.all):
        ap.error("give --sid, --class or --all")

    data = roster_mod.load_roster()
    students = data.get("students", {})
    if not students:
        print("The roster is empty. Run scripts/build_roster.py first.",
              file=sys.stderr)
        return 1

    if args.sid:
        if args.sid not in students:
            print(f"No student with SID {args.sid}.", file=sys.stderr)
            return 1
        targets = [args.sid]
    elif args.klass:
        targets = [s for s, v in students.items() if v.get("class") == args.klass]
        if not targets:
            print(f"No students in class {args.klass}.", file=sys.stderr)
            return 1
    else:
        targets = list(students)

    shared = bool(args.password)
    for sid in targets:
        pw = args.password or secrets.token_urlsafe(9)
        students[sid]["password"] = roster_mod.hash_password(pw)
        if not shared and args.show:
            name = students[sid].get("name_en", "")
            print(f"  {sid}  {name:24}  password: {pw}")

    data["students"] = students
    data["updated"] = __import__("time").strftime("%Y-%m-%d")
    roster_mod.save_roster(data)

    print(f"set the password for {len(targets)} student(s)")
    if shared:
        print("NOTE: they all share this password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
