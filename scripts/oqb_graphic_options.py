#!/usr/bin/env python3
"""Mark the questions whose options are tables or diagrams, not plain text.

Most official HKEAA options are a single line of text. A handful are a
table or a small diagram, and OCR flattens them into an unreadable
string ("Drainage density Higher Lower"). For those the option IMAGE is
the authoritative content, so the garbled OCR text is dropped and the
option is shown as the image alone.

Two signals are combined, because neither is enough on its own:

  * HEIGHT - an option image taller than 120px holds a table or diagram.
    A line of wrapped text is never that tall.
  * OCR LINES - an option whose OCR gives many separate fragments with
    no sentence structure (e.g. "200", "m", "150", "100", "50", "0") is
    a table that OCR shredded, not a sentence.

A plain wrapped sentence has a long fragment or ends in a full stop, so it
is left as text.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent

import json
import os
import re

from PIL import Image

BASE = pathlib.Path(__file__).resolve().parent.parent
OQB = BASE / "data" / "hkeaa_oqb"
BANK = BASE / "data" / "mc_bank.json"
MANIFEST = f"{OQB}/hkeaa_mc_manifest.json"
OCR = f"{OQB}/ocr/geog.json"
TALL = 120


def looks_shredded(lines):
    """True when the OCR fragments are table cells rather than a sentence."""
    if not isinstance(lines, list) or len(lines) < 3:
        return False
    frags = [x.strip() for x in lines if x.strip()]
    if len(frags) < 3:
        return False
    # A sentence has at least one long piece of running text.
    if max(len(f) for f in frags) >= 45:
        return False
    # A sentence usually ends in a full stop.
    if frags[-1].endswith("."):
        return False
    # Most fragments are short words, numbers or single letters.
    short = sum(1 for f in frags if len(f) <= 12)
    return short >= len(frags) * 0.6


def main():
    bank = json.loads(open(BANK, encoding="utf-8").read())
    ocr = json.loads(open(OCR, encoding="utf-8").read())
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    row_of = {m["qcode"]: m["en_id"] for m in manifest if m.get("en_id")}

    marked = 0
    for q in bank["questions"]:
        oi = q.get("option_images") or []
        if not oi:
            continue
        qcode = q.get("hkeaa_qcode")
        row = ocr.get(str(row_of.get(qcode)))

        heights = []
        for rel in oi:
            fp = f"{OQB}/{rel}"
            heights.append(Image.open(fp).size[1] if os.path.exists(fp) else 0)

        graphic = max(heights) >= TALL
        if not graphic and row:
            graphic = any(looks_shredded(lines) for lines in (row.get("options") or []))

        if graphic:
            # Keep the raw OCR so the data is not lost, but do not display
            # it: the flattened text loses the table's column structure.
            q["options_ocr"] = [row["options"][i] if i < len(row.get("options") or [])
                                else [] for i in range(len(oi))] if row else []
            q["options"] = [chr(ord("A") + i) for i in range(len(oi))]
            q["graphic_options"] = True
            marked += 1
        else:
            q.pop("graphic_options", None)
            q.pop("options_ocr", None)

    with open(BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=1)
    print(f"marked {marked} questions as having graphic options")


if __name__ == "__main__":
    main()
