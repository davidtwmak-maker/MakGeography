#!/usr/bin/env python3
"""
Make the remaining "The table shows ..." / "The graph shows ..." stems
self-contained.

After repair_dangling_figures.py, no stem points at a figure NUMBER that
was never produced. But a stem can still say "The table shows the
relationship between X and Y" and then not give the relationship - the
student is told a table exists and is not shown it.

For these, the wording changes to describe the relationship in words, so
the question can be answered from the stem alone.

Usage:  python scripts/repair_dangling_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "data" / "mc_bank.json"

# id -> (old stem, new stem)
REPAIRS = {
    "CP6.2.5-25ea5475": (
        "The table shows the relationship between deforestation rate and "
        "carbon surplus. Which conclusion is most consistent with the data "
        "and the rainforest carbon cycle?",
        "In tropical rainforests, a higher rate of deforestation is "
        "associated with a larger carbon surplus - the carbon released "
        "from cleared forest exceeds the carbon the remaining forest "
        "absorbs. Which conclusion is most consistent with this "
        "relationship and the rainforest carbon cycle?",
    ),
}

# A stem that names a table or graph must carry a figure of its own, so
# the student can actually work with the data.
def has_inline_data(stem: str) -> bool:
    return any(ch.isdigit() for ch in stem)


def main() -> None:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    done = []
    for q in questions:
        qid = q.get("id")
        if qid not in REPAIRS:
            continue
        old, new = REPAIRS[qid]
        if q.get("stem") != old:
            print(f"  SKIP {qid}: stem has changed, review manually")
            continue
        q["stem"] = new
        q["figure_reference_repaired"] = True
        done.append((qid, old, new))

    bank["questions"] = questions
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"repaired {len(done)} table/graph stems")
    for qid, old, new in done:
        print()
        print(f"  {qid}")
        print(f"    - {old}")
        print(f"    + {new}")

    # Report any stem that still names a table or graph with no data.
    print()
    print("=== stems still naming a table/graph with no numbers ===")
    left = 0
    for q in questions:
        s = (q.get("stem") or "")
        low = s.lower()
        if ("the table shows" in low or "the graph shows" in low
                or "a graph of" in low) and not has_inline_data(s):
            print(f"  {q.get('id')}: {s[:150]}")
            left += 1
    if not left:
        print("  (none)")


if __name__ == "__main__":
    main()
