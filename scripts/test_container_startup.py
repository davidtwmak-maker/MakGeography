#!/usr/bin/env python3
"""Check that the app starts in a container.

A deployed container has neither the Obsidian vault nor
~/.hermes/.env. The app has to import and serve anyway.

This calls the routes directly rather than going through Starlette's
test client, because that needs httpx2 - a test-only dependency with
no place in the runtime image.

The home page can be in one of two states, and both are correct:

  * a roster is present, so the home page is the sign-in page and must
    ask for a Student ID;
  * no roster, so the site is open and the study panels render.

What matters is that the page serves.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A container gets the key from the environment, and the vault and the
# Hermes files are not there at all.
for _k in ("MINIMAX_API_KEY", "MINIMAX_BASE_URL", "MAKGEO_PASSWORD",
           "MAKGEO_TEACHER_KEY", "MAKGEO_ROSTER_JSON"):
    os.environ.pop(_k, None)

import app.main as am  # noqa: E402


def main() -> int:
    # The health check touches nothing and needs no session.
    assert am.healthz() == {"ok": True}

    # The home page serves.
    from starlette.requests import Request
    scope = {
        "type": "http", "method": "GET", "path": "/",
        "headers": [], "query_string": b"", "client": ("test", 1),
        "server": ("test", 80), "scheme": "http", "root_path": "",
        "http_version": "1.1",
    }
    resp = am.home(Request(scope))
    assert resp.status_code == 200, resp.status_code
    raw = resp.body
    body = raw.decode() if isinstance(raw, (bytes, bytearray)) else bytes(raw).decode()
    assert "MakGeography" in body, "the home page did not render"

    if am.roster_mod.allowed_sids():
        assert 'name="identifier"' in body, \
            "the sign-in page is not asking for a Student ID"
        print("The roster is present, so the site asks for a Student ID")
    else:
        assert "MC Drilling" in body, "the home page is missing its panels"
        print("No roster, so the site opens straight into the tools")

    # The knowledge base still loads from the committed data.
    assert am.get_kb() is not None

    # The official exam images and the map extracts are still there.
    media = ROOT / "data" / "hkeaa_oqb"
    assert media.is_dir(), "the official exam media is missing"

    print("The app serves with no vault and no ~/.hermes/.env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
