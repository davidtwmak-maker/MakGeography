"""Real HKDSE essay-question shapes, per elective.

The essay generator used to invent a question stem from the notes alone.
That works, but the stems it produced were sometimes not the shape the
exam uses: a real DSE short essay pairs a knowledge-and-mechanism Part
(a) with a judgement Part (b) about a NAMED measure, and the two parts
sit in a specific relationship to each other.

This file holds the question shapes the generator draws on. Each entry
records the command pairing and what each part must ACCOMPLISH, so the
generator can write a stem in the house form instead of inventing one.

IMPORTANT - two rules this file exists to enforce:

1. A shape is not a question. Nothing here reproduces a past paper's
   wording, mark scheme or answer key. The fields say what a part must
   DO, never what it should SAY, so a shape cannot be copied into a stem.

2. A shape does not carry its own subject matter. The subject comes from
   the notes and the sub-topic the student picked; the shape only says
   how the two parts relate. This matters: when a shape also named the
   topic (as an earlier draft did), the generator produced stems that
   read like the past paper the shape was drawn from.

The shapes were compiled from the teacher's own Question Collection
notes, which record the essay questions in each pack together with the
transferable structure of each.
"""

from __future__ import annotations

# The command pairing each shape uses, as (part_a, part_b) keys matching
# essay.PART_A_COMMANDS / essay.PART_B_COMMANDS.
#
# "describe_explain" / "account" -> knowledge and mechanism
# "discuss" / "evaluate" / "assess" -> judgement

