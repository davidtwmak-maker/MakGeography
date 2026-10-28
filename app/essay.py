"""The Essay Generator.

A student picks an elective (CP1–CP7, EP1), a sub-topic or a set of them,
and the number of marks. The generator then:

1. Collects the note content for those sub-topics from the curriculum
   scaffolding - the same material the Notes section shows.
2. Asks the LLM to write an exam-style essay on that material, with a
   question stem, a mark scheme and an exemplar answer.

The scope is deliberately CP1–CP7 and EP1 only. F2 and F3 are a different
course with a different syllabus, and a practice essay that mixes the two
would teach the wrong content. The generator therefore refuses an F2/F3
topic rather than quietly drawing on those notes.

Everything the essay says comes from the notes. The generator does not
have its own facts.
"""
from __future__ import annotations

import json
import re

from . import llm

# The electives the generator covers. F2 and F3 are excluded on purpose.
ESSAY_ELECTIVES = ("CP1", "CP2", "CP3", "CP4", "CP5", "CP6", "CP7", "EP1")
EXCLUDED_ELECTIVES = ("F2", "F3")

# The DSE short essay is 12 marks: two paired-command parts of 6 marks
# each. The two-part split is the format the exam actually uses, so the
# generator offers it as the default.
MARK_OPTIONS = (12, 8, 16, 20)

# Requests per browser per minute. An essay is a long generation, so the
# limit is tighter than the chatbot's.
ESSAY_RATE_LIMIT = 4

# The exam's paired command words.
#
# A DSE short essay is TWO parts with DIFFERENT command words. The first
# part is written for knowledge and mechanism; the second is written for
# explanation and judgement on a named measure. The command word is not
# interchangeable across the two halves, and one command word running
# across both parts is a single-command question wearing a 12-mark label -
# not the exam format.
#
# So the command choice is split: the student sets each part separately.
PART_A_COMMANDS = {
    "account": "Account for",
    "describe_explain": "Describe and explain",
    "explain": "Explain",
}

PART_B_COMMANDS = {
    "discuss": "Discuss whether",
    "explain_why": "Explain why",
    "evaluate": "Evaluate",
    "assess": "Assess",
}

# What to look for in the question stem for each command. The full phrase
# is the usual form; the fallbacks cover the ways a model paraphrases it.
COMMAND_MARKERS = {
    "account": ("account for", "accounts for"),
    "describe_explain": ("describe and explain", "describe & explain"),
    "explain": ("explain",),
    "discuss": ("discuss whether", "discuss"),
    "explain_why": ("explain why", "explain how"),
    "evaluate": ("evaluate",),
    "assess": ("assess",),
}

# The default pairing - the one that matches the most recent real papers.
DEFAULT_COMMAND_A = "describe_explain"
DEFAULT_COMMAND_B = "discuss"

# A command word does not have to appear as one contiguous phrase. "Describe
# and explain" and "Describe the pattern and explain the process" are the
# same command word, so the part check also accepts a half that carries
# every verb of the command word, in any order.
COMMAND_VERBS = {
    "describe_explain": ("describe", "explain"),
    "explain_why": ("explain",),
    "account": ("account",),
    "explain": ("explain",),
    "discuss": ("discuss",),
    "evaluate": ("evaluate",),
    "assess": ("assess",),
}


