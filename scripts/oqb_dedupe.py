#!/usr/bin/env python3
"""Deduplicate the OQB attachment files by SHA-256.

Every question in a paper that uses a map extract points at the SAME map
file, so the downloader wrote it once per question (20 copies of an 11 MB
PDF per year). Replace them with one copy per unique file and record the
mapping so the app can still find the right map for each question.
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


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if not os.path.isdir(ATT):
        print("no attachments dir")
        return 0

    # qid -> {label: path}
    by_q = defaultdict(dict)
    for qid in os.listdir(ATT):
        d = os.path.join(ATT, qid)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            by_q[qid][f] = os.path.join(d, f)

    uniq = {}          # sha -> canonical path
    dupes = 0
    freed = 0
    mapping = {}       # qid -> {label: canonical relative path}

    for qid, files in sorted(by_q.items()):
        mapping[qid] = {}
        for fname, path in sorted(files.items()):
            s = sha(path)
            size = os.path.getsize(path)
            if s not in uniq:
                uniq[s] = path
                mapping[qid][fname] = os.path.join(SUBJECT, "_attachments", fname)
            else:
                canon = uniq[s]
                # same bytes - drop the duplicate
                os.remove(path)
                freed += size
                dupes += 1
                mapping[qid][fname] = os.path.relpath(canon, BASE)
        # remove the now-empty per-question dir
        d = os.path.join(ATT, qid)
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)

    # move the survivors into a flat directory
    flat = os.path.join(ATT, "_files")
    os.makedirs(flat, exist_ok=True)
    final = {}
    for s, path in uniq.items():
        dest = os.path.join(flat, os.path.basename(path))
        if os.path.abspath(path) != os.path.abspath(dest):
            shutil.move(path, dest)
        final[s] = os.path.relpath(dest, BASE)

    with open(os.path.join(BASE, "attachment_map.json"), "w", encoding="utf-8") as fh:
        json.dump({"files": final, "by_question": mapping}, fh,
                  ensure_ascii=False, indent=1)

    print("unique files:", len(uniq))
    print("duplicates removed:", dupes)
    print(f"space freed: {freed/1e6:.1f} MB")
    print("wrote:", os.path.join(BASE, "attachment_map.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