QUESTION_PATTERNS: dict[str, list[dict]] = {
    "CP3": [
        {
            "id": "CP3-P1",
            "commands": ("describe_explain", "discuss"),
            "part_a_task": "build the causal chain behind a location "
                           "decision - each factor linked to the next, not "
                           "listed beside each other",
            "part_b_task": "judge ONE NAMED measure taken from the notes "
                           "against the alternatives available in the same "
                           "set, and reach a verdict",
            "shape": "Part (a) accounts for WHY an industry locates where it "
                     "does. Part (b) judges whether a named measure would "
                     "attract or retain that industry.",
            "example_year": "teacher's CP3 pack",
        },
        {
            "id": "CP3-P2",
            "commands": ("account", "evaluate"),
            "part_a_task": "account for a pattern of decline, tying each "
                           "cause back to the mechanism behind it",
            "part_b_task": "evaluate ONE NAMED policy or plan from the notes "
                           "as the way of reversing that pattern",
            "shape": "Part (a) accounts for a pattern of decline. Part (b) "
                     "evaluates whether a named policy reverses it.",
            "example_year": "teacher's CP3 pack",
        },
    ],
    "CP4": [
        {
            "id": "CP4-P1",
            "commands": ("describe_explain", "evaluate"),
            "part_a_task": "build a causal chain from a population or "
                           "economic movement to the competing land uses it "
                           "creates, with Hong Kong evidence",
            "part_b_task": "evaluate whether ONE NAMED land-supply or "
                           "renewal measure, taken from the notes, can "
                           "resolve that competition",
            "shape": "Part (a) explains a phenomenon with Hong Kong "
                     "evidence. Part (b) evaluates whether the named "
                     "measure solves it.",
            "angle_hint": "Name ONE specific place and ONE specific "
                          "conflict in the stem, not the issue in general.",
            "example_year": "2014 DSE Q5",
        },
        {
            "id": "CP4-P2",
            "commands": ("describe_explain", "discuss"),
            "part_a_task": "account for why housing in Hong Kong has become "
                           "hard to afford or hard to live in - the supply "
                           "and quality mechanisms, not the symptoms",
            "part_b_task": "discuss whether ONE NAMED measure for adding or "
                           "renewing housing is the most appropriate, "
                           "weighing it against the alternatives",
            "shape": "Part (a) describes and explains the problem. Part (b) "
                     "judges the named solution against the alternatives.",
            "angle_hint": "Choose which mechanism to lead on - household "
                          "size against unit size, the ageing of the stock, "
                          "the cost of land. Lead on ONE, and let Part (b) "
                          "judge the measure against that same mechanism.",
            "example_year": "2016 DSE Q6",
        },
        {
            "id": "CP4-P3",
            "commands": ("account", "discuss"),
            "part_a_task": "account for why a built-up area has declined, "
                           "naming the mechanism behind each driver",
            "part_b_task": "discuss whether ONE NAMED renewal strategy from "
                           "the notes is the most appropriate response",
            "shape": "Part (a) accounts for the decline. Part (b) judges "
                     "whether the named strategy is the most appropriate.",
            "angle_hint": "Name a specific area and a specific driver. Do "
                          "not open on the issue in general.",
            "example_year": "2020 DSE Q7",
        },
        {
            "id": "CP4-P4",
            "commands": ("describe_explain", "assess"),
            "part_a_task": "show how the three pillars of sustainable "
                           "development have been applied to a named Hong "
                           "Kong renewal project",
            "part_b_task": "assess the difficulty the government faces in "
                           "adopting those ideas",
            "shape": "Part (a) describes and explains the application. Part "
                     "(b) assesses the difficulty of implementing it.",
            "angle_hint": "Choose one pillar and one renewal project to "
                          "open on. Do not open on sustainable development in "
                          "general.",
            "example_year": "2012 Practice Paper Q1",
        },
    ],
    "CP5": [
        {
            "id": "CP5-P1",
            "commands": ("describe_explain", "discuss"),
            "part_a_task": "separate the physical trigger from the human "
                           "root causes in a named case, and show how the "
                           "two interact",
            "part_b_task": "discuss whether ONE NAMED intervention from the "
                           "notes combats that famine, against the "
                           "alternatives",
            "shape": "Part (a) explains why famine occurs there. Part (b) "
                     "judges whether the named measure combats it.",
            "example_year": "teacher's CP5 pack",
        },
        {
            "id": "CP5-P2",
            "commands": ("account", "evaluate"),
            "part_a_task": "account for an uneven pattern of agricultural "
                           "production or consumption, through physical and "
                           "human factors together",
            "part_b_task": "evaluate ONE NAMED farming measure from the "
                           "notes as the way of narrowing that gap",
            "shape": "Part (a) accounts for the pattern. Part (b) evaluates "
                     "whether sustainable practice can close the gap.",
            "example_year": "teacher's CP5 pack",
        },
    ],
    "CP6": [
        {
            "id": "CP6-P1",
            "commands": ("describe_explain", "discuss"),
            "part_a_task": "compare a pattern of clearance in two named "
                           "regions and account for why the drivers differ",
            "part_b_task": "discuss whether ONE NAMED management measure "
                           "from the notes is the most effective response",
            "shape": "Part (a) explains the pattern with mechanisms. Part "
                     "(b) judges the named measure against the alternatives.",
            "example_year": "teacher's CP6 pack",
        },
        {
            "id": "CP6-P2",
            "commands": ("account", "evaluate"),
            "part_a_task": "account for the knock-on effects of forest "
                           "clearance on one named system and one named "
                           "community, linking each to the change that "
                           "caused it",
            "part_b_task": "evaluate ONE NAMED restoration measure from the "
                           "notes against the alternatives",
            "shape": "Part (a) accounts for the impacts. Part (b) evaluates "
                     "whether the measure actually addresses them.",
            "example_year": "teacher's CP6 pack",
        },
    ],
    "CP7": [
        {
            "id": "CP7-P1",
            "commands": ("describe_explain", "discuss"),
            "part_a_task": "explain the mechanism behind recent warming and "
                           "weigh the evidence for it, naming how each line "
                           "of evidence is gathered",
            "part_b_task": "discuss whether ONE NAMED international "
                           "agreement from the notes is an effective "
                           "response",
            "shape": "Part (a) explains the mechanism and the evidence. Part "
                     "(b) judges whether the named agreement works.",
            "example_year": "teacher's CP7 pack",
        },
        {
            "id": "CP7-P2",
            "commands": ("account", "evaluate"),
            "part_a_task": "account for the physical and social impacts of "
                           "warming in one named region, keeping the two "
                           "registers distinct",
            "part_b_task": "evaluate ONE NAMED adaptation measure from the "
                           "notes against the alternatives",
            "shape": "Part (a) accounts for the impacts. Part (b) evaluates "
                     "the named adaptation against mitigation.",
            "example_year": "teacher's CP7 pack",
        },
    ],
}

