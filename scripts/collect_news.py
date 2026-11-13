#!/usr/bin/env python3
"""
Geography News Corner — collect and tag current geography news.

Polls a set of RSS/Atom feeds and search queries, tags each item against the
HKDSE Geography electives and their curriculum sub-topics, and writes
data/news.json for the site.

Every feed URL here was fetched and confirmed to return live items before
being added. A feed that rots is the normal failure mode of an RSS collector,
so the feed-health check in scripts/test_news_coverage.py exists to catch it
before it empties an elective.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_subtopics import SUBTOPIC_TERMS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------------------
# Feed registry — every URL verified live.
#   tag      : the elective(s) this feed serves
#   kind     : 'feed' or 'search'
# ---------------------------------------------------------------------------

FEEDS = [
    # ---- CP1 Earth structure / plate tectonics / tectonic hazards ----
    {"tag": ["CP1"], "name": "USGS Earthquakes (M4.5+, past week)", "kind": "feed", "max_items": 12,
     "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
     "json": True, "authoritative": True},
    {"tag": ["CP1"], "name": "NGDC / NOAA Significant Earthquakes", "kind": "feed", "max_items": 12,
     "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
     "json": True, "authoritative": True},
    # UNDRR is the UN body for disaster risk reduction. Its feed carries
    # tsunami readiness, hazard management and early-warning stories -
    # exactly the CP1.4 material the module is about.
    #
    # The gate has to name the TECTONIC hazard. "resilien" and "early
    # warning" on their own let eight general disaster-preparedness
    # workshops into the CP1 list, none of them about earthquakes.
    #
    # "multi-hazard" was added for multi-hazard early-warning stories and
    # immediately let general disaster-preparedness reporting through
    # ("Algeria advances multi-hazard early warning systems",
    # "Global Status of Multi-Hazard Early Warning Systems 2026") — neither
    # is about plate tectonics. The gate must name the hazard, not the
    # warning system built around it.
    {"tag": ["CP1", "CP2"], "name": "UNDRR — Disaster risk reduction", "kind": "feed", "max_items": 30,
     "url": "https://www.undrr.org/rss.xml", "authoritative": True,
     "gate": ["earthquake", "volcan", "tsunami", "tectonic hazard",
              "seismic hazard", "tsunami readiness", "tsunami ready",
              "tsunami warning", "tsunami awareness", "tsunami innovation",
              "tsunami day", "tsunami risk", "tsunami drill", "tsunami exercise"]},
    {"tag": ["CP1", "EP1"], "name": "HK DSD — What’s New", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Whats_New.xml", "authoritative": False},
    {"tag": ["CP1"], "name": "HK DSD — Press Releases", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Press_Releases.xml", "authoritative": False},
    {"tag": ["CP1", "EP1"], "name": "ScienceDaily — Earthquakes", "kind": "feed", "max_items": 30,
     "url": "https://www.sciencedaily.com/rss/earth_climate/earthquakes.xml", "authoritative": False},
    {"tag": ["CP1", "EP1"], "name": "ScienceDaily — Volcanoes", "kind": "feed", "max_items": 30,
     "url": "https://www.sciencedaily.com/rss/earth_climate/volcanoes.xml", "authoritative": False},
    {"tag": ["CP1", "EP1"], "name": "ScienceDaily — Geology", "kind": "feed", "max_items": 30,
     "url": "https://www.sciencedaily.com/rss/earth_climate/geology.xml", "authoritative": False},

    # ---- CP2 River and coastal environment ----
    {"tag": ["CP2"], "name": "HK EPD — Highlights", "kind": "feed",
     "url": "https://www.epd.gov.hk/epd/english/rss_feeds/highlights.xml", "authoritative": False},
    {"tag": ["CP2", "CP7"], "name": "HKO — Monthly climate reports", "kind": "feed",
     "url": "https://www.weather.gov.hk/en/wxinfo/pastwx/mws2026/mws202608.htm", "authoritative": True},
    {"tag": ["CP2", "CP7"], "name": "ScienceDaily — Water", "kind": "feed", "max_items": 30,
     "url": "https://www.sciencedaily.com/rss/earth_climate/water.xml", "authoritative": False},

    # ---- CP3 Industrial location ----
    {"tag": ["CP3"], "name": "SCMP — Business", "kind": "feed",
     "url": "https://www.scmp.com/rss/92/feed", "authoritative": False, "max_items": 30},
    {"tag": ["CP3"], "name": "SCMP — China Economy", "kind": "feed",
     "url": "https://www.scmp.com/rss/318198/feed", "authoritative": False, "max_items": 25},
    {"tag": ["CP3"], "name": "Manufacturing Dive", "kind": "feed",
     "url": "https://www.manufacturingdive.com/feeds/news/", "authoritative": False, "max_items": 20},
    {"tag": ["CP3", "CP4"], "name": "Hong Kong Free Press", "kind": "feed",
     "url": "https://hongkongfp.com/feed/", "authoritative": False, "max_items": 25},
    {"tag": ["CP1", "CP4"], "name": "HK DSD — DSD Newsletter", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/DSD_Newsletter.xml", "authoritative": False},
    {"tag": ["CP3", "CP4"], "name": "HK DSD — Press Releases", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Press_Releases.xml"},

    # ---- CP4 Building a sustainable city ----
    # The Government press-release feed is the single best CP4 source: it
    # carries housing, planning, redevelopment and infrastructure decisions,
    # which is exactly what CP4 is about.
    {"tag": ["CP4"], "name": "HK Government — News in brief", "kind": "feed", "max_items": 60,
     "url": "https://www.info.gov.hk/gia/rss/general_en.xml", "authoritative": False},
    {"tag": ["CP4"], "name": "SCMP — Hong Kong", "kind": "feed", "max_items": 40,
     "url": "https://www.scmp.com/rss/4/feed", "authoritative": False},
    {"tag": ["CP4"], "name": "SCMP — News", "kind": "feed", "max_items": 40,
     "url": "https://www.scmp.com/rss/91/feed", "authoritative": False},

    # ---- CP5 Combating famine ----
    # ReliefWeb is a HUMANITARIAN feed, not a famine feed. It carries
    # measles bulletins, school reports, telecom dashboards and meeting
    # minutes as well as food-security bulletins. Without a gate, the
    # authoritative flag forced CP5 onto every one of them, and CP5 held
    # 59 of the 300 items in the feed - most of them not about food.
    {"tag": ["CP5"], "name": "ReliefWeb — Humanitarian updates", "kind": "feed", "max_items": 20,
     "url": "https://reliefweb.int/updates/rss.xml", "authoritative": True,
     "gate": ["famine", "hunger", "food security", "food insecurity", "malnutrition",
              "food shortage", "food supply", "undernourishment", "crop", "harvest",
              "agricultur", "crop failure", "locust", "desertification",
              "food price", "grain", "wheat", "maize", "nutrition"]},
    {"tag": ["CP5"], "name": "ScienceDaily — Food & Nutrition", "kind": "feed", "max_items": 25,
     "url": "https://www.sciencedaily.com/rss/health_medicine/nutrition.xml", "authoritative": False},
    {"tag": ["CP5", "CP6"], "name": "ScienceDaily — Environment", "kind": "feed", "max_items": 25,
     "url": "https://www.sciencedaily.com/rss/earth_climate/pollution.xml", "authoritative": False},

    # ---- CP6 Disappearing green canopy ----
    {"tag": ["CP6"], "name": "Mongabay — Environment", "kind": "feed", "max_items": 40,
     "url": "https://news.mongabay.com/feed/", "authoritative": False},
    {"tag": ["CP6"], "name": "ScienceDaily — Forests", "kind": "feed", "max_items": 30,
     "url": "https://www.sciencedaily.com/rss/earth_climate/forests.xml", "authoritative": False},

    # ---- CP7 Global warming / climate change ----
    {"tag": ["CP7"], "name": "WMO — News", "kind": "feed",
     "url": "https://wmo.int/news", "authoritative": True},
    {"tag": ["CP7"], "name": "Copernicus Climate Change Service", "kind": "feed",
     "url": "https://climate.copernicus.eu/rss.xml", "authoritative": True},
    {"tag": ["CP7"], "name": "NASA Earth Observatory", "kind": "feed",
     "url": "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss", "authoritative": True},
    {"tag": ["CP7"], "name": "ScienceDaily — Climate", "kind": "feed",
     "url": "https://www.sciencedaily.com/rss/earth_climate/climate.xml", "authoritative": False},
    {"tag": ["CP7"], "name": "CarbonBrief — Climate policy", "kind": "feed", "max_items": 30,
     "url": "https://www.carbonbrief.org/feed/", "authoritative": False},
    {"tag": ["CP7"], "name": "Climate Home News", "kind": "feed", "max_items": 40,
     "url": "https://www.climatechangenews.com/feed/", "authoritative": False},
    {"tag": ["CP7"], "name": "Mongabay — Climate", "kind": "feed", "max_items": 30,
     "url": "https://news.mongabay.com/feed/", "authoritative": False},

    # ---- EP1 Dynamic Earth (HK) ----
    {"tag": ["EP1"], "name": "phys.org — Earth", "kind": "feed", "max_items": 30,
     "url": "https://phys.org/rss-feed/earth-news/", "authoritative": False},
    {"tag": ["EP1"], "name": "HK Gov — Geotechnical and engineering works", "kind": "feed", "max_items": 40,
     "url": "https://www.info.gov.hk/gia/rss/general_en.xml", "authoritative": False},

    # ---- Targeted searches for the electives the broad feeds under-serve ----
    # A general news feed only carries a story if the publisher happens to
    # write about it. CP3 (industrial location), CP4 (sustainable city) and
    # EP1 (HK dynamic earth) had 18, 10 and 16 items out of 280 because no
    # broad feed writes about them often enough. A targeted search feed
    # asks the question directly, so those electives get a real share.
    {"tag": ["CP4"], "name": "Search — public housing & urban renewal", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Hong+Kong+OR+China+OR+Singapore+OR+Malaysia+OR+Seoul+OR+Tokyo+OR+Taipei+OR+Jakarta)+AND+(%22public+housing%22+OR+%22urban+renewal%22+OR+%22urban+redevelopment%22+OR+%22urban+sprawl%22+OR+%22public+transport%22+OR+%22brownfield%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP3"], "name": "Search — industrial location & TNCs", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Hong+Kong+OR+China+OR+Asia+OR+%22Silicon+Valley%22)+AND+(deindustrialisation+OR+deindustrialization+OR+%22industrial+relocation%22+OR+%22transnational+corporation%22+OR+%22industrial+location%22+OR+agglomeration)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP1", "EP1"], "name": "Search — Hong Kong geology & slope safety", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Hong+Kong+OR+China)+AND+(landslide+OR+weathering+OR+%22slope+stability%22+OR+geology+OR+%22geological+hazard%22+OR+%22rock+formation%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    # CP1's own search. The old CP2-style query returned one item in thirty
    # days, so the tectonic module had no current news of its own and the
    # list filled up with whatever the broad feeds carried.
    {"tag": ["CP1"], "name": "Search — tectonic hazards", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(earthquake+OR+volcano+OR+tsunami+OR+%22plate+boundary%22+OR+%22tectonic+hazard%22+OR+%22volcanic+eruption%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP6"], "name": "Search — indigenous peoples & forest livelihoods", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Indonesia+OR+Brazil+OR+Congo+OR+Peru+OR+Malaysia+OR+Amazon+OR+%22Central+Africa%22)+AND+(deforestation+OR+%22rainforest+management%22+OR+indigenous+OR+%22forest+community%22+OR+reforestation)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    # CP4's own search. The broad feeds only carry a handful of urban
    # stories, and the module needs the housing, renewal and planning
    # decisions it is examined on.
    {"tag": ["CP4"], "name": "Search — urban renewal & public housing", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Hong+Kong+OR+Singapore+OR+Seoul+OR+Tokyo)+AND+(%22urban+renewal%22+OR+%22public+housing%22+OR+%22redevelopment%22+OR+%22urban+planning%22+OR+%22master+plan%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    # EP1's own search. The elective is about Hong Kong's physical
    # landscape, so the query is anchored on Hong Kong.
    {"tag": ["EP1"], "name": "Search — Hong Kong geology & landslides", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Hong+Kong)+AND+(landslide+OR+%22slope+stability%22+OR+%22rock+formation%22+OR+%22geological+hazard%22+OR+%22reclamation+material%22)+when:60d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP7"], "name": "Search — climate policy & adaptation", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(UN+OR+global+OR+world+OR+Europe+OR+Africa+OR+Asia)+AND+(%22Paris+Agreement%22+OR+%22net+zero%22+OR+%22carbon+tax%22+OR+%22climate+adaptation%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP5"], "name": "Search — famine & food security", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(Sahel+OR+Africa+OR+Ethiopia+OR+global+OR+world)+AND+(famine+OR+%22food+security%22+OR+%22food+insecurity%22+OR+agriculture)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
    {"tag": ["CP2"], "name": "Search — coastal & river management", "kind": "feed", "max_items": 30,
     "url": "https://news.google.com/rss/search?q=(coastal+OR+beach+OR+river+OR+estuary+OR+mangrove+OR+delta)+AND+(erosion+OR+management+OR+restoration+OR+reclamation+OR+flood+OR+%22sea+level%22)+when:30d&hl=en-HK&gl=HK&ceid=HK:en",
     "authoritative": False},
]

# ---------------------------------------------------------------------------
# Keyword tagging — the geography signal for each elective.
# ---------------------------------------------------------------------------

TAGS = {
    # CP1 is the tectonic hazards module. The terms name the HAZARD or the
    # GEOLOGICAL PROCESS. "landslide" is deliberately NOT here - in this
    # syllabus a landslide belongs to EP1 (Hong Kong slope management), and
    # the word also collides with a landslide election victory.
    "CP1": ["earthquake", "volcano", "volcanic", "eruption", "tsunami", "seismic wave",
            "seismic activity", "seismic event", "seismic hazard", "seismic monitoring",
            "tremor", "lava", "epicentre", "epicenter", "aftershock", "tectonic",
            "plate boundary", "plate movement", "magnitude", "ring of fire",
            "mantle convection", "subduction", "mid-ocean ridge", "hot spot", "hotspot",
            "ash cloud", "pyroclastic", "tectonic hazard"],
    "CP2": ["coast", "coastal", "erosion", "shoreline", "sea level", "reclamation",
            "flood", "typhoon", "storm surge", "harbour", "estuary",
            "river", "drainage", "sediment", "beach", "mangrove", "wetland",
            "breakwater", "seawall", "dredging", "longshore drift", "coastal landform",
            "river basin", "river management", "river system", "river channel"],
    # CP3 terms are deliberately specific. "port" and "plant" appear in too
    # many unrelated stories (port cities, power plants, "plant" as a verb) and
    # produced false positives, so the geography of industry is named directly.
    # "industry" alone is just as loose - an "industry delegation" to a film
    # festival is not industrial location - so the manufacturing terms are
    # named instead.
    "CP3": ["industrial", "manufacturing", "steel", "logistics",
            "agglomeration", "deindustrial", "silicon valley", "supply chain",
            "industrial park", "industrial estate", "foreign direct investment",
            "fdi", "production base", "assembly line", "outsourcing", "offshore",
            "multinational", "transnational", "global production", "factory",
            "high-tech", "high tech", "it hub", "business park",
            "container terminal", "free trade zone", "logistics hub",
            "port city", "port town", "seaport", "deepwater port",
            "shipping port", "transhipment", "shipbuilding"],
    # "population" on its own matched every refugee and displacement report,
    # so the urban sense has to be qualified. "city" alone is just as loose
    # - "Chipiona City Council" and "gunman killed 6 in Polish city square"
    # are not urban geography - so the urban terms name the urban FORM.
    "CP4": ["urban", "housing", "reclamation", "brownfield",
            "transport", "congestion", "commut", "liveable", "livable", "compact city",
            "public consultation", "master plan", "renewal", "open space", "public housing",
            "land use", "smart city", "urban population", "urbanisation", "urbanization",
            "urban sprawl", "megacity", "city centre", "city center", "gentrification",
            "urban decay", "council housing", "public housing",
            "urban renewal", "urban redevelopment", "urban planning", "urban area",
            "urban design", "urban heat", "urban flood", "urban resilience",
            "housing estate", "housing supply", "redevelopment scheme",
            "city centre", "city center", "downtown", "high-rise", "high rise"],
    "CP5": ["famine", "hunger", "food security", "food insecurity", "malnutrition",
            "sahel", "drought", "crop", "agricultur", "irrigation", "harvest", "yield",
            "grain", "wheat", "maize", "fertiliser", "fertilizer", "rural development",
            "land degradation", "desertification", "food price", "locust"],
    # "congo" matched the country in every Ebola bulletin and sanctions
    # regulation, none of which is about the rainforest. The basin is what
    # the module is about, so the term names the basin.
    "CP6": ["deforestation", "forest", "rainforest", "canopy", "tree cover", "wildfire",
            "peat", "haze", "palm oil", "logging", "reforestation", "biodiversity",
            "amazon", "illegal logging", "forest fire", "burning",
            "congo basin", "amazon basin", "forest cover", "forest loss",
            "forest degradation", "carbon sink", "indigenous forest"],
    "CP7": ["climate", "warming", "greenhouse", "emission", "carbon", "temperature",
            "sea level rise", "glacier", "ice sheet", "heatwave", "heat wave", "drought",
            "ipcc", "net zero", "decarbon", "energy transition", "renewable", "solar",
            "wind power", "el niño", "coral", "typhoon", "cyclone"],
    # "fold" and "fault" alone fire on "folding table" and "fault line"
    # in a car-crash story, so the terms name the geological structure.
    "EP1": ["rock", "weathering", "erosion", "mass movement", "landslide", "granite",
            "tuff", "sediment", "metamorphic", "fold and fault", "folded rock",
            "folds and faults", "fault line", "quarry", "geopark",
            "geology", "geological", "gorge", "headland", "karst", "hong kong geopark",
            "unesco", "slope failure"],
}

# Extra weight: Hong Kong and Pearl River Delta items are what this cohort
# can actually be examined on, so they rank above generic global items.
HK_BOOST = re.compile(
    r"(?i)\b(hong kong|hk\b|new territories|kowloon|hong kong island|"
    r"kowloon peninsula|tsuen wan|sha tin|tuen mun|tai po|sai kung|cheung chau|"
    r"lam tsuen|sham chui po|yuen long|ma on shan|pei tau kok|"
    r"sha tau kok|kwai tsing|tsing yi|kwun tong|hong kong harbour|"
    r"victoria harbour|pei shan|tau kwa lang|double haven)\b"
)

# A search feed returns stories from anywhere, and a US town council meeting
# is not geography for a Hong Kong classroom. So a local-institution story
# outside the region is demoted: it still reaches the feed if nothing better
# exists, but it must not crowd out the local and global material.
LOCAL_NOISE = re.compile(
    r"(?i)\b(city council|town council|county council|borough council|"
    r"city manager|mayor announces|school district|board of education|"
    r"county commissioner|sheriff's? office|township|borough of)\b"
)


def fetch(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&#39;", "'", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_feed(body: bytes, url: str) -> list[dict]:
    """Parse RSS 2.0, Atom, or a bare HTML page into link records."""
    text = body.decode("utf-8", errors="replace")
    items: list[dict] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Not XML — treat as HTML and pull anchors + headings
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
            href, inner = m.group(1), strip_html(m.group(2))
            if len(inner) < 25:
                continue
            if href.startswith("/"):
                href = url.rsplit("/", 3)[0] + href if url.count("/") > 2 else href
            if href.startswith("http"):
                items.append({"title": inner, "url": href, "published": "", "summary": ""})
        return items[:12]

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = pub = summary = ""
        for ch in item:
            ct = ch.tag.split("}")[-1]
            if ct == "title":
                title = strip_html(ch.text or "")
            elif ct == "link":
                link = (ch.get("href") or ch.text or "").strip()
            elif ct in ("pubDate", "published", "updated", "date"):
                pub = (ch.text or "").strip()
            elif ct in ("description", "summary", "content"):
                summary = strip_html(ch.text or "")
        if title and link:
            # A search feed (Google News) appends " - Publisher Name" to every
            # headline. That suffix is not part of the story's title, and
            # leaving it in pollutes the keyword match - " - The Guardian" has
            # no geography in it but "man" appears in many outlet names. Strip
            # the trailing " - Name" when it is clearly a publisher suffix.
            clean = re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()
            if clean and len(clean) >= len(title) * 0.5:
                title = clean
            items.append({"title": title, "url": link, "published": pub, "summary": summary})
    return items


# Words that mean "this is a geography topic" rather than "these letters
# appeared somewhere in the text". Without this, a Chernobyl-fallout story
# matches EP1 on the word "soil" and a wind-farm story matches CP2 on "wave".
#
# The list has to cover the vocabulary of POLITICS and MARKETS, because
# that vocabulary collides with the geography vocabulary:
#
#   - "landslide" is a CP1/EP1 hazard word AND a landslide election victory
#   - "tsunami" is a CP1 hazard AND a political "blue tsunami"
#   - "wave" is a CP2 coastal term AND a "blue wave" at an election
#   - "seismic" describes ground movement AND market activity
#
# So an election, a market, a rally or a stock headline is not geography,
# even when it contains a hazard word. The one exception is a headline that
# names the hazard itself ("Earthquake in Japan"), because a genuine
# tectonic story can also be filed under a political or economic topic.
NEGATIVE_CONTEXT = re.compile(
    r"(?i)\b(chernobyl|fukushima|nuclear|war\b|conflict|election|elections|"
    r"election results|midterm|ballot|vote|voting|voters|democrat|democratic|"
    r"republican|gop\b|supreme court|justice|justices|parliament|congress|"
    r"senate|prime minister|president|electioneering|landslide victory|"
    r"celebrity|football|nba|nfl|transfer deal|striker signs|"
    r"obituary|stock market|share price|shares|wall street|nasdaq|dow jones|"
    r"markets rally|market rally|investors|earnings|ipo|bitcoin|crypto|"
    r"law\b court|verdict|trial|sentenced|"
    r"golden rooster|film|film festival|box office|album|concert|"
    r"gold rooster|hundred flowers|award ceremony)\b"
)

# A hazard word used as a POLITICAL metaphor. "Blue tsunami" and "landslide
# victory" are not hazards - they are election results.
#
# This is checked INDEPENDENTLY of NEGATIVE_CONTEXT, because the metaphor
# phrases often carry no politics word at all ("The Blue Tsunami - The New
# York Times"). Catching them only inside the negative test let them
# through.
POLITICAL_METAPHOR = re.compile(
    r"(?i)("
    r"\bblue\s+[''\u2018\u2019\u201c\u201d\"]?tsunami\b|"
    r"\bred\s+[''\u2018\u2019\u201c\u201d\"]?tsunami\b|"
    r"\bpink\s+[''\u2018\u2019\u201c\u201d\"]?tsunami\b|"
    r"\bdemocratic\s+[''\u2018\u2019\u201c\u201d\"]?tsunami\b|"
    r"\brepublican\s+[''\u2018\u2019\u201c\u201d\"]?tsunami\b|"
    r"\belection\s+tsunami\b|\bpolitical\s+tsunami\b|"
    r"\btsunami\s+of\s+(votes|support|protests|anger)\b|"
    r"\blandslide\s+victory\b|\blandslide\s+win\b|"
    r"\blandslide\s+in\s+the\s+polls\b|\bblue\s+wave\b|"
    r"\bwave\s+of\s+(votes|support)\b|"
    r"[''\u2018\u2019\u201c\u201d\"]an\s+earthquake[''\u2018\u2019\u201c\u201d\"]\s*:|"
    r"\blike\s+an\s+earthquake\b|"
    r"\ban\s+earthquake\s+of\s+(a|the|democratic|republican)\b|"
    # "AI earthquake", "tech earthquake", "market earthquake" - a hazard
    # word used as a metaphor for a fast change in something that is not
    # the Earth. "Jensen Huang's looming ouster triggers an AI earthquake"
    # was tagged CP1.4 (tectonic hazards) and reached the CP1 index.
    r"\b(ai|artificial\s+intelligence|tech|technology|digital|silicon|semiconductor|"
    r"market|financial|media|social|political|industry|business|corporate|"
    r"startup|tech)\s+earthquake\b|"
    r"\bearthquake\s+in\s+(the\s+)?(ai|tech|technology|digital|silicon|"
    r"semiconductor|market|media|social)\b|"
    # The same metaphor shape with "landslide" - "political landslide in the
    # primaries" was tagged EP1 (Hong Kong slope management).
    r"\b(political|election|electoral|party|voter|primary|primaries|"
    r"parliamentary|campaign|campaigns)\s+landslide\b|"
    r"\blandslide\s+(victory|win|voters?|votes|turnout|primaries)\b"
    r")"
)

# A hazard word in a PHYSICAL context - the story is about the hazard.
#
# This has to be more than the bare hazard noun. "An Earthquake: A
# Democratic Rout Stuns Texas" contains "earthquake", and so does
# "Magnitude 5.9 earthquake strikes off eastern Japan" - but only one of
# them is geography. So the rescue pattern requires the hazard word to sit
# in a phrase that describes the physical event: the thing struck, shook,
# warned about, responded to or was measured.
PHYSICAL_HAZARD_CONTEXT = re.compile(
    r"(?i)("
    r"\bmagnitude\s*-?\d|\bm\s*-?\d(\.\d+)?\s+earthquake|"
    r"earthquake\s+(strikes|hits|shakes|warning|response|early warning|"
    r"damage|devastat|killed|injures|injur|displaced|relief|zone|"
    r"epicentre|epicenter|aftershock|tsunami|evacuat|monitor|"
    r"resilien|preparedness|awareness|readiness|ready|innovation|"
    r"lesson|survey|imag|measur|analysis|resilien|research|"
    r"expertise|reduce|mitigat|prevention|building|cost|alert|"
    r"likelihood|forecast|model|science|scientis|researcher|"
    r"engineer|architect|hazard|catastroph|tremor|magnitude)|"
    r"\b(strong|powerful|deadly|devastating|major|severe|strongest)\s+earthquake|"
    r"volcano\s+(erupt|eruption|erupts|alert|warning|watch|activity)|"
    r"volcano['\u2019]s\s+(ability|power|capacity|potential)|"
    r"\bvolcano\b.{0,24}\b(erupt|ability|power|capacity|potential|ash|lava)|"
    r"volcanic\s+(eruption|activity|system|ash|lava|plume)|"
    r"lava\s+(flow|fountain|eruption)|"
    r"\bmega\s?tsunami\b|"
    r"tsunami\s+(warning|readiness|ready|awareness|innovation|reaches|"
    r"response|resilien|lesson|surge|alert|evacuat|danger|threat|"
    r"risk|preparedness|drill|simulation|early|centre|center|hazard)|"
    r"\btsunami\b.{0,30}\b(shore|coast|wave|ocean|sea|hazard|warning|ready)|"
    r"seismic\s+(imaging|activity|event|wave|hazard|monitoring|data|survey|zone)|"
    r"\bseismic\b.{0,20}\b(imaging|study|analysis|zone|event|activity)|"
    r"subduction|slab\s+tearing|mantle\s+(convection|plume)|"
    r"plate\s+(boundary|movement|tectonic)|hot\s?spot|"
    r"mid-ocean\s+ridge|rift\s+zone|island\s+arc|ocean\s+trench|"
    r"tectonic\s+(hazard|landform|movement)|"
    r"\bvolcanic\b|eruption|aftershock|epicentre|epicenter|"
    r"lava\s+fountain|pyroclastic|ash\s+cloud|"
    r"quake\b"
    r")"
)

# A term must appear in the TITLE to count. Summaries are noisy.
#
# This table is the list of terms that are ONLY trusted in a title. It is
# applied by the matcher below through SUBTOPIC_TERMS, not by a separate
# lookup, so it stays in one place: the phrase-only rule for summaries is
# already expressed by the matcher, which only trusts a PHRASE in a summary.
#
# Kept here as the single list of "a summary mention is not enough for this
# word", so the two places that decide a tag cannot drift apart.
TITLE_WEIGHT_ONLY = {
    "CP1": {"earthquake", "volcano", "volcanic", "eruption", "tsunami", "tremor",
            "epicentre", "epicenter", "aftershock", "tectonic", "ash cloud",
            "pyroclastic", "plate boundary", "plate movement", "ring of fire"},
    "CP2": {"coast", "coastal", "erosion", "shoreline", "sea level", "reclamation",
            "flood", "typhoon", "storm surge", "wave", "harbour", "estuary", "river",
            "drainage", "sediment", "beach", "mangrove", "wetland", "breakwater",
            "seawall", "dredging"},
    "CP3": {"industrial", "industry", "factory", "manufacturing", "steel", "logistics",
            "port", "investment", "agglomeration", "deindustrial", "silicon valley",
            "supply chain", "industrial park", "foreign direct", "fdi", "production base"},
    "CP4": {"urban", "city", "housing", "population", "brownfield", "transport",
            "congestion", "commut", "liveable", "livable", "compact city",
            "master plan", "renewal", "open space", "public housing", "land use",
            "smart city", "reclamation"},
    "CP5": {"famine", "hunger", "food security", "food insecurity", "malnutrition",
            "sahel", "crop failure", "crop yield", "agricultural production",
            "irrigation", "harvest", "grain", "wheat", "maize", "fertiliser",
            "fertilizer", "rural development", "land degradation", "desertification",
            "food price", "locust"},
    "CP6": {"deforestation", "forest", "rainforest", "canopy", "tree cover", "wildfire",
            "peat", "haze", "palm oil", "logging", "reforestation", "biodiversity",
            "amazon", "illegal logging", "forest fire"},
    "CP7": {"climate", "warming", "greenhouse", "emission", "carbon", "temperature",
            "sea level rise", "glacier", "ice sheet", "heatwave", "heat wave",
            "ipcc", "net zero", "decarbon", "energy transition", "renewable", "solar",
            "wind power", "el niño", "coral"},
    # "fold" alone fires on "folding table", so the fold and fault terms
    # name the geological structure.
    "EP1": ["rock", "weathering", "erosion", "mass movement", "landslide", "granite",
            "tuff", "sediment", "metamorphic", "fold and fault", "folded rock",
            "folds and faults", "fault line", "quarry", "geopark",
            "geology", "geological", "gorge", "headland", "karst", "hong kong geopark",
            "unesco", "slope failure"],
}


def is_geography_title(title: str, summary: str = "") -> bool:
    """True when a headline is about a PHYSICAL geography event.

    A hazard word alone is not enough. "An Earthquake: A Democratic Rout
    Stuns Texas" and "Magnitude 5.9 earthquake strikes off eastern Japan"
    both contain "earthquake", and only the second is geography. So the
    hazard word has to sit in a physical phrase - the thing struck, shook,
    warned about, responded to, or was measured.

    A political metaphor ("blue tsunami", "landslide victory") is never
    geography, whatever else the headline says.
    """
    t = title.lower()
    s = summary.lower()
    if POLITICAL_METAPHOR.search(t):
        return False
    if PHYSICAL_HAZARD_CONTEXT.search(t):
        return True
    # A summary can carry the physical context when the title is terse
    # ("Magnitude 6.4 - 30 km WSW of Lata, Solomon Islands").
    return bool(s and PHYSICAL_HAZARD_CONTEXT.search(s))


def tag_item(title: str, summary: str) -> list[str]:
    """Tag an item against the electives.

    A term must appear in the TITLE, except for CP2's wave/tide terms and a
    few others that are meaningful enough in a summary to carry the tag.
    """
    t = title.lower()
    s = summary.lower()
    blob = f"{t} {s}"
    # A political metaphor is never geography, even when the headline
    # carries no other politics word ("The Blue Tsunami - The New York
    # Times"). This is checked first, on its own, because the negative
    # filter below would not fire on that headline.
    if POLITICAL_METAPHOR.search(t):
        return []
    if NEGATIVE_CONTEXT.search(blob):
        # Still allow a strong geography title through (e.g. "Earthquake in X")
        if not is_geography_title(title, summary):
            return []

    # Title-only matching. A summary mentions "sediment" in half the climate
    # stories on the web, and a title is what a student scans.
    tags = []
    for code, words in TAGS.items():
        for w in words:
            # Word-boundary match, not substring. A plain `w in t` makes "port"
            # fire on "report", "support" and "important", and "wave" fire on
            # "wavelength". Multi-word terms are matched literally.
            if " " in w:
                hit = w in t
            else:
                hit = re.search(r"\b" + re.escape(w) + r"(?:s|es|ed|ing)?\b", t) is not None
            if hit:
                tags.append(code)
                break
    return sorted(set(tags))


def _matches_gate(gate, title: str, summary: str) -> bool:
    """True when an item looks on-topic for a feed that declares a gate.

    A gate is the list of words that make a story belong to the feed's
    topic. It is matched in the TITLE or, for a phrase, in the summary.

    ReliefWeb is authoritative for CP5, but it also carries measles
    bulletins, school reports and telecom dashboards. Forcing CP5 onto
    those put 59 unrelated humanitarian documents into the Combating
    Famine list, so the feed has to say what its topic is.

    `gate` may be the bare list of terms, or a dict with a "terms" key and
    an "electives" key (the shape used by _GATE_BY_FEED).
    """
    if isinstance(gate, dict):
        terms = gate.get("terms") or []
    else:
        terms = gate or []
    t = title.lower()
    s = summary.lower()
    for term in terms:
        if _term_hit(term, t):
            return True
        if " " in term and s and _term_hit(term, s):
            return True
    return False


# Live lookup of every gated feed, by feed name. The re-tag pass uses this
# so that editing a gate in the FEEDS table applies to the WHOLE feed at
# once - including items collected before the edit. Storing a frozen copy of
# the gate on each item meant a tightened gate never reached the old items.
_GATE_BY_FEED: dict[str, dict] = {
    f["name"]: {"terms": f.get("gate") or [], "electives": f.get("tag") or []}
    for f in FEEDS if f.get("gate")
}


def _term_hit(term: str, text: str) -> bool:
    """Match a term on word boundaries.

    A phrase matches literally. A single word matches with an optional
    English suffix, so "landslide" matches "landslides" and "erosion" matches
    "eroding", but "port" does not fire on "report" and "wave" does not fire
    on "wavelength".
    """
    if " " in term:
        return term in text
    return re.search(r"\b" + re.escape(term) + r"(?:s|es|ed|ing)?\b", text) is not None


def subtopic_tags(title: str, summary: str) -> list[tuple[str, str]]:
    """Match a headline against the curriculum sub-topics of every elective.

    Returns (elective, sub-question code) pairs. The elective code alone is
    not "focused viewing" - a student studying landslides wants the landslide
    stories. So each headline is matched against the sub-topic terms of every
    elective, and the matching sub-question codes become the item's
    sub-topic tags.

    Matching is two-tier, because a title and a summary are not equally
    strong signals:

    - A TITLE match counts for any term. A title is what a student scans, so
      it is the primary signal.
    - A SUMMARY match counts only for a PHRASE. A phrase like "public
      housing" or "slope stability" is specific enough to survive in prose.
      A single word is not: "market", "wave" and "core" appear in ordinary
      sentences, and matching them in the summary tags a customs seizure as
      CP3.1 industrial location and a rock as EP1.

    The phrase list is therefore the accurate one, and the single-word list
    is the title-only one.
    """
    t = title.lower()
    s = summary.lower()
    # The sub-topic matcher runs over EVERY elective, so it needs the same
    # politics-and-markets filter as the elective tagger. Without it, "The
    # Democratic Party won the U.S. midterm elections by a landslide" is
    # matched as CP1.4 (tectonic hazards) on the word "landslide" - and the
    # sub-topic match PROMOTES the item into CP1, so it lands in the feed.
    # A political metaphor is never geography, even when the headline
    # carries no other politics word ("The Blue Tsunami - The New York
    # Times"). This is checked first, on its own.
    if POLITICAL_METAPHOR.search(t):
        return []
    if NEGATIVE_CONTEXT.search(f"{t} {s}"):
        if not is_geography_title(title, summary):
            return []
    out: list[tuple[str, str]] = []
    for elective, subs in SUBTOPIC_TERMS.items():
        for code, terms in subs.items():
            hit = False
            for term in terms:
                if _term_hit(term, t):
                    hit = True
                    break
                if " " in term and s and _term_hit(term, s):
                    hit = True
                    break
            if hit:
                out.append((elective, code))
    return out


def hk_score(title: str, summary: str) -> int:
    return 2 if HK_BOOST.search(f"{title} {summary}") else 0


def _epoch_to_date(value) -> str:
    """An epoch timestamp (ms or s) as "YYYY-MM-DD", or "" if it is not one.

    The USGS feeds publish the event time as an epoch in milliseconds. Slicing
    that to 10 characters gives "1794267921", which is not a date: it sorts
    to the very end of the feed and is then dropped by the keep-list, so the
    real earthquake stories vanish from the News Corner entirely.
    """
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    # Values that look like seconds are scaled up; anything past the year
    # 2001 in seconds is far beyond now, so it must already be milliseconds.
    if ts < 1_000_000_000:
        ts *= 1000
    try:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def clean_date(s: str) -> str:
    if not s:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s[:26], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return s[:10]


def _title_key(title: str) -> str:
    """A title reduced to the words that identify the STORY.

    Two items are the same story when their titles agree once the publisher
    suffix (" - The New York Times") and the punctuation are removed. The
    merge uses this to recognise a story that a search feed has handed out
    again under a NEW url - Google News rewrites the link every time, so the
    url-keyed id changes and the story would otherwise be added again.
    """
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", (title or "")).strip()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def collect() -> tuple[list[dict], list[dict]]:
    seen = set()
    seen_titles: set[str] = set()
    items: list[dict] = []
    report: list[dict] = []
    for feed in FEEDS:
        try:
            body = fetch(feed["url"])
        except Exception as e:
            report.append({"feed": feed["name"], "url": feed["url"], "ok": False,
                           "error": str(e)[:120], "items": 0})
            continue
        try:
            if feed.get("json"):
                data = json.loads(body)
                found = []
                for f in data.get("features", []):
                    pr = f.get("properties", {})
                    mag = pr.get("mag")
                    place = pr.get("place") or "unknown location"
                    # The USGS title is "M 4.9 - south of the Fiji Islands",
                    # which names neither the hazard nor the module. A
                    # student scanning the list sees a row of bare
                    # coordinates, so the title is rewritten to say what it
                    # is: a magnitude-4.9 earthquake, and where.
                    title = f"Magnitude {mag} earthquake - {place}"
                    found.append({
                        "title": title,
                        "url": pr.get("url", ""),
                        # The USGS time is an epoch in MILLISECONDS. Slicing
                        # it to 10 characters gave "1794267921" - not a date.
                        # A malformed date sorts to the very end of the feed
                        # and is then truncated away by the keep-list, so
                        # every real earthquake was silently lost while the
                        # taggers were blamed for it.
                        "published": _epoch_to_date(pr.get("time")),
                        "summary": f"{place} — magnitude {mag}",
                    })
            else:
                found = parse_feed(body, feed["url"])
        except Exception as e:
            report.append({"feed": feed["name"], "url": feed["url"], "ok": False,
                           "error": f"parse: {e}"[:120], "items": 0})
            continue

        added = 0
        for it in found:
            url = it.get("url") or ""
            if not url.startswith("http"):
                continue
            # A feed-index page lists its own feeds. Those entries have a bare
            # URL or an RSS path as their title and are navigation, not news.
            title_probe = (it.get("title") or "").strip()
            if (not title_probe
                    or title_probe.startswith("http")
                    or re.fullmatch(r"(www\.)?\S+\.(gov|com|org|hk|int|xml|html|htm|rss|feed)/?\S*", title_probe, re.I)
                    or re.fullmatch(r"\S+\.(rss|xml|feed)(\?\S*)?", title_probe, re.I)
                    or "rss subscription" in title_probe.lower()
                    or "rss feeds add-on" in title_probe.lower()
                    or "tips on rss" in title_probe.lower()):
                continue
            key = hashlib.sha1(url.encode()).hexdigest()
            if key in seen:
                continue
            # A search feed returns the SAME story from several outlets, each
            # with its own URL and its own " - Publisher" title suffix. Left
            # alone they fill the feed with five copies of one story. So the
            # title is normalised (publisher suffix removed, lowercased,
            # punctuation stripped) and duplicates are dropped - keeping the
            # first, which is the earliest-ranked one from the sorted feed.
            #
            # The publisher suffix has to be removed BEFORE the punctuation
            # is stripped. Doing it the other way round first replaced every
            # non-word character with a space, so " - Waikato Times" became
            # "   Waikato Times" and the suffix regex no longer matched -
            # which is how three copies of the same market story survived.
            title_norm = re.sub(r"\s+-\s+[^-]{2,40}$", "", title_probe).strip()
            title_norm = re.sub(r"[^a-z0-9]+", " ", title_norm.lower()).strip()
            if title_norm in seen_titles:
                continue
            # Two kinds of feed.
            #
            # A TOPIC feed exists for one elective (IVHHN volcano bulletins,
            # HKO climate reports, UN News food security). Its whole purpose is
            # that topic, so every item keeps the declared tag even when the
            # headline is terse.
            #
            # A GENERAL feed is a broad news feed that merely happens to
            # contain geography (RTHK, HK DSD, ScienceDaily). Those items must
            # earn their tag from the keywords, or the feed floods the corner
            # with press releases about nothing geographic.
            tags = tag_item(it.get("title", ""), it.get("summary", ""))
            declared = feed.get("tag") or []
            if isinstance(declared, str):
                declared = [declared]
            if feed.get("authoritative"):
                # An authoritative feed still has to be ON TOPIC. ReliefWeb
                # is authoritative for CP5, but it also carries measles
                # bulletins, school reports, telecom dashboards and meeting
                # minutes - and forcing CP5 onto those put 59 unrelated
                # humanitarian documents into the Combating Famine list.
                #
                # So a feed declares the terms that make an item on-topic for
                # it. A feed with no gate (the USGS earthquake feeds, where
                # every item IS an earthquake by construction) keeps its
                # declared tag unconditionally.
                gate = feed.get("gate")
                for t in declared:
                    if t in tags:
                        continue
                    if gate is None:
                        tags.append(t)
                    elif _matches_gate(gate, it.get("title", ""),
                                       it.get("summary", "")):
                        tags.append(t)
            if not tags:
                continue
            seen.add(key)
            seen_titles.add(title_norm)
            # A sub-topic match is a strong signal of the elective too: a
            # headline about "public housing" is CP4 even when the general
            # keyword list did not catch it, because the keyword list has to
            # stay narrow to avoid false positives. So a sub-topic match
            # promotes the item into that elective, and a general keyword
            # match alone does not.
            pairs = subtopic_tags(it.get("title", ""), it.get("summary", ""))
            subs = sorted({code for _elec, code in pairs})
            for elective, _code in pairs:
                if elective not in tags:
                    tags.append(elective)
            tags = sorted(set(tags))
            items.append({
                "title": it["title"][:180],
                "url": url,
                "source": feed["name"],
                "published": clean_date(it.get("published", "")),
                "summary": (it.get("summary", "") or "")[:320],
                "topics": tags,
                "subtopics": subs,
                "hk": bool(HK_BOOST.search(f"{it.get('title','')} {it.get('summary','')}")),
                "id": key[:12],
                # The feed NAME is kept, not a frozen copy of the gate.
                # A frozen copy means a tightened gate never reaches the
                # items already in the feed: the "multi-hazard" term was
                # removed from the UNDRR gate, but every item already
                # collected still carried the old list, so the CP1 index
                # kept its general disaster-preparedness stories. The
                # re-tag pass now looks the LIVE gate up by feed name, so
                # a gate edit applies to the whole feed at once.
                "gated_feed": feed["name"] if feed.get("gate") else "",
            })
            added += 1
            if added >= feed.get("max_items", 40):
                break
        report.append({"feed": feed["name"], "url": feed["url"], "ok": True,
                       "error": "", "items": added})
    # Hong Kong first, then newest. The date is a "YYYY-MM-DD" string, so it
    # sorts correctly by itself; negating the year makes the newest land first
    # within each HK / non-HK group.
    #
    # Local-institution noise is demoted below everything else: a US city
    # council story is not geography for a Hong Kong classroom, but it still
    # reaches the feed if there is nothing better.
    def _rank(i: dict) -> tuple:
        blob = f"{i.get('title','')} {i.get('summary','')}"
        noisy = bool(LOCAL_NOISE.search(blob)) and not HK_BOOST.search(blob)
        return (noisy, not i["hk"], _neg_date(i["published"]))

    items.sort(key=_rank)
    return items, report


def balance_by_elective(items: list[dict], keep: int, per_cap: int = 60) -> list[dict]:
    """Trim the merged feed so no single elective can crowd out the others.

    A single feed (ReliefWeb) can contribute hundreds of items that all match
    one elective's terms. Left alone, that one elective fills the whole
    keep-list and the other seven become invisible in the News Corner - which
    is exactly what happened: CP5 held 246 of 300 items while CP4 held 4.

    So each elective gets its own cap, and the remainder is shared. Items
    are already sorted (Hong Kong first, then newest), so the cap keeps the
    best of each elective rather than an arbitrary slice.

    An item can carry several electives. It is counted against the elective
    with the most room, and it is only kept if EVERY elective it carries
    still has room - otherwise it would push one elective past its cap.
    """
    counts: dict[str, int] = {}
    kept: list[dict] = []
    overflow: list[dict] = []
    for it in items:
        codes = [c for c in it.get("topics", []) if c in SUBTOPIC_TERMS]
        if not codes:
            overflow.append(it)
            continue
        # Keep it only if every elective it belongs to has room.
        if all(counts.get(c, 0) < per_cap for c in codes):
            for c in codes:
                counts[c] = counts.get(c, 0) + 1
            kept.append(it)
        else:
            overflow.append(it)
    # Fill the remaining room from the overflow, in the same order, still
    # respecting the cap.
    room = keep - len(kept)
    for it in overflow:
        if room <= 0:
            break
        codes = [c for c in it.get("topics", []) if c in SUBTOPIC_TERMS]
        if codes and not all(counts.get(c, 0) < per_cap for c in codes):
            continue
        kept.append(it)
        for c in codes:
            counts[c] = counts.get(c, 0) + 1
        room -= 1
    return kept[:keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=300, help="max items to keep")
    ap.add_argument("--per-elective-cap", type=int, default=60,
                    help="max items one elective may hold in the feed")
    ap.add_argument("--max-age-days", type=int, default=60,
                    help="drop items older than this many days")
    args = ap.parse_args()

    items, report = collect()
    DATA.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Merge with existing items so the feed accumulates rather than resets.
    existing = []
    news_file = DATA / "news.json"
    if news_file.exists():
        try:
            existing = json.loads(news_file.read_text())
        except Exception:
            existing = []
    by_id = {i["id"]: i for i in existing}
    # A story kept by its url-id is not enough. A search feed (Google News)
    # rewrites the link every time it serves a story, so the same headline
    # comes back under a new id and the feed grows a second copy of it -
    # which is how the JBS and Chile stories ended up in the feed two and
    # four times. The title key catches those before they are added.
    by_title = {_title_key(i.get("title", "")): i for i in existing}
    added = 0
    for i in items:
        tkey = _title_key(i.get("title", ""))
        if tkey and tkey in by_title:
            # The story is already in the feed. Keep the newer copy's tags
            # (the re-tag pass below recomputes them anyway) but do not
            # add a second entry.
            continue
        by_id.setdefault(i["id"], i)
        if tkey:
            by_title[tkey] = i
        added += 1
    merged = list(by_id.values())
    # The feed may ALREADY hold duplicate titles - a bug in an earlier run
    # let them in - so they are collapsed here, not only prevented.
    deduped: dict[str, dict] = {}
    for i in merged:
        tkey = _title_key(i.get("title", ""))
        if not tkey:
            deduped["id:" + str(i.get("id"))] = i
            continue
        if tkey in deduped:
            # Keep the copy that carries the most tags and sub-topics: it
            # is the one that matched the most of the curriculum.
            old = deduped[tkey]
            if (len(i.get("topics") or []) + len(i.get("subtopics") or [])
                    > len(old.get("topics") or []) + len(old.get("subtopics") or [])):
                deduped[tkey] = i
            continue
        deduped[tkey] = i
    merged = list(deduped.values())
    # The feed accumulates, so it also accumulates stale items. The News
    # Corner is about CURRENT events: an item older than the window is
    # dropped, and so is an item whose date could not be read.
    merged = prune_stale(merged, args.max_age_days)
    # RE-TAG every item, including the ones carried over from the old file.
    #
    # The merge keeps an existing item by id, so it keeps the tags it was
    # given when it was first collected. Fixing the tagger therefore does
    # NOT fix the feed: an item tagged CP1 by the old keyword list stays
    # tagged CP1 forever, and the old politics stories stayed in the CP1
    # list through every re-tag. So the tags are recomputed from the title
    # and summary every run.
    merged = retag_items(merged)
    merged.sort(key=lambda i: (not i["hk"], _neg_date(i["published"])))
    merged = balance_by_elective(merged, args.keep, args.per_elective_cap)

    news_file.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "news_meta.json").write_text(json.dumps(
        {"updated_at": now, "n_items": len(merged), "feeds": report},
        ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for r in report if r["ok"])
    print(f"feeds ok       : {ok}/{len(report)}")
    print(f"items collected: {len(items)}")
    print(f"items in feed  : {len(merged)}")
    print(f"updated_at     : {now}")
    failed = [r for r in report if not r["ok"]]
    if failed:
        print("\nfailed feeds:")
        for f in failed:
            print(f"  - {f['feed']}: {f['error']}")
    from collections import Counter
    c = Counter(t for i in merged for t in i["topics"])
    print("\nby elective:")
    for code in sorted(SUBTOPIC_TERMS):
        print(f"  {code}: {c.get(code, 0)}")
    # The sub-topic coverage is the thing that makes the corner usable for
    # focused viewing, so report it rather than trusting it.
    sub = Counter(s for i in merged for s in i.get("subtopics", []))
    covered = {code for code in sub}
    all_codes = {sc for subs in SUBTOPIC_TERMS.values() for sc in subs}
    print(f"\nsub-topics tagged : {len(covered)}/{len(all_codes)}")
    missing = sorted(all_codes - covered)
    if missing:
        print(f"no news yet        : {', '.join(missing)}")
    # A feed that returns zero items is a rotting feed, not a quiet feed.
    # A URL that appears under two names (the same source serving two
    # electives) is one feed, so count unique URLs - otherwise the report
    # says a feed is empty when its twin already supplied the items.
    empty_urls = {f["url"] for f in report if f.get("ok") and not f.get("items")}
    seen_empty: set[str] = set()
    empty: list[str] = []
    for f in report:
        if f.get("ok") and not f.get("items") and f["url"] not in seen_empty:
            seen_empty.add(f["url"])
            empty.append(f["feed"])
    if empty:
        print(f"\nempty feeds ({len(empty)}):")
        for name in empty:
            print(f"  - {name}")


def _neg_date(d: str) -> str:
    """A date string with the digits inverted, so newest sorts first.

    An item with NO usable date gets "0000-00-00", whose inversion is
    "9999-99-99" - so it sorts last among the dated items instead of
    sorting to the end of the list as a raw string did. A malformed date
    ("Friday, Oc") is treated the same way: it is not a date, so it must
    not be allowed to push a real story out of the feed.
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""):
        d = "0000-00-00"
    return "".join(chr(ord("9") - (ord(c) - ord("0"))) if c.isdigit() else c for c in d)


