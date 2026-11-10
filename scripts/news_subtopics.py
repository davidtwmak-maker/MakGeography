"""Sub-topic keyword map for the News Corner.

David's News Corner requirement (27 Oct framework, item 1) is news "tagged for
focused viewing" across CP1-CP7 and EP1. Tagging by elective code alone is not
focused enough: a student who has just learned about landslides wants the
landslide stories, not every story that mentions Hong Kong rock.

So every elective carries a hand-checked set of sub-topic codes, and each
sub-topic carries the words that make a headline relevant to it. A headline
that matches nothing is still tagged with its elective, but it carries no
sub-topic.

The words here are deliberately specific. "city" on its own is not an urban
geography signal; "public housing", "reclamation", "redevelopment" are. A
term must match on word boundaries, so "port" does not fire on "report" and
"wave" does not fire on "wavelength".

Each term may be a plain word ("landslide") or a phrase ("slope stability").
Phrases match literally; words match with an optional English suffix
(s/es/ed/ing).
"""

# elective -> sub-topic code -> terms
# Codes match data/curriculum.json leaf ids.
SUBTOPIC_TERMS = {
    # CP1 is "Opportunities and Risks - is it rational to live in
    # hazard-prone areas?". The teacher's own scaffold puts the tectonic
    # hazards in CP1.4: volcanic eruptions, earthquakes and tsunamis, plus
    # hazard management (monitoring, prediction, warning).
    #
    # The terms have to name the HAZARD, not any word that can appear near
    # one. "folding" alone fires on a folding table, "landslide" alone fires
    # on an election won by a landslide, "early warning" alone fires on a
    # famine early-warning bulletin, and "wave" fires on a blue wave at an
    # election. So a term is either the hazard itself or a phrase that
    # names the geography.
    "CP1": {
        "CP1.1": ["internal structure", "earth's interior", "earth crust", "earth mantle",
                  "earth core", "asthenosphere", "plate movement", "mantle convection",
                  "ridge push", "slab pull", "plate boundary", "plate boundaries",
                  "continental drift", "mantle convection", "inner core", "outer core"],
        # Folding and faulting are GEOLOGICAL STRUCTURES, so the term has to
        # name the structure - "folding table" is not a fold.
        "CP1.2": ["internal force", "internal process", "folding mountain", "folded rock",
                  "anticline", "syncline", "fold and fault", "faulting", "fault line",
                  "fault plane", "volcanism", "igneous rock", "magma chamber",
                  "volcanic activity"],
        "CP1.3": ["destructive boundary", "constructive boundary", "hot spot", "hotspot",
                  "mantle plume", "subduction zone", "mid-ocean ridge", "rift zone",
                  "fold mountain", "block mountain", "atoll", "plate boundary",
                  "island arc", "ocean trench", "rift valley"],
        # The hazard terms. A landslide is NOT a CP1 hazard - in this
        # syllabus it belongs to EP1 (Hong Kong slope management), so it is
        # deliberately absent here.
        "CP1.4": ["volcanic eruption", "eruption", "earthquake", "quake", "tsunami",
                  "tremor", "epicentre", "epicenter", "aftershock",
                  "seismic wave", "seismic activity", "seismic event",
                  "seismic hazard", "seismic monitoring",
                  "lava flow", "pyroclastic", "ash cloud", "hazard management",
                  "hazard-prone", "vulnerability", "evacuation",
                  "tectonic hazard", "volcano", "volcanic"],
    },
    "CP2": {
        "CP2.1": ["hydrological cycle", "water cycle", "river system", "river regime",
                  "river energy", "discharge", "sediment transport", "fluvial", "braided river",
                  "channel network", "drainage basin", "catchment", "flood", "river management",
                  "channelisation", "embankment", "dam"],
        # "wave" alone fires on "blue wave" at an election, so the wave terms
        # name the coastal process.
        "CP2.2": ["wave erosion", "wave deposition", "wave refraction", "wave action",
                  "wave power", "wave height", "wave climate", "coastal wave",
                  "swell", "longshore drift", "coastal landform", "beach erosion",
                  "beach nourishment", "beach management", "sandy beach", "beach system",
                  "headland", "sea cave", "sea stack", "sea stump",
                  "spit", "sandbar", "tombolo",
                  "coastal management", "coastal erosion", "seawall", "breakwater",
                  "groynes", "revetment",
                  "land use zoning", "marine park", "mass wasting", "salt marsh", "mangrove"],
    },
    "CP3": {
        "CP3.1": ["industrial location", "location factor", "raw material", "market location",
                  "market-oriented", "transport cost", "cheap labour", "cheap labor",
                  "factory location", "labour cost", "labor cost", "industrial infrastructure"],
        "CP3.2": ["manufacturing in china", "pearl river delta", "zhujiang", "factory relocation",
                  "hong kong manufacturing", "industrial field trip", "ying pu", "tuen mun",
                  "industrial estate in china", "coastal industrial", "manufacturing industry"],
        "CP3.3": ["silicon valley", "global it centre", "global it center", "start-up industry",
                  "startup industry", "venture capital", "hightech park", "high-tech park"],
        "CP3.4": ["agglomeration", "industrial cluster", "concentration of industry"],
        "CP3.5": ["transnational corporation", "tnc", "multinational corporation",
                  "deindustrialization", "deindustrialisation", "industrial relocation",
                  "industrial decline", "offshoring", "outsourcing", "footloose"],
    },
    "CP4": {
        "CP4.1": ["sustainable development", "sustainable city", "sustainability",
                  "triple bottom line", "sustainable development goal"],
        "CP4.2": ["urban problem", "urban growth", "urbanisation", "urbanization",
                  "urban sprawl", "urban decay", "inner city", "public housing",
                  "new town", "new towns", "housing estate", "population density",
                  "congestion", "overcrowding", "substandard housing"],
        "CP4.3": ["liveable city", "livable city", "compact city", "green space",
                  "open space", "public space", "indicator of a sustainable"],
        "CP4.4": ["urban decay in hong kong", "case study in hong kong", "hong kong new town",
                  "hong kong new towns"],
        "CP4.5": ["planning strategy", "planning strategies", "master plan", "urban renewal",
                  "urban redevelopment", "redevelopment scheme", "land use zoning",
                  "re-imaging", "reimaging", "adaptive reuse", "brownfield site",
                  "brownfield redevelopment", "heritage conservation",
                  "rail plus property", "rail-plus-property"],
        "CP4.6": ["price of developing", "trade-off in sustainable", "tradeoff in sustainable",
                  "challenge of sustainable", "gentrification", "displacement of residents"],
    },
    "CP5": {
        "CP5.1": ["agricultural system", "crop farming", "pastoral farming", "commercial farming",
                  "subsistence farming", "mixed farming", "plantation"],
        "CP5.2": ["sahel", "nomadic herding", "pastoralist", "saharan"],
        "CP5.3": ["southern california", "irrigation farming", "imperial valley",
                  "central valley", "water transfer", "salinity"],
        "CP5.4": ["famine", "hunger", "food insecurity", "malnutrition", "food shortage",
                  "global food production", "food trade", "crop failure", "famine causes",
                  "food supply", "undernourishment"],
        "CP5.5": ["combating famine", "famine relief", "food aid", "wfp", "world food programme",
                  "emergency relief", "famine early warning"],
        "CP5.6": ["sustainable agriculture", "multiple cropping", "water conservation",
                  "soil conservation", "terracing", "agroforestry", "crop rotation",
                  "green revolution", "pesticide", "fertiliser runoff", "fertilizer runoff",
                  "soil degradation", "desertification", "land degradation"],
    },
    "CP6": {
        "CP6.1": ["rainforest", "tropical rainforest", "amazon rainforest", "forest canopy",
                  "nutrient cycle", "forest ecosystem", "rainforest structure", "understory",
                  "lianas", "biome"],
        "CP6.2": ["deforestation", "forest clearance", "forest loss", "forest cover",
                  "carbon cycle", "carbon sink", "carbon storage", "biodiversity loss",
                  "logging", "forest degradation", "net forest loss"],
        "CP6.3": ["indigenous rights", "indigenous livelihoods", "indigenous community",
                  "indigenous communities", "indigenous peoples and", "traditional livelihood",
                  "forest dependence", "rainforest tribe", "amazonian community",
                  "penan", "tribal community", "indigenous land"],
        "CP6.4": ["sustainable management of rainforest", "reforestation", "reforestation",
                  "replanting forest", "agroforestry", "biofuel", "biofuel",
                  "national park", "nature reserve", "protected area", "logging regulation",
                  "afforestation", "forest restoration", "community forest"],
        "CP6.5": ["feedback mechanism", "climate feedback", "rainforest climate"],
    },
    "CP7": {
        "CP7.1": ["global warming", "greenhouse effect", "greenhouse gas", "energy balance",
                  "evidence of global warming", "sea level rise", "glacier", "ice sheet",
                  "weather versus climate", "microclimate", "record high temperature",
                  "global temperature", "warming trend", "climate record",
                  "hotter than", "temperature rise", "temperature record",
                  "climate heatwave", "heatwave", "heat wave"],
        "CP7.2": ["cause of global warming", "human activity", "fossil fuel", "greenhouse gas emission",
                  "carbon emission", "garbage burning", "deforestation drives warming"],
        "CP7.3": ["impact of climate change", "heat island", "urban heat", "climate change impact",
                  "physiological drought", "crop yield loss", "coastal flooding"],
        "CP7.4": ["paris agreement", "kyoto protocol", "climate agreement", "net zero target",
                  "carbon tax", "climate policy", "cop28", "cop29", "cop30"],
        "CP7.5": ["mitigation", "adaptation", "carbon sequestration", "carbon capture",
                  "emission reduction", "renewable energy", "solar power", "wind power",
                  "energy transition", "decarbonisation", "decarbonization"],
        "CP7.6": ["hong kong climate", "hong kong warming", "hong kong temperature",
                  "hong kong sea level", "hong kong emission", "hong kong carbon"],
    },
    "EP1": {
        "EP1.1": ["rock cycle", "rock formation", "igneous rock", "sedimentary rock",
                  "metamorphic rock", "granite", "tuff", "basalt", "limestone", "marble",
                  "sandstone", "shale", "conglomerate", "weathering of rock"],
        "EP1.2": ["fold in hong kong", "fault in hong kong", "hong kong geopark",
                  "unesco global geopark", "geopark", "hong kong landscape",
                  "urban development landscape"],
        "EP1.3": ["weathering", "mass movement", "slope stability",
                  "factor of safety", "shear stress", "shear strength", "granular weathering",
                  "salt weathering", "salt crystallisation", "chemical weathering",
                  "physical weathering", "honeycomb weathering", "spheroidal weathering",
                  "rockfall", "landslip"],
        "EP1.4": ["landslide in hong kong", "slope management", "slope stabilisation",
                  "slope stabilization", "landslide prevention", "landslide warning",
                  "landslide monitoring", "geological hazard", "geohazard",
                  "sham wan", "reclamation material", "airport reclamation",
                  "drainage tunnel", "geological survey", "geoengineering"],
    },
}

# Electives that need no sub-topic match to keep an item: every elective has
# at least one sub-topic, so this is just a completeness guard.
ALL_ELECTIVES = tuple(SUBTOPIC_TERMS)


def subtopic_codes(elective: str) -> list[str]:
    return list(SUBTOPIC_TERMS.get(elective.upper(), {}))


def all_codes() -> list[str]:
    out = []
    for subs in SUBTOPIC_TERMS.values():
        out.extend(subs)
    return sorted(out)


if __name__ == "__main__":
    n = sum(len(v) for v in SUBTOPIC_TERMS.values())
    terms = sum(len(t) for v in SUBTOPIC_TERMS.values() for t in v.values())
    print(f"{len(SUBTOPIC_TERMS)} electives, {n} sub-topics, {terms} terms")
    for code in ALL_ELECTIVES:
        print(f"  {code}: {len(SUBTOPIC_TERMS[code])} sub-topics")
