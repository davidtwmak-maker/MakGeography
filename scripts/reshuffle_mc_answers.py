#!/usr/bin/env python3
"""
Spread the answer letters across the AI-generated MC questions.

The model that wrote these questions put the correct option first for 78%
of the CP6 set and 91% of the CP7 set - it writes "A" because that is how
it writes, not because A is more often right. A student drilling the bank
would learn to press A and nothing else.

This applies the same deterministic permutation the builder now uses: the
options are reordered by a hash of the question's stem, so the correct
letter is wherever the permutation puts it. The same question always gets
the same order, so a student who retries sees the same layout.

Only AI-generated questions are touched. The official HKEAA questions keep
their printed options and their printed answer letters - those are the
exam's own.

Usage:  python scripts/reshuffle_mc_answers.py [--dry]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "data" / "mc_bank.json"

DRAFTED = "AI-generated"


def shuffle_options(options: list[str], answer: str, key: str,
                    correct_text: str = "") -> tuple[list[str], str]:
    """Permute the options so the correct one is not always in one place.

    The model writes the answer it chose, and it chose "A" for 78% of the
    CP6 questions (91% for CP7) - it put the right answer first because that
    is how it writes. A student who learns to press A learns nothing.

    The permutation is driven by a hash of the question's stem, so the same
    question always gets the same order and a student who retries sees the
    same layout. `correct_text` identifies the right option by its WORDS
    rather than its position, which makes the operation idempotent: running
    it twice gives the same result, so the migration script is safe to
    re-run.
    """
    if len(options) != 4 or answer not in "ABCD":
        return options, answer
    correct = correct_text or options["ABCD".index(answer)]
    if correct not in options:
        correct = options["ABCD".index(answer)]
    others = [o for o in options if o != correct]
    if len(others) != 3:
        return options, answer
    # The distractors are sorted before the shuffle so the permutation is
    # applied to a CANONICAL order. Without that, the operation is not
    # idempotent: the second run starts from a different order, shuffles it
    # again, and the distractor letters shift even though the answer
    # letter does not.
    others = sorted(others)
    digest = hashlib.sha256(key.encode()).digest()
    # Fisher-Yates with the digest as the source of the swaps. The digest
    # is 32 bytes, so the first three drive the shuffle and the fourth
    # picks where the correct option lands.
    order = list(others)
    for i in range(len(order) - 1, 0, -1):
        j = digest[i] % (i + 1)
        order[i], order[j] = order[j], order[i]
    pos = digest[3] % 4
    order.insert(pos, correct)
    return order, "ABCD"[pos]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    bank = json.loads(BANK.read_text(encoding="utf-8"))
    qs = bank.get("questions", [])

    before = Counter()
    after = Counter()
    changed = 0

    for q in qs:
        if DRAFTED not in str(q.get("source", "")):
            continue
        before[q.get("answer")] += 1
        opts = list(q.get("options") or [])
        # The right option is identified by its WORDS, not its letter, so
        # the operation is idempotent and re-running it is safe. The
        # recorded text is the one the shuffle produced last time.
        correct_text = q.get("correct_option_text") or ""
        if not correct_text:
            correct_text = opts["ABCD".index(q.get("answer", "A"))] \
                if q.get("answer") in "ABCD" and len(opts) == 4 else ""
        new_opts, new_ans = shuffle_options(opts, q.get("answer", "A"),
                                             q.get("stem", ""),
                                             correct_text)
        if new_ans != q.get("answer") or new_opts != opts:
            changed += 1
        q["options"] = new_opts
        q["answer"] = new_ans
        q["correct_option_text"] = correct_text
        after[new_ans] += 1

    print(f"drafted questions : {sum(before.values())}")
    print(f"moved            : {changed}")
    print(f"before           : {dict(sorted(before.items()))}")
    print(f"after            : {dict(sorted(after.items()))}")
    total = sum(after.values()) or 1
    print(f"largest share    : {max(after.values()) / total:.0%} "
          f"(was {max(before.values()) / max(sum(before.values()), 1):.0%})")

    if args.dry:
        print("\n-- dry run, nothing written --")
        return

    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"\nwritten          : {BANK}")


if __name__ == "__main__":
    main()
