#!/usr/bin/env python3
"""
Replace MC questions that test the syllabus list instead of the geography.

A few generated questions asked which items appear in a curriculum list,
e.g. "The Module 2 consequences list includes flooding, erosion and
pollution. Which pair of other consequences is included in the same
list?" That is a question about the syllabus, not a geography question, so
it is not useful practice for a student.

This finds those questions and regenerates them with a prompt that asks for
a Section A style item on the heading's geography. Questions that merely
happen to contain the words "which pair of" are left alone - only the ones
that name a syllabus list are replaced.

Usage:  python scripts/replace_meta_questions.py [--dry-run]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# A stem that names a syllabus LIST and asks what is in it.
META = re.compile(
    r"(consequences list|list includes|which items appear|"
    r"included in the same list|in the same list|"
    r"(Module|Topic|Guiding question)s?\s*\d?\s*(list|includes))",
    re.I,
)

# A stem that is a genuine geography question but happens to match a
# looser pattern - these are kept.
KEEP = re.compile(
    r"which pair of (conditions|processes|features|factors|landforms|"
    r"measures|outcomes|statements|reasons|types)", re.I)


def is_meta(stem: str) -> bool:
    if KEEP.search(stem):
        return False
    return bool(META.search(stem))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location(
        "bmc", str(BASE / "scripts" / "build_mc_bank.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_mc_bank.py")
    bmc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bmc)

    path = DATA / "mc_bank.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    questions = bank["questions"] if isinstance(bank, dict) else bank

    targets = [q for q in questions if is_meta(q.get("stem", ""))]
    print(f"meta-questions found: {len(targets)}")
    for q in targets:
        print(f"  {q['id']:24} {q['stem'][:90]}")
    if not targets:
        return
    if args.dry_run:
        return

    cur = json.loads((DATA / "curriculum.json").read_text(encoding="utf-8"))
    leaf_info = {}
    for el in cur["electives"]:
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                leaf_info[leaf.get("id")] = (
                    el.get("code", ""), leaf.get("title", ""),
                    leaf.get("summary", ""))

    kb = bmc.load_kb()
    llm = bmc.get_llm()

    replaced = 0
    for q in targets:
        lid = q.get("subtopic")
        code, title, desc = leaf_info.get(lid, ("", q.get("subtopic_title", ""), ""))
        got = bmc.generate_for(kb, llm, code, lid, title, 1, desc)
        if not got:
            print(f"  {lid}: regeneration failed, keeping the original")
            continue
        new = got[0]
        if is_meta(new.get("stem", "")):
            print(f"  {lid}: replacement still a meta-question, keeping the original")
            continue
        q["stem"] = new["stem"]
        q["options"] = new["options"]
        q["answer"] = new["answer"]
        q["explanation"] = new["explanation"]
        replaced += 1
        print(f"  {lid}: replaced")
        print(f"    {new['stem'][:100]}")

    path.write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\nreplaced {replaced}; bank holds {len(questions)}")


if __name__ == "__main__":
    main()
