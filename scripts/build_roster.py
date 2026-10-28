#!/usr/bin/env python3
"""Build data/roster.json from the school's class list.

The class list is the school's own release: one sheet per class, with
the student ID in column A, the class in B, the seat number in C, the
English name in D, the Chinese name in E, the gender in F and the house
in G.

The roster this builds holds the names and SIDs, plus a password hash for
each student. No password is ever written to a file: the script either
sets every student to the same shared password (with a warning), or
leaves each student with no password so the teacher can set them one at
a time.

Usage:
    python scripts/build_roster.py                 # build, no passwords
    python scripts/build_roster.py --password X    # build, one shared password
    python scripts/build_roster.py --from-csv p    # build from a CSV instead
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import roster as roster_mod  # noqa: E402

F6_CLASSES = ("6A", "6B", "6C", "6D", "6E", "6IB")
SID_RE = re.compile(r"^\d{8}$")


def read_xlsx(path: Path, classes=F6_CLASSES) -> list[dict]:
    """Read the F6 sheets of a class-list workbook."""
    z = zipfile.ZipFile(path)

    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        for si in re.findall(r"<si>(.*?)</si>", x, re.S):
            shared.append("".join(
                html.unescape(t) for t in re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))

    wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    rid2t = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    sheets = re.findall(r'<sheet name="([^"]+)"[^>]*r:id="([^"]+)"', wb)

    def grid(name: str) -> list[dict]:
        target = None
        for n, rid in sheets:
            if n == name:
                target = rid2t.get(rid)
        if not target:
            return []
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        x = z.read(target).decode("utf-8", "replace")
        rows = []
        for row in re.findall(r"<row[^>]*>(.*?)</row>", x, re.S):
            cells: dict[str, str] = {}
            for cm in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', row, re.S):
                col, attrs, body = cm.group(1), cm.group(2), cm.group(3)
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                if not v:
                    cells[col] = ""
                elif 't="s"' in attrs:
                    cells[col] = shared[int(v.group(1))]
                else:
                    cells[col] = v.group(1)
            rows.append(cells)
        return rows

    students: list[dict] = []
    for cls in classes:
        for r in grid(cls):
            sid = (r.get("A") or "").strip()
            if not SID_RE.match(sid):
                continue
            students.append({
                "sid": sid,
                "class": (r.get("B") or cls).strip(),
                "no": (r.get("C") or "").strip(),
                "name_en": (r.get("D") or "").strip(),
                "name_zh": (r.get("E") or "").strip(),
                "gender": (r.get("F") or "").strip(),
                "house": (r.get("G") or "").strip(),
            })
    return students


def read_csv(path: Path) -> list[dict]:
    """Read a roster from a CSV with the same columns."""
    out = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = (row.get("sid") or row.get("student_id") or "").strip()
            if not SID_RE.match(sid):
                continue
            out.append({
                "sid": sid,
                "class": (row.get("class") or "").strip(),
                "no": (row.get("no") or "").strip(),
                "name_en": (row.get("name_en") or row.get("name") or "").strip(),
                "name_zh": (row.get("name_zh") or "").strip(),
                "gender": (row.get("gender") or "").strip(),
                "house": (row.get("house") or "").strip(),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class-list", type=Path,
                    help="the school's class list workbook (.xlsx)")
    ap.add_argument("--from-csv", type=Path,
                    help="a CSV with sid,class,no,name_en,name_zh,gender,house")
    ap.add_argument("--password",
                    help="give every student this one password (shared)")
    ap.add_argument("--classes", default=",".join(F6_CLASSES),
                    help="comma-separated class names to include")
    args = ap.parse_args()

    classes = tuple(c.strip() for c in args.classes.split(",") if c.strip())

    if args.from_csv:
        students = read_csv(args.from_csv)
    elif args.class_list:
        students = read_xlsx(args.class_list, classes)
    else:
        # The most recent release the teacher has already downloaded.
        scratch = Path.home() / ".hermes" / "cache" / "scratch"
        candidates = sorted(scratch.glob("*2627*Class_List*.xlsx"), reverse=True)
        if not candidates:
            print("No class list found. Pass --class-list or --from-csv.", file=sys.stderr)
            return 2
        print(f"using {candidates[0].name}")
        students = read_xlsx(candidates[0], classes)

    if not students:
        print("No students found.", file=sys.stderr)
        return 1

    existing = roster_mod.load_roster().get("students", {})
    out: dict[str, dict] = {}
    for s in students:
        rec = {
            "name_en": s["name_en"],
            "name_zh": s["name_zh"],
            "class": s["class"],
            "no": s["no"],
            "house": s["house"],
        }
        # Keep the password a student already has.
        old = existing.get(s["sid"])
        if old and old.get("password"):
            rec["password"] = old["password"]
        if args.password:
            rec["password"] = roster_mod.hash_password(args.password)
        out[s["sid"]] = rec

    data = {
        "updated": __import__("time").strftime("%Y-%m-%d"),
        "source": ("class list workbook" if (args.class_list or args.from_csv is None)
                   else "CSV"),
        "classes": list(classes),
        "note": ("Passwords are PBKDF2 hashes. Use "
                 "scripts/set_student_password.py to set or change one."),
        "students": out,
    }
    roster_mod.save_roster(data)

    with_pw = sum(1 for v in out.values() if v.get("password"))
    by_class: dict[str, int] = {}
    for v in out.values():
        by_class[v["class"]] = by_class.get(v["class"], 0) + 1
    print(f"roster written: {len(out)} students, {with_pw} with a password")
    print("by class:", dict(sorted(by_class.items())))
    if args.password:
        print("\nWARNING: every student has the SAME password. Anyone who "
              "knows one can sign in as any student.\n"
              "Set them individually with scripts/set_student_password.py.")
    else:
        print("\nNo passwords set. Set them with:\n"
              "    python scripts/set_student_password.py --all --password X")
    return 0


if __name__ == "__main__":
    sys.exit(main())
