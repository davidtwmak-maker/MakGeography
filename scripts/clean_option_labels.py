#!/usr/bin/env python3
"""
Strip redundant "A." style labels from MC options in the existing bank.

The model sometimes writes the option label even though the interface adds
one, so the option reads "A. A. Citywide average air temperature ...".

This cleans the bank in place without regenerating it, so the 12 verified
official HKEAA items and every curated question are preserved.

Usage:  python scripts/clean_option_labels.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

sys.path.insert(0, str(BASE / "scripts"))

from build_mc_bank import strip_option_label  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = DATA / "mc_bank.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    questions = bank["questions"] if isinstance(bank, dict) else bank

    changed = 0
    for q in questions:
        opts = q.get("options") or []
        cleaned = [strip_option_label(str(o), j) for j, o in enumerate(opts)]
        if cleaned != opts:
            changed += 1
            q["options"] = cleaned

    print(f"questions with a redundant label: {changed} of {len(questions)}")
    if args.dry_run:
        return

    path.write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"written: {path}")

    # Confirm none are left.
    left = 0
    for q in questions:
        for j, o in enumerate(q.get("options") or []):
            if re.match(r"^[A-Da-d]\s*[).:]", str(o).strip()):
                left += 1
    print("options still carrying a label:", left)


if __name__ == "__main__":
    main()
