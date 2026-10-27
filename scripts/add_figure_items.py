#!/usr/bin/env python3
"""
Add the HKEAA items whose figure IS printed on the slide itself.

The earlier pass skipped any item that referred to a figure that was not on
the slide, because a question without its figure is useless. But three of
those slides do carry their own figure:

  2022 Q13  the three population-density graphs are printed on the slide
  2024 Q9   the coastal spit diagram with the wind arrow is printed on it
  2024 Q13  the aerial photograph of the container yard is printed on it

Those are usable, because the site shows the slide. The rest stay out:

  2023 Q2   needs the Hong Kong map extract, which is not on the slide
  2024 Q6   needs the map extract for grid square 0979
  2025 Q3   needs the map extract for the footpath gradient

Usage:  python scripts/add_figure_items.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# Transcribed from the slide itself. The asterisk is HKEAA's.
FIGURE_ITEMS = [
    {
        "year": 2022, "q": 13, "paper": "Paper 1", "elect": "CP1",
        "subtopic": "CP1.1.3",
        "stem": ("The graphs below show the changes in population density at "
                 "different stages of development of a city. Which of the "
                 "following statements is/are correct? (1) Population density "
                 "decreases with the distance from the city centre at the "
                 "different stages of development. (2) More people move back to "
                 "the city centre at the later stage of development. (3) The "
                 "city experiences urban growth."),
        "options": ["(1) only", "(3) only", "(1) and (2) only",
                    "(2) and (3) only"],
        "answer": "B",
        "explanation": ("Statement (1) is false because at stage 3 population "
                        "density first rises with distance from the centre. "
                        "Statement (2) is false because stage 3 shows outward "
                        "and suburban growth, not movement back to the centre. "
                        "Statement (3) is correct: the later-stage graph shows "
                        "the city growing and expanding outward."),
        "source_page": 18,
        "source_url": ("https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_"
                       "Information/geog/GEOG-PowerPoint-2022.pdf"),
        "slide_image": "slide_crops/hkeaa-2022-p18.png",
    },
    {
        "year": 2024, "q": 9, "paper": "Paper 1", "elect": "CP2",
        "subtopic": "CP2.2.4",
        "stem": ("Refer to the figure below, which shows a section of coast. "
                 "The prevailing wind direction of this area is __________."),
        "options": ["south-west", "west", "north", "east"],
        "answer": "D",
        "explanation": ("With north oriented upwards, the blue arrow shows the "
                        "air moving towards the west. Wind directions are named "
                        "for where the wind comes FROM, so the wind comes from "
                        "the east. The red arrow along the spit shows the "
                        "direction of spit growth, not the wind."),
        "source_page": 18,
        "source_url": ("https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_"
                       "Information/geog/GEOG-PowerPoint-2024.pdf"),
        "slide_image": "slide_crops/hkeaa-2024-p18.png",
    },
    {
        "year": 2024, "q": 13, "paper": "Paper 1", "elect": "CP4",
        "subtopic": "CP4.3.1",
        "stem": ("Refer to the photograph below, which shows land use X in Hong "
                 "Kong. Which of the following adverse social impacts is/are "
                 "brought about by land use X? (1) traffic congestion "
                 "(2) unpleasant view (3) disruption of rural lifestyle"),
        "options": ["(1) only", "(1) and (2) only", "(2) and (3) only",
                    "(1), (2) and (3)"],
        "answer": "D",
        "explanation": ("The container yard brings heavy truck traffic into and "
                        "out of the area, so traffic congestion is an impact as "
                        "well as the unpleasant view and the disruption of the "
                        "rural lifestyle."),
        "source_page": 20,
        "source_url": ("https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_"
                       "Information/geog/GEOG-PowerPoint-2024.pdf"),
        "slide_image": "slide_crops/hkeaa-2024-p20.png",
    },
]


def main() -> None:
    bank_path = DATA / "mc_bank.json"
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])
    existing = {q.get("id") for q in questions}

    added = 0
    for item in FIGURE_ITEMS:
        q = dict(item)
        q["topics"] = [q["elect"]]
        q["subtopic_title"] = q["stem"][:60]
        q["source"] = (f"HKEAA {q['paper']} {q['year']} Item {q['q']} "
                       f"(official examination briefing)")
        q["id"] = f"hkeaa-{q['year']}-q{q['q']}"
        q["official"] = True
        q["found_by"] = "vision"
        if q["id"] in existing:
            continue
        questions.append(q)
        added += 1

    questions.sort(key=lambda q: (0 if q.get("official") else 1,
                                   q.get("topics", ["ZZ"])[0],
                                   q.get("subtopic", ""),
                                   q.get("stem", "")))
    bank["questions"] = questions
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    from collections import Counter
    print(f"added {added}; bank holds {len(questions)}")
    print("official:", sum(1 for q in questions if q.get("official")))
    print("by elective:", dict(Counter(t for q in questions for t in q.get("topics", []))))


if __name__ == "__main__":
    main()
