#!/usr/bin/env python3
"""
Repair the option-letter references inside AI-generated MC explanations.

`reshuffle_mc_answers.py` permuted the options and updated the `answer`
field, but it never rewrote the letters that the explanation text names.
After the shuffle those letters were stale: "B is incorrect because ..."
could name the very option that had become the answer, and a coordinated
group ("Options B, C and D") could end up reading "B, C and C".

The repair works from the ORIGINAL option order, which is still in the git
history (the commit before the shuffle). For every letter the explanation
refers to, the option TEXT it pointed at then is looked up in the CURRENT
options, and the letter it now carries is written in its place.

Reference shapes handled:
  prefix   "Option B", "option B", "answer B", "distractor B"
  claim    "B is incorrect", "B is correct"
  describe "B reverses these effects", "B confuses ..."
  paren    "Abrasion (B) instead occurs ..."
  group    "Options B, C and D", "C and D"
  subject  "A links each practice to a mechanism", "A syncline bends downwards"
           (the letter is the grammatical subject and the clause after it
            paraphrases the option's content)

A letter that cannot be resolved is left untouched and reported, never
guessed. The English article "A" is not a reference unless it is the
subject of a clause that paraphrases an option.

Usage:  python scripts/fix_mc_explanation_letters.py [--dry]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "data" / "mc_bank.json"
PRE_SHUFFLE = "6bf83cd^"  # the commit before the answer-letter shuffle

# --- reference shapes ------------------------------------------------------

PREFIX = re.compile(
    r"(?i)\b(?:option|options|answer|choice|choices|distractor|distractors)\s*$")
PAREN = re.compile(r"^\s*\(\s*([ABCD])\s*\)")
CLAIM_VERB = re.compile(
    r"(?i)^\s+(?:is|are)\s+(?:incorrect|wrong|not\s+correct|false|correct|right|true)\b")
DESCRIBE_VERB = re.compile(
    r"(?i)^\s+(?:describ\w*|confus\w*|revers\w*|wrongly|incorrectly|correctly|"
    r"associat\w*|omits?|ignor\w*|overstat\w*|mix(?:es)?\s+up|states?|means?|"
    r"gives?|lists?|demonstrat\w*|show\w*|indicat\w*|reflect\w*|represent\w*|"
    r"counts\b|measures\b|links?\b|balances\b|combines\b|promotes\b|"
    r"mainl?y\s+(?:demonstrat|show|indicat|measure|reflect|represent)\w*|"
    r"is\s+the\s+main\s+distractor|may\s+target|would\s+\w+)\b")

# A coordinated group of letters: "B, C and D" / "C and D" / "B"
GROUP = re.compile(
    r"(?<![\w])(?P<letters>[ABCD](?:\s*,\s*[ABCD])*(?:\s+(?:and|or)\s+[ABCD])?)(?![\w])")
TOKEN = re.compile(r"(?<![A-Za-z0-9])([ABCD])(?![A-Za-z0-9])")
# A standalone capital A-D is not always an option reference. Scientific
# and unit notation puts one there: "Gt C" (gigatonnes of carbon), "-18°C",
# "1.1°C", "CO2", "R&D". The context decides:
#   - the letter is preceded by a unit-ish word (Gt, CO, CH, N2O, ppm) or
#     followed by a degree sign or a unit, and is not near an option word
#     -> not a reference.
#   - the letter is followed by ", " or " and " inside a run of letters
#     (e.g. "Options B, C and D") -> a group, handled elsewhere.
UNIT_BEFORE = re.compile(
    r"(?i)\b(?:gt|co|ch|n2o|h2o|ppm|kg|km2|km3|ha|mt|m3|m2|r&d|usd|hk\$)\s*$")
UNIT_AFTER = re.compile(r"^\s*[°%]")


STOP = set(
    "the a an and or but of to in on for with by is are was were be been being "
    "that this these those it its as at from than then when where which who "
    "whom whose what how why not no nor do does did have has had can could may "
    "might must shall should will would about into over under between each "
    "other more most less least such same both all any some one two three "
    "four because while during their they them his her our your my me we you "
    "i us he she includes including describes describe links each practice "
    "mechanism".split())


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[A-Za-z]{3,}", text.lower()) if w not in STOP}


def _classify(exp: str, m) -> str | None:
    """Return the reference shape for a single letter token, or None."""
    before = exp[max(0, m.start() - 24):m.start()]
    after = exp[m.end():m.end() + 90]
    if PREFIX.search(before):
        return "prefix"
    if PAREN.match(after):
        return "paren"
    if CLAIM_VERB.match(after):
        return "claim"
    if DESCRIBE_VERB.match(after):
        return "describe"
    return None


def find_references(exp: str, old_options, old_answer):
    """Yield (start, end, letter, shape) for every option reference."""
    out = []
    # 1. coordinated groups first - they own their letters.
    group_spans = []
    for m in GROUP.finditer(exp):
        letters = [c for c in m.group("letters") if c in "ABCD"]
        if len(letters) < 2:
            continue
        before = exp[max(0, m.start() - 24):m.start()]
        after = exp[m.end():m.end() + 90]
        # A group must be an option reference, not a pair of initials.
        if not (PREFIX.search(before)
                or CLAIM_VERB.match(after)
                or DESCRIBE_VERB.match(after)
                or re.match(r"(?i)^\s+(?:incorrectly|wrongly)\b", after)
                or re.search(r"(?i)\b(?:describe|describes|associat\w*|confus\w*|"
                             r"revers\w*|count\w*|measure\w*|match\w*|give\w*|"
                             r"demonstrat\w*|show\w*|indicat\w*|reflect\w*|"
                             r"represent\w*|mainly|balance\w*|promot\w*|combin\w*|"
                             r"support\w*|provid\w*|requir\w*|use\w*|target\w*)\b",
                             after)):
            continue
        group_spans.append(m.span())
        out.append((m.start("letters"), m.end("letters"), letters, "group"))

    # 2. single letters outside any group span. A group ALWAYS wins: a
    #    letter that opens a group ("B and D mainly demonstrate ...") is
    #    part of the group, not a subject reference.
    for m in TOKEN.finditer(exp):
        if any(s <= m.start() < e for s, e in group_spans):
            continue
        # a capital in scientific or unit notation is not a reference
        _before = exp[max(0, m.start() - 24):m.start()]
        _after = exp[m.end():m.end() + 90]
        if UNIT_BEFORE.search(_before) or UNIT_AFTER.match(_after):
            continue
        shape = _classify(exp, m)
        if shape:
            out.append((m.start(), m.end(), m.group(1), shape))
            continue
        # 3. bare-subject reference: the letter begins a sentence and the
        #    clause after it talks about one of the options.
        #
        #    This is where the English article "A" collides with an option
        #    letter: "A syncline bends downwards" names the option in words,
        #    while "A links each practice to a mechanism" points at the
        #    option by its letter. The two are told apart by the word that
        #    follows:
        #
        #      - the word after the letter is the NAME of the option the
        #        letter points at      -> a reference, remap the letter
        #      - the word after the letter is the NAME of a DIFFERENT
        #        option                 -> the English article, leave it
        #      - the word after the letter is a verb or adverb
        #                               -> a reference, remap the letter
        sent_start = exp.rfind(".", 0, m.start()) + 1
        if exp[sent_start:m.start()].strip():
            continue  # not the start of a sentence
        if len(old_options) != 4:
            continue
        # If this sentence carries a coordinated group, this letter may be
        # part of it - the group already owns those letters.
        if any(sent_start <= s < exp.find(".", m.end()) + 1 or
               (s >= sent_start and e <= (exp.find(".", m.end()) + 1))
               for s, e in group_spans):
            continue
        clause = exp[m.end():m.end() + 70]
        if not clause:
            continue
        letter = m.group(1)
        pointed = old_options["ABCD".index(letter)]
        head = re.match(r"\s*([A-Za-z]+)", clause)
        head_word = (head.group(1).lower() if head else "")
        cw_clause = content_words(clause)

        pointed_words = content_words(pointed)
        if head_word and head_word in pointed_words:
            out.append((m.start(), m.end(), letter, "subject"))
            continue

        # Is the head word the name of a DIFFERENT option? Then the capital
        # letter is the English article and must not be touched.
        best = None
        best_score = 0
        for i, txt in enumerate(old_options):
            cw_opt = content_words(txt)
            if not cw_opt:
                continue
            shared = len(cw_opt & cw_clause)
            extra = len(cw_clause - cw_opt)
            score = shared * 2 + min(extra, 3)
            if shared >= 1 and score > best_score:
                best_score = score
                best = "ABCD"[i]
        if best is not None and best != letter:
            other_words = content_words(old_options["ABCD".index(best)])
            if head_word and head_word in other_words:
                continue  # the English article - leave it alone
        out.append((m.start(), m.end(), letter, "subject"))

    out.sort(key=lambda r: r[0])
    return out


def _remap_group(group_text: str, old_letters, new_letters) -> str:
    """Rewrite the letters inside a coordinated group, keeping its joiner.

    "C and D" with C->B and D->A becomes "B and A", not "B, A".
    """
    # The letters are replaced BY POSITION. Searching for the letter text
    # instead (rfind) can land on a letter that was just substituted, which
    # swaps the two members of the group.
    pieces = []
    idx = 0
    pos = 0
    for m in re.finditer(r"[ABCD]", group_text):
        pieces.append(group_text[idx:m.start()])
        pieces.append(new_letters[pos] if pos < len(new_letters) else m.group(0))
        idx = m.end()
        pos += 1
    pieces.append(group_text[idx:])
    return "".join(pieces)


def resolve(exp, old_options, old_answer, current_options):
    """Rewrite stale option-letter references. Returns (text, changes, unresolved)."""
    if not exp:
        return exp, [], []

    old_letter_text = {}
    if old_options and len(old_options) == 4 and old_answer in "ABCD":
        for i, txt in enumerate(old_options):
            old_letter_text["ABCD"[i]] = txt

    text_to_new = {}
    if current_options and len(current_options) == 4:
        for i, txt in enumerate(current_options):
            text_to_new[txt] = "ABCD"[i]

    changes = []
    unresolved = []
    out = exp
    # Replace from the end so earlier offsets stay valid.
    for start, end, payload, shape in sorted(find_references(exp, old_options, old_answer),
                                             key=lambda r: r[0], reverse=True):
        letters = payload if isinstance(payload, list) else [payload]
        new_letters = []
        ok = True
        for L in letters:
            referenced = old_letter_text.get(L)
            if referenced is None:
                unresolved.append((L, shape, "no original text"))
                ok = False
                break
            newL = text_to_new.get(referenced)
            if newL is None:
                unresolved.append((L, shape, "option text gone"))
                ok = False
                break
            new_letters.append(newL)
        if not ok:
            continue
        if new_letters == letters:
            continue
        if shape == "group":
            # Rebuild the group from its OWN text so the joiner ("and" /
            # "or") and the sequence of the letters survive. Substituting
            # letter by letter would turn "C and D" into "C, D".
            original_group_text = exp[start:end]
            out = out[:start] + _remap_group(original_group_text, letters, new_letters) + out[end:]
        else:
            out = out[:start] + new_letters[0] + out[end:]
        for oldL, newL in zip(letters, new_letters):
            changes.append((oldL, newL, shape))
    changes.reverse()
    unresolved.reverse()
    return out, changes, unresolved


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    bank = json.loads(BANK.read_text(encoding="utf-8"))
    qs = bank.get("questions", [])

    raw = subprocess.run(
        ["git", "-C", str(BASE), "show", f"{PRE_SHUFFLE}:data/mc_bank.json"],
        capture_output=True, text=True, check=True,
    ).stdout
    old_bank = json.loads(raw)
    old_by_id = {q["id"]: q for q in old_bank.get("questions", []) if q.get("id")}

    fixed = 0
    shapes = Counter()
    all_unresolved = []
    for q in qs:
        if q.get("official"):
            continue
        old = old_by_id.get(q.get("id"))
        if not old:
            continue
        new_exp, changes, unresolved = resolve(
            q.get("explanation") or "",
            old.get("options") or [],
            old.get("answer") or "",
            q.get("options") or [],
        )
        if changes:
            q["explanation"] = new_exp
            fixed += 1
            for _, _, shape in changes:
                shapes[shape] += 1
        if unresolved:
            all_unresolved.append((q["id"], unresolved))

    print(f"questions scanned        : {len(qs)}")
    print(f"explanations repaired    : {fixed}")
    print(f"letter references moved  : {sum(shapes.values())}")
    print(f"  by shape               : {dict(shapes)}")
    print(f"unresolved references    : {len(all_unresolved)}")
    for qid, unres in all_unresolved:
        print(f"    {qid}: {unres}")

    if args.dry:
        print("\n-- dry run, nothing written --")
        return

    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"\nwritten                  : {BANK}")


if __name__ == "__main__":
    main()
