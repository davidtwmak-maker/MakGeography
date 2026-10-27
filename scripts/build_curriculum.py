#!/usr/bin/env python3
"""
Emit data/curriculum.json - the HKDSE Geography curriculum scaffold.

The structure comes from the official HKEAA Geography Curriculum and Assessment
Guide (edb.gov.hk), extracted to data/curriculum_from_official.json. This
script attaches the vault `source_hints` (which MakGeography note holds each
leaf's content) and writes the merged file the site reads.

Run it after editing either source.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# Which vault notes carry each leaf's content. Keyed by a distinctive phrase
# from the official leaf title.
HINTS = {
    "Earth's internal structure": ["1. Earth Structure Basics"],
    "Earth structure": ["1. Earth Structure Basics"],
    "Plate movement": ["2. Internal forces and processes"],
    "Internal forces": ["2. Internal forces and processes"],
    "Internal processes": ["2. Internal forces and processes"],
    "Volcanism": ["2.2.3 Volcanism", "3.4 Intraplate Volcanism- Hot Spot & Mantle Plume"],
    "Folding": ["2. Internal forces and processes", "3.1 Convergent Plate Boundaries"],
    "Faulting": ["2. Internal forces and processes", "3.3 Transform Plate Boundary"],
    "Tectonic landforms": ["3. Tectonic landforms and features"],
    "Convergent": ["3.1 Convergent Plate Boundaries"],
    "Divergent": ["3.2 Divergent Plate Boundaries"],
    "Transform": ["3.3 Transform Plate Boundary"],
    "Intraplate": ["3.4 Intraplate Volcanism- Hot Spot & Mantle Plume"],
    "Tectonic hazards": ["4. Tectonic Hazards"],
    "Volcanic eruptions": ["4.1 VOLCANIC ERUPTIONS"],
    "Earthquakes": ["4.2 EARTHQUAKES"],
    "Tsunamis": ["4.3 TSUNAMIS"],
    "Hazard management": ["4. Tectonic Hazards", "4.1 VOLCANIC ERUPTIONS",
                          "4.2 EARTHQUAKES", "4.3 TSUNAMIS"],
    "Opportunities and Risks": ["CP1 Opportunities and Risks. Is it rational to live."],
}

# Fallback: the main note for each elective.
GENERIC = {
    "CP1": ["1. Earth Structure Basics"],
    "CP2": ["1.0 River & Coastal environment"],
    "CP3": ["1.1 Industrial Location Factors — F6 Revision"],
    "CP4": ["4.1 Sustainable Development — F6 Revision"],
    "CP5": ["5.1 Agricultural Systems — F6 Revision"],
    "CP6": ["CP6 Disappearing Green Canopy Detailed Notes"],
    "CP7": ["CP7 Global Warming Detailed Notes"],
    "EP1": ["EP1 Dynamic Earth HK"],
}


def hints_for(title: str, code: str) -> list[str]:
    t = title.lower()
    for key, val in HINTS.items():
        if key.lower() in t:
            return val
    return GENERIC.get(code, [])


def main():
    src = DATA / "curriculum_from_official.json"
    cur = json.loads(src.read_text(encoding="utf-8"))
    n = 0
    for el in cur["electives"]:
        code = el.get("code", "")
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                leaf["source_hints"] = hints_for(leaf.get("title", ""), code)
                n += 1
    out = DATA / "curriculum.json"
    out.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"leaves with hints : {n}")
    print(f"written           : {out}")


if __name__ == "__main__":
    main()