def _band_text(part_marks: int) -> str:
    """The band ladder for a part worth `part_marks` marks.

    For the 6-mark part of a 12-mark essay this gives the house form:
    top 6 | middle 3-5 | low 1-2.
    """
    low = max(1, part_marks // 3)
    return f"top {part_marks} | middle {low + 1}-{part_marks - 1} | low 1-{low}"

SYSTEM_PROMPT = """\
You are an HKDSE Geography examiner writing practice material for Form 6 \
students in Hong Kong. You write from the REFERENCE NOTES below and nothing \
else.

THE TWO-PART FORMAT - READ THIS FIRST

A DSE short essay is never a single command word running across the whole \
question. It is TWO parts, and EACH PART CARRIES ITS OWN COMMAND WORD. The \
command word sets what each part is rewarded for, so the two parts must not \
share one:

- Part (a) is written for KNOWLEDGE AND MECHANISM. It earns marks for \
describing a pattern, accounting for causes, or explaining a process - and \
the relevant concepts must carry the mechanism, not a list of facts.
- Part (b) is written for EXPLANATION AND JUDGEMENT. It earns marks for \
weighing a named measure or mode against the alternatives and reaching a \
judgement.

The command word for each part is given in the user message. Use the Part (a) \
command word in the first half of the question stem and the Part (b) command \
word in the second half. The two halves must each open with their own command \
word, in the order given. Do NOT merge them into one instruction, and do NOT \
let one command word run across both halves.

THE OUTPUT STRUCTURE

- A QUESTION STEM that names the place or case, then carries BOTH command \
words in order, ending with the mark allocation in square brackets, e.g. \
"... [12]". Write the stem as two sentences, one per part, each opening with \
its own command word.
- A MARK SCHEME, structured as:
    * "Notes to Markers" - a short paragraph on what is being rewarded and \
how quality is judged (judge quality and depth, not point-counting; credit \
any relevant reasonable answer the scheme does not list).
    * A separate section for EACH part. Each part section carries:
        - "Part (a) - Relevant concepts" (or "(b)"), as BULLETS - one bullet \
per concept, each carrying its mechanism, never prose, never a paragraph.
        - "Performance bands" for THAT PART, high to low, scaled to that \
part's own mark allocation.
    * The two parts' bands must sum to the question's total.
- AN EXEMPLAR ANSWER, written the way a strong student would write it in the \
time allowed: linked cause and effect, named evidence, syllabus terminology, \
and a judgement where the Part (b) command asks for one. The exemplar \
answers Part (a) and Part (b) in the same order as the stem.

Rules:
1. Use ONLY the facts, case studies and figures in the REFERENCE NOTES. If \
the notes do not cover something, leave it out. Never add a case study, \
date, statistic or mechanism that is not there.
2. Do NOT invent a figure, graph or table. The mark scheme and exemplar \
answer work from the text alone.
3. Every concept in the mark scheme must be supportable from the notes, and \
the exemplar answer must demonstrate every concept you list.
4. A "relative importance" or "discuss whether" command needs BOTH sides: \
raise the other factors with their mechanisms, AND judge the named factor \
against them. A one-sided answer caps into the middle band - write that cap \
into the band text.
5. A "justify" command is one-directional: the scheme scores only arguments \
FOR the stated choice. Say so in the Notes to Markers.
6. The exemplar answer must be the length a student could actually write, \
not a summary. For a 12-mark essay, roughly 500-700 words. Do not pad with \
restatement.
7. Use the Hong Kong syllabus terminology throughout.
8. Write in English, in the same register as the notes.
9. Do NOT discuss or reveal any real test paper, mock, predicted paper, \
mark scheme or answer key. This is freshly written practice material.
10. Do not reference F2 or F3 material. Those are a different course and are \
out of scope.
11. The Part (b) command word judges a NAMED thing - a specific measure, \
mode or policy taken from the notes (for example channelisation, agroforestry, \
advanced technology). Never make the second half a free-topic "is \
sustainability possible" question. Name the thing in the stem.

REFERENCE NOTES:
{context}
"""


def _strip_reasoning(text: str) -> str:
    return llm._strip_reasoning(text)


def _leaf_terms(title: str) -> set[str]:
    from .curriculum import STOPWORDS
    return {
        w for w in re.findall(r"[a-z][a-z\-]{3,}", (title or "").lower())
        if w not in STOPWORDS
    }


def _leaf_content(matcher, leaf: dict) -> list[dict]:
    """The note content for one curriculum leaf, for writing from.

    An essay needs the whole note, not the one section whose heading
    shares a word with the leaf title - a 12-mark essay on "Earthquakes"
    that only sees a paragraph on seismic waves cannot be written. So the
    full note is taken, and the narrowed match is added on top for any
    section the full-note lookup did not reach.
    """
    hints = matcher.hints_for(leaf)
    whole = matcher.match_notes(hints)
    if whole:
        return whole
    return matcher.match(hints, leaf.get("title", ""))


def collect_source(
    matcher,
    curriculum: dict,
    code: str,
    leaf_ids: list[str] | None = None,
    max_chars: int = 20000,
) -> tuple[list[dict], str]:
    """Collect the note content for the chosen sub-topics.

    Returns (sources, context_text). The sources are the note sections the
    essay is built from; they are shown to the student so the essay can be
    checked against the notes.
    """
    code = (code or "").upper()
    if code not in ESSAY_ELECTIVES:
        raise ValueError(
            f"{code or 'That topic'} is not covered by the essay generator. "
            f"It covers {', '.join(ESSAY_ELECTIVES)} only."
        )

    wanted = set(leaf_ids or [])
    picked: list[dict] = []
    seen: set[str] = set()

    for el in curriculum.get("electives", []):
        if el.get("code", "").upper() != code:
            continue
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                lid = leaf.get("id")
                if wanted and lid not in wanted:
                    continue
                content = _leaf_content(matcher, leaf)
                # The leaf's OWN note comes first, so the context budget is
                # spent on the material that belongs to this sub-topic
                # rather than on a supporting note that was pulled in
                # first by accident.
                primary = matcher.resolve_source(str(leaf.get("source", "")))
                if primary:
                    # resolve_source returns a normalised (lower-case) title,
                    # while a chunk keeps the note's own capitalisation.
                    want = primary.strip().lower()
                    content.sort(
                        key=lambda c: 0 if c["title"].strip().lower() == want else 1
                    )
                for c in content:
                    key = c["title"] + "#" + str(c["n"])
                    if key in seen:
                        continue
                    seen.add(key)
                    picked.append({
                        **c,
                        "leaf_id": lid,
                        "leaf_title": leaf.get("title"),
                        "subquestion": f"{sq.get('number')}. {sq.get('title')}",
                    })

    # If the student picked specific sub-topics but none of them resolved
    # to a note, fall back to the whole elective so the essay still has
    # material - and say so, rather than inventing content.
    if wanted and not picked:
        for el in curriculum.get("electives", []):
            if el.get("code", "").upper() != code:
                continue
            for sq in el.get("subquestions", []):
                for leaf in sq.get("leaves", []):
                    if leaf.get("id") not in wanted:
                        continue
                    content = _leaf_content(matcher, leaf)
                    for c in content:
                        key = c["title"] + "#" + str(c["n"])
                        if key in seen:
                            continue
                        seen.add(key)
                        picked.append({
                            **c,
                            "leaf_id": leaf.get("id"),
                            "leaf_title": leaf.get("title"),
                            "subquestion": f"{sq.get('number')}. {sq.get('title')}",
                        })

    # Build the reference block the model reads.
    parts = []
    used = 0
    for i, s in enumerate(picked, 1):
        block = (
            f"[{i}] {s['title']}"
            + (f" — {s['heading']}" if s["heading"] else "")
            + f"\n{s['text']}"
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    context = "\n\n".join(parts)
    return picked, context


def resolve_commands(
    command_a: str | None,
    command_b: str | None,
    marks: int,
) -> tuple[str, str, int, int]:
    """Resolve the two command words and the two part mark allocations.

    Returns (cmd_a, cmd_b, part_a_marks, part_b_marks).

    A 12-mark (or larger) essay is two parts. An 8-mark essay is one part
    and only one command word, so the Part (b) slot is empty and part (a)
    takes the whole allocation. Splitting the marks is even, with the
    larger remainder going to part (a) so the first half is never short.
    """
    if marks >= 12:
        key_a = command_a if command_a in PART_A_COMMANDS else DEFAULT_COMMAND_A
        key_b = command_b if command_b in PART_B_COMMANDS else DEFAULT_COMMAND_B
        part_a = marks // 2
        part_b = marks - part_a
        return PART_A_COMMANDS[key_a], PART_B_COMMANDS[key_b], part_a, part_b

    key_a = command_a if command_a in PART_A_COMMANDS else DEFAULT_COMMAND_A
    return PART_A_COMMANDS[key_a], "", marks, 0


def build_prompt(
    context: str,
    code: str,
    subtopic_titles: list[str],
    marks: int,
    command_a: str | None = None,
    command_b: str | None = None,
    topic_title: str = "",
) -> list[dict]:
    """Build the chat messages for one essay."""
    cmd_a, cmd_b, part_a_marks, part_b_marks = resolve_commands(
        command_a, command_b, marks
    )

    if part_b_marks:
        shape = (
            f"This is a {marks}-mark essay. Write it as TWO parts of "
            f"{part_a_marks} and {part_b_marks} marks. Each part has its own "
            f"command word:\n"
            f"  Part (a) - {part_a_marks} marks - command word: "
            f"\"{cmd_a}\". This part is written for knowledge and mechanism: "
            f"describe the pattern, account for the causes, or explain the "
            f"process. The relevant concepts must carry the mechanism.\n"
            f"  Part (b) - {part_b_marks} marks - command word: "
            f"\"{cmd_b}\". This part is written for explanation and "
            f"judgement: it must require the student to weigh the named "
            f"measure against the alternatives and reach a judgement.\n"
            f"  Part (a) performance bands: {_band_text(part_a_marks)}.\n"
            f"  Part (b) performance bands: {_band_text(part_b_marks)}."
        )
        stem_rule = (
            "QUESTION\n"
            "[ONE stem, written as TWO sentences: the first opens with the "
            "Part (a) command word, the second opens with the Part (b) "
            "command word. End with the total marks in square brackets, "
            "e.g. [12].]"
        )
        scheme_rule = (
            "MARK SCHEME\n"
            "Notes to Markers\n"
            "[one paragraph]\n"
            "\n"
            "Part (a) - Relevant concepts\n"
            "[one bullet per concept, each with its mechanism]\n"
            "Part (a) - Performance bands\n"
            "[high band first, down to the lowest]\n"
            "\n"
            "Part (b) - Relevant concepts\n"
            "[one bullet per concept, each with its mechanism]\n"
            "Part (b) - Performance bands\n"
            "[high band first, down to the lowest]"
        )
        answer_rule = (
            "EXEMPLAR ANSWER\n"
            "[the student-level answer, answering Part (a) then Part (b), "
            "in the same order as the stem]"
        )
    else:
        shape = (
            f"This is a {marks}-mark essay. Write it as ONE part with a "
            f"single command word: \"{cmd_a}\". Marks per concept: about "
            f"{marks // 3}, so the student needs roughly three developed "
            f"points. Performance bands: {_band_text(marks)}."
        )
        stem_rule = (
            "QUESTION\n"
            "[the stem, opening with the command word, ending with the "
            "mark allocation in square brackets]"
        )
        scheme_rule = (
            "MARK SCHEME\n"
            "Notes to Markers\n"
            "[one paragraph]\n"
            "\n"
            "Relevant concepts\n"
            "[one bullet per concept, each with its mechanism]\n"
            "Performance bands\n"
            "[high band first, down to the lowest]"
        )
        answer_rule = (
            "EXEMPLAR ANSWER\n"
            "[the student-level answer]"
        )

    subs = "; ".join(subtopic_titles) if subtopic_titles else "the elective"
    cmd_line = (
        f"Part (a) command word: {cmd_a}"
        + (f"\nPart (b) command word: {cmd_b}" if cmd_b else "")
    )
    user = f"""\
Write a practice essay for the HKDSE Geography short essay.

Elective: {code} {topic_title}
Sub-topic(s) covered: {subs}
{cmd_line}

{shape}

Follow the required output structure exactly:

{stem_rule}

{scheme_rule}

{answer_rule}

Write ALL of it. The whole essay is about 700-900 words. Do not stop
part-way, and do not leave a section as a placeholder.

Start writing now with "QUESTION." """
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": user},
    ]


# The three headings the essay must carry. A generation that does not
# have all three is not an essay, whatever the model says.
REQUIRED_SECTIONS = ("QUESTION", "MARK SCHEME", "EXEMPLAR ANSWER")


def _question_stem(text: str) -> str:
    """The question stem - the block between QUESTION and MARK SCHEME."""
    up = text.upper()
    a = up.find("QUESTION")
    b = up.find("MARK SCHEME", a + 1)
    if a < 0 or b < 0:
        return ""
    stem = text[a:b]
    # The model writes "QUESTION." with a full stop, and sometimes a
    # heading marker under it. The label's own punctuation is not part of
    # the question, and leaving it in put a stray "." at the head of the
    # stem - which then read as the end of an empty first sentence, so
    # the stem was split in the wrong place and Part (a) looked empty.
    stem = re.sub(r"^[#\s]*QUESTION\b[.:\-]?\s*", "", stem, count=1, flags=re.I)
    return stem


def _mark_scheme_parts(text: str) -> dict[str, str]:
    """Split the mark scheme into its Part (a) and Part (b) sections.

    The split is on the part label, so a section runs from its own
    "Part (a)" / "Part (b)" heading to the next part label or the end of
    the mark scheme. A heading that does not name its part is ignored -
    the part label, not the concepts heading, defines the boundary.
    """
    up = text.upper()
    start = up.find("MARK SCHEME")
    if start < 0:
        return {}
    end = up.find("EXEMPLAR ANSWER", start)
    scheme = text[start:end if end > start else len(text)]

    # A part's own heading may be written as markdown ("### Part (a) -
    # Relevant concepts"), as bold text ("**Part (a)** - Relevant
    # concepts") or as a plain line ("Part (a) - Relevant concepts"). All
    # three are headings. A mention inside a sentence - the "Notes to
    # Markers" paragraph says "Part (a) rewards ..." - is not, so the
    # label must sit at the START of a line to count.
    #
    # The label is also followed by the name of a part section. That is
    # what separates a real heading from the notes prose, which continues
    # with a sentence rather than a section name.
    _PART_SECTIONS = (
        "relevant concepts", "performance bands", "marking scheme",
        "mark scheme", "key points", "concepts",
    )
    _label_re = re.compile(
        r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?PART\s*\(\s*([AB])\s*\)",
        re.I,
    )
    first: dict[str, tuple[int, int]] = {}
    for _m in _label_re.finditer(scheme):
        _label = _m.group(1).lower()
        if _label in first:
            continue
        # The rest of the line, with the markdown and bold markers off.
        _line_end = scheme.find("\n", _m.end())
        _line = scheme[_m.end():(_line_end if _line_end > 0 else len(scheme))]
        _line = re.sub(r"[*_#`]", " ", _line).lower()
        if not any(s in _line for s in _PART_SECTIONS):
            continue  # prose mention, not a heading
        first[_label] = (_m.start(), _m.end())

    out: dict[str, str] = {}
    if "a" in first and "b" in first:
        a_start, a_end = first["a"]
        b_start, b_end = first["b"]
        if a_start < b_start:
            out["a"] = scheme[a_end:b_start]
            out["b"] = scheme[b_end:]
        else:
            out["b"] = scheme[b_end:a_start]
            out["a"] = scheme[a_end:]
    elif "a" in first:
        out["a"] = scheme[first["a"][1]:]
    elif "b" in first:
        out["b"] = scheme[first["b"][1]:]
    return out


def _first_sentences(text: str, n: int = 3) -> list[str]:
    """The first n sentences of a block, for command-word checks.

    A command word at the start of a sentence is what carries the command.
    Splitting on the full stop would break on "U.S." or a decimal, so the
    split is on a period followed by whitespace and a capital.
    """
    flat = " ".join(text.split())
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z(])", flat)
    return [p.strip() for p in parts[:n] if p.strip()]


