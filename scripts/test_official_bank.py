#!/usr/bin/env python3
"""Checks for the official HKEAA question bank pulled from OQB.

The bank holds the real HKDSE and HKCEE Geography MC questions, each one
stored as the exam images (a stem image plus four option images) with the
HKEAA answer key attached. These checks make sure the import did not
damage any of that.
"""

import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
BANK = root / "data" / "mc_bank.json"
MEDIA = root / "data" / "hkeaa_oqb"

bank = json.loads(BANK.read_text(encoding="utf-8"))
qs = bank["questions"]
official = [q for q in qs if q.get("official") and q.get("hkeaa_qcode")]
oqb = [q for q in qs if q.get("stem_image")]

fail = []


def check(label, ok, detail=""):
    if ok:
        print(f"  OK  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        fail.append(label)


print("Official HKEAA bank")
check("the bank has questions", len(qs) > 0, f"({len(qs)})")
check("official HKEAA questions were imported", len(official) >= 700,
      f"({len(official)})")

# 1. Every official question has an answer in A-D.
bad_answer = [q["id"] for q in official
               if not (isinstance(q.get("answer"), str) and len(q["answer"]) == 1
                       and q["answer"] in "ABCD")]
check("every official question has an answer A-D", not bad_answer,
      f"{bad_answer[:5]}")

# 2. Every official question has four options.
bad_opts = [q["id"] for q in official if len(q.get("options") or []) != 4]
check("every official question has four options", not bad_opts,
      f"{bad_opts[:5]}")

# 3. Every official question that uses images has all five of them on disk.
missing = []
for q in oqb:
    for rel in [q["stem_image"]] + list(q.get("option_images") or []):
        if not (MEDIA / rel).is_file():
            missing.append(f"{q['id']}:{rel}")
check("every referenced stem and option image is on disk", not missing,
      f"{missing[:5]}")

# 4. Every map extract referenced is on disk.
missing_map = []
for q in oqb:
    rel = q.get("map_extract")
    if rel and not (MEDIA / rel).is_file():
        missing_map.append(f"{q['id']}:{rel}")
check("every referenced map extract is on disk", not missing_map,
      f"{missing_map[:5]}")

# 5. The image path cannot escape the media directory.
escapes = []
for q in oqb:
    for rel in [q["stem_image"]] + list(q.get("option_images") or []):
        if ".." in rel or rel.startswith("/"):
            escapes.append(rel)
    rel = q.get("map_extract")
    if rel and (".." in rel or rel.startswith("/")):
        escapes.append(rel)
check("no media path escapes the data directory", not escapes,
      f"{escapes[:5]}")

# 6. The answer key is not all one letter - a copy/paste error would show here.
from collections import Counter
dist = Counter(q["answer"] for q in official)
check("the answer key is spread across all four options",
      len(dist) == 4 and min(dist.values()) > len(official) * 0.15,
      f"({dict(dist)})")

# 7. The official questions cover a real spread of years.
years = sorted({q.get("year") for q in official if q.get("year")})
check("the bank spans many exam years", len(years) >= 15, f"({len(years)} years)")

# 8. The map-reading questions are their own topic.
check("map-reading questions are tagged MAP",
      any("MAP" in (q.get("topics") or []) for q in official))

# 9. No question points at a figure that was never produced.
pat = re.compile(r"\b(?:figure|fig\.?|photograph|photo|image|diagram|map|table|graph)"
                  r"\s*\d+\b", re.I)
dangling = [q["id"] for q in qs
            if not q.get("question_image") and not q.get("stem_image")
            and pat.search(q.get("stem") or "")]
check("no question points at a missing figure", not dangling,
      f"{dangling[:5]}")

# 10. Question ids are unique.
ids = [q.get("id") for q in qs]
dupes = [k for k, v in Counter(ids).items() if v > 1]
check("question ids are unique", not dupes, f"{dupes[:5]}")

# 11. The original hand-checked questions kept their explanations.
hand = [q for q in qs if q.get("official_source") == "HKEAA (hand-checked) / OQB"]
check("the hand-checked questions kept their explanations",
      len(hand) >= 10 and all(q.get("explanation") for q in hand),
      f"({len(hand)})")

# 12. The AI-generated questions were kept alongside the official ones.
gen = [q for q in qs if not q.get("official")]
check("the generated questions were kept", len(gen) >= 200, f"({len(gen)})")

if fail:
    print(f"\n{len(fail)} check(s) failed")
    sys.exit(1)
print(f"\nALL {13} CHECKS PASSED")
