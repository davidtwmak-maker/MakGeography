#!/usr/bin/env python3
"""The News Corner covers every elective and every sub-question it can.

David's News Corner requirement (27 Oct framework, item 1) is news "tagged
for focused viewing" across CP1-CP7 and EP1. Two things went wrong before
this test existed, and both were invisible until the counts were checked:

1. Fourteen of thirty-four feeds had rotted and returned nothing, so whole
   electives were served by a single source - CP5 held 246 of 300 items while
   CP4 held 4 and EP1 held 3.
2. Nothing tagged a story by sub-question, so "focused viewing" meant only
   "filter by elective", and a student who had just learned about landslides
   had to wade through every CP1 story to find one.

So this test asserts:
  - every elective is represented in the live feed, and no elective holds a
    disproportionate share of it;
  - the feed carries sub-topic tags, and the sub-topic codes are real
    curriculum sub-questions;
  - the tagger behaves - it finds the obvious headlines and does not fire on
    the words that used to cause false positives.

No network calls. It reads data/news.json, which the collector writes.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from news_subtopics import SUBTOPIC_TERMS  # noqa: E402
import collect_news as CN  # noqa: E402

ELECTIVES = ["CP1", "CP2", "CP3", "CP4", "CP5", "CP6", "CP7", "EP1"]

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


# ---------------------------------------------------------------- the feed

news_path = ROOT / "data" / "news.json"
if not news_path.exists():
    print("data/news.json is missing - the collector has never run")
    sys.exit(1)

items = json.loads(news_path.read_text(encoding="utf-8"))
check(len(items) >= 150, f"only {len(items)} items in the feed")

by_elective = Counter()
for it in items:
    for t in it.get("topics", []):
        if t in ELECTIVES:
            by_elective[t] += 1

print(f"feed items: {len(items)}")
print("by elective:")
for code in ELECTIVES:
    print(f"  {code}: {by_elective.get(code, 0)}")

# Every elective must be represented. A single-source elective is what
# happened before (CP4 had 4 items, EP1 had 3).
for code in ELECTIVES:
    check(by_elective.get(code, 0) >= 8,
          f"{code} has only {by_elective.get(code, 0)} items - it is effectively "
          f"invisible in the News Corner")

# No elective may hold more than half the feed. Before the balancing, CP5
# held 246 of 300.
total_tagged = sum(by_elective.values())
if total_tagged:
    for code in ELECTIVES:
        share = by_elective.get(code, 0) / total_tagged
        check(share <= 0.40,
              f"{code} holds {share:.0%} of the feed - one elective is crowding "
              f"out the others")

# ------------------------------------------------------------- sub-topics

curriculum = json.loads((ROOT / "data" / "curriculum.json").read_text(encoding="utf-8"))
real_codes = set()
for el in curriculum["electives"]:
    for q in el.get("subquestions") or []:
        real_codes.add(q["id"])

# The map's codes must be real curriculum sub-questions.
for code in SUBTOPIC_TERMS:
    for sub in SUBTOPIC_TERMS[code]:
        check(sub in real_codes,
              f"{sub} is in the tag map but is not a curriculum sub-question")

sub_counter = Counter()
for it in items:
    for s in it.get("subtopics", []):
        check(s in real_codes,
              f"item '{it.get('title','')[:40]}' carries unknown sub-topic {s}")
        sub_counter[s] += 1

tagged_items = sum(1 for it in items if it.get("subtopics"))
print(f"\nsub-topics tagged: {len(sub_counter)}/{len(real_codes)} "
      f"curriculum sub-questions")
print(f"items with a sub-topic tag: {tagged_items}/{len(items)}")
check(tagged_items >= len(items) * 0.4,
      f"only {tagged_items} of {len(items)} items carry a sub-topic tag - "
      f"'focused viewing' is not working")

# The sub-topic codes in the live feed must match the map.
for s in sub_counter:
    check(s in real_codes, f"live feed carries unknown sub-topic {s}")

# ---------------------------------------------------------------- the tagger

def subs(title: str, summary: str = "") -> set[str]:
    return {code for _el, code in CN.subtopic_tags(title, summary)}


POSITIVE = [
    ("Hong Kong government announces new public housing redevelopment scheme",
     "CP4.2"),
    ("Urban renewal authority approves plans for a brownfield site",
     "CP4.5"),
    ("Landslide warning issued after heavy rain on hillside slopes",
     "EP1.4"),
    ("Study reveals how salt weathering hollows out granite in coastal areas",
     "EP1.3"),
    ("Earthquake of magnitude 6.0 strikes near the Solomon Islands",
     "CP1.4"),
    ("Amazon deforestation falls to lowest level on record",
     "CP6.2"),
    ("Drought in the Sahel causes crop failure and food insecurity",
     "CP5.4"),
    ("Global temperatures hit record high as heatwave grips cities",
     "CP7.1"),
    ("Factory relocation to the Pearl River Delta reshapes manufacturing",
     "CP3.2"),
    ("Beach nourishment restores eroded stretch of shoreline",
     "CP2.2"),
]
print("\ntagger positives:")
for title, expected in POSITIVE:
    got = subs(title)
    ok = expected in got
    check(ok, f"'{title[:46]}...' should be tagged {expected}, got {sorted(got)}")
    print(f"  {'ok ' if ok else 'FAIL'} {expected:<7} {title[:60]}")

# The false positives that were found in the live feed.
NEGATIVE = [
    # "brownfield" alone is a US TV programme's name, not urban geography.
    ("Brownfield Ag Weather Today", "CP4.5"),
    # "Indigenous Peoples' Day" is a US holiday, not a forest livelihood.
    ("City of Salem offices closed in observation of Indigenous Peoples' Day",
     "CP6.3"),
    # A word-boundary failure: "port" inside "report".
    ("Annual report on the port authority published", "CP3.1"),
    # A word-boundary failure: "wave" inside "wavelength".
    ("Scientists measure the wavelength of the new instrument", "CP2.2"),
    # Generic press-release noise.
    ("Hong Kong Customs detects drug trafficking case at airport", "CP3.1"),
    ("Liquor Licensing Board to meet on Tuesday", "CP4.4"),
]
print("\ntagger negatives:")
for title, forbidden in NEGATIVE:
    got = subs(title)
    ok = forbidden not in got
    check(ok, f"'{title[:46]}...' must not be tagged {forbidden}, got {sorted(got)}")
    print(f"  {'ok ' if ok else 'FAIL'} not {forbidden:<7} {title[:60]}")

# ---------------------------------------------------------------------------
# CP1 must be TECTONIC. This is the one the teacher reported: the CP1 list
# was full of food-security bulletins and US election stories, and not one
# of them was about earthquakes.
#
# The failures were of two kinds. The politics vocabulary collides with the
# hazard vocabulary ("landslide" in an election, "blue tsunami", "wave"), and
# the sub-topic match PROMOTES an item into the elective - so a bad
# sub-topic match put a market report into the tectonic hazards list.
CP1_NOT_TECTONIC = [
    "The Democratic Party won the U.S. midterm elections by a landslide, "
    "but Southeast Asian countries are worried",
    "Markets rally on back of Democrats' landslide midterm election win",
    "FirstFT: Wall Street sheds $3.2tn as Democratic midterm landslide "
    "upends AI bet",
    "US midterm blue tsunami jolts Asian markets as tighter AI, fiscal "
    "scrutiny looms",
    "The Blue Tsunami - The New York Times",
    "How Democrats’ blue ‘tsunami’ crested in North Carolina",
    "‘An Earthquake’: A Democratic Rout Stuns Texas",
    "There's No Modern Precedent for This Democratic Tsunami",
    "Final polls, models and markets see a \"blue tsunami\"",
    "US voters unleash blue wave, handing Congress to Democrats",
    "Lesotho Food Security Outlook October 2026 - May 2027: Depleted stocks "
    "and below-average harvest to sustain Stressed outcomes",
    "World: Financing the Last Mile: An Investment Case for Early Warnings "
    "for All",
    "The State of Early Warning Around the World (November 2026)",
    "Woman narrowly escapes death as folding table falls from Hong Kong "
    "building",
    "Baidu’s new AI simulator gives robotaxis a crash course in rare road "
    "hazards",
    "Will the US midterm ‘blue tsunami’ erode China’s faith in Trump and "
    "Xi’s relationship?",
]
print("\nCP1 must be tectonic (these must NOT be tagged CP1):")
for title in CP1_NOT_TECTONIC:
    got = CN.tag_item(title, "")
    ok = "CP1" not in got
    check(ok, f"'{title[:46]}...' must not be tagged CP1, got {got}")
    print(f"  {'ok ' if ok else 'FAIL'} not CP1     {title[:58]}")

# And the other way round: the tectonic stories must survive, because a
# filter that drops everything is as broken as one that drops nothing.
CP1_MUST_BE_TECTONIC = [
    "Magnitude 5.9 earthquake strikes off eastern Japan, shakes Tokyo",
    "Magnitude 7 earthquake - 189 km ENE of Nagqu, China",
    "Strong earthquake shakes central Japan, shattering store windows",
    "Powerful earthquake in Tibet's Nagqu area leaves 16 dead",
    "Magnitude 6.1 quake hits off Tokyo, but no tsunami alert issued",
    "Kilauea volcano erupts: See the 660-foot lava fountain",
    "Crystals hint at a volcano's ability to erupt",
    "Seismic imaging reveals double slab tearing at a subduction–collision "
    "transition",
    "Six communities creating a culture of tsunami readiness",
    "Seven innovations that buy time before a tsunami reaches the shore",
    "On World Tsunami Awareness Day, a reminder to be Tsunami Ready",
    "US East Coast could face 'cataclysmic' megatsunami from unstable Spain "
    "volcano, scientist warns",
    "Researchers explore how AI could improve earthquake safety",
    "Scientists discover a hidden 100-million-year-old volcanic system",
    "China’s Xi Jinping orders urgent relief after Tibet earthquake leaves "
    "16 dead",
]
print("\nCP1 must keep the tectonic stories:")
for title in CP1_MUST_BE_TECTONIC:
    got = CN.tag_item(title, "")
    ok = "CP1" in got
    check(ok, f"'{title[:46]}...' must be tagged CP1, got {got}")
    print(f"  {'ok ' if ok else 'FAIL'} CP1       {title[:58]}")

# The physical-hazard test must not depend on the politics filter, because
# "The Blue Tsunami - The New York Times" carries no politics word at all.
print("\nhazard context:")
for title, want in [
    ("Magnitude 5.9 earthquake strikes off eastern Japan", True),
    ("Strong earthquake shakes central Japan", True),
    ("The Blue Tsunami - The New York Times", False),
    ("‘An Earthquake’: A Democratic Rout Stuns Texas", False),
    ("The Democratic Party won the U.S. midterm elections by a landslide",
     False),
]:
    got = CN.is_geography_title(title, "")
    ok = got is want
    check(ok, f"is_geography_title({title[:40]!r}) is {got}, expected {want}")
    print(f"  {'ok ' if ok else 'FAIL'} {str(want):<5} {title[:58]}")

# ---------------------------------------------- the CP1 index must be right
#
# The News Corner names the module by its sub-questions. CP1's sub-questions
# are Earth structure, Internal forces, Tectonic landforms and Tectonic
# hazards - so a student filtering CP1.4 expects earthquakes, volcanoes and
# tsunamis. "Landslide" belongs to EP1 (Hong Kong slope management), and
# "early warning" on a famine bulletin is not hazard management.
cur_cp1 = {q["id"]: q["title"]
           for el in curriculum["electives"] if el["code"] == "CP1"
           for q in el.get("subquestions") or []}
check(set(cur_cp1) == {"CP1.1", "CP1.2", "CP1.3", "CP1.4"},
      f"CP1's sub-questions changed: {sorted(cur_cp1)}")
print("\nCP1 sub-questions:")
for code in sorted(cur_cp1):
    print(f"  {code} {cur_cp1[code]}")

# The live CP1 list must not carry an item whose sub-topic is not a CP1
# sub-question, and it must carry real tectonic stories.
cp1_items = [it for it in items if "CP1" in it.get("topics", [])]
check(len(cp1_items) >= 8,
      f"CP1 has only {len(cp1_items)} items - it is effectively invisible")
tectonic_words = re.compile(
    r"(?i)earthquake|volcan|tsunami|seismic|magnitude|tremor|lava|"
    r"tectonic|epicentre|epicenter|aftershock|eruption|"
    # CP1.1 Earth structure and CP1.2/CP1.3 internal processes are part of
    # the same module, so a story about the Earth's interior or a plate
    # boundary belongs here too.
    r"earth['\u2019]s interior|earth interior|inner core|outer core|"
    r"mantle|crust|asthenosphere|plate boundary|plate movement|"
    r"subduction|slab tear|mantle plume|hot\s?spot|mid-ocean ridge|"
    r"rift zone|island arc|ocean trench|continental drift|magma|"
    r"volcanic system|volcanic system|fossil|rocks?\b.*\bearth|"
    r"earth['\u2019]s structure|geological|geology")
not_tectonic = [it for it in cp1_items
                if not tectonic_words.search(it.get("title", ""))]
check(not not_tectonic,
      "CP1 carries non-tectonic stories: "
      + "; ".join(it["title"][:50] for it in not_tectonic[:4]))
print(f"\nCP1 items: {len(cp1_items)}, "
      f"{len(not_tectonic)} of them not about a tectonic event")

# ------------------------------------------- the feed's dates must be dates
#
# A malformed date sorts to the end of the feed and is then truncated away.
# The USGS feeds publish an epoch in MILLISECONDS, and slicing it to ten
# characters produced "1794267921" - so every real earthquake was silently
# lost while the taggers were blamed for it.
bad_dates = [it for it in items
             if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", it.get("published") or "")]
check(not bad_dates,
      f"{len(bad_dates)} items have an unparseable date, e.g. "
      + ", ".join(repr(it.get("published")) for it in bad_dates[:3]))
check(CN._epoch_to_date(1794267921429) == "2026-11-09",
      f"_epoch_to_date gave {CN._epoch_to_date(1794267921429)!r} for a "
      "millisecond epoch")
check(CN._epoch_to_date("") == "" and CN._epoch_to_date(None) == "",
      "_epoch_to_date must return empty for a missing timestamp")
print(f"\ndates: {len(items) - len(bad_dates)}/{len(items)} are real dates; "
      "the millisecond epoch converts correctly")

# ----------------------------------------- the feed must not go stale
#
# The feed accumulates across runs, so it also accumulates old stories. A
# story from 2023 was still in the feed in 2026. The News Corner is about
# CURRENT events.
stale = []
today = _date(2026, 11, 10)
for it in items:
    d = it.get("published") or ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        continue
    try:
        age = (today - _date(*map(int, d.split("-")))).days
    except ValueError:
        continue
    if age > 60:
        stale.append((d, it["title"][:50]))
check(not stale,
      f"{len(stale)} items are older than 60 days, e.g. {stale[:3]}")
print(f"stale items (>60 days): {len(stale)}")

# ------------------------------------------- the same story must not repeat
#
# A search feed returns one story from several outlets. The publisher
# suffix is stripped from the title, but the dedupe key was computed AFTER
# the punctuation was stripped - so the suffix regex no longer matched and
# three copies of the same market story survived.
dupes = [t for t, n in Counter(it["title"] for it in items).items() if n > 1]
check(not dupes, f"{len(dupes)} titles appear more than once, e.g. {dupes[:2]}")
print(f"duplicate titles: {len(dupes)}")

# ------------------------------------------ a re-tag must clear bad tags
#
# The feed keeps an item by id, so it keeps the tags it was given when it
# was first collected. Fixing the tagger does NOT fix the feed unless every
# item is re-tagged - and that is how the politics stories stayed in the
# CP1 list through every re-collect.
stale_tagged = [
    {"id": "x", "title": "Markets rally on back of Democrats' landslide "
                         "midterm election win",
     "summary": "", "topics": ["CP1"], "subtopics": ["CP1.4"],
     "published": "2026-11-09", "hk": False},
]
retagged = CN.retag_items(stale_tagged)
check(not retagged,
      f"a re-tag kept a politics story: {retagged}")
print(f"re-tag drops a story that no longer matches: {not retagged}")

# ------------------------------------- the sub-topic filter is one elective
#
# The front end sends the sub-topic with the request, and the sub-topic
# belongs to ONE elective. So a filter left over from another elective asks
# for "CP2 AND CP1.4" and shows a fraction of the items.
#
# This checks the rule the front end implements: a sub-topic code is only
# valid under the elective it belongs to.
all_codes = {}
for el in curriculum["electives"]:
    for q in el.get("subquestions") or []:
        all_codes[q["id"]] = el["code"]
check(all_codes.get("CP1.4") == "CP1" and all_codes.get("CP2.2") == "CP2",
      f"the sub-topic ownership changed: {all_codes}")
_front_news = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
assert "d.subtopics" in _front_news, (
    "the news panel does not read the sub-topic list the server sends")
assert "sel.value" in _front_news, (
    "the news panel never clears the sub-topic filter")
# The server sends the WHOLE sub-question list in every reply, so a check
# that only asks "does this code exist" finds a stale CP1.4 filter valid
# under CP2. The check has to ask which ELECTIVE owns the code.
assert "s.elective === t" in _front_news, (
    "the news panel does not check that the sub-topic belongs to the "
    "selected elective - a filter left over from another elective would "
    "silently cut the list")
print(f"\nsub-topic ownership: CP1.4 -> CP1, CP2.2 -> CP2 "
      f"({len(all_codes)} sub-questions)")

# --------------------------------------------------------------- the cap

# The balancing must survive a hostile input: one elective's items cannot
# push another past the cap.
hostile = []
for i in range(200):
    hostile.append({"title": f"famine story {i}", "topics": ["CP5"], "subtopics": []})
for i in range(5):
    hostile.append({"title": f"landslide story {i}", "topics": ["EP1"], "subtopics": []})
kept = CN.balance_by_elective(hostile, keep=100, per_cap=60)
counts = Counter(t for it in kept for t in it.get("topics", []))
check(counts.get("CP5", 0) <= 60,
      f"the per-elective cap broke: CP5 kept {counts.get('CP5', 0)} of 100")
check(counts.get("EP1", 0) >= 1,
      "the balancing dropped the minority elective entirely")
print(f"\ncap check: CP5 kept {counts.get('CP5', 0)}/60, "
      f"EP1 kept {counts.get('EP1', 0)}")

# ------------------------------------------------------------- the result

if failures:
    print(f"\n{len(failures)} FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print("\nNews Corner OK: every elective is represented, sub-topics are tagged, "
      "the tagger holds its precision")
