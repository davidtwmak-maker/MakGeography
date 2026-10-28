#!/usr/bin/env python3
"""Rebuild the attachment index after deduplication.

Two fixes over the first pass:
  1. the by_question paths pointed at the pre-move location
  2. every year's map is called "map.pdf", so identical basenames from
     different years collided. Name each survivor by its year and give
     each question the path of the file that actually served it.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict

BASE = BASE / "data" / "hkeaa_oqb"
SUBJECT = "geog"
ATT = os.path.join(BASE, SUBJECT, "_attachments")
FLAT = os.path.join(ATT, "_files")
OUT = os.path.join(BASE, "attachment_map.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest = json.load(open(f"{BASE}/hkeaa_mc_manifest.json", encoding="utf-8"))
    raw = json.load(open(f"{BASE}/_raw/{SUBJECT}.json", encoding="utf-8"))
    by_id = {r["id"]: r for r in raw}

    # qid -> year (from the row's qcode)
    qid_year = {}
    for r in raw:
        qc = r.get("qcode") or ""
        parts = qc.split("_")
        if len(parts) >= 3 and parts[-2].isdigit():
            qid_year[r["id"]] = int(parts[-2])

    # Rebuild: walk the ORIGINAL per-question attachment mapping in the raw
    # rows. We know the filename each question asked for; find the file in
    # _files whose content matches that name+year.
    files = {}
    for f in sorted(os.listdir(FLAT)):
        p = os.path.join(FLAT, f)
        files[sha(p)] = p

    # name -> [(sha, path)]  (map.pdf appears for many years)
    by_name = defaultdict(list)
    for s, p in files.items():
        by_name[os.path.basename(p)].append((s, p))

    def pick(name, year):
        """Choose the right map file for a question's year."""
        cands = by_name.get(name) or []
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # Prefer a file whose stored year matches.
        for s, p in cands:
            base = os.path.basename(p)
            m = base[:4]
            if m.isdigit() and int(m) == year:
                return (s, p)
        # otherwise fall back to the largest file (the full paper map)
        return max(cands, key=lambda sp: os.path.getsize(sp[1]))

    # name the flat files by year where we can
    renamed = {}
    for name, cands in by_name.items():
        if len(cands) == 1:
            s, p = cands[0]
            renamed[s] = p
            continue
        for s, p in cands:
            stem = os.path.splitext(os.path.basename(p))[0]
            if stem.isdigit():
                newp = os.path.join(FLAT, f"{stem}.pdf")
            else:
                # same generic name from different years: use the sha prefix
                newp = os.path.join(FLAT, f"{name[:-4]}_{s[:8]}.pdf")
            if os.path.abspath(p) != os.path.abspath(newp):
                shutil.move(p, newp)
            renamed[s] = newp

    by_question = {}
    for r in raw:
        att = r.get("attachment") or {}
        if not att:
            continue
        year = qid_year.get(r["id"], 0)
        qid = str(r["id"])
        entry = by_question.setdefault(qid, {})
        for label, fname in att.items():
            hit = pick(fname, year)
            if hit:
                entry[label] = os.path.relpath(renamed[hit[0]], BASE)

    out = {"files": {s: os.path.relpath(p, BASE) for s, p in renamed.items()},
           "by_question": by_question}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print("unique files:", len(renamed))
    for s, p in sorted(renamed.items(), key=lambda kv: kv[1]):
        print("  ", os.path.basename(p), f"{os.path.getsize(p):,}")
    print("questions with an attachment:", len(by_question))

    # verify every referenced path exists
    missing = []
    for qid, e in by_question.items():
        for label, rel in e.items():
            if not os.path.exists(os.path.join(BASE, rel)):
                missing.append((qid, label, rel))
    print("broken references:", len(missing))
    for m in missing[:6]:
        print("   ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
