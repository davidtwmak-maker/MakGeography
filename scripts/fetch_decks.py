#!/usr/bin/env python3
"""
Download HKEAA's free examination briefing decks for Geography.

These are HKEAA's own published slides for teachers. They are not ours to
redistribute, so the PDFs stay out of the repository (see .gitignore) and are
fetched locally instead. Only the rendered slide crops of the individual
questions are committed, as those are short fair-dealing extracts of the
question itself with HKEAA credited on each.

Usage:  python scripts/fetch_decks.py [year ...]
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "papers"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = [2022, 2023, 2024, 2025, 2026]
URL = ("https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/"
       "GEOG-PowerPoint-{year}.pdf")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36")


def fetch(year: int) -> bool:
    path = OUT / f"geog_brief_{year}.pdf"
    if path.exists() and path.stat().st_size > 100_000:
        print(f"{year}: already present ({path.stat().st_size:,} bytes)")
        return True
    req = urllib.request.Request(URL.format(year=year), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001
        print(f"{year}: FAILED - {e}")
        return False
    if len(data) < 100_000 or not data.startswith(b"%PDF"):
        print(f"{year}: FAILED - not a PDF ({len(data)} bytes)")
        return False
    path.write_bytes(data)
    print(f"{year}: saved {len(data):,} bytes -> {path.name}")
    return True


def main() -> None:
    years = [int(a) for a in sys.argv[1:]] or YEARS
    ok = sum(fetch(y) for y in years)
    print(f"\n{ok}/{len(years)} decks available")
    if ok < len(years):
        sys.exit(1)


if __name__ == "__main__":
    main()
