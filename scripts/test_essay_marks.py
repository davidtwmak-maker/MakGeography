"""Test that the generator offers only the 12-mark two-part essay.

The exam's short essay is 12 marks in two parts, and that is the only
format the generator offers.

The 8/16/20-mark options are gone. The 8-mark essay is a single part,
so it has no Part (b) and no question pattern applies to it - a
different generator, not a different setting. The 16- and 20-mark
essays were never the exam's short-essay format either.

The rule is enforced in three places, and all three must agree:
  - the server's MARK_OPTIONS, which the API publishes
  - the front end, which builds the marks dropdown from the server
  - the API, which coerces any other mark count to 12
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import essay  # noqa: E402

failures = []
checks = 0


def check(label, ok, detail=""):
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


print("1. The server offers only the 12-mark essay")
check("MARK_OPTIONS is just 12", essay.MARK_OPTIONS == (12,),
      str(essay.MARK_OPTIONS))
check("12 is in MARK_OPTIONS", 12 in essay.MARK_OPTIONS)

print("2. The front end reads the options from the server")
app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
check("the front end reads d.marks", "d.marks" in app_js)
# A hardcoded option list would drift from the server again.
hardcoded = re.findall(
    r'<option value="(\d+)"[^>]*>\d+ marks', app_js)
check("the front end hardcodes no mark options", not hardcoded,
      str(hardcoded))

template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
m = re.search(r'<select id="essayMarks">(.*?)</select>', template, re.S)
check("the template's marks select is present", bool(m))
if m:
    body = m.group(1)
    check("the template names no mark options",
          "option" not in body, body.strip()[:80])

print("3. The API coerces anything else to 12")
main_py = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
check("the API falls back to 12 for an unknown mark count",
      "payload.marks if payload.marks in essay.MARK_OPTIONS else 12"
      in main_py)

print("4. The 12-mark essay is still a two-part essay")
ca, cb, pa, pb = essay.resolve_commands("describe_explain", "discuss", 12)
check("12 marks -> two parts", bool(cb) and pa + pb == 12, f"{pa}+{pb}")
check("12 marks -> 6 and 6", (pa, pb) == (6, 6), f"{pa}+{pb}")

print("5. A two-part essay always has a pattern to follow")
# The pattern block is only offered for a two-part essay, so the
# 12-mark path must reach it.
from app import essay_patterns as ep  # noqa: E402
user = essay.build_prompt(
    "NOTES", "CP3", ["Silicon Valley"], 12, "describe_explain", "discuss"
)[1]["content"]
check("the 12-mark prompt carries a pattern block",
      "QUESTION PATTERNS" in user)
check("the 12-mark prompt names a Part (b)", "Part (b)" in user)
check("a pattern exists for the default pairing",
      len(ep.matching_patterns("CP3", "describe_explain", "discuss")) == 1)

print()
if failures:
    print(f"{len(failures)} of {checks} checks FAILED")
    sys.exit(1)
print(f"ALL {checks} CHECKS PASSED")
