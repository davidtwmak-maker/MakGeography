#!/usr/bin/env python3
"""
Render the HKEAA official exam questions as clean images.

Why this exists
---------------
The official HKDSE Geography multiple-choice questions are published by
HKEAA only inside their "Question Briefing" slide decks. A briefing slide
carries far more than the question: a section banner, a note about which
option was most popular, a column of candidate percentages, a commentary
box explaining the common wrong answer, answer colours, and HKEAA's own
branding.

Two of those are actively harmful in a drilling app:

- The percentages give the answer away. The most popular WRONG option
  always scores higher than the correct one, so the highest number is
  never the answer - but a student can still work it backwards.
- The commentary box spells out the misconception, which is the whole
  point of the question.

So the slide is rendered and everything that is not part of the question
is removed.

What the image contains
-----------------------
The options are already rendered by the app as buttons, so the image
carries only what text cannot: the question stem, any figure (map,
photograph, graph) and the numbered statements, as they appeared in the
exam paper. The options table is not in the image - and that is what
takes the response percentages, the answer asterisk and the answer
colours with it.

How it is done
--------------
Two layouts are in use.

Live-text decks (2024, 2025, 2026): the question and the analysis are
both selectable text. The analysis is covered with opaque white
rectangles drawn on the page before it is rendered.

Raster decks (2022): the question was screenshotted into the slide, so
there is no text to work with. The slide image is cropped to the
question and the analysis is painted out at the pixel level.

PyMuPDF's redaction API cannot be used here. The text in these decks
sits inside a transparency group, so apply_redactions() reports success
while leaving the text in place. Opaque white rectangles do remove it.

The yellow highlight
--------------------
HKEAA highlights the statement that their commentary is about. The
highlight is a yellow vector fill with the question text drawn on top of
it, so it cannot simply be covered - that would take the statement with
it. Instead the yellow pixels are recoloured white in the rendered
image, which leaves the black text on top untouched.

One figure is handled specially. In the 2024 Item 9 map, HKEAA drew a
blue arrow for the wind and a red arrow for the direction of spit
growth over the top of the original exam figure. Both are HKEAA's
analysis, not part of the exam figure, and the blue one gives the
answer away - so the original embedded raster is used instead.

Usage:  python scripts/render_question_images.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
PAPERS = BASE / "data" / "papers"
OUT = BASE / "data" / "question_images"

ZOOM = 3.0

# ---------------------------------------------------------------------------
# Per-slide configuration, in page points.
#
#   crop    : the region of the slide holding the question - stem, figure
#             and numbered statements. The options table sits below this
#             region and is not included.
#   cover   : rectangles covered with white - the analysis material that
#             falls inside the crop.
#   figure  : replace the figure with the original embedded raster.
#   yellow  : recolour the yellow highlight behind a statement to white.
# ---------------------------------------------------------------------------

RASTER = {
    "hkeaa-2022-q11": {
        "deck": "geog_brief_2022.pdf",
        "teal": True, "page": 17,
        # "QT 11 Plant X is still a major iron and steel plant ..." and
        # the three statements. The options start at y=197.
        "crop": (70, 98, 470, 190),
    },
    "hkeaa-2022-q13": {
        "deck": "geog_brief_2022.pdf", "page": 18,
        # The stem, the three population-density graphs, the follow-up
        # question and the three statements. The options start at y=402.
        "crop": (14, 92, 510, 398),
        # HKEAA drew a red oval over the stage 3 graph to point at the
        # part of the curve the answer depends on. The question's own
        # embedded image is rendered instead of the slide, so the oval
        # never appears.
        "raster": (18, 96, 510, 457),
    },
    "hkeaa-2022-q16": {
        "deck": "geog_brief_2022.pdf",
        "teal": True, "page": 19,
        # The stem and the three statements. The options start at y=362.
        "crop": (20, 215, 685, 352),
    },
    "hkeaa-2022-q17": {
        "deck": "geog_brief_2022.pdf",
        "teal": True, "page": 20,
        # The stem and the three statements. The options start at y=323.
        "crop": (22, 212, 680, 312),
    },
}

LIVE = {
    "hkeaa-2024-q9": {
        "deck": "geog_brief_2024.pdf", "page": 18,
        # The stem, the map of the coast, and the question line.
        "crop": (50, 135, 520, 356),
        "cover": [
            # The two commentary boxes.
            (364, 168, 550, 270),
            (364, 272, 550, 315),
            # The leader lines from the map into the commentary.
            (293, 178, 370, 211),
            (293, 259, 370, 288),
        ],
        "figure": (71, 163, 332, 327),
    },
    "hkeaa-2024-q12": {
        "deck": "geog_brief_2024.pdf", "page": 19,
        # The stem. The options start at y=184.
        "crop": (50, 145, 660, 178),
    },
    "hkeaa-2024-q13": {
        "deck": "geog_brief_2024.pdf", "page": 20,
        # The stem, the photograph and the three statements. The options
        # start at y=380.
        "crop": (50, 116, 676, 378),
        "cover": [
            # The commentary box and its leader line.
            (60, 159, 386, 258),
            # The red pointer line to the photograph. It starts beside
            # the photograph and crosses onto it; the part on the photo
            # goes when the clean exam image is put back.
            (378, 220, 404, 284),
        ],
        "yellow": True,
        # The photograph carries HKEAA's yellow outline of the container
        # yard, a red pointer line and the "Land use X" label. The raw
        # exam photograph is used instead, so none of that survives.
        "figure": (402, 154, 671, 351),
    },
    "hkeaa-2024-q20": {
        "deck": "geog_brief_2024.pdf", "page": 21,
        # The stem and the three statements. The options start at y=362.
        "crop": (50, 126, 670, 258),
        "cover": [
            # The leader line from the highlighted statement into the
            # commentary box below.
            (178, 248, 232, 259),
        ],
        "yellow": True,
    },
    "hkeaa-2025-q5": {
        "deck": "geog_brief_2025.pdf", "page": 14,
        # The stem and the three statements. The options start at y=315.
        "crop": (28, 148, 760, 313),
    },
    "hkeaa-2025-q19": {
        "deck": "geog_brief_2025.pdf", "page": 15,
        # The stem. The options start at y=218.
        "crop": (28, 146, 765, 214),
    },
    "hkeaa-2025-q20": {
        "deck": "geog_brief_2025.pdf", "page": 16,
        # The stem and the three statements. The options start at y=307.
        "crop": (30, 151, 750, 304),
    },
    "hkeaa-2026-q14": {
        "deck": "geog_brief_2026.pdf", "page": 12,
        # The stem and the three statements. The options start at y=265.
        # The crop starts below the grey "Section A" banner.
        "crop": (46, 94, 645, 228),
    },
    "hkeaa-2026-q16": {
        "deck": "geog_brief_2026.pdf", "page": 13,
        # The stem and the three statements. The options start at y=229.
        # The crop starts below the grey "Section A" banner, which ends
        # at y=64.4, and stops short of the slide's green decorative
        # swoosh in the top-right corner.
        "crop": (44, 94, 655, 226),
    },
}

ALL = {}
ALL.update(RASTER)
ALL.update(LIVE)


def embedded_raster(page, bbox, tol=4):
    """The original exam image embedded in the slide, as a PIL image.

    On the 2022 decks the question was screenshotted into the slide, so
    the image itself holds the question. Rendering that image directly
    bypasses any vector graphics HKEAA drew on top of it - on Item 13
    they drew a red oval over the stage 3 graph.
    """
    x0, y0, x1, y1 = bbox
    for info in page.get_image_info(xrefs=True):
        ib = pymupdf.Rect(info["bbox"])
        if (abs(ib.x0 - x0) > tol or abs(ib.y0 - y0) > tol
                or abs(ib.x1 - x1) > tol or abs(ib.y1 - y1) > tol):
            continue
        pix = pymupdf.Pixmap(page.parent, info["xref"])
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img, ib
    return None, None


def cover_analysis(page, boxes):
    """Cover the analysis material with opaque white.

    PyMuPDF's redaction API cannot be used on these decks - the text
    sits inside a transparency group, so apply_redactions() reports
    success while leaving the text in place. Drawing an opaque white
    rectangle over the region does remove it, and it also covers the
    vector graphics behind it.
    """
    if not boxes:
        return
    shape = page.new_shape()
    for box in boxes:
        shape.draw_rect(pymupdf.Rect(*box))
    shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
    shape.commit()


def swap_in_raw_figure(page, bbox):
    """Replace the figure with the original embedded raster.

    HKEAA draws their analysis on top of the exam figure as vector
    graphics. The original figure is still in the file as a raster
    image, so the raster is drawn over the vectors to restore it.
    """
    x0, y0, x1, y1 = bbox
    for info in page.get_image_info(xrefs=True):
        ib = pymupdf.Rect(info["bbox"])
        if (abs(ib.x0 - x0) > 2 or abs(ib.y0 - y0) > 2
                or abs(ib.x1 - x1) > 2 or abs(ib.y1 - y1) > 2):
            continue
        pix = pymupdf.Pixmap(page.parent, info["xref"])
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        page.insert_image(pymupdf.Rect(x0, y0, x1, y1), pixmap=pix, overlay=True)
        return


def remove_teal_stripe(img):
    """Remove the teal template stripe down the left edge of the slide.

    The stripe is a sloping shape: at some rows it reaches x=59, at
    others x=22. Chasing that with a fixed rectangle either leaves a
    sliver or cuts into the question, so the teal pixels are removed
    directly instead.
    """
    arr = np.array(img).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    teal = (g > 105) & ((g - r) > 45) & ((b - r) > 40)
    if not teal.any():
        return img
    # Only the stripe, never the question. It slopes inward towards
    # the bottom of the slide, so the band it can occupy is wider than
    # its widest point at the top.
    limit = int(arr.shape[1] * 0.12)
    teal[:, limit:] = False
    arr[teal] = 255
    return Image.fromarray(arr.astype(np.uint8))


def remove_left_edge_stripe(img):
    """Remove the slide's coloured template stripe from the left edge.

    The stripe is a solid shape that reaches further right at some
    heights than others, so it is removed by colour rather than by a
    fixed rectangle. Only the far-left band is touched, so the
    question text is never at risk.
    """
    arr = np.array(img).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # The stripe is a saturated teal / green. The question text is
    # black on white, and the scan fringe around it is far weaker.
    saturated = (np.maximum(np.maximum(r, g), b)
                 - np.minimum(np.minimum(r, g), b)) > 45
    coloured = saturated & (g >= r) & (g > 80)

    limit = int(arr.shape[1] * 0.10)
    coloured[:, limit:] = False
    if not coloured.any():
        return img
    arr[coloured] = 255
    return Image.fromarray(arr.astype(np.uint8))


def whiten_yellow(img):
    """Recolour the yellow highlight to white, keeping the text on top.

    The highlight is a yellow fill with the question's black text drawn
    over it. Repainting the yellow pixels leaves the text intact, which
    covering the region would not.
    """
    arr = np.array(img).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    yellow = (r > 150) & (g > 110) & (b < 190) & ((r - b) > 55) & ((g - b) > 40)
    if not yellow.any():
        return img
    arr[yellow] = 255
    return Image.fromarray(arr.astype(np.uint8))


def render(cfg, out_path):
    doc = pymupdf.open(PAPERS / cfg["deck"])
    page = doc[cfg["page"] - 1]

    if "raster" in cfg:
        # The question's own image, rendered directly. Anything HKEAA
        # drew on the slide over the top of it is bypassed.
        img, ib = embedded_raster(page, cfg["raster"])
        if img is None:
            raise RuntimeError(f"no embedded image at {cfg['raster']}")
        # Map the page-point crop onto the image's own pixels.
        sx = img.width / (ib.x1 - ib.x0)
        sy = img.height / (ib.y1 - ib.y0)
        c = cfg["crop"]
        crop = (int((c[0] - ib.x0) * sx), int((c[1] - ib.y0) * sy),
                int((c[2] - ib.x0) * sx), int((c[3] - ib.y0) * sy))
        crop = (max(0, crop[0]), max(0, crop[1]),
                min(img.width, crop[2]), min(img.height, crop[3]))
        img.crop(crop).save(out_path)
        doc.close()
        return

    cover_analysis(page, cfg.get("cover", []))
    if "figure" in cfg:
        swap_in_raw_figure(page, cfg["figure"])

    pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    if cfg.get("yellow"):
        img = whiten_yellow(img)
    if cfg.get("teal"):
        img = remove_teal_stripe(img)
        img = remove_left_edge_stripe(img)

    c = tuple(int(v * ZOOM) for v in cfg["crop"])
    crop = (max(0, c[0]), max(0, c[1]),
            min(img.width, c[2]), min(img.height, c[3]))
    img.crop(crop).save(out_path)
    doc.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for qid, cfg in sorted(ALL.items()):
        out = OUT / f"{qid}.png"
        render(cfg, out)
        with Image.open(out) as im:
            size = im.size
        written.append(qid)
        print(f"  {qid}: {size[0]}x{size[1]}  -> {out.name}")

    (OUT / "index.json").write_text(
        json.dumps({q: f"{q}.png" for q in written}, indent=1),
        encoding="utf-8")
    print(f"\nwrote {len(written)} question images to {OUT}")


if __name__ == "__main__":
    main()
