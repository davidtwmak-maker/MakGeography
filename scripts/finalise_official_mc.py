#!/usr/bin/env python3
"""
Finish the official HKEAA items: drop the one that needs the Hong Kong map
extract, and write the reasoning behind each official answer.

The reasoning comes from HKEAA's own commentary on the slide, or from the
geography behind the answer, and is written in plain exam-answer language.

Usage:  python scripts/finalise_official_mc.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# 2024 Q6 needs the Hong Kong map extract, which is not printed on its
# slide, so it cannot be answered from the slide alone. Drop it.
DROP = {("2024", "6")}

EXPLANATIONS = {
    ("2024", "12"): (
        "A raw material-oriented activity uses its raw materials at or near "
        "the place of production. Cheese making is an example because milk is "
        "perishable and bulky, so it is processed close to where the milk is "
        "produced. Bread making uses flour that can be transported easily, and "
        "car manufacturing and newspaper printing are not raw material "
        "activities at all."
    ),
    ("2024", "20"): (
        "All three are consequences. A higher mean sea level increases wave "
        "erosion along the coast, the people living in coastal lowlands face "
        "resettlement because of the risk of flooding, and warmer oceans and "
        "a higher sea surface give more energy to tropical cyclones, so they "
        "form more often."
    ),
    ("2025", "19"): (
        "Climate change shifts the climatic zones that support each biome, so "
        "biomes migrate towards the poles - southward in the Southern "
        "Hemisphere. Coral bleaching is a problem in warm tropical water, not "
        "the polar region; extreme rainfall in Hong Kong is a weather "
        "consequence rather than an ecological one; and the Amazon rainforest "
        "faces MORE forest fires, not fewer."
    ),
    ("2022", "11"): (
        "Iron and steel production is capital-intensive rather than "
        "labour-intensive, so cheap labour is not a sufficient reason for "
        "the plant to stay in China. Agglomeration of heavy industries and "
        "upgraded production facilities are both genuine reasons, so "
        "(1) and (2) only is correct."
    ),
    ("2022", "16"): (
        "All three follow from inappropriate chemical fertilizer use in a "
        "hot, dry climate: nutrients leach down to contaminate groundwater, "
        "runoff causes eutrophication in water bodies, and soluble salts "
        "accumulate in the soil, worsened by high evaporation and poor "
        "drainage."
    ),
    ("2022", "17"): (
        "Economic development, driven by poverty and the need for land and "
        "livelihoods, is the major cause of Amazon deforestation. Urban "
        "development cleared a much smaller area than economic development, "
        "so rapid urbanisation is not a 'major' cause."
    ),
    ("2022", "13"): (
        "At stage 3 population density first rises with distance from the "
        "centre, so statement (1) is false. Stage 3 shows outward and "
        "suburban growth rather than people moving back to the centre, so "
        "statement (2) is false. The later-stage graph does show the city "
        "growing and expanding outward, so (3) only is correct."
    ),
    ("2024", "9"): (
        "With north oriented upwards, the blue arrow shows the air moving "
        "towards the west. Wind directions are named for where the wind comes "
        "FROM, so the wind comes from the east. The red arrow along the spit "
        "shows the direction of spit growth, not the wind."
    ),
    ("2024", "13"): (
        "The container yard brings heavy truck traffic into and out of the "
        "area, so traffic congestion is an impact as well as the unpleasant "
        "view and the disruption of the rural lifestyle."
    ),
    ("2025", "5"): (
        "The Kai Tak Cruise Terminal is built on the newly reclaimed Kai Tak "
        "airport site, so deep waterfront is its location advantage. It is "
        "not close to Kwun Tong Typhoon Shelter, and although a railway "
        "serves the airport, accessibility by railway is not the decisive "
        "location factor for a cruise terminal."
    ),
    ("2025", "20"): (
        "Tree planting cools the urban heat island directly through "
        "evapotranspiration and through shading, so (1) and (3) are correct. "
        "Absorbing more carbon dioxide is a climate benefit rather than a "
        "direct cooling mechanism, so (2) is not the answer here."
    ),
    ("2026", "14"): (
        "Urban encroachment in Hong Kong replaces farmland, changes the "
        "character of rural communities and raises the risk of flooding "
        "through harder surfaces and loss of natural drainage, so all three "
        "are problems."
    ),
    ("2026", "16"): (
        "Sunlight is a natural input, not a human one, so (1) is excluded. "
        "Crop residues are human inputs because they are deliberately "
        "returned to the soil. Genetically modified seeds are also a human "
        "input, but the item asks for examples of human input in ORGANIC "
        "farming, where genetically modified seeds are not permitted, so "
        "(2) only is correct."
    ),
}


# Corrections to the tags the extractors guessed from the slide's neighbours.
# 2024 Q20 is a climate-change (CP7) question; the geometric extractor put it
# in CP2 because it sits between two CP2 items in the deck.
TAG_FIXES = {
    ("2024", "20"): ("CP7", "CP7.1.1"),
    ("2024", "9"): ("CP2", "CP2.2.4"),
    ("2024", "13"): ("CP4", "CP4.3.1"),
    ("2022", "13"): ("CP1", "CP1.1.3"),
    ("2025", "5"): ("CP4", "CP4.4.1"),
    ("2025", "19"): ("CP7", "CP7.1.3"),
    ("2025", "20"): ("CP7", "CP7.1.3"),
    ("2026", "14"): ("CP4", "CP4.3.1"),
    ("2026", "16"): ("CP5", "CP5.6.1"),
    ("2024", "12"): ("CP3", "CP3.1.1"),
    ("2022", "11"): ("CP3", "CP3.1.1"),
    ("2022", "16"): ("CP5", "CP5.3.1"),
    ("2022", "17"): ("CP6", "CP6.2.1"),
}


def main() -> None:
    path = DATA / "mc_bank.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    dropped = 0
    kept = []
    for q in questions:
        key = (str(q.get("year")), str(q.get("q")))
        if q.get("official") and key in DROP:
            dropped += 1
            continue
        if q.get("official"):
            expl = EXPLANATIONS.get(key)
            if expl:
                q["explanation"] = expl
            fix = TAG_FIXES.get(key)
            if fix:
                elect, sub = fix
                q["topics"] = [elect]
                q["elect"] = elect
                q["subtopic"] = sub
        kept.append(q)

    bank["questions"] = kept
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")

    off = [q for q in kept if q.get("official")]
    print(f"dropped {dropped}; bank holds {len(kept)}")
    print(f"official {len(off)}; with explanation "
          f"{sum(1 for q in off if (q.get('explanation') or '').strip())}")


if __name__ == "__main__":
    main()
