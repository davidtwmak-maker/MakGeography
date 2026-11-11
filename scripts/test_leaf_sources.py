#!/usr/bin/env python3
"""
A curriculum leaf must serve content, and an elective must not collapse.

CP6 and CP7 both had every leaf pointing at the same module note, so the
Notes page showed one outline under all 41 leaves and the Essay Generator
had 8,000 characters of outline to write from instead of the teacher's
concept notes. The material was there; the wiring was not.

Two leaves of the same elective sharing a note is FINE and normal - CP2's
five coastal leaves all draw on the teacher's one "River & Coastal
environment" note, because that is how he wrote it. The defect is the whole
elective serving ONE note while the vault holds several, so the test
checks that an elective REACHES its concept notes, not that every leaf is
alone.

Usage:  python scripts/test_leaf_sources.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import get_matcher  # noqa: E402

DATA = ROOT / "data"

# How many concept notes the vault holds for each elective. An elective
# with several notes must serve more than one.
CONCEPT_NOTE_COUNT = {
    "CP1": 12, "CP2": 7, "CP3": 7, "CP4": 7, "CP5": 6,
    "CP6": 18, "CP7": 23, "EP1": 12,
}


def main() -> int:
    cur = json.loads((DATA / "curriculum.json").read_text(encoding="utf-8"))
    kb = json.loads((DATA / "kb.json").read_text(encoding="utf-8"))
    kb_paths = {d.get("path", "").split("/")[-1] for d in kb.get("docs", [])}
    matcher = get_matcher()

    failures: list[str] = []
    total_leaves = 0

    for el in cur.get("electives", []):
        code = el.get("code", "")
        served: set[str] = set()
        leaf_count = 0
        code_failures: list[str] = []

        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                lid = leaf.get("id", "")
                total_leaves += 1
                leaf_count += 1

                # A named source note must exist in the knowledge base.
                src = leaf.get("source") or ""
                if src and src.split("/")[-1] not in kb_paths:
                    code_failures.append(
                        f"{lid}: source note is not in the KB - {src}")

                # The leaf must serve content.
                content = matcher.match(
                    matcher.hints_for(leaf), leaf.get("title", ""))
                if not content:
                    code_failures.append(f"{lid}: serves no content")
                    continue
                served.update(str(c.get("path") or "") for c in content)

        expected = CONCEPT_NOTE_COUNT.get(code)
        if expected and expected > 1 and len(served) < 2:
            code_failures.append(
                f"{code}: all {leaf_count} leaves serve ONE note - the "
                f"elective has {expected} concept notes that are never used")
        failures.extend(code_failures)
        print("%-5s leaves=%-4d notes served=%-4d %s" % (
            code, leaf_count, len(served),
            "OK" if not code_failures else f"{len(code_failures)} PROBLEM(S)"))

    print(f"\nleaves checked : {total_leaves}")

    if failures:
        print(f"FAIL - {len(failures)} problem(s):")
        for f in failures[:40]:
            print("  -", f)
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1

    print("\nPASS - every leaf serves content, every named source note is in")
    print("       the knowledge base, and no elective collapses onto one note.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
