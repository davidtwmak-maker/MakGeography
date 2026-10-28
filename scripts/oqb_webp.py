#!/usr/bin/env python3
"""Convert the official HKEAA question images to WebP.

The raw PNGs from the OQB platform are 149 MB for 7,650 files. WebP at
quality 88 is visually lossless for exam text and grid references but a
third of the size, which keeps the repository small enough to push and
deploy.

The original PNGs are left on disk; only the .webp copies are written
alongside them, and the bank is rewritten to point at the .webp files.
A .webp with the same stem as a .png is skipped if it already exists,
so the script can be re-run safely.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

BANK = BASE / "data" / "mc_bank.json"
MEDIA = BASE / "data" / "hkeaa_oqb"
QUALITY = 88


def convert(rel):
    src = os.path.join(MEDIA, rel)
    dst = os.path.splitext(src)[0] + ".webp"
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return "skip", os.path.getsize(dst)
    try:
        im = Image.open(src).convert("RGB")
        im.save(dst, "WEBP", quality=QUALITY, method=4)
        return "ok", os.path.getsize(dst)
    except Exception as e:
        return f"fail:{type(e).__name__}", 0


def main():
    bank = json.loads(open(BANK, encoding="utf-8").read())
    qs = bank["questions"]

    rels = []
    for q in qs:
        for r in [q.get("stem_image")] + list(q.get("option_images") or []):
            if r and r.endswith(".png"):
                rels.append(r)
    rels = sorted(set(rels))
    print(f"converting {len(rels)} images at quality {QUALITY}")

    before = sum(os.path.getsize(os.path.join(MEDIA, r)) for r in rels)
    stats = {"ok": 0, "skip": 0}
    after = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (status, size) in enumerate(ex.map(convert, rels), 1):
            if status in stats:
                stats[status] += 1
            after += size
            if i % 1000 == 0:
                print(f"  {i}/{len(rels)}")

    print(f"ok {stats['ok']}, skipped {stats['skip']}")
    print(f"PNG {before/1e6:.1f} MB -> WebP {after/1e6:.1f} MB")

    # Point the bank at the WebP files.
    changed = 0
    for q in qs:
        if q.get("stem_image", "").endswith(".png"):
            q["stem_image"] = os.path.splitext(q["stem_image"])[0] + ".webp"
            changed += 1
        oi = q.get("option_images")
        if oi:
            q["option_images"] = [os.path.splitext(p)[0] + ".webp" if p.endswith(".png") else p
                                  for p in oi]
    with open(BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=1)
    print(f"bank now points at WebP ({changed} stem images rewritten)")


if __name__ == "__main__":
    main()
