#!/usr/bin/env python3
"""
Repair the three figure-bearing HKEAA items.

The geometric extractor only captured the first line of these stems and no
explanation. The full wording, and the reasoning behind the official answer,
were read off the slides themselves (see data/hkeaa_NOTES.md).

Usage:  python scripts/repair_figure_items.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

REPAIRS = {
    ("2022", "13"): {
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
    },
    ("2024", "9"): {
        "stem": ("Refer to the figure below, which shows a section of coast. "
                 "The prevailing wind direction of this area is __________."),
        "options": ["south-west", "west", "north", "east"],
        "answer": "D",
        "explanation": ("With north oriented upwards, the blue arrow shows the "
                        "air moving towards the west. Wind directions are named "
                        "for where the wind comes FROM, so the wind comes from "
                        "the east. The red arrow along the spit shows the "
                        "direction of spit growth, not the wind."),
    },
    ("2024", "13"): {
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
    },
}


def main() -> None:
    path = DATA / "mc_bank.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for q in bank.get("questions", []):
        if not q.get("official"):
            continue
        key = (str(q.get("year")), str(q.get("q")))
        rep = REPAIRS.get(key)
        if not rep:
            continue
        for field, value in rep.items():
            if q.get(field) != value:
                q[field] = value
                changed += 1
        q["subtopic_title"] = q["stem"][:60]
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"repaired {changed} fields")


if __name__ == "__main__":
    main()
