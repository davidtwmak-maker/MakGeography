#!/usr/bin/env python3
"""
Merge the official HKEAA questions into one file, keeping the best
transcription of each.

Two extractions were made of the same HKEAA briefing slides:

* a geometric extractor that reads the PDF's word positions
  (scripts/extract_hkeaa_mc.py), and
* a vision transcription that reads the rendered slide.

They agree on 3 items, so the union is 13. Where they disagree, the
transcription that has a complete stem, four options and a marked answer
wins; the other is kept in a "also found" note for the record.

Usage:  python scripts/merge_official_mc.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# (year, item) -> curriculum leaf. Taken from the child's reading of the
# slides against the HKEAA assessment framework.
SUBTOPIC_HINTS = {
    (2022, 11): "CP3.1.1", (2022, 16): "CP5.3.1", (2022, 17): "CP6.2.1",
    (2024, 6): "CP4.3.1", (2024, 9): "CP2.2.4", (2024, 12): "CP3.1.1",
    (2024, 13): "CP4.3.1", (2024, 20): "CP7.1.1",
    (2025, 3): "CP2.1.1", (2025, 5): "CP4.4.1", (2025, 19): "CP7.1.3",
    (2025, 20): "CP7.1.3",
    (2026, 14): "CP4.3.1", (2026, 16): "CP5.6.1",
}

ELECTIVE_HINTS = {
    "CP2": "CP2", "CP3": "CP3", "CP4": "CP4", "CP5": "CP5",
    "CP6": "CP6", "CP7": "CP7", "CP1": "CP1", "EP1": "EP1",
}


def score(q: dict) -> tuple:
    """Higher is better. A complete item with a marked answer wins."""
    opts = q.get("options") or []
    return (
        len(opts) == 4,
        bool(q.get("answer")),
        len(q.get("stem") or ""),
        sum(len(o) for o in opts),
    )


def main() -> None:
    primary = json.loads((DATA / "hkeaa_mc_raw.json").read_text(encoding="utf-8"))
    extra_path = Path("/tmp/my_version.json")
    extra = json.loads(extra_path.read_text(encoding="utf-8")) if extra_path.exists() else []

    merged: dict[tuple, dict] = {}
    for q in list(primary) + list(extra):
        key = (q.get("year"), q.get("q"))
        if key not in merged or score(q) > score(merged[key]):
            merged[key] = q

    # Keep a record of the items that were only found by one extractor.
    seen_in = {}
    for q in list(primary):
        seen_in[(q.get("year"), q.get("q"))] = "vision"
    for q in list(extra):
        k = (q.get("year"), q.get("q"))
        seen_in[k] = "vision+geometry" if k in seen_in else "geometry"

    out = []
    for key in sorted(merged):
        q = dict(merged[key])
        elect = q.get("elect")
        q["elect"] = ELECTIVE_HINTS.get(elect, elect) if elect else None
        q["subtopic"] = SUBTOPIC_HINTS.get(key, q.get("subtopic"))
        q["found_by"] = seen_in.get(key, "unknown")
        out.append(q)

    (DATA / "hkeaa_mc_raw.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    print(f"merged {len(out)} official items")
    print("by elective:", dict(Counter(q["elect"] for q in out)))
    print("by extractor:", dict(Counter(q["found_by"] for q in out)))
    for q in out:
        print(f"  {q['year']} Q{q['q']:>2} {q['elect']} ans={q['answer']} "
              f"({q['found_by']})")


if __name__ == "__main__":
    main()