# The house rule for a DSE short essay, stated once so the prompt can
# point at it instead of restating it in three places.
ESSAY_SHAPE_RULE = (
    "A DSE short essay is TWO parts. Part (a) is written for knowledge and "
    "mechanism - it accounts for a phenomenon and carries the causal "
    "chain. Part (b) is written for judgement - it weighs a NAMED measure "
    "(a policy, strategy, mode or technique) against the alternatives in "
    "the same set and reaches a verdict. The two parts must sit in a "
    "stated relationship to each other; a Part (b) that does not answer "
    "the Part (a) question is not a DSE essay."
)


def patterns_for(code: str) -> list[dict]:
    """The question shapes for one elective."""
    return QUESTION_PATTERNS.get((code or "").upper(), [])


def matching_patterns(code: str, cmd_a: str | None, cmd_b: str | None) -> list[dict]:
    """The patterns whose command pairing matches the one chosen.

    A pattern says how the two parts relate, and that relationship is
    tied to its command pairing - "describe_explain" into "discuss" is a
    different shape from "account" into "evaluate". So a pattern whose
    pairing is not the one the student chose describes a different
    question, and putting it in front of the model invites it to write
    the wrong question.

    When the student chose the default pairing, every pattern for the
    elective is fair game: the defaults are the commonest pairings, and
    the model is told to pick one.

    A single-part essay (8 marks) has no Part (b), so no pattern
    applies - the caller must not ask for one.
    """
    if not cmd_b:
        return []
    pats = patterns_for(code)
    if not pats:
        return []
    exact = [p for p in pats
              if tuple(p.get("commands", ())) == (cmd_a, cmd_b)]
    if exact:
        return exact
    # The student chose a pairing that has no recorded pattern. Fall back
    # to the whole set: the pattern still carries the house shape, and
    # the prompt names the pairing the student asked for.
    return pats


def pattern_block(code: str, pattern: dict) -> str:
    """One pattern, rendered for the prompt."""
    cmd_a, cmd_b = pattern.get("commands", ("describe_explain", "discuss"))
    lines = [
        f"[{pattern.get('id', '')}]",
        f"Command pairing: Part (a) {cmd_a} / Part (b) {cmd_b}.",
        f"What Part (a) must accomplish: {pattern.get('part_a_task', '')}.",
        f"What Part (b) must accomplish: {pattern.get('part_b_task', '')}.",
        f"Relationship between the parts: {pattern.get('shape', '')}.",
    ]
    hint = pattern.get("angle_hint")
    if hint:
        lines.append(f"Angle to open on: {hint}")
    year = pattern.get("example_year")
    if year:
        lines.append(
            f"This pattern follows the shape of a real exam question ({year}). "
            "Write a FRESH stem on the sub-topic chosen - do not reproduce "
            "that question's wording, subject or measure, and do not "
            "reproduce any mark scheme or answer key."
        )
    return "\n".join(lines)


def patterns_block(code: str, cmd_a: str | None = None,
                   cmd_b: str | None = None) -> str:
    """The patterns for one elective, rendered for the prompt.

    Only the patterns matching the chosen command pairing are rendered,
    so the model is never shown a shape that describes a different
    question. With no cmd_b - an 8-mark single-part essay - there is no
    pattern to follow and this returns nothing.
    """
    if cmd_b is None:
        pats = patterns_for(code)
    else:
        pats = matching_patterns(code, cmd_a, cmd_b)
    if not pats:
        return ""
    body = "\n\n".join(pattern_block(code, p) for p in pats)
    return (
        "QUESTION PATTERNS TO FOLLOW\n"
        "These are the shapes real DSE essay questions take for this "
        "elective. Pick ONE and follow its structure.\n"
        "\n"
        "A pattern says what each part must ACCOMPLISH, not what it should "
        "SAY, and it does not carry its own subject matter. Take the "
        "SUBJECT, the PLACE and the NAMED MEASURE from the reference notes "
        "and the chosen sub-topic - the pattern only tells you how the two "
        "parts relate. Write a fresh stem: do not reuse a pattern's "
        "wording, and do not write a stem that could be mistaken for a "
        "past paper's question. Never reproduce an exam paper's wording, "
        "mark scheme or answer key.\n\n"
        + body
    )