def _has_command(sentence: str, markers: tuple[str, ...]) -> bool:
    low = sentence.lower()
    return any(m in low for m in markers)


def _split_stem_on_command(
    body: str,
    markers_b: tuple[str, ...],
    markers_a: tuple[str, ...],
) -> tuple[str, str] | None:
    """Split a question stem into its two halves at the Part (b) command.

    Splitting on sentence position is fragile: the model often writes a
    first half with several clauses ("Describe and explain X, and explain
    how X reinforced itself."), so the second half is not reliably the
    second sentence. Splitting on where the Part (b) COMMAND WORD appears
    is robust - the command word is what makes it the second half.

    Returns (part_a_text, part_b_text), or None if no split point is
    found.
    """
    low = body.lower()
    # The Part (b) command word must not open the stem - that would mean the
    # Part (a) half is missing entirely.
    candidates: list[tuple[int, str]] = []
    for m in markers_b:
        for hit in re.finditer(r"\b" + re.escape(m) + r"\b", low):
            if hit.start() == 0:
                continue
            candidates.append((hit.start(), m))
    if not candidates:
        return None
    candidates.sort()
    pos, _marker = candidates[0]

    # Walk back to the start of the sentence containing the command word,
    # so the Part (a) half keeps its own full sentence.
    head = body[:pos].rstrip()
    m = re.search(r"(?<=[.?!])\s+(?=[A-Z(])", head)
    if m:
        head = head[:m.start()]
    tail = body[pos:].strip()
    return head.strip(), tail


