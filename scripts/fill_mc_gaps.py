#!/usr/bin/env python3
"""
Fill the sub-topics that are missing from data/mc_bank.json.

The main builder can time out on a long prompt (a busy LLM endpoint), and a
timed-out sub-topic simply gets no questions. This script finds the gaps and
retries them with a tighter context, which comes back reliably.

Usage:  python scripts/fill_mc_gaps.py [--rounds 3]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
DATA = BASE / "data"


def load_kb():
    from app.kb import KnowledgeBase

    return KnowledgeBase(DATA / "kb.json")


def curriculum_leaves():
    """Every curriculum leaf with the official description that goes with it.

    The description matters: a title like "Braided rivers and channel
    networks" is too thin to prompt good questions on its own, whereas
    the official summary names the landform, the process and the case
    study, which is what the question needs.
    """
    cur = json.loads((DATA / "curriculum.json").read_text(encoding="utf-8"))
    leaves = []
    for el in cur["electives"]:
        code = el.get("code", "")
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                leaves.append((code, leaf.get("id", ""), leaf.get("title", ""),
                               leaf.get("summary", "")))
    return leaves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--per-subtopic", type=int, default=2)
    args = ap.parse_args()

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bmc", str(BASE / "scripts" / "build_mc_bank.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_mc_bank.py")
    bmc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bmc)

    kb = load_kb()
    llm = bmc.get_llm()
    bank_path = DATA / "mc_bank.json"
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    for rnd in range(args.rounds):
        have = {q.get("subtopic") for q in questions}
        gaps = [(c, i, t, d) for c, i, t, d in curriculum_leaves()
                if i and i not in have]
        if not gaps:
            print("no gaps left")
            break
        print(f"\n=== round {rnd + 1}: {len(gaps)} gap(s) ===")
        for code, lid, title, _ in gaps:
            print(f"  {lid:12s} {title[:50]}")
            got = bmc.generate_for(kb, llm, code, lid, title,
                                   args.per_subtopic, _)
            if got:
                questions.extend(got)
                print(f"    -> {len(got)}")
            else:
                print("    -> still failed")

        bank["questions"] = questions
        bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"  bank now holds {len(questions)} questions")

    from collections import Counter

    print("\nby elective:", dict(Counter(t for q in questions for t in q.get("topics", []))))


if __name__ == "__main__":
    main()
