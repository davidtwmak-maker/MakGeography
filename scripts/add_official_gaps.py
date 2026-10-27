#!/usr/bin/env python3
"""
Add the 33 official sub-questions that were missing from the curriculum
scaffold.

The scaffold was built from the teacher's note headings. A separate, careful
read of the official C&A Guide compared every leaf against the guide's
guiding questions, Explanatory Notes and Concepts columns, and found 33
official sub-questions with no leaf at all.

They belong in the Notes page. A student using the site to cover the
syllabus should see the whole official structure, including the parts the
teacher's own notes do not reach, and see them marked as "no note yet"
rather than find them silently absent.

The 7 leaves flagged as `extra_leaves` are teacher additions that are not in
the official guide. They are kept - they are useful teaching content - but
they are marked so no one mistakes them for official headings.

Usage:  python scripts/add_official_gaps.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

# id -> (title, summary, where the vault is most likely to cover it)
# The source hint is a NOTE TITLE, not a file path - the Notes API matches on
# both the note title and its section headings. An empty list means the
# scaffold is honest that there is no note yet.
GAPS: dict[str, dict] = {
    "CP1.4.5": {
        "title": "Vulnerability of less developed areas and the rationality of living in hazard-prone areas",
        "summary": ("Official GQ12-15: why less developed areas are more vulnerable "
                    "to natural hazards (literacy and awareness, socio-economic and "
                    "technological gaps); the advantages and disadvantages of living "
                    "in hazard-prone areas."),
        "source_hints": ["CP1 Opportunities and Risks. Is it rational to live."],
    },
    "CP2.1.0": {
        "title": "The hydrological cycle",
        "summary": ("Official GQ1 asks for a brief introduction to the hydrological "
                    "cycle - its characteristics, stores and transfers."),
        "source_hints": ["1.0 River & Coastal environment"],
    },
    "CP2.1.6": {
        "title": "Braided rivers and channel networks",
        "summary": ("The official landform list for Module 2 includes braids and the "
                    "channel network as distinct features."),
        "source_hints": ["1.0 River & Coastal environment", "1.1 River System"],
    },
    "CP2.2.7": {
        "title": "Land use zoning as a management strategy",
        "summary": ("The official management list for Module 2 names land use zoning "
                    "alongside channelisation, breakwaters and beach nourishment."),
        "source_hints": ["2.5 Managing coastal environment"],
    },
    "CP2.2.8": {
        "title": "Mass wasting and ecosystem disturbance as consequences",
        "summary": ("The official consequences list for Module 2 includes mass wasting "
                    "and disturbance or damage to the ecosystem alongside flooding, "
                    "erosion and pollution."),
        "source_hints": ["2.5 Managing coastal environment"],
    },
    "CP2.2.9": {
        "title": "Conflict and the evaluation of management strategies",
        "summary": ("The official Concepts column for Module 2 lists 'Conflict' and "
                    "'Management', and the Explanatory Notes require evaluation of the "
                    "methods and strategies used and their possible consequences."),
        "source_hints": ["2.5 Managing coastal environment"],
    },
    "CP3.2.2": {
        "title": "Hong Kong's manufacturing industry and its relocation to the Zhujiang (Pearl River) Delta",
        "summary": ("Official GQ1-2: where Hong Kong's manufacturing industry was "
                    "located in the past (1950s-1970s), where it is now, and the "
                    "relocation of Hong Kong's manufacturing industry to the Zhujiang "
                    "(Pearl River) Delta."),
        "source_hints": ["CP3 Industrial Location Detailed Notes"],
    },
    "CP3.2.3": {
        "title": "The Hong Kong industrial field trip",
        "summary": ("The official Skills column for GQ7-8 asks for a field trip to "
                    "Cyberport or the Hong Kong Science Park to identify the factors "
                    "favouring the IT industry there."),
        "source_hints": ["CP3 Industrial Location Detailed Notes"],
    },
    "CP3.5.3": {
        "title": "Impacts of industrial relocation and the measures to alleviate them",
        "summary": ("Official GQ10-11: the likely social, economic and environmental "
                    "impacts of changing industrial location and modes of production "
                    "(flow of technology, changes in employment), and the measures to "
                    "alleviate them."),
        "source_hints": ["CP3 Industrial Location Detailed Notes"],
    },
    "CP4.2.2": {
        "title": "Urban growth, urbanisation and the changing internal structure of the city",
        "summary": ("Official GQ1-4: the definition of urban growth and urbanisation; "
                    "their causes (natural increase of the urban population, "
                    "rural-urban migration, reclassification of areas); and the "
                    "changing internal structure of the city."),
        "source_hints": ["CP4 Sustainable City Detailed Notes"],
    },
    "CP4.2.3": {
        "title": "Provision of public housing and new towns",
        "summary": ("Official GQ6 names the provision of public housing and the "
                    "building of new towns as specific measures for alleviating urban "
                    "problems."),
        "source_hints": ["CP4 Sustainable City Detailed Notes"],
    },
    "CP4.3.2": {
        "title": "Indicators of a sustainable city",
        "summary": ("Official GQ11 asks for the characteristics of a sustainable city, "
                    "and the Skills column requires compiling indicators from various "
                    "sources and then re-designing the indicators."),
        "source_hints": ["CP4 Sustainable City Detailed Notes"],
    },
    "CP4.5.2": {
        "title": "Regenerating and re-imaging the city",
        "summary": ("Official GQ12 names 'regenerating and re-imaging the city' as a "
                    "method of making a city sustainable."),
        "source_hints": ["CP4 Sustainable City Detailed Notes"],
    },
    "CP4.6.2": {
        "title": "The price of developing a sustainable city",
        "summary": ("Official GQ13 makes the price of developing a sustainable city a "
                    "required topic."),
        "source_hints": ["CP4 Sustainable City Detailed Notes"],
    },
    "CP5.2.2": {
        "title": "Nomadic herding in the Sahel",
        "summary": ("Official GQ6: the agricultural characteristics of nomadic "
                    "herding in the Sahel, with attention to the technological, "
                    "economic, political and socio-cultural aspects."),
        "source_hints": ["CP5 Combating Famine Detailed Notes", "5.4 Famine — Causes & Characteristics (F6 Revision)"],
    },
    "CP5.3.2": {
        "title": "Irrigation farming in Southern California",
        "summary": ("Official GQ6: the agricultural characteristics of irrigation "
                    "farming in Southern California, with technological, economic, "
                    "political and socio-cultural aspects."),
        "source_hints": ["CP5 Combating Famine Detailed Notes", "5.4 Famine — Causes & Characteristics (F6 Revision)"],
    },
    "CP5.4.2": {
        "title": "Global patterns of food production, consumption and trade",
        "summary": ("Official GQ1-3: the uneven availability of food supplies relative "
                    "to demand on a global scale; global patterns of food production "
                    "and consumption in relation to population and other factors."),
        "source_hints": ["CP5 Combating Famine Detailed Notes", "5.4 Famine — Causes & Characteristics (F6 Revision)"],
    },
    "CP5.6.2": {
        "title": "Consequences of misuse and overuse of agricultural technology",
        "summary": ("Official GQ10-11: reduction of biodiversity, habitat loss, land "
                    "degradation, soil erosion, chemical pollution of land and "
                    "watercourses, and the impact on the rural landscape."),
        "source_hints": ["CP5 Combating Famine Detailed Notes", "5.4 Famine — Causes & Characteristics (F6 Revision)"],
    },
    "CP5.6.3": {
        "title": "Multiple cropping, water conservation and soil conservation",
        "summary": ("Official GQ11 names multiple cropping and water and soil "
                    "conservation methods as measures for sustainable agricultural "
                    "development, alongside organic farming."),
        "source_hints": ["CP5 Combating Famine Detailed Notes", "5.4 Famine — Causes & Characteristics (F6 Revision)"],
    },
    "CP6.1.4": {
        "title": "Abiotic and biotic components, energy flow and ecological equilibrium",
        "summary": ("Official GQ2-4 requires the definition of an ecosystem, its "
                    "abiotic and biotic components, the links and interrelationships "
                    "between them, energy flow in the ecosystem, and ecological "
                    "equilibrium."),
        "source_hints": ["CP6 Disappearing Green Canopy Detailed Notes"],
    },
    "CP6.2.5": {
        "title": "Global distribution and the rate of deforestation",
        "summary": ("Official GQ1: the global distribution of tropical rainforests and "
                    "deforestation in rainforest regions - its rate and conditions."),
        "source_hints": ["CP6 Disappearing Green Canopy Detailed Notes"],
    },
    "CP6.4.4": {
        "title": "Roles of different parties and conflicts of interest",
        "summary": ("Official GQ10-13: the roles played by native people and local "
                    "dwellers, government officials, private developers and "
                    "environmentalists in developing and protecting rainforest "
                    "resources, and the conflicts of interest between them."),
        "source_hints": ["CP6 Disappearing Green Canopy Detailed Notes"],
    },
    "CP6.4.5": {
        "title": "Afforestation, logging regulation, national parks and natural reserves",
        "summary": ("Official GQ10 names afforestation, regulation on logging "
                    "activities, and the setting up of national parks and natural "
                    "reserves as the measures to protect tropical rainforest."),
        "source_hints": ["CP6 Disappearing Green Canopy Detailed Notes"],
    },
    "CP7.1.4": {
        "title": "Weather versus climate, and climate at local, national and global scale",
        "summary": ("Official GQ1-2 asks for the definitions of 'weather' and 'climate' "
                    "and a brief introduction to climate at local, national and global "
                    "scale."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "CP7.2.3": {
        "title": "Natural versus human causes, and the irreversible-trend debate",
        "summary": ("Official GQ4-6 requires natural and human causes of global "
                    "warming AND the supporting and opposing arguments on whether "
                    "global warming is a long-term fluctuation of temperature or an "
                    "irreversible trend."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "CP7.2.4": {
        "title": "Garbage burning and other named human activities",
        "summary": ("Official GQ4-5 names the specific human activities that enhance "
                    "the greenhouse effect: deforestation, burning of fossil fuels, "
                    "garbage burning, emission of chlorofluorocarbons."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "CP7.3.4": {
        "title": "Urban climate: the heat island effect and microclimate",
        "summary": ("Official GQ7-9: urban growth and development leading to local "
                    "climatic variation focusing on the heat island effect; its "
                    "effects on atmospheric composition, temperature, and "
                    "precipitation."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "CP7.3.5": {
        "title": "Winners and losers of climate change",
        "summary": ("Official GQ10 frames the consequences around winners and losers - "
                    "sea level, flood frequency, new farming opportunities, health "
                    "risks, and climatic prediction becoming more difficult."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "CP7.4.4": {
        "title": "Conflicting views and roles of key players",
        "summary": ("Official GQ12: the complexities of reaching a global agreement, in "
                    "particular the conflicting views and roles of key players."),
        "source_hints": ["CP7 Global Warming Detailed Notes"],
    },
    "EP1.1.2": {
        "title": "The Earth as a system and its internal structure",
        "summary": ("Official Topic 1 requires Earth systems - the interaction between "
                    "the atmosphere, the lithosphere and the hydrosphere - and the "
                    "internal structure of the Earth."),
        "source_hints": ["EP1 Geological Features in Hong Kong — Rock Characteristics, Internal/External Processes (F6 Revision)", "EP1 Dynamic Earth HK"],
    },
    "EP1.2.6": {
        "title": "Modification of Hong Kong landscapes by urban development",
        "summary": ("Official Topic 2 requires students to overlay the urban "
                    "development map on the relief map (or use GIS) to show how urban "
                    "development has modified Hong Kong's landscape."),
        "source_hints": ["EP1 Dynamic Earth HK"],
    },
    "EP1.3.6": {
        "title": "Slope stability and the factor of safety",
        "summary": ("Teacher addition in emphasis. The shear stress / shear strength / "
                    "factor of safety framework is not an official named item, but it is "
                    "the mechanism that explains the official requirement for the causes "
                    "of landslides in Hong Kong, including natural and human factors."),
        "source_hints": ["EP1 Geological Features in Hong Kong — Rock Characteristics, Internal/External Processes (F6 Revision)"],
        "teacher_addition": True,
        "teacher_note": ("Teacher addition in emphasis. The shear stress / shear strength / "
                         "factor of safety framework is not an official named item, but it "
                         "is the mechanism that explains the official requirement for "
                         "'causes of landslides in Hong Kong, including natural and human "
                         "factors'. Keep."),
    },
    "EP1.4.6": {
        "title": "Geological resources: reclamation materials and the Hong Kong International Airport",
        "summary": ("Official Topic 4 requires sources and distribution of reclamation "
                    "materials, the environmental impact of extracting them, and the "
                    "local example of the Hong Kong International Airport."),
        "source_hints": ["EP1 Dynamic Earth HK"],
    },
    "EP1.4.7": {
        "title": "Sham Wan landslide as the official local example",
        "summary": ("Official Topic 4 names the Sham Wan landslide as the local "
                    "example, and the Skills column requires a field trip to Sham Wan "
                    "to identify the measures adopted to prevent landslides."),
        "source_hints": ["EP1 Dynamic Earth HK"],
    },
}

# The teacher's own leaves that are NOT in the official guide. They stay, but
# they are labelled so nobody mistakes them for official headings.
TEACHER_ADDITIONS = {
    "CP6.2.4", "CP6.4.3", "CP6.5.1", "CP7.5.2", "CP7.6.2", "EP1.2.5", "EP1.3.6",
}


def main() -> None:
    path = DATA / "curriculum.json"
    cur = json.loads(path.read_text(encoding="utf-8"))

    added = 0
    for el in cur["electives"]:
        for sq in el.get("subquestions", []):
            # leaves in this sub-question, e.g. CP2.1.x
            prefix = f"{el['code']}.{sq.get('number')}."
            mine = [l for l in sq.get("leaves", []) if l.get("id", "").startswith(prefix)]
            if not mine:
                continue
            existing = {l["id"] for l in mine}
            # Insert the new leaves in id order.
            for leaf_id, spec in GAPS.items():
                if not leaf_id.startswith(prefix) or leaf_id in existing:
                    continue
                if spec.get("teacher_addition") and el["code"] == "EP1" and sq.get("number") == 3:
                    pass  # teacher additions are inserted like any other leaf
                sq.setdefault("leaves", []).append({
                    "id": leaf_id,
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "source_hints": spec["source_hints"],
                    "official": True,
                    "added_for_syllabus_coverage": True,
                })
                added += 1
            # Sort the leaves by their numeric part.
            sq["leaves"] = sorted(
                sq.get("leaves", []),
                key=lambda l: int(l["id"].rsplit(".", 1)[-1]) if l.get("id", "").rsplit(".", 1)[-1].isdigit() else 0,
            )
            # Mark the teacher's own additions.
            for leaf in sq["leaves"]:
                if leaf.get("id") in TEACHER_ADDITIONS:
                    leaf["teacher_addition"] = True
                    leaf["teacher_note"] = (
                        leaf.get("teacher_note")
                        or ("Teacher addition: useful content, but not an official "
                            "heading in the C&A Guide.")
                    )

    path.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")

    leaves = sum(len(s.get("leaves", [])) for s in
                 (sq for e in cur["electives"] for sq in e["subquestions"]))
    subs = sum(len(e.get("subquestions", [])) for e in cur["electives"])
    print(f"added {added} official leaves; now {subs} sub-questions, {leaves} leaves")
    marked = sum(1 for e in cur["electives"] for s in e["subquestions"]
                 for l in s.get("leaves", []) if l.get("teacher_addition"))
    print(f"teacher additions marked: {marked}")


if __name__ == "__main__":
    main()
