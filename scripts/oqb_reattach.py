#!/usr/bin/env python3
"""Re-download the OQB attachment (map extract) files with unique names.

The first dedupe pass moved files into a flat directory where every year's
map was called "map.pdf", so the later ones overwrote the earlier ones and
14 of the 23 unique files were lost. Download each attachment again and
name it <year>_<original name>, then index by SHA-256.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import hashlib
import json
import os
import shutil
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oqb_api import fetch_blob, load_token

BASE = BASE / "data" / "hkeaa_oqb"
SUBJECT = "geog"
ATT = os.path.join(BASE, SUBJECT, "_attachments")
FLAT = os.path.join(ATT, "_files")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    raw = json.load(open(f"{BASE}/_raw/{SUBJECT}.json", encoding="utf-8"))
    qid_year = {}
    for r in raw:
        parts = (r.get("qcode") or "").split("_")
        if len(parts) >= 3 and parts[-2].isdigit():
            qid_year[r["id"]] = int(parts[-2])

    # one download job per (year, filename, url)
    jobs = {}
    for r in raw:
        att = r.get("attachment") or {}
        urls = r.get("attachment_url") or {}
        year = qid_year.get(r["id"], 0)
        for label, fname in att.items():
            if label in urls and fname:
                key = (year, fname)
                jobs.setdefault(key, (urls[label], label, year, fname))

    print(f"unique attachment jobs: {len(jobs)}")
    os.makedirs(FLAT, exist_ok=True)

    # clear the flat dir so nothing stale survives
    for f in os.listdir(FLAT):
        p = os.path.join(FLAT, f)
        if os.path.isfile(p):
            os.remove(p)

    done = 0
    for (year, fname), (url, label, y, fn) in sorted(jobs.items()):
        stem = os.path.splitext(fname)[0]
        ext = os.path.splitext(fname)[1] or ".bin"
        dest = os.path.join(FLAT, f"{year}_{stem}{ext}")
        if not (os.path.exists(dest) and os.path.getsize(dest) > 0):
            try:
                n = fetch_blob(url, dest)
                print(f"  {year} {fname} -> {os.path.basename(dest)} ({n:,} bytes)")
            except Exception as e:
                print(f"  FAILED {year} {fname}: {e}")
                continue
        done += 1
    print("downloaded:", done)

    # index: sha -> path, and question -> {label: path}
    files = {}
    for f in sorted(os.listdir(FLAT)):
        p = os.path.join(FLAT, f)
        files[sha(p)] = p

    by_name = defaultdict(list)
    for s, p in files.items():
        by_name[os.path.basename(p)].append((s, p))

    def pick(name, year):
        """Find the file that matches this question's year and name."""
        cands = by_name.get(name) or []
        if not cands:
            cands = by_name.get(f"{year}_{name}") or []
        if not cands:
            return None
        for s, p in cands:
            if os.path.basename(p).startswith(f"{year}_"):
                return (s, p)
        return cands[0]

    by_question = {}
    for r in raw:
        att = r.get("attachment") or {}
        if not att:
            continue
        year = qid_year.get(r["id"], 0)
        entry = by_question.setdefault(str(r["id"]), {})
        for label, fname in att.items():
            hit = pick(fname, year)
            if hit:
                entry[label] = os.path.relpath(files[hit[0]], BASE)

    out = {"files": {s: os.path.relpath(p, BASE) for s, p in files.items()},
           "by_question": by_question}
    with open(os.path.join(BASE, "attachment_map.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print("unique files:", len(files))
    for s, p in sorted(files.items(), key=lambda kv: kv[1]):
        print("  ", os.path.basename(p), f"{os.path.getsize(p):,}")
    missing = [(q, l, rel) for q, e in by_question.items()
               for l, rel in e.items()
               if not os.path.exists(os.path.join(BASE, rel))]
    print("questions with attachment:", len(by_question), " broken refs:", len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
