#!/usr/bin/env python3
"""
Crop multiple-choice questions out of official HKDSE Geography papers into
PNG images the website can show.

Source: the HKEAA published examination briefing decks and question papers.
Both are official publications for the public examination. Nothing here comes
from a commercial question book.

The pipeline:

1. Download the PDF (cached in data/papers/).
2. Find the pages that hold Section A (the multiple-choice items).
3. Locate each question by its number, using the PDF's own word positions.
4. Crop with a little padding and save as PNG.
5. Write a manifest so the site knows what each image is.

Usage:
    python scripts/crop_papers.py --list
    python scripts/crop_papers.py --paper 2025 --source brief [--tag CP3]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
PAPER_DIR = DATA / "papers"
CROP_DIR = DATA / "crops"
MANIFEST = DATA / "paper_crops.json"

HKEAA = "https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog"

# The briefing decks HKEAA publishes after each examination. They contain the
# Section A items with the official answer marked, which makes them both the
# question source and the answer key.
BRIEFING = {
    "2022": f"{HKEAA}/GEOG-PowerPoint-2022.pdf",
    "2023": f"{HKEAA}/GEOG-PowerPoint-2023.pdf",
    "2024": f"{HKEAA}/GEOG-PowerPoint-2024.pdf",
    "2025": f"{HKEAA}/GEOG-PowerPoint-2025.pdf",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DPI = 170


def fetch(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    print(f"  downloading {url}")
    subprocess.run(
        ["curl", "-sL", "--max-time", "240", "-A", UA, "-o", str(dest), url],
        check=True,
    )
    if not dest.exists() or dest.stat().st_size < 10_000:
        raise RuntimeError(f"download failed: {url}")
    return dest


def page_is_mc(text: str) -> bool:
    """A Section A page has several options and several numbered stems."""
    opts = len(re.findall(r"(?m)^\s*[A-D][.)]\s*\S", text))
    nums = len(re.findall(r"(?m)^\s*(\d{1,2})[.)]\s+[A-Z]", text))
    return opts >= 4 and nums >= 2


def crop_page(pdf_path: Path, page_no: int, out_dir: Path, year: str,
              source: str, dpi: int = DPI) -> list[dict]:
    """Crop each numbered MC question out of one PDF page.

    Uses the PDF's word positions, so the box is exact rather than guessed.
    """
    import pymupdf
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    page = doc[page_no]

    words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, word_no
    if not words:
        doc.close()
        return []

    # Group words into visual rows by their y midpoint.
    rows: dict[int, list] = {}
    for w in words:
        key = round(((w[1] + w[3]) / 2) / 4)
        rows.setdefault(key, []).append(w)
    ordered = [sorted(rows[k], key=lambda w: w[0]) for k in sorted(rows)]

    # A question begins at a row whose first token is "N." or "N)".
    starts = []
    for i, row in enumerate(ordered):
        if not row:
            continue
        tok = row[0][4]
        if re.fullmatch(r"\d{1,2}[.)]", tok):
            n = int(tok.rstrip(".)"))
            if 1 <= n <= 60:
                starts.append((i, n))

    if not starts:
        doc.close()
        return []

    # Render the page once at the target DPI.
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    results = []
    for si, (row_i, qnum) in enumerate(starts):
        end_i = starts[si + 1][0] if si + 1 < len(starts) else len(ordered)
        block = [w for row in ordered[row_i:end_i] for w in row]
        if not block:
            continue
        x0 = min(w[0] for w in block) * zoom
        y0 = min(w[1] for w in block) * zoom
        x1 = max(w[2] for w in block) * zoom
        y1 = max(w[3] for w in block) * zoom
        pad = 10
        box = (
            max(0, int(x0 - pad)),
            max(0, int(y0 - pad)),
            min(img.width, int(x1 + pad)),
            min(img.height, int(y1 + pad)),
        )
        if box[2] - box[0] < 80 or box[3] - box[1] < 40:
            continue
        stem = " ".join(w[4] for row in ordered[row_i:row_i + 3] for w in row)
        digest = hashlib.sha1(stem.encode()).hexdigest()[:8]
        name = f"{year}_{source}_q{qnum:02d}_{digest}.png"
        img.crop(box).save(out_dir / name)
        results.append({
            "id": f"{year}-{source}-q{qnum}",
            "file": f"data/crops/{year}/{name}",
            "year": year,
            "source": source,
            "question": qnum,
            "page": page_no + 1,
            "stem_preview": stem[:200],
            "width": box[2] - box[0],
            "height": box[3] - box[1],
        })

    doc.close()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show known papers")
    ap.add_argument("--paper", help="year, e.g. 2025")
    ap.add_argument("--source", default="brief", choices=["brief"])
    ap.add_argument("--tag", default="", help="elective code, e.g. CP3")
    ap.add_argument("--dpi", type=int, default=DPI)
    args = ap.parse_args()

    if args.list or not args.paper:
        print("Known papers:")
        for y, u in sorted(BRIEFING.items()):
            print(f"  {y}  {u}")
        print("\nUsage: python scripts/crop_papers.py --paper 2025 --source brief")
        return

    url = BRIEFING.get(args.paper)
    if not url:
        print(f"No known source for {args.paper}. Try --list.")
        return

    pdf = fetch(url, PAPER_DIR / f"geog_brief_{args.paper}.pdf")

    import pymupdf

    doc = pymupdf.open(pdf)
    print(f"{pdf.name}: {doc.page_count} pages")

    manifest = []
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
    by_id = {m["id"]: m for m in manifest}

    out_dir = CROP_DIR / args.paper
    total = 0
    for page_no in range(doc.page_count):
        text = doc[page_no].get_text()
        if not page_is_mc(text):
            continue
        got = crop_page(pdf, page_no, out_dir, args.paper, args.source, args.dpi)
        if got:
            for g in got:
                if args.tag:
                    g["elective"] = args.tag
                by_id[g["id"]] = g
            total += len(got)
            print(f"  page {page_no + 1}: {len(got)} questions")
    doc.close()

    manifest = sorted(by_id.values(), key=lambda m: (m["year"], m["source"], m["question"]))
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"\n{total} crops this run; manifest holds {len(manifest)} -> {MANIFEST}")


if __name__ == "__main__":
    main()
