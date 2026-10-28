"""The essay generator must produce a TWO-part question with TWO different
command words.

The bug this guards against: one command word ("Describe and explain")
running across all 12 marks of both parts. That is a single-command question
wearing a 12-mark label, not the DSE format.

Run:  python scripts/test_essay_parts.py
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


# ---------------------------------------------------------------- commands --
print("1. The two command lists are separate and correct")
check("Part (a) has the knowledge commands",
      set(essay.PART_A_COMMANDS) == {"account", "describe_explain", "explain"},
      str(list(essay.PART_A_COMMANDS)))
check("Part (b) has the judgement commands",
      set(essay.PART_B_COMMANDS) == {"discuss", "explain_why", "evaluate", "assess"},
      str(list(essay.PART_B_COMMANDS)))
check("the two lists do not overlap",
      not (set(essay.PART_A_COMMANDS) & set(essay.PART_B_COMMANDS)))
check("every command has a marker to look for",
      all(k in essay.COMMAND_MARKERS for k in
          list(essay.PART_A_COMMANDS) + list(essay.PART_B_COMMANDS)))

# ------------------------------------------------------------------ marks --
print("\n2. Mark allocation")
ca, cb, pa, pb = essay.resolve_commands("describe_explain", "discuss", 12)
check("12 marks -> two parts", bool(cb) and pa + pb == 12, f"{pa}+{pb}")
check("12 marks -> 6 and 6", (pa, pb) == (6, 6), f"{pa}+{pb}")
ca, cb, pa, pb = essay.resolve_commands("account", "evaluate", 20)
check("20 marks -> two parts summing to 20", pa + pb == 20, f"{pa}+{pb}")
check("20 marks -> 10 and 10", (pa, pb) == (10, 10), f"{pa}+{pb}")
ca, cb, pa, pb = essay.resolve_commands("describe_explain", "discuss", 8)
check("8 marks -> one part, no Part (b) command", cb == "" and pa == 8, f"a={ca!r} b={cb!r}")
check("an unknown Part (b) key falls back to the default",
      essay.resolve_commands("describe_explain", "nonsense", 12)[1]
      == essay.PART_B_COMMANDS[essay.DEFAULT_COMMAND_B])
check("an unknown Part (a) key falls back to the default",
      essay.resolve_commands("nonsense", "discuss", 12)[0]
      == essay.PART_A_COMMANDS[essay.DEFAULT_COMMAND_A])

# ----------------------------------------------------------------- prompt --
print("\n3. The prompt asks for two different command words")
msgs = essay.build_prompt(
    "NOTES", "CP3", ["Silicon Valley"], 12,
    "describe_explain", "discuss",
)
user = msgs[1]["content"]
check("the prompt names the Part (a) command", "Describe and explain" in user)
check("the prompt names the Part (b) command", "Discuss whether" in user)
check("the prompt says the two parts are separate",
      "TWO parts" in user)
check("the prompt gives the Part (a) band ladder", "Part (a) performance bands" in user)
check("the prompt gives the Part (b) band ladder", "Part (b) performance bands" in user)
check("the prompt asks for a separate mark-scheme section per part",
      "Part (a) - Relevant concepts" in user and "Part (b) - Relevant concepts" in user)
system = msgs[0]["content"]
check("the system prompt forbids one command word across both halves",
      "must not share one" in system or "do NOT let one command word run" in system)

msgs8 = essay.build_prompt("NOTES", "CP3", ["Silicon Valley"], 8,
                            "describe_explain", "discuss")
user8 = msgs8[1]["content"]
check("an 8-mark prompt does not ask for a Part (b)", "Part (b)" not in user8)

# ------------------------------------------------------- the structure check --
print("\n4. The validator catches one command word running across both parts")

GOOD = """QUESTION
Describe and explain the locational factors of the IT industry in Silicon Valley.
Discuss whether the clustering of high-tech firms can maintain its advantage in the long run. [12]

