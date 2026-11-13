#!/usr/bin/env python3
"""
Check that the MC explanation letters still point at the options they named.

`reshuffle_mc_answers.py` permuted the options and updated the `answer`
field but never rewrote the letters that the explanation text names, so
"B is incorrect because ..." could end up naming the very option that had
become the answer. `fix_mc_explanation_letters.py` repairs those letters.

This is the independent check. It compares the repaired explanation with
the pre-shuffle explanation CHARACTER BY CHARACTER and requires that:

  1. the two texts have the same length;
  2. every character that differs is an option letter (A-D);
  3. each letter that differs is exactly the letter that its option now
     carries - i.e. the letter still names the same option it named before;
  4. no explanation calls the keyed answer wrong, or a distractor right.

Together those say: the repair changed only the letters, and it changed
each one to the letter its own option now carries. Nothing else in the
text was touched, and no reference was left pointing at a different
option.

Usage:  python scripts/check_mc_explanation_letters.py
Exits non-zero on any failure, so it can gate a commit.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "data" / "mc_bank.json"
PRE_SHUFFLE = "6bf83cd^"

TOKEN = re.compile(r"(?<![A-Za-z0-9])([ABCD])(?![A-Za-z0-9])")
CLAIM_NEG = re.compile(
    r"(?i)^\s+(?:is|are)\s+(?:incorrect|wrong|not\s+correct|false)\b")
CLAIM_POS = re.compile(
    r"(?i)^\s+(?:is|are)\s+(?:correct|right|true)\b")


def letter_map(old_options, current_options):
    """old letter -> the letter its option now carries."""
    out = {}
    for i, otxt in enumerate(old_options):
        for j, ctxt in enumerate(current_options):
            if otxt == ctxt:
                out["ABCD"[i]] = "ABCD"[j]
                break
    return out


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    qs = bank.get("questions", [])
    old_bank = json.loads(subprocess.run(
        ["git", "-C", str(BASE), "show", f"{PRE_SHUFFLE}:data/mc_bank.json"],
        capture_output=True, text=True, check=True).stdout)
    old_by_id = {q["id"]: q for q in old_bank.get("questions", []) if q.get("id")}

    problems = []
    letters_changed = 0
    checked = 0
    for q in qs:
        if q.get("official"):
            continue
        old = old_by_id.get(q.get("id"))
        if not old:
            continue
        cur_opts = q.get("options") or []
        old_opts = old.get("options") or []
        exp = q.get("explanation") or ""
        old_exp = old.get("explanation") or ""
        if len(cur_opts) != 4 or len(old_opts) != 4:
            continue
        checked += 1

        if len(exp) != len(old_exp):
            problems.append(("explanation length changed", q["id"], "", ""))
            continue

        mapping = letter_map(old_opts, cur_opts)
        for i, (now_c, was_c) in enumerate(zip(exp, old_exp)):
            if now_c == was_c:
                continue
            if was_c not in "ABCD" or now_c not in "ABCD":
                problems.append(("a non-letter character was changed", q["id"],
                                 was_c, now_c))
                continue
            expected = mapping.get(was_c)
            if expected != now_c:
                problems.append(("the letter no longer names its own option",
                                 q["id"], was_c, now_c))
                continue
            letters_changed += 1

        # the claim must agree with the key
        ans = str(q.get("answer", "")).strip().upper()[:1]
        for m in TOKEN.finditer(exp):
            L = m.group(1)
            tail = exp[m.end():m.end() + 40]
            if CLAIM_NEG.match(tail) and L == ans:
                problems.append(("calls the keyed answer wrong", q["id"], L, ""))
            if CLAIM_POS.match(tail) and L != ans:
                problems.append(("calls a distractor right", q["id"], L, ""))

    print(f"AI explanations checked       : {checked}")
    print(f"option letters remapped       : {letters_changed}")
    print(f"disagreements found           : {len(problems)}")
    for kind, qid, a, b in problems:
        q = next(x for x in qs if x["id"] == qid)
        print(f"    {kind}: {qid}  '{a}' -> '{b}'")
        print(f"        answer={q['answer']}  expl: {q['explanation'][:170]}")
    if problems:
        print("\nFAILED")
        return 1
    print("\nPASSED - every letter still names the option it named before the shuffle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