def check_two_parts(
    text: str,
    command_a: str | None,
    command_b: str | None,
    marks: int,
) -> str | None:
    """Return why the two-part structure failed, or None if it is fine.

    This is the check that stops one command word running across the whole
    question. A 12-mark essay must open its first half with the Part (a)
    command word and its second half with a DIFFERENT Part (b) command word.
    """
    cmd_a, cmd_b, _pa, _pb = resolve_commands(command_a, command_b, marks)
    if not cmd_b:
        return None  # single-part essay, nothing to split

    stem = _question_stem(text)
    if not stem:
        return "the question stem was missing"

    # The stem after the word QUESTION and before the mark allocation.
    body = re.sub(r"^[#\s]*QUESTION\b[.:\-]?\s*", "", stem, count=1, flags=re.I).strip()
    body = re.sub(r"\s*\[\d+\]\s*$", "", body).strip()
    if not body:
        return "the question stem was missing"

    key_a = command_a if command_a in PART_A_COMMANDS else DEFAULT_COMMAND_A
    key_b = command_b if command_b in PART_B_COMMANDS else DEFAULT_COMMAND_B
    markers_a = COMMAND_MARKERS.get(key_a, ())
    markers_b = COMMAND_MARKERS.get(key_b, ())

    # The shared-command case is checked FIRST and reported in its own
    # words, because it is the specific failure this whole function
    # exists to catch: one command word running across all 12 marks.
    if markers_a and markers_b:
        # Two shapes of the shared-command failure:
        #   1. the Part (a) command appears and a Part (b) command appears
        #      later too - the same word running on;
        #   2. the Part (a) command appears TWICE and no Part (b) command
        #      appears at all - one word opening both halves.
        low_body = body.lower()
        has_b = any(
            re.search(r"\b" + re.escape(b) + r"\b", low_body)
            for b in markers_b
        )
        a_count = max(
            len(re.findall(r"\b" + re.escape(m) + r"\b", low_body))
            for m in markers_a
        )
        if a_count >= 2 and not has_b:
            return (
                f"the same command word \"{cmd_a}\" ran across both "
                f"halves of the question stem - the two parts need "
                f"different command words"
            )
        if has_b and a_count >= 2:
            return (
                f"the same command word \"{cmd_a}\" ran across both "
                f"halves of the question stem - the two parts need "
                f"different command words"
            )

    parts = _split_stem_on_command(body, markers_b, markers_a)
    if parts is None:
        return (
            f"the question stem was not split into two parts - the second "
            f"half must open with the Part (b) command word \"{cmd_b}\""
        )
    part_a_text, part_b_text = parts

    if markers_a and not _has_command(part_a_text, markers_a):
        # Try the looser form: every verb of the command word present, in
        # any order.
        _verbs = COMMAND_VERBS.get(key_a, ())
        if not (_verbs and all(
            re.search(r"\b" + re.escape(v) + r"\b", part_a_text.lower())
            for v in _verbs
        )):
            return (
                f"the first half of the question stem did not use the "
                f"Part (a) command word \"{cmd_a}\""
            )
    if markers_b and not _has_command(part_b_text, markers_b):
        return (
            f"the second half of the question stem did not use the Part (b) "
            f"command word \"{cmd_b}\""
        )
    if not part_a_text.strip():
        return (
            "the first half of the question stem was empty - the question "
            "needs a Part (a) as well as a Part (b)"
        )

    # The mark scheme must have a separate section for each part, and each
    # section must carry its own relevant concepts.
    #
    # Counting the headings is not enough: "Part (b) - Performance bands"
    # carries the part label too, and a "Relevant concepts" heading that has
    # been moved out of its part would still be counted. So the mark scheme
    # is split into parts and each part is checked on its own.
    sections = _mark_scheme_parts(text)
    for label in ("a", "b"):
        sec = sections.get(label)
        if sec is None:
            return "the mark scheme did not have a separate section for each part"
        if "RELEVANT CONCEPTS" not in sec.upper():
            return (
                f"the mark scheme's Part ({label}) section had no relevant "
                f"concepts of its own"
            )
        if "PERFORMANCE BANDS" not in sec.upper():
            return (
                f"the mark scheme's Part ({label}) section had no performance "
                f"bands of its own"
            )

    return None


