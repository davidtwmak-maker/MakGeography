#!/usr/bin/env python3
"""
Render the HKEAA briefing slides that carry a complete Section A item, so the
site can show the official slide beside the transcribed question.

The slide image is HKEAA's own published material and carries HKEAA's
copyright. It is shown to students through the site's existing password gate,
and the source is credited on every image. See data/hkeaa_NOTES.md for the
copyright position and what is and is not redistributed.

Usage:  python scripts/render_slide_crops.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf

BASE = Path(__file__).resolve().parent.parent
PAPERS = BASE / "data" / "papers"
OUT = BASE / "data" / "slide_crops"
OUT.mkdir(parents=True, exist_ok=True)

DECKS = {
    2022: "geog_brief_2022.pdf",
    2023: "geog_brief_2023.pdf",
    2024: "geog_brief_2024.pdf",
    2025: "geog_brief_2025.pdf",
    2026: "geog_brief_2026.pdf",
}

DPI = 150


def main() -> None:
    items = json.loads((BASE / "data" / "hkeaa_mc_raw.json").read_text(encoding="utf-8"))
    by_page: dict[tuple[int, int], list[dict]] = {}
    for q in items:
        by_page.setdefault((q["year"], q["source_page"]), []).append(q)

    manifest = []
    for (year, page), qs in sorted(by_page.items()):
        deck = PAPERS / DECKS[year]
        if not deck.exists():
            print(f"skip {year} p{page}: no deck")
            continue
        doc = pymupdf.open(deck)
        pix = doc[page - 1].get_pixmap(dpi=DPI)
        name = f"hkeaa-{year}-p{page}.png"
        path = OUT / name
        pix.save(path)
        rel = f"slide_crops/{name}"
        for q in qs:
            q["slide_image"] = rel
        manifest.append({
            "year": year, "page": page, "file": rel,
            "items": [f"{q['year']} Q{q['q']}" for q in qs],
        })
        print(f"{year} p{page} -> {name}  ({len(qs)} item(s))")

    (BASE / "data" / "hkeaa_mc_raw.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (BASE / "data" / "slide_crops_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(manifest)} slide images -> {OUT}")


if __name__ == "__main__":
    main()
