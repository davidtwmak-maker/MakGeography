#!/usr/bin/env python3
"""Build the MakGeography MC bank from the OQB HKEAA download + OCR.

Produces the app's question shape:
  id, year, q, paper, elect, subtopic, stem, options, answer, explanation,
  source, official, topics, question_image / option_images

The stem text and option text come from the OCR pass; the original exam
images are kept alongside so students can see the paper as it was printed.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oqb_taxonomy import classify, TOPIC_LABEL

APP = BASE
BASE = os.path.join(APP, "data/hkeaa_oqb")
SUBJECT = "geog"


def join_lines(lines):
    """Join OCR lines into paragraphs, keeping numbered statements apart."""
    out = []
    for l in lines:
        s = " ".join(str(l).split())
        if not s:
            continue
        out.append(s)
    return out


def clean_stem(lines):
    """The stem may contain the numbered statements (1)(2)(3) and their text.

    HKEAA stem images carry the question AND the four statements; the option
    images carry the "which combination" answers. Split the stem so the
    statements are preserved as part of the question.
    """
    ls = join_lines(lines)
    if not ls:
        return ""
    # Detect the common shape: statement markers on their own lines
    text = " ".join(ls)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_option(lines):
    ls = join_lines(lines)
    return " ".join(ls).strip()


def main():
    manifest = json.load(open(f"{BASE}/hkeaa_mc_manifest.json", encoding="utf-8"))
    raw = json.load(open(f"{BASE}/_raw/{SUBJECT}.json", encoding="utf-8"))
    ocr = json.load(open(f"{BASE}/ocr/{SUBJECT}.json", encoding="utf-8"))
    amap = json.load(open(f"{BASE}/attachment_map.json", encoding="utf-8"))
    by_id = {r["id"]: r for r in raw}
    att_by_qid = amap.get("by_question", {})

    out = []
    skipped = {"no_ocr": 0, "no_answer": 0, "bad_opts": 0}

    for m in manifest:
        if m["subject"] != SUBJECT:
            continue
        qid = m["en_id"] or m["zh_id"]
        row = by_id.get(qid)
        if not row:
            skipped["no_ocr"] += 1
            continue
        o = ocr.get(str(qid))
        if not o:
            skipped["no_ocr"] += 1
            continue

        opts = [clean_option(x) for x in o["options"]]
        # Some questions have graphical options (a diagram to read, a letter
        # on a diagram, a sequence). OCR cannot read those, so the option
        # text is the letter alone and the real content is the image. Keep
        # them, but flag them so the UI shows the image.
        graphic = (len(opts) != 4) or any(not t for t in opts)
        if graphic:
            opts = [(t if t else "") for t in (opts + ["", "", "", ""])[:4]]
            for i, t in enumerate(opts):
                if not t:
                    opts[i] = chr(ord("A") + i)
        else:
            pass  # all four options read cleanly as text

        # OQB answer keys are ZERO-based: "[0]" is the first option.
        # Verified against the app's 11 existing hand-checked official
        # questions (2022 Q11/Q13/Q16/Q17, 2024 Q9/Q12/Q13/Q20, 2025 Q5/Q19/Q20)
        # - every one matches with zero-based indexing.
        try:
            ans_idx = int(str(m["en_answer"] or m["zh_answer"]).strip("[]"))
        except Exception:
            skipped["no_answer"] += 1
            continue
        if not (0 <= ans_idx < 4):
            skipped["no_answer"] += 1
            continue

        elect, label, is_map = classify(m.get("topic_code"), m.get("dimension_code"))
        stem = clean_stem(o["stem"])

        # The paper's map extract, if this question needs one.
        att = att_by_qid.get(str(qid), {})
        map_extract = None
        for v in att.values():
            map_extract = v
            break

        rec = {
            "id": f"hkeaa-{m['qcode']}",
            "year": m["year"],
            "q": m["question_no"],
            "paper": "Paper 1",
            "elect": elect,
            "stem": stem,
            "options": opts,
            "answer": "ABCD"[ans_idx],
            "answer_index": ans_idx,
            "explanation": "",
            "source": (f"HKEAA Geography {m['year']} Paper 1 Q{m['question_no']} "
                       f"(official HKEAA question, via the OQB platform)"),
            "official": True,
            "found_by": "oqb",
            "topics": [elect],
            "subtopic": f"{elect}.{m['year']}Q{m['question_no']}",
            "subtopic_title": label,
            "hkeaa_qcode": m["qcode"],
            "hkeaa_topic": (m.get("topic_code") or [None])[0],
            "hkeaa_dimension": (m.get("dimension_code") or [None])[0],
            "is_dse": bool(m.get("is_dse")),
            "difficulty": m.get("difficulty") or "",
            "suggested_score": m.get("suggested_score"),
            "suggested_time": m.get("suggested_time"),
            "attachments": m.get("attachments") or {},
            "stem_image": f"geog/{qid}/{row.get('content')}",
            "option_images": [f"geog/{qid}/{c.get('content')}"
                              for c in sorted(row.get("choices") or [],
                                              key=lambda c: c.get("seq") or 0)],
            "has_map_extract": bool(m.get("attachments")),
            "map_extract": map_extract,
            "graphic_options": graphic,
        }
        out.append(rec)

    out.sort(key=lambda x: (x["year"], x["q"] or 0))
    print("built:", len(out), "skipped:", skipped)
    print("by elective:", dict(Counter(q["elect"] for q in out)))
    print("by year:", dict(sorted(Counter(q["year"] for q in out).items())))
    print("with map extract:", sum(1 for q in out if q["has_map_extract"]))
    print("empty stems:", sum(1 for q in out if not q["stem"]))
    print("answer distribution:", dict(Counter(q["answer"] for q in out)))

    dest = os.path.join(APP, "data/mc_bank_oqb_geog.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"questions": out}, fh, ensure_ascii=False, indent=1)
    print("wrote:", dest, os.path.getsize(dest), "bytes")


if __name__ == "__main__":
    main()
