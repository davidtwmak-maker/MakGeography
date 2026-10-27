#!/usr/bin/env python3
"""
Extract the real multiple-choice items from HKEAA's examination briefing decks.

The decks are HKEAA's own post-exam briefing slides. Most slides report
candidate performance statistics ("36% chose Option B"), but a handful show a
complete Section A item: the stem, all four options, the percentage of
candidates who picked each, and an asterisk on the correct one.

This script pulls those complete items out. It never reconstructs a question
from a partial one, and it never guesses an answer.

Output: data/hkeaa_mc_raw.json
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
PAPER_DIR = DATA / "papers"
OUT = DATA / "hkeaa_mc_raw.json"
NOTES = DATA / "hkeaa_NOTES.md"

HKEAA = "https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog"
DECKS = {2022: f"{HKEAA}/GEOG-PowerPoint-2022.pdf",
         2023: f"{HKEAA}/GEOG-PowerPoint-2023.pdf",
         2024: f"{HKEAA}/GEOG-PowerPoint-2024.pdf",
         2025: f"{HKEAA}/GEOG-PowerPoint-2025.pdf"}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# The item number and the elective, read off each slide. Recorded by hand from
# the deck, not inferred.
KNOWN_ITEMS = {
    (2023, 22): (2, "CP4"),      # grid square access / land use
    (2024, 16): (6, "CP4"),      # grid square 0979 statements
    (2024, 18): (9, "CP2"),      # coast, prevailing wind
    (2024, 19): (12, "CP3"),     # raw material-oriented manufacturing
    (2024, 20): (13, "CP4"),     # land use X adverse social impacts
    (2024, 21): (20, "CP2"),     # consequences of sea level rise
    (2025, 13): (3, "CP1"),      # average gradient (map reading)
    (2025, 14): (5, "CP4"),      # Kai Tak Cruise Terminal location
    (2025, 15): (19, "CP7"),     # ecological impact of climate change
    (2025, 16): (20, "CP7"),     # tree planting and urban heat island
}


def fetch(year: int) -> Path:
    dest = PAPER_DIR / f"geog_brief_{year}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100_000:
        return dest
    url = DECKS[year]
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=240) as r:
        dest.write_bytes(r.read())
    return dest


def clean(s: str) -> str:
    s = s.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_page(page, item_no: int, year: int) -> dict | None:
    """Pull one complete MC item off a briefing slide.

    The slides are laid out consistently:

        x ~56-80    the stem, then any (1) (2) (3) statements
        x ~91       the option markers A. B. C. D.  (B.* when correct)
        x ~149      the option text
        x ~410      the percentage of candidates who chose it

    Reading the geometry rather than the text order is what makes this
    reliable: the raw text extraction interleaves the statements, the options
    and the percentages in a confusing order.
    """
    rows = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if not txt:
                continue
            x0, y0, x1, y1 = line["bbox"]
            rows.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": txt})
    if not rows:
        return None

    # Option markers: a line whose text is exactly "A." or "B.*" etc. The x
    # position differs between decks (52, 91 or 97), so find them by their
    # text and then work out the layout from their positions.
    markers = []
    for r in rows:
        m = re.fullmatch(r"([A-D])\.(\*)?", r["text"].strip())
        if m:
            markers.append({"letter": m.group(1), "star": bool(m.group(2)), **r})
    if len(markers) != 4:
        return None
    markers.sort(key=lambda m: m["y0"])
    if [m["letter"] for m in markers] != ["A", "B", "C", "D"]:
        return None

    # The option text sits to the right of the marker on the same row. The
    # percentage column is further right, so exclude it by requiring the text
    # to start before the percentage column and not be a bare percentage.
    # The percentage column is a column of bare "NN%" entries. Its x position
    # varies by deck, and in some decks it sits to the LEFT of the option
    # text, so identify it by the column, not by a fixed x.
    pct_rows = [r for r in rows if re.fullmatch(r"\d+%", r["text"].strip())]
    pct_cols = {}
    for r in pct_rows:
        pct_cols.setdefault(round(r["x0"]), []).append(r)

    def in_pct_column(r) -> bool:
        # A percentage column is a vertical run of bare "NN%" entries. A text
        # entry belongs to that column if it sits at the same x as one of
        # those entries. Some decks put the percentage LEFT of the option
        # text and some RIGHT, so the x is worked out per deck, not assumed.
        return any(abs(r["x0"] - px) < 25 for px in pct_cols)

    # The percentage column may sit to the RIGHT of the option text (2024:
    # text at x=149, percentage at x=409) or to the LEFT (2025: text at x=106,
    # percentage at x=644). Work out which side by comparing each percentage's
    # x with the option text's x.
    text_xs = []
    for mk in markers:
        peers = [
            r for r in rows
            if abs(r["y0"] - mk["y0"]) < 8
            and r["x0"] > mk["x1"] + 3
            and not re.fullmatch(r"\d+%?", r["text"].strip())
        ]
        if peers:
            text_xs.append(min(r["x0"] for r in peers))
    pct_right = False
    if text_xs and pct_cols:
        min_text_x = min(text_xs)
        pct_xs = list(pct_cols)
        # If every percentage column is right of the option text, the
        # percentages sit on the right.
        pct_right = all(px > min_text_x + 60 for px in pct_xs)

    def is_percentage(r) -> bool:
        t = r["text"].strip()
        if re.fullmatch(r"\d+%", t):
            return True
        if re.fullmatch(r"\(\d+%\)", t):
            return True
        return False

    options = {}
    correct = None
    for i, mk in enumerate(markers):
        # An option can wrap onto a second line just below it. The wrap must
        # sit above the NEXT option marker, or it belongs to that option.
        next_top = markers[i + 1]["y0"] if i + 1 < len(markers) else None
        same_row = [
            r for r in rows
            if abs(r["y0"] - mk["y0"]) < 8
            and r["x0"] > mk["x1"] + 3
            and not is_percentage(r)
            and not (pct_right and in_pct_column(r))
        ]
        cont = []
        if same_row:
            anchor_x = same_row[0]["x0"]
            for r in rows:
                if not (mk["y1"] < r["y0"] < mk["y1"] + 16):
                    continue
                if next_top is not None and r["y0"] >= next_top - 4:
                    continue
                if abs(r["x0"] - anchor_x) > 8:
                    continue
                if is_percentage(r):
                    continue
                if pct_right and in_pct_column(r):
                    continue
                cont.append(r)
        allrows = sorted(same_row + cont, key=lambda r: (round(r["y0"] / 8), r["x0"]))
        text = clean(" ".join(r["text"] for r in allrows))
        # Some decks attach the candidate percentage to the option text
        # ("(8%)"). Strip it.
        text = re.sub(r"\(\d+%\)\s*$", "", text).strip()
        options[mk["letter"]] = text
        if mk["star"]:
            correct = mk["letter"]

    if correct is None or not all(options.values()):
        return None

    # The stem and any (1)(2)(3) statements live above the first option marker.
    opt_top = min(m["y0"] for m in markers)
    above = [r for r in rows
             if r["y1"] < opt_top - 2 and r["x0"] < 560
             and r["text"].strip() != "* Correct answer"]
    above.sort(key=lambda r: (round(r["y0"] / 6), r["x0"]))

    stem_parts = []
    statements = []
    for r in above:
        t = r["text"].strip()
        if t == "Section A":
            continue
        if t.startswith("\u2022"):
            # A bullet marks the exam commentary. The question stem is the
            # bullet too, so peel the bullet off and then decide.
            t = t.lstrip("\u2022 ").strip()
        # Commentary about the exam rather than the question.
        if ("most popular answer" in t
                or "performance of candidates" in t
                or "overall improvement in the overall" in t
                or "slight improvement in the overall" in t):
            continue
        t = re.sub(r"^In Item \d+,\s*", "", t)
        if not t or re.match(r"^\d+%?$", t) or t == "*":
            continue
        if re.fullmatch(r"\(\d+%\)", t):
            continue
        # A stray caption for a figure on the slide.
        if t in ("Wind direction", "Land use X"):
            continue
        if re.match(r"^\(\d\)\s", t):
            statements.append(t)
        else:
            stem_parts.append(t)

    # Build the stem from the QUESTION lines only.
    #
    # The slide mixes three kinds of line: the question, the (1)(2)(3)
    # statements, and the examiner's commentary on how candidates answered.
    # The question is the line group that carries the actual ask - it ends
    # with "?" or "__________." - and the commentary follows it.
    #
    # Rather than pattern-match the commentary (which differs every slide),
    # take the text UP TO the end of the question, and put the statements
    # back at the end where the student needs them.
    joined = clean(" ".join(stem_parts))

    # The question ends at the first "?" or "__________." after the ask starts.
    cut = -1
    m = re.search(r"\?|_+\.|_+\.\s", joined)
    if m:
        cut = m.end()
    stem = joined[:cut].strip() if cut > 0 else joined

    # Now cut any commentary that was spliced into the question line itself.
    # The commentary always starts with one of these phrases.
    stem = re.sub(
        r"\s*(?:candidates might|misinterpreted|misunderstanding|"
        r"might have thought|awareness of|aware of the|"
        r"the direction of the spit|formation of tropical cyclones|"
        r"extreme rainfall is primarily).*$",
        "", stem, flags=re.I).strip()

    # If the stem still starts with commentary, drop everything up to the
    # first capitalised clause that reads like a question.
    stem = re.sub(r"^.*?(?:There was a slight|the same as last year\.?)\s*",
                  "", stem).strip()

    if len(stem) < 12:
        return None

    # Statements are part of the question, not the options. Append them to the
    # stem so the reader knows what (1)(2)(3) refer to.
    if statements:
        stem = stem + " " + clean(" ".join(statements))

    return {
        "paper": "Paper 1",
        "year": year,
        "q": item_no,
        "elect": None,   # set by the caller
        "stem": stem,
        "options": [options["A"], options["B"], options["C"], options["D"]],
        "answer": correct,
        "explanation": "",
    }


def main():
    import pymupdf

    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    sources = []

    for year in sorted(DECKS):
        print(f"\n=== {year} ===")
        pdf = fetch(year)
        doc = pymupdf.open(pdf)
        for page_no in range(doc.page_count):
            key = (year, page_no + 1)
            if key not in KNOWN_ITEMS:
                continue
            item_no, elective = KNOWN_ITEMS[key]
            item = parse_page(doc[page_no], item_no, year)
            if not item:
                print(f"  page {page_no + 1} (Item {item_no}): could not parse a complete item")
                continue
            item["elect"] = elective
            item["source_page"] = page_no + 1
            item["source_url"] = DECKS[year]
            items.append(item)
            print(f"  page {page_no + 1} (Item {item_no}) -> {elective} {item['answer']}")
        doc.close()
        sources.append(DECKS[year])

    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(items)} official items -> {OUT}")

    from collections import Counter
    print("by elective:", dict(Counter(i["elect"] for i in items)))

    lines = [
        "# Official HKEAA multiple-choice items",
        "",
        "## What this is",
        "",
        f"{len(items)} genuine multiple-choice items from HKEAA's own post-examination",
        "briefing decks, with the official correct answer (the asterisked option).",
        "",
        "## Why it is small",
        "",
        "HKEAA does not publish the full past papers for free. The Subject",
        "Examination Report and Question Papers (with marking schemes) are sold -",
        "the year pages only expose an order form:",
        "",
        "  https://www.hkeaa.edu.hk/en/resources/publications/list_of_publications/hkdse_erqp_pub/2023.html",
        "  -> form_hkdse_2023_erqp.pdf",
        "",
        "The briefing decks ARE free, but they are examination briefing slides:",
        "candidate performance statistics, which option most candidates picked, and",
        "which was correct. Only a handful of slides show a complete item - stem,",
        "all four options, and the asterisked answer. Those are the ones here.",
        "",
        "## Sources",
        "",
    ]
    for u in sources:
        lines.append(f"- {u}")
    lines += [
        "",
        "## Items",
        "",
        "| Year | Item | Elective | Answer | Deck page |",
        "|---|---|---|---|---|",
    ]
    for i in items:
        lines.append(f"| {i['year']} | {i['q']} | {i['elect']} | {i['answer']} | {i['source_page']} |")
    lines += [
        "",
        "## Deliberately not used",
        "",
        "- **Candidate script exemplars** (`*Sample-geog-Level*-E.pdf`). These are real",
        "  candidate exam scripts, some with seat numbers. They are not question",
        "  papers and reading them raises a student-privacy problem. They were found,",
        "  then deleted without use.",
        "- **Oxford / 600MC question books.** Publisher material licensed for",
        "  classroom use only; the teacher's own note says do not redistribute.",
        "- **Predicted grade tests and combo quizzes** in the vault. Assessment",
        "  material, excluded from the site entirely.",
        "",
        "## Consequence for the MC bank",
        "",
        "The repository cannot serve full official past-paper MC questions without",
        "purchase, so the MC bank is mostly AI-generated from the MakGeography notes,",
        "with these official items as the genuine sample.",
        "",
    ]
    NOTES.write_text("\n".join(lines), encoding="utf-8")
    print(f"notes -> {NOTES}")


if __name__ == "__main__":
    main()
