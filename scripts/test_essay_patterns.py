"""Test the question patterns that shape the generated stem.

The patterns hold the real DSE essay-question shapes per elective. They
were added to stop the generator inventing a stem instead of writing one
in the house form.

Two rules the code has to keep:

1. A pattern is only shown to the model when its command pairing matches
   the one the student chose. A pattern describes how ITS two parts
   relate, so a pattern with a different pairing describes a different
   question - and CP4 alone has four patterns with four different
   pairings.

2. An 8-mark essay is a SINGLE part. No pattern applies to it, because
   every pattern talks about a Part (b) that must not exist. This was a
   real bug: the pattern block was injected unconditionally, so an 8-mark
   prompt asked for a Part (b) it was not going to get.

And the rule that keeps them safe: a pattern gives the SHAPE, never the
wording, and never its own subject matter.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import essay  # noqa: E402
from app import essay_patterns as ep  # noqa: E402

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


def prompt_for(code, marks, cmd_a, cmd_b):
    return essay.build_prompt(
        "NOTES", code, ["Silicon Valley"], marks, cmd_a, cmd_b
    )[1]["content"]


print("1. A pattern is only shown when its pairing matches")
for code, pats in sorted(ep.QUESTION_PATTERNS.items()):
    for pat in pats:
        cmd_a, cmd_b = pat["commands"]
        user = prompt_for(code, 12, cmd_a, cmd_b)
        check(f"{code}: {cmd_a}/{cmd_b} shows [{pat['id']}]",
              f"[{pat['id']}]" in user)

print("2. A pairing with no pattern of its own still gets the house shape")
# CP4 has describe_explain/evaluate, describe_explain/discuss,
# account/discuss, describe_explain/assess. There is no account/evaluate
# pattern for CP4, so the set is offered - but the wrong pattern must not
# be presented as if it were the chosen one.
user = prompt_for("CP4", 12, "account", "evaluate")
check("CP4 account/evaluate still gets patterns",
      "QUESTION PATTERNS" in user)

print("3. An 8-mark essay gets no pattern and no Part (b)")
user8 = prompt_for("CP3", 8, "describe_explain", "discuss")
check("the 8-mark prompt names no Part (b)", "Part (b)" not in user8)
check("the 8-mark prompt has no pattern block",
      "QUESTION PATTERNS" not in user8)
check("the 8-mark prompt has no pattern id",
      "[CP3-P" not in user8)
check("the 8-mark prompt still asks for one part",
      "ONE part" in user8)

print("4. The pattern set is keyed on the pairing")
check("CP3 has one pattern per pairing",
      len(ep.matching_patterns("CP3", "describe_explain", "discuss")) == 1)
check("CP3 account/evaluate picks the other pattern",
      [p["id"] for p in ep.matching_patterns("CP3", "account", "evaluate")]
      == ["CP3-P2"])
check("CP4 describe_explain/assess picks its own",
      [p["id"] for p in ep.matching_patterns(
          "CP4", "describe_explain", "assess")] == ["CP4-P4"])
check("no pairing returns the whole CP4 set by accident",
      len(ep.matching_patterns("CP4", "describe_explain", "discuss")) == 1)

print("5. A single-part essay matches no pattern")
check("matching_patterns returns nothing with no Part (b)",
      ep.matching_patterns("CP3", "describe_explain", "") == [])
check("matching_patterns returns nothing for no Part (b)",
      ep.matching_patterns("CP3", "describe_explain", None) == [])

print("6. A pattern gives the shape, never the wording")
# Every pattern must describe what a part must DO, and must not carry a
# named case study or a subject of its own - otherwise the generator
# reproduces the past paper the pattern was drawn from.
for code, pats in sorted(ep.QUESTION_PATTERNS.items()):
    for pat in pats:
        blob = " ".join(
            str(pat.get(k, "")) for k in
            ("part_a_task", "part_b_task", "shape", "angle_hint")
        ).lower()
        # A named measure is allowed - the prompt says take it from the
        # notes. A named CASE STUDY as the pattern's own subject is not.
        for banned in ("silicon valley", "kwun tong", "amazon rainforest",
                       "hong kong's x", "case study of"):
            check(f"{code} {pat['id']} carries no subject of its own",
                  banned not in blob)

print("7. The pattern block tells the model not to copy the wording")
block = ep.patterns_block("CP3", "describe_explain", "discuss")
check("the block says to write a fresh stem",
      "fresh stem" in block.lower())
check("the block says not to reuse the wording",
      "do not reuse" in block.lower() or "do not reproduce" in block.lower())
check("the block says the pattern carries no subject",
      "does not carry its own subject matter" in block.lower())

print()
if failures:
    print(f"{len(failures)} of {checks} checks FAILED")
    sys.exit(1)
print(f"ALL {checks} CHECKS PASSED")
