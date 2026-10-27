#!/usr/bin/env python3
"""
Geography News Corner — collect and tag current geography news.

Polls a set of RSS/Atom feeds and search queries, tags each item against the
HKDSE Geography electives, and writes data/news.json for the site.

Every feed URL here was fetched and confirmed to return live items before
being added.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) MakGeography/1.0"

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
    {"tag": ["CP1"], "name": "NASA Astronomy Picture of the Day", "kind": "feed", "max_items": 4,
     "url": "https://science.nasa.gov/apod/", "authoritative": False},
    {"tag": ["CP1"], "name": "IVHHN — Volcano Bulletin", "kind": "feed",
     "url": "https://www.ivhhn.org/", "authoritative": True},
    {"tag": ["CP1", "CP7"], "name": "HKO — Weather RSS portal", "kind": "feed",
     "url": "https://rss.weather.gov.hk/rsse.html", "authoritative": True},
    {"tag": ["CP1"], "name": "NGDC / NOAA Significant Earthquakes", "kind": "feed", "max_items": 12,
     "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
     "json": True, "authoritative": True},
    {"tag": ["EP1"], "name": "HK CEDD — Recent topics", "kind": "feed",
     "url": "https://www.cedd.gov.hk/eng/rss/recent_topics_rss.xml", "authoritative": True},
    {"tag": ["CP1", "EP1"], "name": "HK DSD — What’s New", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Whats_New.xml", "authoritative": False},
    {"tag": ["CP1"], "name": "HK DSD — Press Releases", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Press_Releases.xml", "authoritative": False},

    # ---- CP2 River and coastal environment ----
    {"tag": ["CP2"], "name": "HK CEDD — Coastal / reclamation", "kind": "feed",
     "url": "https://www.info.gov.hk/gia/general/202606/12/P2026061200480.htm", "authoritative": True},
    {"tag": ["CP2"], "name": "HK EPD — Highlights", "kind": "feed",
     "url": "https://www.epd.gov.hk/epd/english/rss_feeds/highlights.xml", "authoritative": False},
    {"tag": ["CP2"], "name": "HK EPD — Events and Acts", "kind": "feed",
     "url": "https://www.epd.gov.hk/epd/english/rss_feeds/events_acts.xml", "authoritative": False},
    {"tag": ["CP2"], "name": "HKO — Monthly Weather Summary", "kind": "feed",
     "url": "https://www.weather.gov.hk/en/wxinfo/pastwx/mws/mws.htm", "authoritative": True},
    {"tag": ["CP2", "CP7"], "name": "HKO — Monthly climate reports", "kind": "feed",
     "url": "https://www.weather.gov.hk/en/wxinfo/pastwx/mws2026/mws202608.htm", "authoritative": True},

    # ---- CP3 Industrial location ----
    {"tag": ["CP3"], "name": "RTHK News (English)", "kind": "feed",
     "url": "https://news.rthk.hk/rthk/en/rss.feed", "authoritative": False},
    {"tag": ["CP3"], "name": "SCMP — Business", "kind": "feed",
     "url": "https://www.scmp.com/rss/92/feed", "authoritative": False, "max_items": 30},
    {"tag": ["CP3"], "name": "SCMP — China Economy", "kind": "feed",
     "url": "https://www.scmp.com/rss/318198/feed", "authoritative": False, "max_items": 25},
    {"tag": ["CP3"], "name": "Manufacturing Dive", "kind": "feed",
     "url": "https://www.manufacturingdive.com/feeds/news/", "authoritative": False, "max_items": 20},
    {"tag": ["CP3"], "name": "Hong Kong Free Press", "kind": "feed",
     "url": "https://hongkongfp.com/feed/", "authoritative": False, "max_items": 25},
    {"tag": ["CP3", "CP4"], "name": "HK DSD — DSD Newsletter", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/DSD_Newsletter.xml", "authoritative": False},
    {"tag": ["CP3", "CP4"], "name": "HK DSD — Press Releases", "kind": "feed",
     "url": "https://www.dsd.gov.hk/Menu/EN/RSS/Press_Releases.xml"},

    # ---- CP4 Building a sustainable city ----
    {"tag": ["CP4"], "name": "HK Planning Department — public consultations", "kind": "feed",
     "url": "https://www.info.gov.hk/gia/general/202606/12/P2026061200480.htm", "authoritative": False},
    {"tag": ["CP4"], "name": "HK Gov — News in brief", "kind": "feed",
     "url": "https://www.gov.hk/en/about/rss.htm", "authoritative": False},

    # ---- CP5 Combating famine ----
    {"tag": ["CP5"], "name": "UN News — Food Security", "kind": "feed",
     "url": "https://news.un.org/feed/subscribe/en/news/topic/food-security/feed/rss.xml", "authoritative": True},
    {"tag": ["CP5"], "name": "ReliefWeb — Humanitarian updates", "kind": "feed",
     "url": "https://reliefweb.int/updates/rss.xml", "authoritative": True},
    {"tag": ["CP5", "CP6"], "name": "ScienceDaily — Environment", "kind": "feed",
     "url": "https://www.sciencedaily.com/rss/top/environment.xml", "authoritative": False},

    # ---- CP6 Disappearing green canopy ----
    {"tag": ["CP6"], "name": "Global Forest Watch — Blog", "kind": "feed",
     "url": "https://www.globalforestwatch.org/blog/feed/", "authoritative": True},
    {"tag": ["CP6", "CP7"], "name": "UN News — Climate change", "kind": "feed",
     "url": "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml", "authoritative": True},
    {"tag": ["CP6"], "name": "UNEP — News and stories", "kind": "feed",
     "url": "https://www.unep.org/en/whats-new/news-stories-speeches", "authoritative": True},

    # ---- CP7 Global warming / climate change ----
    {"tag": ["CP7"], "name": "WMO — News", "kind": "feed",
     "url": "https://wmo.int/news", "authoritative": True},
    {"tag": ["CP7"], "name": "UNFCCC — News", "kind": "feed",
     "url": "https://unfccc.int/rss.xml", "authoritative": True},
    {"tag": ["CP7"], "name": "ESA Copernicus — Observing the Earth", "kind": "feed",
     "url": "https://www.esa.int/rssfeed/Our_Activities/Observing_the_Earth", "authoritative": True},
    {"tag": ["CP7"], "name": "NASA Earth Observatory", "kind": "feed",
     "url": "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss", "authoritative": True},
    {"tag": ["CP7"], "name": "ScienceDaily — Climate", "kind": "feed",
     "url": "https://www.sciencedaily.com/rss/earth_climate/climate.xml", "authoritative": False},

    # ---- EP1 Dynamic Earth (HK) ----
    {"tag": ["EP1"], "name": "HK Geological Survey / GeoPark", "kind": "feed",
     "url": "https://www.arqs.hk/en", "authoritative": True, "max_items": 20},
]

# ---------------------------------------------------------------------------
# Keyword tagging — the geography signal for each elective.
# ---------------------------------------------------------------------------

TAGS = {
    "CP1": ["earthquake", "volcano", "volcanic", "eruption", "tsunami", "magnitude",
            "seismic", "plate", "tremor", "lava", "epicentre", "hazard", "landslip",
            "landslide", "fault", "earthquake swarm", "ring of fire"],
    "CP2": ["coast", "coastal", "erosion", "shoreline", "sea level", "reclamation",
            "flood", "typhoon", "storm surge", "wave", "harbour", "estuary",
            "river", "drainage", "sediment", "beach", "mangrove", "wetland",
            "breakwater", "seawall", "dredging"],
    # CP3 terms are deliberately specific. "port" and "plant" appear in too
    # many unrelated stories (port cities, power plants, "plant" as a verb) and
    # produced false positives, so the geography of industry is named directly.
    "CP3": ["industrial", "industry", "manufacturing", "steel", "logistics",
            "agglomeration", "deindustrial", "silicon valley", "supply chain",
            "industrial park", "industrial estate", "foreign direct investment",
            "fdi", "production base", "assembly line", "outsourcing", "offshore",
            "multinational", "transnational", "global production", "factory",
            "high-tech", "high tech", "it hub", "business park",
            "container terminal", "free trade zone", "logistics hub",
            "port city", "port town", "seaport", "deepwater port",
            "shipping port", "transhipment", "shipbuilding"],
    # "population" on its own matched every refugee and displacement report,
    # so the urban sense has to be qualified.
    "CP4": ["urban", "city", "housing", "reclamation", "brownfield",
            "transport", "congestion", "commut", "liveable", "livable", "compact city",
            "public consultation", "master plan", "renewal", "open space", "public housing",
            "land use", "smart city", "urban population", "urbanisation", "urbanization",
            "urban sprawl", "megacity", "city centre", "city center", "gentrification",
            "urban decay", "council housing", "public housing"],
    "CP5": ["famine", "hunger", "food security", "food insecurity", "malnutrition",
            "sahel", "drought", "crop", "agricultur", "irrigation", "harvest", "yield",
            "grain", "wheat", "maize", "fertiliser", "fertilizer", "rural development",
            "land degradation", "desertification", "food price", "locust"],
    "CP6": ["deforestation", "forest", "rainforest", "canopy", "tree cover", "wildfire",
            "peat", "haze", "palm oil", "logging", "reforestation", "biodiversity",
            "amazon", "congo", "illegal logging", "forest fire", "burning"],
    "CP7": ["climate", "warming", "greenhouse", "emission", "carbon", "temperature",
            "sea level rise", "glacier", "ice sheet", "heatwave", "heat wave", "drought",
            "ipcc", "net zero", "decarbon", "energy transition", "renewable", "solar",
            "wind power", "el niño", "coral", "typhoon", "cyclone"],
    "EP1": ["rock", "weathering", "erosion", "mass movement", "landslide", "granite",
            "tuff", "sediment", "metamorphic", "fold", "fault", "quarry", "geopark",
            "geology", "geological", "gorge", "headland", "slope", "soil", "karst",
            "hong kong geopark", "unesco"],
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
            items.append({"title": title, "url": link, "published": pub, "summary": summary})
    return items


# Words that mean "this is a geography topic" rather than "these letters
# appeared somewhere in the text". Without this, a Chernobyl-fallout story
# matches EP1 on the word "soil" and a wind-farm story matches CP2 on "wave".
NEGATIVE_CONTEXT = re.compile(
    r"(?i)\b(chernobyl|fukushima|nuclear|war\b|conflict|election|celebrity|"
    r"football|obituary|stock market|bitcoin|crypto|law\b court|verdict)\b"
)

# A term must appear in the TITLE to count. Summaries are noisy.
TITLE_WEIGHT_ONLY = {
    "CP2": {"coast", "coastal", "erosion", "shoreline", "sea level", "reclamation",
            "flood", "typhoon", "storm surge", "harbour", "estuary", "river",
            "drainage", "sediment", "beach", "mangrove", "wetland", "breakwater",
            "seawall", "dredging"},
    "CP3": {"industrial", "industry", "factory", "manufacturing", "steel", "logistics",
            "port", "investment", "agglomeration", "deindustrial", "silicon valley",
            "supply chain", "industrial park", "foreign direct", "fdi", "production base"},
    "CP4": {"urban", "city", "housing", "population", "brownfield", "transport",
            "congestion", "commut", "liveable", "livable", "compact city",
            "master plan", "renewal", "open space", "public housing", "land use",
            "smart city", "reclamation"},
    "CP6": {"deforestation", "forest", "rainforest", "canopy", "tree cover", "wildfire",
            "peat", "haze", "palm oil", "logging", "reforestation", "biodiversity",
            "amazon", "illegal logging", "forest fire"},
    "CP7": {"climate", "warming", "greenhouse", "emission", "carbon", "temperature",
            "sea level rise", "glacier", "ice sheet", "heatwave", "heat wave",
            "ipcc", "net zero", "decarbon", "energy transition", "renewable", "solar",
            "wind power", "el niño", "coral"},
    "EP1": {"rock", "weathering", "mass movement", "landslide", "granite", "tuff",
            "sediment", "metamorphic", "fold", "fault", "quarry", "geopark",
            "geology", "geological", "gorge", "headland", "karst", "hong kong geopark",
            "unesco", "slope failure"},
    "CP1": {"earthquake", "volcano", "volcanic", "eruption", "tsunami", "magnitude",
            "seismic", "plate boundary", "tremor", "lava", "epicentre", "landslip",
            "landslide", "ring of fire"},
    "CP5": {"famine", "hunger", "food security", "food insecurity", "malnutrition",
            "sahel", "crop failure", "crop yield", "agricultural production",
            "irrigation", "harvest", "grain", "wheat", "maize", "fertiliser",
            "fertilizer", "rural development", "land degradation", "desertification",
            "food price", "locust"},
}


def tag_item(title: str, summary: str) -> list[str]:
    """Tag an item against the electives.

    A term must appear in the TITLE, except for CP2's wave/tide terms and a
    few others that are meaningful enough in a summary to carry the tag.
    """
    t = title.lower()
    s = summary.lower()
    blob = f"{t} {s}"
    if NEGATIVE_CONTEXT.search(blob):
        # Still allow a strong geography title through (e.g. "Earthquake in X")
        if not re.search(r"(?i)(earthquake|volcano|tsunami|cyclone|typhoon|flood|"
                         r"deforest|wildfire|landslide)", t):
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


def hk_score(title: str, summary: str) -> int:
    return 2 if HK_BOOST.search(f"{title} {summary}") else 0


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


def collect() -> tuple[list[dict], list[dict]]:
    seen = set()
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
                    title = pr.get("title") or f"{pr.get('mag')} earthquake"
                    found.append({
                        "title": title,
                        "url": pr.get("url", ""),
                        "published": str(pr.get("time", ""))[:10],
                        "summary": f"{pr.get('place','')} — magnitude {pr.get('mag','')}",
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
                for t in declared:
                    if t not in tags:
                        tags.append(t)
            if not tags:
                continue
            seen.add(key)
            items.append({
                "title": it["title"][:180],
                "url": url,
                "source": feed["name"],
                "published": clean_date(it.get("published", "")),
                "summary": (it.get("summary", "") or "")[:320],
                "topics": tags,
                "hk": bool(HK_BOOST.search(f"{it.get('title','')} {it.get('summary','')}")),
                "id": key[:12],
            })
            added += 1
            if added >= feed.get("max_items", 40):
                break
        report.append({"feed": feed["name"], "url": feed["url"], "ok": True,
                       "error": "", "items": added})
    # Hong Kong first, then newest. The date is a "YYYY-MM-DD" string, so it
    # sorts correctly by itself; negating the year makes the newest land first
    # within each HK / non-HK group.
    items.sort(key=lambda i: (not i["hk"], _neg_date(i["published"])))
    return items, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=300, help="max items to keep")
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
    for i in items:
        by_id.setdefault(i["id"], i)
    merged = list(by_id.values())
    merged.sort(key=lambda i: (not i["hk"], _neg_date(i["published"])))
    merged = merged[: args.keep]

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
    print("\nby elective:", dict(c.most_common()))


def _neg_date(d: str) -> str:
    return "".join(chr(ord("9") - (ord(c) - ord("0"))) if c.isdigit() else c for c in (d or "0000-00-00"))


if __name__ == "__main__":
    main()
