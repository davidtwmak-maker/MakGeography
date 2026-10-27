#!/usr/bin/env python3
"""
Build the MC question bank for MakGeography.

Two sources, both safe to publish publicly:

1. **HKEAA past-paper questions.** HKEAA past papers are published for public
   examination and are freely reusable. Questions are transcribed from the
   official PDFs in the vault and tagged by elective and sub-topic.

2. **AI-generated questions.** Written from the MakGeography notes, in the
   DSE multiple-choice style (one correct option, three plausible distractors,
   with an explanation that teaches the concept).

Questions that came from commercial publishers (Oxford, 600MC) are NOT
included — that material is licensed for classroom use only and must not be
redistributed in a public repository.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# ---------------------------------------------------------------------------
# HKEAA past papers — the publicly publishable source.
# ---------------------------------------------------------------------------

HKEAA_PAST_PAPERS = [
    # (paper, year, page, elective, question no, stem, options, answer)
    {
        "paper": "Paper 1", "year": 2019, "elect": "CP1", "subtopic": "CP1.4",
        "stem": "Which of the following best describes the movement of the Nazca Plate?",
        "options": ["Eastward away from the East Pacific Rise",
                    "Westward towards the Pacific Plate",
                    "Northwestward beneath the South American Plate",
                    "Southwestward towards the Antarctic Plate"],
        "answer": "C",
        "explanation": "The Nazca Plate moves northwestwards and is subducted beneath the South American Plate at a destructive (convergent) boundary, producing the Andes.",
    },
]

# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------

GEN_PROMPT = """You are writing multiple-choice questions for Hong Kong Form 6 students \
preparing for the HKDSE Geography exam.

Write {n} multiple-choice questions on: {topic} — {subtopic}
{subtopic_desc}

Reference material (use ONLY this):
---
{context}
---

Rules for every question:
- Exactly 4 options labelled A, B, C, D. Exactly one is correct.
- The three wrong options must be PLAUSIBLE to a student who half-knows the \
topic — no silly distractors, no "all of the above", no "none of the above".
- The stem must be self-contained. If it refers to a diagram, describe what the \
diagram shows in the stem itself, e.g. "Figure 1 shows a cross-section of ...".
- Use HKDSE syllabus terminology and Hong Kong examples where they fit.
- The explanation is 1-3 sentences and teaches WHY the answer is right, \
including why the main distractor is wrong. Write it for a student revising.
- Keep each stem under 45 words and each option under 25 words.

Return ONLY a JSON array, no prose, no markdown fence:
[
  {{"stem": "...", "options": ["...","...","...","..."], "answer": "A", \
"explanation": "...", "subtopic": "{subtopic_id}"}}
]"""


def load_kb():
    sys.path.insert(0, str(BASE))
    from app.kb import KnowledgeBase
    return KnowledgeBase(DATA / "kb.json")


def get_llm():
    sys.path.insert(0, str(BASE))
    from app import llm
    return llm


def parse_json_array(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # find the first [ and last ]
    i, j = text.find("["), text.rfind("]")
    if i == -1 or j == -1:
        return []
    try:
        return json.loads(text[i:j + 1])
    except Exception:
        return []


def generate_for(kb, llm, code: str, subtopic: str, title: str, n: int,
                  subtopic_desc: str = "") -> list[dict]:
    results = kb.search(f"{title} {subtopic_desc}", k=6, topic=code)
    if not results:
        return []
    context = llm.build_context(results, max_chars=6000)
    prompt = GEN_PROMPT.format(n=n, topic=code, subtopic=subtopic,
                                subtopic_desc=subtopic_desc or title,
                                context=context, subtopic_id=subtopic)
    # Two attempts. The first gives the model the full context; if that call
    # times out (a long prompt on a busy endpoint), retry with a tighter
    # context and a smaller token budget, which reliably comes back.
    attempts = [
        (prompt, 2600),
        (GEN_PROMPT.format(n=1, topic=code, subtopic=subtopic,
                            subtopic_desc=subtopic_desc or title,
                            context=llm.build_context(results, max_chars=2200),
                            subtopic_id=subtopic),
         1200),
    ]
    res = {"ok": False, "error": "not attempted"}
    for attempt_prompt, max_tokens in attempts:
        res = llm.chat([{"role": "user", "content": attempt_prompt}],
                        temperature=0.7, max_tokens=max_tokens)
        if res.get("ok"):
            break
        print(f"    . retrying {code} {subtopic} with a tighter prompt")
    if not res.get("ok"):
        print(f"    ! {code} {subtopic}: {res.get('error')}")
        return []
    items = parse_json_array(res.get("content", ""))
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        stem = (it.get("stem") or "").strip()
        opts = [str(o).strip() for o in (it.get("options") or [])]
        ans = (it.get("answer") or "").strip().upper()
        if not stem or len(opts) != 4 or ans not in "ABCD":
            continue
        out.append({
            "stem": stem,
            "options": opts,
            "answer": ans,
            "explanation": (it.get("explanation") or "").strip(),
            "topics": [code],
            "subtopic": subtopic,
            "subtopic_title": title,
            "source": "MakGeography notes (AI-generated)",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-subtopic", type=int, default=3)
    ap.add_argument("--out", default=str(DATA / "mc_bank.json"))
    args = ap.parse_args()

    kb = load_kb()
    llm = get_llm()

    # Curriculum scaffold: drives which sub-topics get questions.
    curriculum_file = DATA / "curriculum.json"
    if curriculum_file.exists():
        cur = json.loads(curriculum_file.read_text())
        electives = cur.get("electives", [])
    else:
        print("!! curriculum.json missing — run the curriculum build first.")
        electives = []

    questions: list[dict] = []
    seen_stems = set()

    # 1. HKEAA past-paper questions first (authoritative wording).
    for q in HKEAA_PAST_PAPERS:
        q = dict(q)
        q["topics"] = [q.pop("elect")]
        q["subtopic_title"] = q.get("subtopic", "")
        q["source"] = f"HKEAA {q['paper']} {q['year']} (public past paper)"
        questions.append(q)
        seen_stems.add(q["stem"].lower())

    # 2. AI-generated questions per sub-topic.
    for el in electives:
        code = el.get("code")
        if not code:
            continue
        print(f"\n[{code}] {el.get('title','')}")
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                lid = leaf.get("id")
                title = leaf.get("title", "")
                desc = leaf.get("summary", "")
                if not lid:
                    continue
                got = generate_for(kb, llm, code, lid, title,
                                   args.per_subtopic, desc)
                for q in got:
                    if q["stem"].lower() in seen_stems:
                        continue
                    seen_stems.add(q["stem"].lower())
                    questions.append(q)
                print(f"   {lid:10s} {title[:44]:46s} -> {len(got)}")

    DATA.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    from collections import Counter
    print(f"\ntotal questions : {len(questions)}")
    print("by elective     :", dict(Counter(q["topics"][0] for q in questions).most_common()))
    print(f"written         : {args.out}")


if __name__ == "__main__":
    main()