MARK SCHEME
Notes to Markers
Judge the depth of the argument rather than the number of points named.

Part (a) - Relevant concepts
- The concentration of universities and research institutes supplies a skilled labour pool, and proximity lets firms share that labour.
- Venture capital clustered locally because investors need to monitor risk closely, which requires physical proximity to start-ups.

Part (a) - Performance bands
Top band: 6
Middle: 3-5
Low: 1-2

Part (b) - Relevant concepts
- Rising land and labour costs in Silicon Valley push firms to relocate, which is a real threat to the cluster.
- Agglomeration economies keep firms close, so the cluster is more durable than cost data alone suggests.

Part (b) - Performance bands
Top band: 6
Middle: 3-5
Low: 1-2

EXEMPLAR ANSWER
The locational factors of the IT industry in Silicon Valley begin with the concentration of research institutions. Universities such as Stanford supplied a skilled labour pool, and firms could recruit from a concentrated local market, which reduced the cost of finding suitable workers compared with a dispersed industry. Proximity also mattered for venture capital. Investors needed to monitor risky start-ups closely, and physical closeness to founders made that monitoring cheaper and faster than long-distance oversight, so capital concentrated in the valley. This locational pattern therefore reflected the interaction of skilled labour supply and capital availability rather than any single factor.

Whether the cluster can maintain its advantage in the long run depends on which forces dominate. Rising land prices and wage costs in the valley push firms to move to lower-cost locations, and several large firms have indeed moved headquarters away. Against this, the advantages of agglomeration are cumulative. Firms that stay gain access to the same labour pool and investor networks that made the cluster attractive in the first place, and moving away means rebuilding both. On balance the cluster is likely to retain its core advantages for some time, although the trend of relocation shows the cost pressure is real and will not disappear.
"""

BAD_SINGLE_COMMAND = GOOD.replace(
    "Discuss whether the clustering of high-tech firms can maintain its advantage in the long run.",
    "Describe and explain the clustering of high-tech firms in maintaining its advantage.",
)

BAD_NO_SECOND = GOOD.replace(
    "Discuss whether the clustering of high-tech firms can maintain its advantage in the long run.",
    "Describe and explain the clustering of high-tech firms in the valley.",
)

check("a correct two-part question passes",
      essay.check_two_parts(GOOD, "describe_explain", "discuss", 12) is None,
      str(essay.check_two_parts(GOOD, "describe_explain", "discuss", 12)))
why = essay.check_two_parts(BAD_SINGLE_COMMAND, "describe_explain", "discuss", 12)
check("the same command word in both halves is rejected", why is not None, str(why))
check("the rejection names the shared command word",
      why is not None and "Describe and explain" in why)
why2 = essay.check_two_parts(BAD_NO_SECOND, "describe_explain", "discuss", 12)
check("a stem with no Part (b) command is rejected", why2 is not None, str(why2))
check("a single-part 8-mark essay is not split-checked",
      essay.check_two_parts(BAD_SINGLE_COMMAND, "describe_explain", "discuss", 8) is None)
why3 = essay.check_two_parts(GOOD, "account", "discuss", 12)
check("a stem that ignores the Part (a) command is rejected", why3 is not None, str(why3))
why4 = essay.check_two_parts(GOOD.replace("Part (b) - Relevant concepts",
                                          "Something else - Relevant concepts"),
                              "describe_explain", "discuss", 12)
check("a mark scheme with no Part (b) section is rejected", why4 is not None, str(why4))

# ------------------------------------------------------------- the old API --
print("\n5. The old single-command API is gone")
check("COMMAND_PAIRS no longer exists", not hasattr(essay, "COMMAND_PAIRS"))
import inspect
sig = inspect.signature(essay.generate)
check("generate() takes command_a and command_b",
      "command_a" in sig.parameters and "command_b" in sig.parameters,
      str(list(sig.parameters)))
check("generate() no longer takes a single 'command'",
      "command" not in sig.parameters)

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED:")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL ESSAY-PART CHECKS PASSED")