def check_structure(text: str) -> str | None:
    """Return why the essay is unusable, or None if it is fine."""
    if not text or len(text) < 800:
        return "the answer was too short to be an essay"
    up = text.upper()
    missing = [s for s in REQUIRED_SECTIONS if s not in up]
    if missing:
        return "the answer was missing " + ", ".join(missing)
    if text.count("(") < 2:
        return "the answer had no marked parts"
    return None


def generate(
    matcher,
    curriculum: dict,
    code: str,
    leaf_ids: list[str] | None = None,
    marks: int = 12,
    command_a: str | None = None,
    command_b: str | None = None,
    topic_title: str = "",
) -> dict:
    """Generate one essay. Returns {ok, essay, sources, error}."""
    try:
        sources, context = collect_source(
            matcher, curriculum, code, leaf_ids
        )
    except ValueError as e:
        return {"ok": False, "error": str(e), "essay": None, "sources": []}

    if not context.strip():
        return {
            "ok": False,
            "error": (
                f"There are no notes covering that part of {code} yet, so an "
                f"essay cannot be written from them. Try another sub-topic."
            ),
            "essay": None,
            "sources": [],
        }

    # Which sub-topic titles the student asked for, for the prompt.
    titles = []
    for el in curriculum.get("electives", []):
        if el.get("code", "").upper() != code.upper():
            continue
        for sq in el.get("subquestions", []):
            for leaf in sq.get("leaves", []):
                if not leaf_ids or leaf.get("id") in leaf_ids:
                    titles.append(leaf.get("title", ""))

    messages = build_prompt(
        context, code.upper(), titles, marks, command_a, command_b, topic_title
    )

    # Retry once on a truncated or malformed answer.
    #
    # A long generation can be cut off by the token budget, and the model
    # sometimes returns a few hundred characters of the question stem and
    # nothing else. Both look like a successful call, so the structure is
    # checked before the result is accepted.
    res = None
    problems = []
    for attempt in range(2):
        res = llm.chat(messages, temperature=0.5, max_tokens=6000,
                       chain=llm.LONG_CHAIN)
        if not res["ok"]:
            problems.append(res["error"])
            break
        why = check_structure(res["content"])
        if why is None:
            why = check_two_parts(
                res["content"], command_a, command_b, marks
            )
        if why is None:
            break
        problems.append(why)
        if attempt == 0:
            # Ask for the whole thing again, and make the budget explicit.
            # The two-part message is the important one: a single command
            # word running across both halves is the failure this catches.
            messages[-1]["content"] += (
                "\n\nIMPORTANT: your previous attempt was rejected "
                f"({why}). Write the WHOLE thing from QUESTION to the end "
                "of the EXEMPLAR ANSWER. Do not stop part-way.\n"
                "The question must have TWO parts with DIFFERENT command "
                "words: the first half opens with the Part (a) command word "
                "and the second half opens with the Part (b) command word. "
                "One command word must NOT run across both halves."
            )
    if not res or not res["ok"]:
        return {
            "ok": False,
            "error": res["error"] if res and not res["ok"] else "; ".join(problems),
            "essay": None,
            "sources": [],
        }
    why = check_structure(res["content"])
    if why is None:
        why = check_two_parts(res["content"], command_a, command_b, marks)
    if why is not None:
        return {
            "ok": False,
            "error": (
                f"The generated essay was not usable ({why}). Please try "
                f"again, or pick fewer sub-topics."
            ),
            "essay": None,
            "sources": [],
        }

    # Keep the note sections the essay was built from, so the student can
    # check it. Collapse to one entry per note for the display.
    shown = []
    seen_notes = set()
    for s in sources:
        if s["title"] in seen_notes:
            continue
        seen_notes.add(s["title"])
        shown.append({
            "title": s["title"],
            "heading": s["heading"],
            "path": s["path"],
            "leaf_title": s.get("leaf_title"),
        })

    cmd_a, cmd_b, part_a, part_b = resolve_commands(command_a, command_b, marks)
    return {
        "ok": True,
        "error": None,
        "essay": res["content"],
        "sources": shown,
        "marks": marks,
        "command_a": cmd_a,
        "command_b": cmd_b,
        "part_a_marks": part_a,
        "part_b_marks": part_b,
        "model": res.get("model"),
        "elapsed": res.get("elapsed"),
    }
