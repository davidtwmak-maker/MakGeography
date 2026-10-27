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

# The exam's paired command words. A "describe" part earns marks for
# description; an "explain/evaluate" part earns marks for mechanism and
# judgement. Mixing them in one part is what makes an essay read as a
# list of facts.
COMMAND_PAIRS = {
    "account": "Account for",
    "describe_explain": "Describe and explain",
    "explain": "Explain",
    "discuss": "Discuss",
    "evaluate": "Evaluate",
    "assess": "Assess",
}

SYSTEM_PROMPT = """\
You are an HKDSE Geography examiner writing practice material for Form 6 \
students in Hong Kong. You write from the REFERENCE NOTES below and nothing \
else.

The essay you write must be in the real HKDSE Geography Paper 1/2 short \
essay format:

- A QUESTION STEM that names the place or case and the command, ending with \
the mark allocation in square brackets, e.g. "... [12]".
- A MARK SCHEME, structured as:
    * "Notes to Markers" - a short paragraph on what is being rewarded and \
how quality is judged (judge quality and depth, not point-counting; credit \
any relevant reasonable answer the scheme does not list).
    * "Relevant concepts" - one BULLET per concept. Each bullet carries the \
mechanism, not prose. Never a paragraph where a bullet belongs.
    * Performance bands, high to low. For a 12-mark essay the bands are \
6 / 3-5 / 1-2 per part (6+6). For other mark totals, scale the bands so \
they sum to the total.
- AN EXEMPLAR ANSWER, written the way a strong student would write it in the \
time allowed: linked cause and effect, named evidence, syllabus terminology, \
and a judgement where the command asks for one.

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
    hints = leaf.get("source_hints", [])
    whole = matcher.match_notes(hints)
    if whole:
        return whole
    return matcher.match(hints, leaf.get("title", ""))


def collect_source(
    matcher,
    curriculum: dict,
    code: str,
    leaf_ids: list[str] | None = None,
    max_chars: int = 12000,
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


def build_prompt(
    context: str,
    code: str,
    subtopic_titles: list[str],
    marks: int,
    command: str | None = None,
    topic_title: str = "",
) -> list[dict]:
    """Build the chat messages for one essay."""
    cmd = COMMAND_PAIRS.get(command or "", command or "")
    if marks >= 12:
        shape = (
            f"This is a {marks}-mark essay. Write it as TWO parts of "
            f"{marks // 2} marks each, using the DSE paired-command style:\n"
            f"  Part (a): a description or account-type command "
            f"({'Account for' if cmd == 'Account for' else 'Describe and explain'}) "
            f"the process or pattern.\n"
            f"  Part (b): a command that asks for explanation and judgement "
            f"({'Discuss whether' if cmd == 'Discuss' else 'Explain why'}) - it "
            f"must require the student to weigh factors up against each other."
        )
    else:
        shape = (
            f"This is a {marks}-mark essay. Write it as ONE part with a "
            f"single command word. Marks per concept: about {marks // 3}, "
            f"so the student needs roughly three developed points."
        )

    subs = "; ".join(subtopic_titles) if subtopic_titles else "the elective"
    user = f"""\
Write a practice essay for the HKDSE Geography short essay.

Elective: {code} {topic_title}
Sub-topic(s) covered: {subs}
Command word: {cmd}

{shape}

Follow the required output structure exactly:
QUESTION
[the stem, ending with the mark allocation in square brackets]

MARK SCHEME
Notes to Markers
[one paragraph]

Part (a) [or the single part] - Relevant concepts
[one bullet per concept, each with its mechanism]
Performance bands
[high band first, down to the lowest]

EXEMPLAR ANSWER
[the student-level answer]

Write ALL of it. The whole essay is about 700-900 words. Do not stop
part-way, and do not leave a section as a placeholder.

Start writing now with "QUESTION."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": user},
    ]


# The three headings the essay must carry. A generation that does not
# have all three is not an essay, whatever the model says.
REQUIRED_SECTIONS = ("QUESTION", "MARK SCHEME", "EXEMPLAR ANSWER")


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
    command: str | None = None,
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
        context, code.upper(), titles, marks, command, topic_title
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
            break
        problems.append(why)
        if attempt == 0:
            # Ask for the whole thing again, and make the budget explicit.
            messages[-1]["content"] += (
                "\n\nIMPORTANT: your previous attempt was incomplete "
                f"({why}). Write the WHOLE thing from QUESTION to the end "
                "of the EXEMPLAR ANSWER. Do not stop part-way."
            )
    if not res or not res["ok"]:
        return {
            "ok": False,
            "error": res["error"] if res and not res["ok"] else "; ".join(problems),
            "essay": None,
            "sources": [],
        }
    why = check_structure(res["content"])
    if why is not None:
        return {
            "ok": False,
            "error": (
                f"The generated essay was incomplete ({why}). Please try "
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

    return {
        "ok": True,
        "error": None,
        "essay": res["content"],
        "sources": shown,
        "marks": marks,
        "command": command,
        "model": res.get("model"),
        "elapsed": res.get("elapsed"),
    }
