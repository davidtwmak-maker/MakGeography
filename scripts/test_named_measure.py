"""The Part (b) stem must name a MEASURE, not a case study.

The real DSE papers judge a policy or strategy:
  2020 Q7  "Discuss whether REDEVELOPMENT is the most appropriate urban
             renewal strategy in these areas."
  2023 Q6  "Discuss whether the CHANNELISATION implemented in recent years
             can manage the river environment in a sustainable way."

A stem that names the case ("the Kwun Tong redevelopment scheme") asks the
wrong question - the student judges one scheme instead of the measure, and
the alternatives never come into it.

Run:  python scripts/test_named_measure.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app.essay as essay

FAIL = []


def check(label, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  {mark} {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        FAIL.append(label)


def wrap(stem, scheme_body="x", answer="y"):
    return f"""QUESTION
{stem} [12]

MARK SCHEME
Notes to Markers
{scheme_body}

Part (a) - Relevant concepts
- a concept

Part (a) - Performance bands
Top: 6

Part (b) - Relevant concepts
- a concept

Part (b) - Performance bands
Top: 6

EXEMPLAR ANSWER
{answer}
"""


print("1. The real papers' wordings pass")
REAL = [
    "Account for the decay of the old urban areas in Hong Kong. "
    "Discuss whether redevelopment is the most appropriate urban renewal "
    "strategy in these areas.",
    "Account for the physical conditions favouring deposition at the lower "
    "course of a river. Discuss whether the channelisation implemented in "
    "recent years can manage the river environment in Hong Kong in a "
    "sustainable way.",
    "Describe and explain the changes brought about by different commercial "
    "agricultural activities on the vegetation characteristics of tropical "
    "rainforests. Discuss whether the development of agroforestry can make "
    "use of the developed tropical rainforests in a sustainable way.",
    "Describe and explain the adverse impact brought about by climate change "
    "on the hydrosphere. Discuss whether advanced technology is effective in "
    "alleviating the adverse impact brought about by climate change on the "
    "hydrosphere.",
    "Describe and explain the locational factors of the IT industry in "
    "Silicon Valley. Discuss whether the clustering of high-tech firms can "
    "maintain its advantage in the long run.",
]
for stem in REAL:
    why = essay.check_named_measure(wrap(stem))
    check(f"passes: {stem[60:100].strip()[:44]}...", why is None, str(why))

print("\n2. A case study in the stem is rejected")
BAD = [
    ("the Kwun Tong redevelopment scheme",
     "Discuss whether the Kwun Tong redevelopment scheme is the most "
     "appropriate approach to urban renewal."),
    ("a named new town",
     "Discuss whether the Sha Tin new town is the most effective way to "
     "increase the land supply."),
    ("a named district",
     "Discuss whether the Kowloon City redevelopment is the most appropriate "
     "urban renewal strategy in these areas."),
    ("a named scheme",
     "Discuss whether the Kai Tak development scheme is the most effective "
     "way to relieve the land shortage."),
]
for label, stem in BAD:
    why = essay.check_named_measure(wrap(stem))
    check(f"rejected: {label}", why is not None, str(why))
    check(f"  ...and the message says MEASURE",
          why is not None and "MEASURE" in why)

print("\n3. A place used as a setting is NOT rejected")
SETTING = [
    "Discuss whether redevelopment is the most appropriate urban renewal "
    "strategy in these areas.",
    "Discuss whether the channelisation can manage the river environment in "
    "Hong Kong in a sustainable way.",
    "Discuss whether zoning is the most appropriate planning strategy in "
    "Hong Kong.",
    "Discuss whether underground space development is the most effective way "
    "to increase the land supply in Hong Kong.",
]
for stem in SETTING:
    why = essay.check_named_measure(wrap(stem))
    check(f"passes: {stem[:52]}...", why is None, str(why))

print("\n4. A stem that is not a judgement question is not policed")
NOT_JUDGE = [
    "Account for the decay of the old urban areas in Hong Kong. "
    "Explain how redevelopment may solve the urban problems in these areas.",
    "Describe and explain the changes in the vegetation characteristics of "
    "tropical rainforests. Explain why commercial agriculture has caused "
    "these changes.",
]
for stem in NOT_JUDGE:
    why = essay.check_named_measure(wrap(stem))
    check(f"not policed: {stem[70:112].strip()[:40]}", why is None, str(why))

print("\n5. The function is wired into generate()")
import inspect
src = inspect.getsource(essay.generate)
check("generate() calls check_named_measure",
      "check_named_measure" in src)
check("the check runs after check_two_parts",
      src.index("check_two_parts") < src.index("check_named_measure"))

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED:")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL NAMED-MEASURE CHECKS PASSED")
