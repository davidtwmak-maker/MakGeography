#!/usr/bin/env python3
"""Merge the OQB HKEAA geography bank into the app's MC bank.

The OQB questions are added alongside the existing 264 (AI-generated plus
the 13 hand-checked official ones). The 11 that overlap are deduplicated by
HKEAA qcode so the hand-checked versions - which carry an explanation and a
rendered paper image - are kept and the OQB copy is dropped.

Output: data/mc_bank.json  (the file the app already reads)
Also:   data/mc_bank_oqb_geog.json  (the OQB-only file, for reference)
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import json
import os
import shutil

APP = BASE
BANK = os.path.join(APP, "data/mc_bank.json")
OQB = os.path.join(APP, "data/mc_bank_oqb_geog.json")
BASE = os.path.join(APP, "data/hkeaa_oqb")


def main():
    bank = json.load(open(BANK, encoding="utf-8"))
    oqb = json.load(open(OQB, encoding="utf-8"))
    existing = bank.get("questions", [])
    new = oqb.get("questions", [])

    # Which HKEAA qcodes are already in the bank? The pre-existing official
    # questions carry year + question number but no qcode field, so derive it.
    by_qcode = {}
    for q in existing:
        qc = q.get("hkeaa_qcode")
        if not qc and q.get("year") and q.get("q") and q.get("official"):
            qc = f"HKEAA_geog_{q['year']}_{q['q']}"
        if qc:
            by_qcode[qc] = q

    kept, replaced, added = [], [], []
    for q in new:
        qc = q.get("hkeaa_qcode")
        old = by_qcode.get(qc)
        if old is None:
            added.append(q)
            continue
        if old.get("explanation"):
            # hand-checked version wins - keep it, and enrich it
            old["oqb_qcode"] = qc
            old.setdefault("official", True)
            old["official_source"] = "HKEAA (hand-checked) / OQB"
            replaced.append(old)
        else:
            kept.append(q)

    # Keep the original order stable: existing first, then new ones.
    out = []
    seen = set()
    for q in existing:
        out.append(q)
        seen.add(q.get("id"))
    for q in added:
        if q["id"] not in seen:
            out.append(q)
            seen.add(q["id"])

    bank["questions"] = out
    with open(BANK, "w", encoding="utf-8") as fh:
        json.dump(bank, fh, ensure_ascii=False, indent=1)

    import collections
    print("existing:", len(existing))
    print("OQB questions:", len(new))
    print("  added (new):", len(added))
    print("  replaced by hand-checked version:", len(replaced))
    print("total in bank now:", len(out))
    print()
    print("by elective:", dict(sorted(collections.Counter(
        (q.get("elect") or "?") for q in out).items())))
    print("official:", sum(1 for q in out if q.get("official")))
    print("wrote:", BANK, os.path.getsize(BANK), "bytes")


if __name__ == "__main__":
    main()
