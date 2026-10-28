#!/usr/bin/env python3
"""Map OQB HKEAA geography questions onto the MakGeography topic taxonomy.

HKEAA topic codes (from the OQB platform) vs the DSE elective structure:

  geog_1  Opportunities and Risks (hazards)          -> CP1
  geog_2  Managing Rivers and Coastal Environments   -> CP2
  geog_3  Changing Industrial Location               -> CP3
  geog_4  Building a Sustainable City                -> CP4
  geog_5  Combating Famine                           -> CP5
  geog_6  Disappearing Green Canopy (deforestation)  -> CP6
  geog_7  Global Warming                             -> CP7
  geog_8  Dynamic Earth: the building of Hong Kong   -> EP1
  geog_9  Weather and Climate                        -> CP7 (weather/climate)
  geog_10 Transport Development, Planning            -> CP4 (transport planning)
  geog_11 Zhujiang (Pearl River) Delta regional study-> CP4 (regional study)
  geog_12 Map Reading and Interpretation             -> all / map skills

Content dimensions:
  DIM1 Living with Our Physical Environment  -> CP1/CP2/EP1
  DIM2 Facing Changes in Human Environment   -> CP3/CP4
  DIM3 Confronting Global Challenges         -> CP5/CP6/CP7
  DIM4 Map Reading and Interpretation         -> map skills

The OQB data gives us topic_code AND dimension_code, and they agree for most
questions. Where a question has only a dimension (older papers), the
dimension supplies the elective. Where it has only a topic, the topic
supplies it. Where they disagree, the topic wins (it is the more specific
classification).
"""

HKEAA_TOPIC_TO_ELECT = {
    "geog_1": "CP1",
    "geog_2": "CP2",
    "geog_3": "CP3",
    "geog_4": "CP4",
    "geog_5": "CP5",
    "geog_6": "CP6",
    "geog_7": "CP7",
    "geog_8": "EP1",
    "geog_9": "CP7",   # Weather and Climate
    "geog_10": "CP4",  # Transport development, planning and management
    "geog_11": "CP4",  # Zhujiang (Pearl River) Delta regional study
    "geog_12": None,   # Map reading - spans every elective
}

DIM_TO_ELECT = {
    "geog_content_DIM1": "CP1",
    "geog_content_DIM2": "CP4",
    "geog_content_DIM3": "CP7",
    "geog_content_DIM4": None,  # map reading - spans every elective
}

# Topics that are genuinely cross-elective: map reading.
MAP_SKILLS_TOPICS = {"geog_12"}

# Extra labels for the sub-topic line the app shows.
TOPIC_LABEL = {
    "CP1": "Opportunities and Risks — living in hazard-prone areas",
    "CP2": "Managing Rivers and Coastal Environments",
    "CP3": "Changing Industrial Location",
    "CP4": "Building a Sustainable City",
    "CP5": "Combating Famine",
    "CP6": "Disappearing Green Canopy",
    "CP7": "Global Warming",
    "EP1": "Dynamic Earth: the building of Hong Kong",
}


def classify(topic_code, dimension_code):
    """Return (elect_code, subtopic_label, is_map_skills)."""
    topic = (topic_code or [None])[0]
    dim = (dimension_code or [None])[0]

    if topic in MAP_SKILLS_TOPICS:
        return "MAP", TOPIC_LABEL.get("CP2", ""), True
    if topic in HKEAA_TOPIC_TO_ELECT and HKEAA_TOPIC_TO_ELECT[topic]:
        return HKEAA_TOPIC_TO_ELECT[topic], TOPIC_LABEL[HKEAA_TOPIC_TO_ELECT[topic]], False
    if dim in DIM_TO_ELECT and DIM_TO_ELECT[dim]:
        return DIM_TO_ELECT[dim], TOPIC_LABEL[DIM_TO_ELECT[dim]], False
    # Nothing usable: treat as map skills so it is still reachable.
    return "MAP", "Map Reading and Interpretation", True
