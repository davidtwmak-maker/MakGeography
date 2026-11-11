#!/usr/bin/env python3
"""
Point each CP6 and CP7 curriculum leaf at its own concept note.

CP6 and CP7 are the two electives whose leaves all named the SAME source
note - "CP6 Disappearing Green Canopy Detailed Notes" for all 18 CP6 leaves
and "CP7 Global Warming Detailed Notes" for all 23 CP7 leaves. The Notes
page then served that one note under every leaf, so a student drilling to
"Causes of deforestation" saw the whole module, and the Essay Generator
built a CP6 essay from 8,000 characters of outline with none of the
detailed concept notes the teacher actually wrote.

The material was never missing. There are 18 CP6 concept notes
(CP6/Concepts/6.1 - 6.18) and 23 CP7 concept notes (CP7/Concepts/7.1 -
7.23), all in the KB, all indexed by their own path. They were simply
never connected to the leaves.

The teacher's own PART numbering decides the mapping: leaf CP6.1.1 carries
the teacher label "PART 1, 1.1 Characteristics", and concept note 6.1 is
"6.1 Tropical Rainforest Characteristics". The note numbers are the
chapter numbers of the teacher's long note, and the leaf labels quote them.

Usage:  python scripts/map_concept_notes.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
CURRICULUM = DATA / "curriculum.json"
OFFICIAL = DATA / "curriculum_from_official.json"

# Leaf id -> the concept note that carries its content, as a path relative
# to the DSE Geography folder. The path is what the matcher resolves, so it
# must be the note's real filename.
CONCEPT_SOURCE = {
    # --- CP6: Disappearing Green Canopy -------------------------------------
    "CP6.1.1": "CP6/Concepts/6.1 Tropical Rainforest Characteristics (F6 Revision).md",
    "CP6.1.2": "CP6/Concepts/6.2 Rainforest Structure (F6 Revision).md",
    "CP6.1.3": "CP6/Concepts/6.3 Nutrient Cycle (F6 Revision).md",
    "CP6.1.4": "CP6/Concepts/6.4 Energy Flow and Ecological Equilibrium (F6 Revision).md",
    "CP6.2.1": "CP6/Concepts/6.5 Causes of Deforestation (F6 Revision).md",
    "CP6.2.2": "CP6/Concepts/6.6 Impacts of Deforestation (F6 Revision).md",
    "CP6.2.3": "CP6/Concepts/6.7 Deforestation Patterns (F6 Revision).md",
    "CP6.2.4": "CP6/Concepts/6.8 Carbon Cycle (F6 Revision).md",
    "CP6.2.5": "CP6/Concepts/6.9 Global Distribution and Rate (F6 Revision).md",
    "CP6.3.1": "CP6/Concepts/6.10 Traditional Livelihood and Forest Dependence (F6 Revision).md",
    "CP6.3.2": "CP6/Concepts/6.11 Impacts on Indigenous Communities (F6 Revision).md",
    "CP6.4.1": "CP6/Concepts/6.12 Sustainable Management of Rainforests (F6 Revision).md",
    "CP6.4.2": "CP6/Concepts/6.13 Reforestation (F6 Revision).md",
    "CP6.4.3": "CP6/Concepts/6.14 Biofuels as an Alternative (F6 Revision).md",
    "CP6.4.4": "CP6/Concepts/6.15 Roles of Different Parties (F6 Revision).md",
    "CP6.4.5": "CP6/Concepts/6.16 Afforestation and Protected Areas (F6 Revision).md",
    "CP6.5.1": "CP6/Concepts/6.17 Feedback Mechanisms (F6 Revision).md",
    "CP6.5.2": "CP6/Concepts/6.18 Climate Change Impacts on Forests (F6 Revision).md",
    # --- CP7: Global Warming ------------------------------------------------
    "CP7.1.1": "CP7/Concepts/7.1 Earth's Energy Balance (F6 Revision).md",
    "CP7.1.2": "CP7/Concepts/7.2 The Greenhouse Effect (F6 Revision).md",
    "CP7.1.3": "CP7/Concepts/7.3 Evidence of Global Warming (F6 Revision).md",
    "CP7.1.4": "CP7/Concepts/7.4 Weather, Climate & Scales (F6 Revision).md",
    "CP7.2.1": "CP7/Concepts/7.5 Greenhouse Gases (F6 Revision).md",
    "CP7.2.2": "CP7/Concepts/7.6 Human Activities (F6 Revision).md",
    "CP7.2.3": "CP7/Concepts/7.7 Natural vs Human Causes (F6 Revision).md",
    "CP7.2.4": "CP7/Concepts/7.8 Garbage Burning & Human Activities (F6 Revision).md",
    "CP7.3.1": "CP7/Concepts/7.9 Physical Impacts (F6 Revision).md",
    "CP7.3.2": "CP7/Concepts/7.10 Social Impacts (F6 Revision).md",
    "CP7.3.3": "CP7/Concepts/7.11 Regional Examples (F6 Revision).md",
    "CP7.3.4": "CP7/Concepts/7.12 Urban Climate & Heat Island (F6 Revision).md",
    "CP7.3.5": "CP7/Concepts/7.13 Winners & Losers (F6 Revision).md",
    "CP7.4.1": "CP7/Concepts/7.14 International Agreements (F6 Revision).md",
    "CP7.4.2": "CP7/Concepts/7.15 Countries' Responses (F6 Revision).md",
    "CP7.4.3": "CP7/Concepts/7.16 Challenges of a Global Agreement (F6 Revision).md",
    "CP7.4.4": "CP7/Concepts/7.17 Conflicting Views & Key Players (F6 Revision).md",
    "CP7.5.1": "CP7/Concepts/7.18 Reducing Emissions (F6 Revision).md",
    "CP7.5.2": "CP7/Concepts/7.19 Carbon Sequestration (F6 Revision).md",
    "CP7.5.3": "CP7/Concepts/7.20 The Need for Adaptation (F6 Revision).md",
    "CP7.5.4": "CP7/Concepts/7.21 Adaptation Strategies (F6 Revision).md",
    "CP7.6.1": "CP7/Concepts/7.22 Observed Trends in Hong Kong (F6 Revision).md",
    "CP7.6.2": "CP7/Concepts/7.23 Hong Kong's Policy Response (F6 Revision).md",
}

# The teacher's long note stays as the second hint on every leaf: it holds
# the module's spine (the exam framing, the at-a-glance summary, the
# self-check), which is worth reading alongside the detail note.
MODULE_NOTE = {
    "CP6": "CP6_Disappearing_Green_Canopy_Detailed_Notes.md",
    "CP7": "CP7_Global_Warming_Detailed_Notes.md",
}


def leaf_list(cur: dict) -> list[tuple[str, dict, dict]]:
    out = []
    for el in cur.get("electives", []):
        code = el.get("code", "")
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                out.append((code, sq, leaf))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report the mapping without writing anything")
    args = ap.parse_args()

    cur = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    official = json.loads(OFFICIAL.read_text(encoding="utf-8"))

    # Every leaf the teacher has a concept note for must be covered.
    kb = json.loads((DATA / "kb.json").read_text(encoding="utf-8"))
    kb_paths = {d.get("path", "").split("/")[-1] for d in kb.get("docs", [])}
    missing = [
        (lid, path) for lid, path in CONCEPT_SOURCE.items()
        if path.split("/")[-1] not in kb_paths
    ]
    if missing:
        print("!! these concept notes are NOT in the knowledge base:")
        for lid, path in missing:
            print("   %-9s %s" % (lid, path))
        raise SystemExit(1)

    # The leaves that exist in the official guide must all be covered.
    off_leaves = {
        leaf["id"]
        for el in official.get("electives", [])
        for sq in el.get("subquestions", [])
        for leaf in sq.get("leaves", [])
    }
    uncovered = sorted(
        lid for lid in off_leaves
        if lid.startswith(("CP6.", "CP7.")) and lid not in CONCEPT_SOURCE
    )
    if uncovered:
        print("!! no concept note mapped for:", ", ".join(uncovered))
        raise SystemExit(1)

    changed = 0
    for code, sq, leaf in leaf_list(cur):
        lid = leaf.get("id", "")
        src = CONCEPT_SOURCE.get(lid)
        if not src:
            continue
        if leaf.get("source") == src:
            continue
        leaf["source"] = src
        # The module note stays as a secondary hint, so the leaf shows both
        # the detail note and the module's framing.
        hints = [h for h in (leaf.get("source_hints") or []) if h]
        mod = MODULE_NOTE.get(code)
        if mod and mod not in hints:
            hints.append(mod)
        leaf["source_hints"] = hints
        changed += 1

    print(f"leaves mapped : {len(CONCEPT_SOURCE)}")
    print(f"changed       : {changed}")
    if args.check:
        print("\n-- check only, nothing written --")
        for code, sq, leaf in leaf_list(cur):
            lid = leaf.get("id", "")
            if lid in CONCEPT_SOURCE:
                print("  %-9s %s" % (lid, leaf.get("source")))
        return

    CURRICULUM.write_text(
        json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written       : {CURRICULUM}")


if __name__ == "__main__":
    main()
