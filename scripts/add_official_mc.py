#!/usr/bin/env python3
"""
Add the official HKEAA items to data/mc_bank.json without regenerating the
whole bank.

The official items come from HKEAA's own examination briefing decks (see
data/hkeaa_NOTES.md). They are the genuine exam wording with the official
answer, so they belong at the top of the bank.

Usage:  python scripts/add_official_mc.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

SUBTOPIC_HINTS = {
    (2023, 2): "CP4.4.1", (2024, 6): "CP4.4.1", (2024, 9): "CP2.2.4",
    (2024, 12): "CP3.1.1", (2024, 13): "CP4.3.1", (2024, 20): "CP7.1.1",
    (2025, 19): "CP7.1.3",
}


def main():
    official_path = DATA / "hkeaa_mc_raw.json"
    bank_path = DATA / "mc_bank.json"

    official = json.loads(official_path.read_text(encoding="utf-8"))
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    existing = {q.get("id") for q in questions}
    added = 0
    for q in official:
        q = dict(q)
        q["topics"] = [q.pop("elect")]
        sub = SUBTOPIC_HINTS.get((q["year"], q["q"]))
        if sub:
            q["subtopic"] = sub
        q["subtopic_title"] = q.get("stem", "")[:60]
        q["source"] = (f"HKEAA {q['paper']} {q['year']} Item {q['q']} "
                       f"(official examination briefing)")
        q["id"] = f"hkeaa-{q['year']}-q{q['q']}"
        q["official"] = True
        if q["id"] in existing:
            continue
        questions.append(q)
        added += 1

    # Official items first, then the generated ones.
    questions.sort(key=lambda q: (0 if q.get("official") else 1,
                                   q.get("topics", ["ZZ"])[0],
                                   q.get("subtopic", ""),
                                   q.get("stem", "")))

    bank["questions"] = questions
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    from collections import Counter
    print(f"added {added} official items; bank now holds {len(questions)}")
    print("by elective:", dict(Counter(t for q in questions for t in q.get("topics", []))))
    print("official:", sum(1 for q in questions if q.get("official")))


if __name__ == "__main__":
    main()
