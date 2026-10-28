"""No MC question may point at a figure that does not exist.

The bank builder's prompt once told the model to make the stem
self-contained by describing a diagram - and gave the example
"Figure 1 shows a cross-section of ...". The model followed the example
literally, so the stem said "Figure 1 shows ..." while no figure was ever
created. The student hunted for a picture that was not there.

The rule:
  - a stem that names a figure NUMBER must have an image attached;
  - a stem that names a table or graph must carry the data in the stem;
  - every other stem is fine, because "A cross-section of rock layers..."
    describes the visual in words and is answerable as it stands.

Run:  python scripts/test_no_dangling_figures.py
"""
import json
import pathlib
import re
import sys

BANK = pathlib.Path(__file__).resolve().parent.parent / "data" / "mc_bank.json"

FAIL = []


def check(label, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  {mark} {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        FAIL.append(label)


questions = json.loads(BANK.read_text(encoding="utf-8"))["questions"]
print(f"bank: {len(questions)} questions")

# 1. A stem naming a figure number must have an image.
#
# The official HKEAA questions carry their image in "stem_image" (the exam
# page as it was printed); the hand-checked ones use "question_image".
# Either counts.
names_a_number = re.compile(
    r"\b(?:figure|fig\.?|photograph|photo|image|diagram|map|table|graph)\s*\d+\b",
    re.I,
)
offenders = [
    q for q in questions
    if not q.get("question_image")
    and not q.get("stem_image")
    and names_a_number.search(q.get("stem") or "")
]
check("no stem names a figure number without an image",
      not offenders,
      f"{len(offenders)} offenders: "
      + ", ".join(q.get("id") for q in offenders[:5]))

# 2. A stem naming a table or graph must carry its own data.
names_a_table = re.compile(
    r"\b(?:the table|the graph|a graph of|the table below)\b", re.I
)
no_data = [
    q for q in questions
    if names_a_table.search(q.get("stem") or "")
    and not any(ch.isdigit() for ch in (q.get("stem") or ""))
]
check("no stem names a table or graph without giving the data",
      not no_data,
      f"{len(no_data)} offenders: "
      + ", ".join(q.get("id") for q in no_data[:5]))

# 3. The official items DO have their image.
official = [q for q in questions if q.get("official")]
check(f"all {len(official)} official questions carry an image",
      all(q.get("question_image") or q.get("stem_image") for q in official),
      f"{sum(1 for q in official if not (q.get('question_image') or q.get('stem_image')))} missing")

# 4. The image file actually exists on disk.
missing_files = []
for q in questions:
    for img in (q.get("question_image"), q.get("stem_image")):
        if not img:
            continue
        f = (BANK.parent / img) if q.get("question_image") else (
            BANK.parent / "hkeaa_oqb" / img)
        if not f.is_file():
            missing_files.append(f"{q.get('id')}:{img}")
check("every referenced image file exists on disk",
      not missing_files,
      f"{len(missing_files)} missing: " + ", ".join(missing_files[:5]))

# 5. The bank is intact - nothing was lost by the repair.
check("the bank still holds its questions", len(questions) >= 264,
      f"{len(questions)}")

# 6. Every stem is non-empty and every question has a key.
check("no blank stems", not [q for q in questions if not (q.get("stem") or "").strip()])
check("every question has an answer key",
      all((q.get("answer") or "").strip() for q in questions))
check("every question has 4 options",
      all(len(q.get("options") or []) == 4 for q in questions))

# 7. The repaired questions still read as English - no doubled articles.
doubled = [
    q.get("id") for q in questions
    if re.search(r"\b(A A|An An|The The|A An|An A)\b", q.get("stem") or "")
]
check("no doubled articles in any stem", not doubled, ", ".join(doubled[:5]))

# 8. The known-repaired question reads correctly.
shing = [q for q in questions if q.get("id") == "CP2.1.1-2d5ed413"]
if shing:
    s = shing[0].get("stem") or ""
    check("the Shing Mun question no longer names a figure",
          "Figure" not in s, s[:80])
    check("the Shing Mun question still describes the river",
          "Shing Mun River" in s and "long-profile" in s)
else:
    check("the Shing Mun question exists", False)

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED:")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL NO-DANGLING-FIGURE CHECKS PASSED")
