#!/usr/bin/env python3
"""
Repair the AI-generated MC questions that point at a figure that does not
exist.

The bank builder's prompt tells the model to make the stem self-contained
BY DESCRIBING the diagram in the stem - and it gives the example
"Figure 1 shows a cross-section of ...". The model follows the example
literally, so the stem says "Figure 1 shows ..." while no figure is ever
created. The question reads as if a figure is attached, and the student
hunts for one that is not there.

Every one of these questions already describes the visual in full in the
stem itself, so the question is answerable - it just names a figure that
is not shown. The repair removes the dangling reference and keeps the
description, so the stem reads as a self-contained textual description.

A question that shows a REAL image is left alone: the 13 official HKEAA
items carry the exam figure, and their "Refer to the figure below"
wording is correct as it stands.

Usage:  python scripts/repair_dangling_figures.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "data" / "mc_bank.json"

# A stem that refers to a visual. The question is only broken if no image
# is attached.
VISUAL_REF = re.compile(
    r"\b(figure|fig\.?|photograph|photo|image|map|table|extract|diagram|"
    r"cross[- ]section|outline development plan|graph)\b",
    re.I,
)

# "Figure 1 shows ..." / "Figure 2 describes ..." / "The table shows ..."
# -> "The ..." is wrong for the table, so the leading article is rebuilt
# from the word that follows.
FIG_LEAD = re.compile(
    r"^(?:the\s+)?(?:figure|fig\.?|table|photograph|photo|image|graph|diagram|map)\s*"
    r"\d*\s*(?:shows|shows the|describes|depicts|illustrates|is|presents)?\s*",
    re.I,
)


def needs_repair(stem: str, image: str | None) -> bool:
    if image:
        return False
    return bool(VISUAL_REF.search(stem))


def repair_stem(stem: str) -> tuple[str, bool]:
    """Remove a dangling figure reference. Returns (stem, changed).

    "Figure 1 shows a cross-section of rock layers ..." becomes
    "A cross-section of rock layers ..." - the description is kept and the
    reference to a picture that was never produced is dropped.
    """
    text = stem.strip()

    m = re.match(
        r"^(?:refer to\s+)?(?:the\s+)?(figure|fig\.?|table|photograph|photo|"
        r"image|graph|diagram|map)\s*(\d+)?\s*",
        text,
        re.I,
    )
    if not m:
        return text, False

    word = m.group(1).lower().rstrip(".")
    rest = text[m.end():]

    # Drop the verb the model used ("shows", "describes", "is" ...).
    vm = re.match(
        r"^(shows|shows the|describes|depicts|illustrates|presents|is|are)\s+",
        rest, re.I,
    )
    if vm:
        rest = rest[vm.end():]
    rest = rest.strip()

    if not rest:
        return text, False

    if word in ("figure", "fig", "photograph", "photo", "image"):
        # The description becomes the subject. Choose the article from the
        # word that actually follows - "a cross-section", "an oxbow lake",
        # "two adjacent drainage basins".
        out = _with_article(rest)
    elif word == "table":
        out = f"The table shows {rest}"
    elif word == "graph":
        out = f"The graph shows {rest}"
    elif word in ("map", "diagram"):
        out = f"The {word} shows {rest}"
    else:
        out = rest

    out = re.sub(r"\s+", " ", out).strip()
    out = _with_article(out)
    out = out[0].upper() + out[1:] if out else out
    return out, True


# A noun phrase that takes no article: a mass noun or a plural.
_NO_ARTICLE_HEADS = (
    "folded rock", "two adjacent", "three adjacent", "several ", "many ",
    "deposited ", "abandoned ", "raised, ", "steep ",
)
# A head that takes "an".
_AN_HEADS = ("anticline", "oxbow", "anticlinal", "arch", "upward", "old ",
              "outline ", "oblique", "inclined", "exposed", "urban ",
              "underground ", "overland ", "aerial ",)


def _with_article(text: str) -> str:
    """Put "A" or "An" in front of a noun phrase if it needs one."""
    t = text.strip()
    if not t:
        return t
    if re.match(r"^(a|an|the|some|one|two|three|several|many|this|these|"
                r"refer|figure|fig|table|photograph|photo|image|graph|"
                r"diagram|map)\b", t, re.I):
        return t
    low = t.lower()
    if low.startswith(_NO_ARTICLE_HEADS):
        return t
    if low.startswith(_AN_HEADS):
        return f"An {t}"
    first = t.split()[0].rstrip(",.")
    article = "An" if first[:1].lower() in "aeiou" else "A"
    return f"{article} {t}"

def main() -> None:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    repaired = []
    for q in questions:
        stem = q.get("stem") or ""
        if not needs_repair(stem, q.get("question_image")):
            continue
        new_stem, changed = repair_stem(stem)
        if changed and new_stem != stem:
            q["stem"] = new_stem
            q["figure_reference_repaired"] = True
            repaired.append((q.get("id"), stem, new_stem))

    bank["questions"] = questions
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"repaired {len(repaired)} dangling figure references")
    for qid, old, new in repaired:
        print()
        print(f"  {qid}")
        print(f"    - {old}")
        print(f"    + {new}")


if __name__ == "__main__":
    main()