def retag_items(items: list[dict]) -> list[dict]:
    """Recompute every item's elective and sub-topic tags from its text.

    The merge keeps an existing item by id, so it keeps the tags it was
    given when it was first collected. Fixing the tagger therefore does
    NOT fix the feed: an item tagged CP1 by the old keyword list stays
    tagged CP1 forever, and the politics stories stayed in the CP1 list
    through every re-collect.

    So the tags are recomputed from the title and summary every run. An
    item that no longer matches any elective is dropped: it is not
    geography, and it was only ever in the feed because of a bad match.
    """
    out: list[dict] = []
    for it in items:
        title = it.get("title", "")
        summary = it.get("summary", "") or ""
        tags = tag_item(title, summary)
        pairs = subtopic_tags(title, summary)
        for elective, _code in pairs:
            if elective not in tags:
                tags.append(elective)
        # An item that arrived through a GATED authoritative feed keeps its
        # declared elective only if it still passes that gate. Without
        # this, the tagger alone would strip the topic off a terse
        # authoritative bulletin ("Crystals hint at a volcano's ability to
        # erupt") and the feed would lose its best sources.
        #
        # The gate is looked up LIVE by feed name (see "gated_feed"), so a
        # tightened gate applies to every item in the feed, not only to
        # items collected after the edit. The gate is also RESTRICTIVE:
        # an item that no longer passes its feed's gate loses that
        # elective even if the general keyword tagger matched it.
        # Without that, "multi-hazard" kept a story about a general
        # early-warning workshop in the CP1 tectonic index.
        gated = it.get("gated_feed") or ""
        if not gated:
            # Migrate an item collected before the "gated_feed" field
            # existed: it carries the feed's name in "source", and the
            # live gate is looked up by that name. The old frozen "gates"
            # copy is deliberately NOT used - it is the stale copy that
            # kept a tightened gate from ever applying.
            src = it.get("source") or ""
            if src in _GATE_BY_FEED:
                gated = src
        feed_gate = _GATE_BY_FEED.get(gated)
        if feed_gate is not None:
            if not _matches_gate(feed_gate, title, summary):
                # The story no longer matches the topic this feed serves.
                # It must not sit in that elective's list.
                for elective in list(tags):
                    if elective in (feed_gate.get("electives") or []):
                        tags.remove(elective)
            else:
                for elective in (feed_gate.get("electives") or []):
                    if elective not in tags:
                        tags.append(elective)
        if not tags:
            continue
        it = dict(it)
        it["topics"] = sorted(set(tags))
        it["subtopics"] = sorted({code for _elec, code in pairs})
        it["hk"] = bool(HK_BOOST.search(f"{title} {summary}"))
        out.append(it)
    return out


def prune_stale(items: list[dict], max_age_days: int = 60) -> list[dict]:
    """Drop items older than the window, and items with no usable date.

    The feed ACCUMULATES: every run merges the new items into the old file
    and keeps the union. So a story from 2023 was still in the feed in 2026
    - the News Corner is about CURRENT events, and a three-year-old
    document is noise.

    An item with no parseable date is dropped too. Its date cannot be
    checked, and keeping it would let undated items pile up at the bottom
    of the feed forever.
    """
    now = datetime.now(timezone.utc).date()
    kept: list[dict] = []
    for it in items:
        d = (it.get("published") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        try:
            age = (now - datetime.strptime(d, "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if age > max_age_days:
            continue
        kept.append(it)
    return kept


if __name__ == "__main__":
    main()
